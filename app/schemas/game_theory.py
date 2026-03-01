from datetime import datetime

from pydantic import BaseModel, Field


class InteractionResponse(BaseModel):
    id: str
    simulation_id: str
    round_number: int
    initiator_agent_id: str | None = None
    target_agent_id: str | None = None
    interaction_type: str
    payload: dict | None = None
    response: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UltimatumConfig(BaseModel):
    num_pairs: int = Field(default=5, description="Number of proposer/responder pairs")
    total_amount: float = Field(default=100.0, description="Total amount to split")
    num_rounds: int = Field(default=3, description="Number of rounds per pair")
    model_id: str | None = None


class StanfordPrisonConfig(BaseModel):
    num_guards: int = Field(default=8, description="Number of guard agents")
    num_prisoners: int = Field(default=16, description="Number of prisoner agents")
    num_days: int = Field(default=1, description="Number of simulated days")
    model_id: str | None = None


class BystanderConfig(BaseModel):
    num_bystanders: int = Field(default=8, description="Number of bystander agents")
    scenario_type: str = Field(default="emergency", description="Type of scenario")
    num_rounds: int = Field(default=3, description="Number of observation rounds")
    model_id: str | None = None
