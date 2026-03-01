import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.engine.game_theory.base_game import BaseGameSimulation
from app.engine.game_theory.prison.analysis import analyze_prison_experiment
from app.engine.game_theory.prison.day_orchestrator import run_day
from app.engine.game_theory.prison.identity_generator import generate_prison_identities
from app.engine.registry import SimulationRegistry

logger = logging.getLogger(__name__)


@SimulationRegistry.register("stanford_prison")
class StanfordPrisonSimulation(BaseGameSimulation):
    """Stanford Prison Experiment: agents assume guard/prisoner roles over multiple days."""

    def validate_config(self, config: dict) -> dict:
        num_guards = config.get("num_guards", 8)
        if not isinstance(num_guards, int) or num_guards < 1 or num_guards > 20:
            raise ValueError("config.num_guards must be an integer between 1 and 20")

        num_prisoners = config.get("num_prisoners", 16)
        if not isinstance(num_prisoners, int) or num_prisoners < 1 or num_prisoners > 30:
            raise ValueError("config.num_prisoners must be an integer between 1 and 30")

        num_days = config.get("num_days", 1)
        if not isinstance(num_days, int) or num_days < 1:
            raise ValueError("config.num_days must be a positive integer")

        max_concurrent = config.get("max_concurrent", settings.MAX_CONCURRENT_AGENTS)
        if not isinstance(max_concurrent, int) or max_concurrent < 1:
            raise ValueError("config.max_concurrent must be a positive integer")

        return {
            "num_guards": num_guards,
            "num_prisoners": num_prisoners,
            "num_days": num_days,
            "max_concurrent": max_concurrent,
            "model_id": config.get("model_id", settings.DEFAULT_MODEL_ID),
        }

    def get_num_agents(self, config: dict) -> int:
        return config.get("num_guards", 8) + config.get("num_prisoners", 16)

    async def run(self, simulation_id: str, config: dict, db_session: AsyncSession) -> str:
        model_id = config.get("model_id")
        max_concurrent = config.get("max_concurrent")

        # Stage 1: Generate identities and assign roles
        logger.info("Stage 1: Generating prison identities for simulation %s", simulation_id)
        guards, prisoners = await generate_prison_identities(
            config, simulation_id, db_session, model_id,
        )

        # Stage 2: Run day simulation(s)
        logger.info("Stage 2: Running day simulation for simulation %s", simulation_id)
        all_interactions: list[dict] = []
        for day in range(config.get("num_days", 1)):
            logger.info("Day %d of simulation %s", day + 1, simulation_id)
            day_interactions = await run_day(
                guards, prisoners, simulation_id, db_session,
                model_id, max_concurrent,
            )
            all_interactions.extend(day_interactions)

        # Stage 3: Analyze results
        logger.info("Stage 3: Analyzing results for simulation %s", simulation_id)
        summary = await analyze_prison_experiment(
            all_interactions,
            config.get("num_guards", 8),
            config.get("num_prisoners", 16),
            simulation_id, db_session, model_id,
        )

        return summary

    def describe(self) -> dict:
        return {
            "name": "Stanford Prison Experiment",
            "description": (
                "Simulates the Stanford Prison Experiment with AI agents assigned "
                "guard and prisoner roles, observing emergent authority dynamics."
            ),
            "config_schema": {
                "num_guards": {"type": "integer", "default": 8, "description": "Number of guard agents"},
                "num_prisoners": {"type": "integer", "default": 16, "description": "Number of prisoner agents"},
                "num_days": {"type": "integer", "default": 1, "description": "Number of simulated days"},
                "max_concurrent": {"type": "integer", "default": settings.MAX_CONCURRENT_AGENTS, "description": "Max concurrent agent calls"},
                "model_id": {"type": "string", "default": settings.DEFAULT_MODEL_ID, "description": "Bedrock model ID"},
            },
        }
