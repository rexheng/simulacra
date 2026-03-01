import logging

from sqlalchemy.ext.asyncio import AsyncSession
from strands import Agent
from strands.models import BedrockModel

from app.config import settings
from app.models.agent_record import AgentRecord

logger = logging.getLogger(__name__)


def create_agent(
    system_prompt: str,
    model_id: str | None = None,
    tools: list | None = None,
    name: str = "agent",
) -> Agent:
    """Create a Strands agent with a Bedrock model."""
    bedrock_model = BedrockModel(
        model_id=model_id or settings.DEFAULT_MODEL_ID,
        region_name=settings.AWS_DEFAULT_REGION,
    )
    kwargs: dict = {
        "model": bedrock_model,
        "system_prompt": system_prompt,
    }
    if tools:
        kwargs["tools"] = tools
    return Agent(**kwargs)


async def run_and_persist_agent(
    agent: Agent,
    input_text: str,
    simulation_id: str,
    agent_index: int,
    agent_name: str,
    persona: dict | None,
    system_prompt: str,
    model_id: str | None,
    db_session: AsyncSession,
) -> AgentRecord:
    """Run an agent and persist the call to the database."""
    result = agent(input_text)

    output_text = str(result.message.get("content", [{}])[0].get("text", "")) if result.message else str(result)
    token_usage = None
    if result.metrics:
        token_usage = {
            "input_tokens": getattr(result.metrics, "input_tokens", None),
            "output_tokens": getattr(result.metrics, "output_tokens", None),
        }

    record = AgentRecord(
        simulation_id=simulation_id,
        agent_index=agent_index,
        agent_name=agent_name,
        persona=persona,
        system_prompt=system_prompt,
        input_text=input_text,
        output_text=output_text,
        model_id=model_id or settings.DEFAULT_MODEL_ID,
        token_usage=token_usage,
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    logger.info("Persisted agent record %s for simulation %s", record.id, simulation_id)
    return record
