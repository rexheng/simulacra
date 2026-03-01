import json
import logging
import random
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import create_agent
from app.config import settings
from app.engine.game_theory.prison.prompts import PRISON_IDENTITY_GENERATOR_PROMPT
from app.models.agent_record import AgentRecord
from app.models.simulation import SimulationStage, SimulationStatus

logger = logging.getLogger(__name__)


async def generate_prison_identities(
    config: dict,
    simulation_id: str,
    db_session: AsyncSession,
    model_id: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Generate personas and assign guard/prisoner roles.

    Returns (guards, prisoners) where each is a list of persona dicts
    with added 'role', 'role_id', and 'agent_record_id' fields.
    """
    num_guards = config.get("num_guards", 8)
    num_prisoners = config.get("num_prisoners", 16)
    total = num_guards + num_prisoners

    stage = SimulationStage(
        simulation_id=simulation_id,
        stage_name="identity_generation",
        stage_order=1,
        status=SimulationStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stage)
    await db_session.commit()

    try:
        prompt = PRISON_IDENTITY_GENERATOR_PROMPT.format(num_personas=total)
        agent = create_agent(system_prompt=prompt, model_id=model_id, name="prison_identity_generator")

        input_text = f"Generate {total} male college student personas for a Stanford Prison Experiment simulation."
        result = agent(input_text)
        output_text = (
            str(result.message.get("content", [{}])[0].get("text", ""))
            if result.message
            else str(result)
        )

        # Persist the generator agent call
        generator_record = AgentRecord(
            simulation_id=simulation_id,
            agent_index=0,
            agent_name="prison_identity_generator",
            persona=None,
            system_prompt=prompt,
            input_text=input_text,
            output_text=output_text,
            model_id=model_id,
        )
        db_session.add(generator_record)

        personas = _parse_personas(output_text)
        if len(personas) < total:
            logger.warning(
                "Generated %d personas but requested %d", len(personas), total
            )

        # Shuffle for random role assignment
        random.shuffle(personas)

        guards = []
        prisoners = []

        for i, persona in enumerate(personas):
            if i < num_guards:
                role = "guard"
                role_id = f"Guard_{i + 1:02d}"
            else:
                role_id = f"Prisoner_{random.randint(1000, 9999)}"
                role = "prisoner"

            persona["role"] = role
            persona["role_id"] = role_id

            record = AgentRecord(
                simulation_id=simulation_id,
                agent_index=i + 1,
                agent_name=role_id,
                persona=persona,
                model_id=model_id,
            )
            db_session.add(record)
            await db_session.flush()

            persona["agent_record_id"] = record.id

            if role == "guard":
                guards.append(persona)
            else:
                prisoners.append(persona)

        stage.status = SimulationStatus.COMPLETED
        stage.completed_at = datetime.now(timezone.utc)
        stage.output = {
            "total_personas": len(personas),
            "guards": len(guards),
            "prisoners": len(prisoners),
        }
        await db_session.commit()

        logger.info(
            "Generated %d guards and %d prisoners for simulation %s",
            len(guards), len(prisoners), simulation_id,
        )
        return guards, prisoners

    except Exception as e:
        stage.status = SimulationStatus.FAILED
        stage.error = str(e)
        stage.completed_at = datetime.now(timezone.utc)
        await db_session.commit()
        raise


def _parse_personas(output_text: str) -> list[dict]:
    """Extract JSON array of personas from agent output."""
    # Try direct parse
    try:
        parsed = json.loads(output_text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
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
