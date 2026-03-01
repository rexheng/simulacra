import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import create_agent
from app.agents.prompts import SYNTHESIS_PROMPT
from app.models.agent_record import AgentRecord
from app.models.simulation import SimulationStage, SimulationStatus

logger = logging.getLogger(__name__)


async def synthesize_responses(
    responses: list[dict],
    simulation_id: str,
    db_session: AsyncSession,
    model_id: str | None = None,
) -> str:
    """Aggregate all respondent outputs into a synthesis report.

    Returns the summary text.
    """
    # Create stage record
    stage = SimulationStage(
        simulation_id=simulation_id,
        stage_name="synthesis",
        stage_order=3,
        status=SimulationStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stage)
    await db_session.commit()

    try:
        system_prompt = SYNTHESIS_PROMPT.format(num_respondents=len(responses))
        agent = create_agent(system_prompt=system_prompt, model_id=model_id, name="synthesizer")

        # Build input with all responses
        response_texts = []
        for i, resp in enumerate(responses):
            persona = resp.get("persona", {})
            name = persona.get("name", f"Respondent {i+1}")
            age = persona.get("age", "?")
            occupation = persona.get("occupation", "?")
            political = persona.get("political_leaning", "?")
            location = persona.get("location_type", "?")
            stance = resp.get("stance", "unknown")

            response_texts.append(
                f"--- Respondent {i+1}: {name} (age {age}, {occupation}, {political}, {location}) ---\n"
                f"Stance: {stance}\n"
                f"Response:\n{resp.get('output_text', 'No response')}\n"
            )

        input_text = "Here are all the citizen responses to the proposed policy:\n\n" + "\n".join(response_texts)

        result = agent(input_text)
        summary = str(result.message.get("content", [{}])[0].get("text", "")) if result.message else str(result)

        # Persist synthesis agent call
        record = AgentRecord(
            simulation_id=simulation_id,
            agent_index=len(responses) + 1,
            agent_name="synthesizer",
            persona=None,
            system_prompt=system_prompt,
            input_text=input_text[:5000],  # Truncate for storage
            output_text=summary,
            model_id=model_id,
        )
        db_session.add(record)

        # Update stage
        stage.status = SimulationStatus.COMPLETED
        stage.completed_at = datetime.now(timezone.utc)
        stage.output = {"summary_length": len(summary)}
        await db_session.commit()

        logger.info("Synthesis complete for simulation %s", simulation_id)
        return summary

    except Exception as e:
        stage.status = SimulationStatus.FAILED
        stage.error = str(e)
        stage.completed_at = datetime.now(timezone.utc)
        await db_session.commit()
        raise
