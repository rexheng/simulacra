import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.engine.registry import SimulationRegistry
from app.models import SimulationRun, SimulationStatus

logger = logging.getLogger(__name__)


async def run_simulation(
    simulation_id: str,
    simulation_type: str,
    config: dict,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Run a simulation in the background. Updates DB records with status and results."""
    async with db_session_factory() as db:
        try:
            # Mark as running
            result = await db.execute(select(SimulationRun).where(SimulationRun.id == simulation_id))
            sim_run = result.scalar_one()
            sim_run.status = SimulationStatus.RUNNING
            await db.commit()

            # Get simulation class and run
            sim_class = SimulationRegistry.get(simulation_type)
            if sim_class is None:
                raise ValueError(f"Unknown simulation type: {simulation_type}")

            instance = sim_class()
            validated_config = instance.validate_config(config)
            summary = await instance.run(simulation_id, validated_config, db)

            # Mark as completed
            result = await db.execute(select(SimulationRun).where(SimulationRun.id == simulation_id))
            sim_run = result.scalar_one()
            sim_run.status = SimulationStatus.COMPLETED
            sim_run.summary = summary
            sim_run.completed_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info("Simulation %s completed successfully", simulation_id)

        except Exception as e:
            logger.exception("Simulation %s failed: %s", simulation_id, e)
            try:
                result = await db.execute(select(SimulationRun).where(SimulationRun.id == simulation_id))
                sim_run = result.scalar_one()
                sim_run.status = SimulationStatus.FAILED
                sim_run.summary = f"Error: {e}"
                sim_run.completed_at = datetime.now(timezone.utc)
                await db.commit()
            except Exception:
                logger.exception("Failed to update simulation %s status to FAILED", simulation_id)
