import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import create_agent
from app.agents.prompts import DISTRIBUTION_GENERATOR_PROMPT
from app.models.agent_record import AgentRecord
from app.models.simulation import SimulationStage, SimulationStatus

logger = logging.getLogger(__name__)


async def generate_distribution(
    config: dict,
    simulation_id: str,
    db_session: AsyncSession,
    model_id: str | None = None,
) -> list[dict]:
    """Generate a diverse set of personas using a Strands agent.

    Returns a list of persona dicts.
    """
    sample_size = config.get("sample_size", 10)

    # Create stage record
    stage = SimulationStage(
        simulation_id=simulation_id,
        stage_name="distribution_generation",
        stage_order=1,
        status=SimulationStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stage)
    await db_session.commit()

    try:
        prompt = DISTRIBUTION_GENERATOR_PROMPT.format(sample_size=sample_size)
        agent = create_agent(system_prompt=prompt, model_id=model_id, name="distribution_generator")

        policy_text = config.get("policy_text", "")
        input_text = f"Generate {sample_size} diverse personas for evaluating this policy: {policy_text}"

        result = agent(input_text)
        output_text = str(result.message.get("content", [{}])[0].get("text", "")) if result.message else str(result)

        # Persist the generator agent call
        generator_record = AgentRecord(
            simulation_id=simulation_id,
            agent_index=0,
            agent_name="distribution_generator",
            persona=None,
            system_prompt=prompt,
            input_text=input_text,
            output_text=output_text,
            model_id=model_id,
        )
        db_session.add(generator_record)

        # Parse personas from output
        personas = _parse_personas(output_text)
        if len(personas) < sample_size:
            logger.warning(
                "Generated %d personas but requested %d", len(personas), sample_size
            )

        # Create agent records for each persona (output_text null — filled in respondent stage)
        for i, persona in enumerate(personas):
            record = AgentRecord(
                simulation_id=simulation_id,
                agent_index=i + 1,
                agent_name=persona.get("name", f"respondent_{i+1}"),
                persona=persona,
                model_id=model_id,
            )
            db_session.add(record)

        # Update stage
        stage.status = SimulationStatus.COMPLETED
        stage.completed_at = datetime.now(timezone.utc)
        stage.output = {"persona_count": len(personas)}
        await db_session.commit()

        logger.info("Generated %d personas for simulation %s", len(personas), simulation_id)
        return personas

    except Exception as e:
        stage.status = SimulationStatus.FAILED
        stage.error = str(e)
        stage.completed_at = datetime.now(timezone.utc)
        await db_session.commit()
        raise


def _parse_personas(output_text: str) -> list[dict]:
    """Extract JSON array of personas from agent output."""
    # Try direct parse first
    try:
        parsed = json.loads(output_text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code block
    import re

    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", output_text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try finding array in text
    start = output_text.find("[")
    end = output_text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(output_text[start : end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse personas from output: %s", output_text[:200])
    raise ValueError("Could not parse personas JSON from agent output")
