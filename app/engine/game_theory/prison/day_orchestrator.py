import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import create_agent
from app.config import settings
from app.engine.game_theory.prison.prompts import (
    GUARD_SYSTEM_PROMPT_TEMPLATE,
    PHASE_DESCRIPTIONS,
    PHASE_ORDER,
    PRISONER_SYSTEM_PROMPT_TEMPLATE,
)
from app.models.agent_record import AgentRecord
from app.models.interaction import InteractionRecord
from app.models.simulation import SimulationStage, SimulationStatus

logger = logging.getLogger(__name__)

MAX_HISTORY_ENTRIES = 20


async def run_day(
    guards: list[dict],
    prisoners: list[dict],
    simulation_id: str,
    db_session: AsyncSession,
    model_id: str | None = None,
    max_concurrent: int | None = None,
) -> list[dict]:
    """Run one day of the prison simulation across 5 phases.

    Returns a list of all interaction dicts from the day.
    """
    max_concurrent = max_concurrent or settings.MAX_CONCURRENT_AGENTS

    stage = SimulationStage(
        simulation_id=simulation_id,
        stage_name="day_simulation",
        stage_order=2,
        status=SimulationStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stage)
    await db_session.commit()

    try:
        all_interactions: list[dict] = []
        semaphore = asyncio.Semaphore(max_concurrent)

        for phase_index, phase_key in enumerate(PHASE_ORDER):
            phase_desc = PHASE_DESCRIPTIONS[phase_key]
            history_text = _format_interaction_history(all_interactions)

            # --- Guards act concurrently ---
            guard_tasks = [
                _run_guard_action(
                    semaphore, guard, phase_desc, history_text,
                    simulation_id, model_id, db_session,
                )
                for guard in guards
            ]
            guard_results = await asyncio.gather(*guard_tasks, return_exceptions=True)

            guard_actions: list[dict] = []
            for i, result in enumerate(guard_results):
                if isinstance(result, Exception):
                    logger.error("Guard %s failed: %s", guards[i].get("role_id"), result)
                else:
                    guard_actions.append(result)

            # --- Targeted prisoners respond concurrently ---
            prisoner_tasks = []
            for action in guard_actions:
                target = action.get("target_prisoner", "all")
                targeted = _resolve_targets(target, prisoners)
                for prisoner in targeted:
                    prisoner_tasks.append(
                        _run_prisoner_response(
                            semaphore, prisoner, action, phase_desc,
                            history_text, simulation_id, model_id, db_session,
                        )
                    )

            prisoner_results = await asyncio.gather(*prisoner_tasks, return_exceptions=True)

            # Persist interactions and collect results
            for result in prisoner_results:
                if isinstance(result, Exception):
                    logger.error("Prisoner response failed: %s", result)
                    continue

                interaction_data = result
                interaction = InteractionRecord(
                    simulation_id=simulation_id,
                    round_number=phase_index,
                    initiator_agent_id=interaction_data["guard_agent_record_id"],
                    target_agent_id=interaction_data["prisoner_agent_record_id"],
                    interaction_type=f"prison_{phase_key}",
                    payload=interaction_data["guard_action"],
                    response=interaction_data["prisoner_response"],
                )
                db_session.add(interaction)
                all_interactions.append(interaction_data)

            await db_session.commit()
            logger.info(
                "Phase %s complete: %d guard actions, %d prisoner responses",
                phase_key, len(guard_actions), len([r for r in prisoner_results if not isinstance(r, Exception)]),
            )

        stage.status = SimulationStatus.COMPLETED
        stage.completed_at = datetime.now(timezone.utc)
        stage.output = {"total_interactions": len(all_interactions)}
        await db_session.commit()

        return all_interactions

    except Exception as e:
        stage.status = SimulationStatus.FAILED
        stage.error = str(e)
        stage.completed_at = datetime.now(timezone.utc)
        await db_session.commit()
        raise


async def _run_guard_action(
    semaphore: asyncio.Semaphore,
    guard: dict,
    phase_description: str,
    interaction_history: str,
    simulation_id: str,
    model_id: str | None,
    db_session: AsyncSession,
) -> dict:
    """Run a single guard agent and return the parsed action."""
    async with semaphore:
        system_prompt = GUARD_SYSTEM_PROMPT_TEMPLATE.format(
            name=guard.get("name", "Guard"),
            role_id=guard["role_id"],
            age=guard.get("age", "unknown"),
            major=guard.get("major", "unknown"),
            hometown=guard.get("hometown", "unknown"),
            background_description=guard.get("background_description", ""),
            socioeconomic_background=guard.get("socioeconomic_background", "middle_class"),
            phase_description=phase_description,
            interaction_history=interaction_history,
        )

        agent = create_agent(
            system_prompt=system_prompt, model_id=model_id, name=guard["role_id"],
        )
        input_text = f"It is now: {phase_description}\n\nDecide your action as {guard['role_id']}."
        result = agent(input_text)
        output_text = (
            str(result.message.get("content", [{}])[0].get("text", ""))
            if result.message
            else str(result)
        )

        # Update the guard's agent record with latest output
        record = await _update_agent_record(
            guard, system_prompt, input_text, output_text,
            simulation_id, model_id, db_session,
        )

        parsed = _parse_json_response(output_text)
        parsed["guard_role_id"] = guard["role_id"]
        parsed["guard_name"] = guard.get("name", "Guard")
        parsed["guard_agent_record_id"] = guard["agent_record_id"]
        return parsed


