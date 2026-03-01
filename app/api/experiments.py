from fastapi import APIRouter

from app.engine.registry import SimulationRegistry

router = APIRouter(prefix="/api/v1/experiments", tags=["experiments"])


@router.get("")
async def list_experiments():
    """List all available simulation types with their config schemas."""
    return SimulationRegistry.list_all()
