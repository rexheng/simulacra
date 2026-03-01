from datetime import datetime

from pydantic import BaseModel, Field


class CreateSimulationRequest(BaseModel):
    simulation_type: str = Field(..., description="Type of simulation to run (e.g. 'policy', 'ultimatum_game')")
    config: dict = Field(default_factory=dict, description="Simulation-specific configuration")


class SimulationResponse(BaseModel):
    id: str
    simulation_type: str
    status: str
    config: dict | None = None
    created_at: datetime
    completed_at: datetime | None = None
    summary: str | None = None
    extra_metadata: dict | None = None

    model_config = {"from_attributes": True}


class SimulationStageResponse(BaseModel):
    id: str
    stage_name: str
    stage_order: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output: dict | None = None
    error: str | None = None

    model_config = {"from_attributes": True}


class SimulationListResponse(BaseModel):
    simulations: list[SimulationResponse]
