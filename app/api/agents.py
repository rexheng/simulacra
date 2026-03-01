from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AgentRecord, InteractionRecord, SimulationRun
from app.schemas.agent import AgentDetailResponse, AgentResponse
from app.schemas.game_theory import InteractionResponse

router = APIRouter(prefix="/api/v1/simulations/{simulation_id}", tags=["agents"])


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(simulation_id: str, db: AsyncSession = Depends(get_db)):
    # Verify simulation exists
    result = await db.execute(select(SimulationRun).where(SimulationRun.id == simulation_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    result = await db.execute(
        select(AgentRecord)
        .where(AgentRecord.simulation_id == simulation_id)
        .order_by(AgentRecord.agent_index)
    )
    return result.scalars().all()


@router.get("/agents/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(simulation_id: str, agent_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentRecord).where(
            AgentRecord.id == agent_id,
            AgentRecord.simulation_id == simulation_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/interactions", response_model=list[InteractionResponse])
async def list_interactions(simulation_id: str, db: AsyncSession = Depends(get_db)):
    # Verify simulation exists
    result = await db.execute(select(SimulationRun).where(SimulationRun.id == simulation_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Simulation not found")

    result = await db.execute(
        select(InteractionRecord)
        .where(InteractionRecord.simulation_id == simulation_id)
        .order_by(InteractionRecord.round_number)
    )
    return result.scalars().all()