async def _run_prisoner_response(
    semaphore: asyncio.Semaphore,
    prisoner: dict,
    guard_action: dict,
    phase_description: str,
    interaction_history: str,
    simulation_id: str,
    model_id: str | None,
    db_session: AsyncSession,
) -> dict:
    """Run a single prisoner agent responding to a guard action."""
    async with semaphore:
        guard_context = (
            f"{guard_action.get('guard_role_id', 'A guard')} ({guard_action.get('guard_name', '')}) "
            f"performed action '{guard_action.get('action', 'unknown')}': "
            f"{guard_action.get('description', 'No description')}"
        )

        system_prompt = PRISONER_SYSTEM_PROMPT_TEMPLATE.format(
            name=prisoner.get("name", "Prisoner"),
            role_id=prisoner["role_id"],
            age=prisoner.get("age", "unknown"),
            major=prisoner.get("major", "unknown"),
            hometown=prisoner.get("hometown", "unknown"),
            background_description=prisoner.get("background_description", ""),
            socioeconomic_background=prisoner.get("socioeconomic_background", "middle_class"),
            phase_description=phase_description,
            interaction_history=interaction_history,
            guard_action_context=guard_context,
        )

        agent = create_agent(
            system_prompt=system_prompt, model_id=model_id, name=prisoner["role_id"],
        )
        input_text = f"Respond to the guard's action: {guard_context}"
        result = agent(input_text)
        output_text = (
            str(result.message.get("content", [{}])[0].get("text", ""))
            if result.message
            else str(result)
        )

        await _update_agent_record(
            prisoner, system_prompt, input_text, output_text,
            simulation_id, model_id, db_session,
        )

        parsed = _parse_json_response(output_text)
        return {
            "phase": phase_description,
            "guard_role_id": guard_action.get("guard_role_id"),
            "guard_name": guard_action.get("guard_name"),
            "guard_agent_record_id": guard_action["guard_agent_record_id"],
            "guard_action": {
                "action": guard_action.get("action", "unknown"),
                "target_prisoner": guard_action.get("target_prisoner", "unknown"),
                "description": guard_action.get("description", ""),
                "reasoning": guard_action.get("reasoning", ""),
            },
            "prisoner_role_id": prisoner["role_id"],
            "prisoner_name": prisoner.get("name", "Prisoner"),
            "prisoner_agent_record_id": prisoner["agent_record_id"],
            "prisoner_response": {
                "response": parsed.get("response", "unknown"),
                "description": parsed.get("description", ""),
                "emotional_state": parsed.get("emotional_state", "unknown"),
            },
        }


async def _update_agent_record(
    persona: dict,
    system_prompt: str,
    input_text: str,
    output_text: str,
    simulation_id: str,
    model_id: str | None,
    db_session: AsyncSession,
) -> AgentRecord:
    """Update the existing agent record with the latest interaction."""
    from sqlalchemy import select

    stmt = select(AgentRecord).where(AgentRecord.id == persona["agent_record_id"])
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()

    if record:
        record.system_prompt = system_prompt
        record.input_text = input_text
        record.output_text = output_text
        record.model_id = model_id or settings.DEFAULT_MODEL_ID
    else:
        record = AgentRecord(
            simulation_id=simulation_id,
            agent_index=0,
            agent_name=persona.get("role_id", "unknown"),
            persona=persona,
            system_prompt=system_prompt,
            input_text=input_text,
            output_text=output_text,
            model_id=model_id or settings.DEFAULT_MODEL_ID,
        )
        db_session.add(record)

    await db_session.flush()
    return record


def _resolve_targets(target: str, prisoners: list[dict]) -> list[dict]:
    """Resolve a guard's target to a list of prisoner dicts."""
    if target == "all" or not target:
        return prisoners

    for prisoner in prisoners:
        if prisoner["role_id"] == target:
            return [prisoner]

    # If target not found, default to a random prisoner
    if prisoners:
        return [prisoners[0]]
    return []


def _format_interaction_history(interactions: list[dict]) -> str:
    """Format recent interactions as context text, capped at MAX_HISTORY_ENTRIES."""
    if not interactions:
        return "INTERACTION HISTORY: No prior interactions today."

    recent = interactions[-MAX_HISTORY_ENTRIES:]
    lines = ["INTERACTION HISTORY (recent events):"]
    for entry in recent:
        guard_id = entry.get("guard_role_id", "Guard")
        prisoner_id = entry.get("prisoner_role_id", "Prisoner")
        action = entry.get("guard_action", {})
        response = entry.get("prisoner_response", {})
        lines.append(
            f"- {guard_id} -> {prisoner_id}: "
            f"[{action.get('action', '?')}] {action.get('description', '')} "
            f"| Response: [{response.get('response', '?')}] {response.get('description', '')} "
            f"(emotional state: {response.get('emotional_state', '?')})"
        )
    return "\n".join(lines)


def _parse_json_response(output_text: str) -> dict:
    """Extract a JSON object from agent output."""
    # Try direct parse
    try:
        parsed = json.loads(output_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", output_text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try finding object in text
    start = output_text.find("{")
    end = output_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(output_text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse JSON from output: %s", output_text[:200])
    return {"action": "unknown", "description": output_text[:200], "reasoning": "Parse failure"}
