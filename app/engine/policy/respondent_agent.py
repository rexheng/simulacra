import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import create_agent
from app.agents.prompts import RESPONDENT_PROMPT_TEMPLATE
from app.config import settings
from app.models.agent_record import AgentRecord
from app.models.simulation import SimulationStage, SimulationStatus

logger = logging.getLogger(__name__)


async def run_respondent_swarm(
    personas: list[dict],
    policy_text: str,
    simulation_id: str,
    db_session: AsyncSession,
    model_id: str | None = None,
    max_concurrent: int | None = None,
) -> list[dict]:
    """Run all respondent agents concurrently with rate limiting.

    Returns a list of response dicts with persona + output.
    """
    max_concurrent = max_concurrent or settings.MAX_CONCURRENT_AGENTS

    # Create stage record
    stage = SimulationStage(
        simulation_id=simulation_id,
        stage_name="respondent_swarm",
        stage_order=2,
        status=SimulationStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stage)
    await db_session.commit()

    try:
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = []
        for i, persona in enumerate(personas):
            tasks.append(
                _run_single_respondent(
                    semaphore, persona, policy_text, simulation_id, i + 1, model_id, db_session
                )
            )

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful responses
        results = []
        errors = 0
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                logger.error("Respondent %d failed: %s", i + 1, resp)
                errors += 1
            else:
                results.append(resp)

        stage.status = SimulationStatus.COMPLETED
        stage.completed_at = datetime.now(timezone.utc)
        stage.output = {"responses_collected": len(results), "errors": errors}
        await db_session.commit()

        logger.info(
            "Collected %d responses (%d errors) for simulation %s",
            len(results), errors, simulation_id,
        )
        return results

    except Exception as e:
        stage.status = SimulationStatus.FAILED
        stage.error = str(e)
        stage.completed_at = datetime.now(timezone.utc)
        await db_session.commit()
        raise


async def _run_single_respondent(
    semaphore: asyncio.Semaphore,
    persona: dict,
    policy_text: str,
    simulation_id: str,
    agent_index: int,
    model_id: str | None,
    db_session: AsyncSession,
) -> dict:
    """Run a single respondent agent behind a semaphore."""
    async with semaphore:
        key_concerns = persona.get("key_concerns", [])
        if isinstance(key_concerns, list):
            key_concerns = ", ".join(key_concerns)

        system_prompt = RESPONDENT_PROMPT_TEMPLATE.format(
            name=persona.get("name", f"Respondent {agent_index}"),
            age=persona.get("age", "unknown"),
            occupation=persona.get("occupation", "citizen"),
            location_type=persona.get("location_type", "urban"),
            education=persona.get("education", "unknown"),
            income_level=persona.get("income_level", "medium"),
            political_leaning=persona.get("political_leaning", "center"),
            key_concerns=key_concerns,
        )

        agent = create_agent(system_prompt=system_prompt, model_id=model_id, name=persona.get("name", "respondent"))
        input_text = f"Please respond to the following proposed policy:\n\n{policy_text}"

        result = agent(input_text)
        output_text = str(result.message.get("content", [{}])[0].get("text", "")) if result.message else str(result)

        # Extract stance from output
        structured_output = _extract_stance(output_text)

        # Update the existing agent record for this persona
        stmt = select(AgentRecord).where(
            AgentRecord.simulation_id == simulation_id,
            AgentRecord.agent_index == agent_index,
        )
        existing = await db_session.execute(stmt)
        record = existing.scalar_one_or_none()

        if record:
            record.system_prompt = system_prompt
            record.input_text = input_text
            record.output_text = output_text
            record.structured_output = structured_output
            record.model_id = model_id or settings.DEFAULT_MODEL_ID
        else:
            record = AgentRecord(
                simulation_id=simulation_id,
                agent_index=agent_index,
                agent_name=persona.get("name", f"respondent_{agent_index}"),
                persona=persona,
                system_prompt=system_prompt,
                input_text=input_text,
                output_text=output_text,
                structured_output=structured_output,
                model_id=model_id or settings.DEFAULT_MODEL_ID,
            )
            db_session.add(record)

        await db_session.commit()

        return {
            "persona": persona,
            "output_text": output_text,
            "stance": structured_output.get("stance", "unknown") if structured_output else "unknown",
        }


def _extract_stance(output_text: str) -> dict | None:
    """Try to extract the stance from the respondent's output."""
    stances = ["strongly support", "support", "neutral", "oppose", "strongly oppose"]
    text_lower = output_text.lower()

    detected_stance = "unknown"
    for stance in stances:
        if stance in text_lower:
            detected_stance = stance
            break

    return {"stance": detected_stance, "raw_length": len(output_text)}
