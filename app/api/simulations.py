from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.engine.registry import SimulationRegistry
from app.engine.runner import run_simulation
from app.models import SimulationRun, SimulationStage, SimulationStatus
from app.schemas.simulation import (
    CreateSimulationRequest,
    SimulationListResponse,
    SimulationResponse,
    SimulationStageResponse,
)

router = APIRouter(prefix="/api/v1/simulations", tags=["simulations"])


@router.post("", response_model=SimulationResponse, status_code=201)
async def create_simulation(
    request: CreateSimulationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Validate simulation type exists
    sim_class = SimulationRegistry.get(request.simulation_type)
    if sim_class is None:
        available = list(SimulationRegistry._registry.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown simulation type: {request.simulation_type}. Available: {available}",
        )

    # Validate config
    try:
        instance = sim_class()
        instance.validate_config(request.config)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Create simulation run
    sim_run = SimulationRun(
        simulation_type=request.simulation_type,
        status=SimulationStatus.PENDING,
        config=request.config,
    )
    db.add(sim_run)
    await db.commit()
    await db.refresh(sim_run)

    # Kick off in background
    background_tasks.add_task(
        run_simulation, sim_run.id, request.simulation_type, request.config, async_session_factory
    )

    return sim_run


@router.get("", response_model=SimulationListResponse)
async def list_simulations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SimulationRun).order_by(SimulationRun.created_at.desc()))
    simulations = result.scalars().all()
    return SimulationListResponse(simulations=simulations)


@router.get("/{simulation_id}", response_model=SimulationResponse)
async def get_simulation(simulation_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SimulationRun).where(SimulationRun.id == simulation_id))
    sim_run = result.scalar_one_or_none()
    if sim_run is None:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim_run


@router.get("/{simulation_id}/stages", response_model=list[SimulationStageResponse])
async def get_simulation_stages(simulation_id: str, db: AsyncSession = Depends(get_db)):
    # Verify simulation exists
    result = await db.execute(select(SimulationRun).where(SimulationRun.id == simulation_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    result = await db.execute(
        select(SimulationStage)
        .where(SimulationStage.simulation_id == simulation_id)
        .order_by(SimulationStage.stage_order)
    )
    return result.scalars().all()
