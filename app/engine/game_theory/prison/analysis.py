import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import create_agent
from app.engine.game_theory.prison.prompts import PHASE_ORDER, PRISON_ANALYSIS_PROMPT
from app.models.agent_record import AgentRecord
from app.models.simulation import SimulationStage, SimulationStatus

logger = logging.getLogger(__name__)


async def analyze_prison_experiment(
    all_interactions: list[dict],
    num_guards: int,
    num_prisoners: int,
    simulation_id: str,
    db_session: AsyncSession,
    model_id: str | None = None,
) -> str:
    """Analyze all prison experiment interactions and produce a behavioral report.

    Returns the analysis summary text.
    """
    stage = SimulationStage(
        simulation_id=simulation_id,
        stage_name="analysis",
        stage_order=3,
        status=SimulationStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stage)
    await db_session.commit()

    try:
        interaction_data = _format_interactions_for_analysis(all_interactions)

        system_prompt = PRISON_ANALYSIS_PROMPT.format(
            num_guards=num_guards,
            num_prisoners=num_prisoners,
            num_phases=len(PHASE_ORDER),
            interaction_data=interaction_data,
        )

        agent = create_agent(
            system_prompt=system_prompt, model_id=model_id, name="prison_analyst",
        )
        input_text = (
            "Analyze the interaction data provided and produce a comprehensive "
            "behavioral categorization report comparing results to Zimbardo's findings."
        )

        result = agent(input_text)
        summary = (
            str(result.message.get("content", [{}])[0].get("text", ""))
            if result.message
            else str(result)
        )

        # Persist analyst agent record
        record = AgentRecord(
            simulation_id=simulation_id,
            agent_index=num_guards + num_prisoners + 1,
            agent_name="prison_analyst",
            persona=None,
            system_prompt=system_prompt,
            input_text=input_text,
            output_text=summary,
            model_id=model_id,
        )
        db_session.add(record)

        stage.status = SimulationStatus.COMPLETED
        stage.completed_at = datetime.now(timezone.utc)
        stage.output = {"summary_length": len(summary)}
        await db_session.commit()

        logger.info("Analysis complete for simulation %s", simulation_id)
        return summary

    except Exception as e:
        stage.status = SimulationStatus.FAILED
        stage.error = str(e)
        stage.completed_at = datetime.now(timezone.utc)
        await db_session.commit()
        raise


def _format_interactions_for_analysis(interactions: list[dict]) -> str:
    """Format all interactions grouped by phase for the analysis prompt."""
    # Group by phase
    phase_groups: dict[str, list[dict]] = {}
    for entry in interactions:
        phase = entry.get("phase", "unknown")
        phase_groups.setdefault(phase, []).append(entry)

    lines = []
    for phase_name, entries in phase_groups.items():
        lines.append(f"\n## {phase_name}")
        lines.append(f"({len(entries)} interactions)\n")
        for entry in entries:
            guard_action = entry.get("guard_action", {})
            prisoner_response = entry.get("prisoner_response", {})
            lines.append(
                f"- {entry.get('guard_role_id', '?')} ({entry.get('guard_name', '?')}) "
                f"-> {entry.get('prisoner_role_id', '?')} ({entry.get('prisoner_name', '?')})"
            )
            lines.append(
                f"  Guard action: [{guard_action.get('action', '?')}] "
                f"{guard_action.get('description', '')}"
            )
            lines.append(f"  Guard reasoning: {guard_action.get('reasoning', '')}")
            lines.append(
                f"  Prisoner response: [{prisoner_response.get('response', '?')}] "
                f"{prisoner_response.get('description', '')}"
            )
            lines.append(
                f"  Emotional state: {prisoner_response.get('emotional_state', '?')}"
            )
            lines.append("")

    return "\n".join(lines)
