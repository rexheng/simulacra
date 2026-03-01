from pydantic import BaseModel


class AgentResponse(BaseModel):
    id: str
    agent_index: int
    agent_name: str
    persona: dict | None = None
    output_text: str | None = None
    structured_output: dict | None = None

    model_config = {"from_attributes": True}


class AgentDetailResponse(AgentResponse):
    system_prompt: str | None = None
    input_text: str | None = None
    model_id: str | None = None
    token_usage: dict | None = None
