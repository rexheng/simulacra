# Bystander Effect Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the Bystander Effect simulation that tests diffusion of responsibility across group sizes [1, 5, 15], using parallel independent witness agents.

**Architecture:** Single simulation generates 15 personas, runs 3 conditions (group sizes 1, 5, 15) using proximity-sorted subsets, with optional follow-up for indecisive agents. Follows existing prison simulation patterns: identity_generator → scenario_runner → analysis, all persisted via SimulationStage + AgentRecord.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, Strands Agents SDK (AWS Bedrock), asyncio

---

### Task 1: Create prompts.py — All prompt templates

**Files:**
- Create: `app/engine/game_theory/bystander/prompts.py`

**Step 1: Create the prompts file with all templates**

```python
"""Prompt templates for the Bystander Effect simulation."""

SCENARIO_TEXTS = {
    "emergency": (
        "It is 2:45 AM. You hear desperate screaming from outside your apartment building. "
        "Looking out, you see a woman being attacked by a man in the parking area below. "
        "She is crying out 'Please, somebody help me! He's going to kill me!' "
        "The attacker is striking her repeatedly. The area is dimly lit by a single streetlight."
    ),
    "theft": (
        "It is 11:30 PM. You hear the sound of breaking glass from the parking lot outside "
        "your apartment building. Looking out, you see someone smashing car windows with a "
        "crowbar, rifling through the interiors. They've already hit two vehicles and are "
        "moving to a third. The lot is partially lit."
    ),
    "harassment": (
        "It is 9:15 PM. At the bus stop visible from your apartment, a man is aggressively "
        "confronting a young woman. He is shouting obscenities, blocking her path, and has "
        "grabbed her arm. She is visibly frightened and trying to pull away. The street is "
        "otherwise quiet."
    ),
    "medical": (
        "It is 3:20 PM on a weekday. A person on the sidewalk below your apartment has "
        "suddenly collapsed. They appear to be having a seizure — their body is convulsing "
        "and they've fallen near the curb, dangerously close to traffic. No one on the "
        "street has stopped yet."
    ),
}


IDENTITY_GENERATOR_PROMPT = """\
You are a persona generator for a social psychology simulation studying the bystander effect.

Generate exactly {num_personas} diverse personas who live in the same apartment complex. \
Each person should be a realistic, distinct individual with traits that could plausibly \
influence whether they intervene in an emergency.

Each persona must include these fields:
- name: A realistic full name (diverse ethnicities and backgrounds)
- age: An integer between 19 and 78
- gender: "male", "female", or "non-binary"
- occupation: Their current job or role (e.g., "retired nurse", "college student", "taxi driver")
- living_situation: Who they live with (e.g., "lives alone", "lives with partner and toddler", \
"shares apartment with two roommates")
- years_in_neighbourhood: An integer between 0 and 40
- background_description: 2-3 sentences describing their temperament, daily routine, and \
relationship to the neighbourhood. Include details that could influence intervention behaviour \
(e.g., medical training, history of community involvement, anxiety disorders, night-shift worker)
- proximity_score: An integer from 1 to 10 (10 = directly witnessing from window with clear view, \
1 = barely audible from deep inside their flat)

Make personas genuinely diverse in age, gender, occupation, personality, and proximity. \
Include some who would plausibly intervene (e.g., former military, nurse, community activist) \
and some who would plausibly not (e.g., elderly person living alone, anxious introvert, \
someone with a sleeping child).

Output ONLY a valid JSON array of persona objects. No additional text or explanation."""


WITNESS_SYSTEM_PROMPT_TEMPLATE = """\
You are {name}, a {age}-year-old {gender} {occupation}.
{background_description}
Living situation: {living_situation}. Years in this neighbourhood: {years_in_neighbourhood}.
Proximity to the event: {proximity_score}/10 \
(10 = directly witnessing from your window, 1 = barely audible from inside your flat).

SCENARIO: {scenario_text}

You are aware that approximately {num_other_witnesses} other people are also witnessing \
this event from nearby apartments/locations.

Based on who you are and the situation, what do you do? Consider your personality, \
your proximity, the time of night, your living situation, and how the presence of \
{num_other_witnesses} other witnesses affects your sense of personal responsibility.

Respond with ONLY a valid JSON object (no other text):
{{
  "decision": "intervene_directly" or "call_emergency_services" or "alert_neighbor" or "observe_and_wait" or "ignore",
  "reasoning": "Your internal thought process as this person (2-3 sentences)",
  "confidence": <1-10 how certain you are of your choice>,
  "time_to_decide_seconds": <estimated seconds before you act>
}}"""


FOLLOW_UP_PROMPT_TEMPLATE = """\
It has been 2 minutes since you first noticed the incident. The screaming continues and \
has become more desperate. No one appears to have intervened — no sirens, no voices calling \
out, no movement from other apartments. The situation is unchanged or worsening.

You previously decided to observe and wait. Knowing that 2 minutes have passed with no \
intervention from anyone, what do you do now?

Respond with ONLY a valid JSON object (no other text):
{{
  "decision": "intervene_directly" or "call_emergency_services" or "alert_neighbor" or "observe_and_wait" or "ignore",
  "reasoning": "Your updated internal thought process (2-3 sentences)",
  "confidence": <1-10 how certain you are of your choice>,
  "time_to_decide_seconds": <estimated seconds before you act>
}}"""


ANALYSIS_PROMPT = """\
You are a social psychology researcher analyzing results from a simulated bystander effect \
experiment. The study tested {num_conditions} group-size conditions: {group_sizes}.

For each condition, the same pool of witnesses was presented with an emergency scenario. \
They made independent decisions without knowing what others chose. The key variable is \
group size — how awareness of other witnesses affects willingness to intervene.

{decision_data}

Produce a structured analysis covering:

1. **Intervention Rate by Group Size**: For each condition, calculate the percentage who \
chose to intervene (intervene_directly + call_emergency_services + alert_neighbor = intervention). \
Present the bystander effect curve.

2. **Decision Type Breakdown**: For each group size, count how many chose each decision type. \
Identify which forms of intervention were most/least common.

3. **Demographic Correlations**: Analyze whether specific traits correlated with intervention:
   - Caregiving/medical backgrounds vs. others
   - Long-term residents (10+ years) vs. newcomers
   - High proximity (7-10) vs. low proximity (1-4)
   - Age groups, gender, living situation patterns

4. **Second Decision Phase Analysis** (if applicable): How many "observe_and_wait" agents \
changed their decision in the follow-up? What tipped them?

5. **Comparison to Darley & Latané (1968)**: Compare intervention rates to classic findings:
   - Solo witness: ~85% intervene
   - Group of 5+: ~31% intervene
   - Note: our agents are not experiencing real physiological stress, so rates may differ

6. **Notable Individual Cases**: Identify 2-3 personas whose decisions were surprising given \
their profile (e.g., a nurse who ignored, or an anxious introvert who intervened directly). \
Analyze their reasoning.

Be analytical and reference specific agent decisions as evidence."""
```

**Step 2: Commit**

```bash
git add app/engine/game_theory/bystander/prompts.py
git commit -m "feat(bystander): add prompt templates for identity generation, witness decisions, and analysis"
```

---

### Task 2: Create identity_generator.py — Persona generation

**Files:**
- Create: `app/engine/game_theory/bystander/identity_generator.py`

**Step 1: Create the identity generator**

This follows the pattern from `app/engine/game_theory/prison/identity_generator.py` but generates bystander personas with the fields from our design.

```python
"""Identity generation for the Bystander Effect simulation."""

import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import create_agent
from app.config import settings
from app.engine.game_theory.bystander.prompts import IDENTITY_GENERATOR_PROMPT
from app.models.agent_record import AgentRecord
from app.models.simulation import SimulationStage, SimulationStatus

logger = logging.getLogger(__name__)


async def generate_bystander_identities(
    num_personas: int,
    simulation_id: str,
    db_session: AsyncSession,
    model_id: str | None = None,
) -> list[dict]:
    """Generate bystander personas and persist them.

    Returns a list of persona dicts sorted by proximity_score descending,
    each with an added 'agent_record_id' field.
    """
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
        prompt = IDENTITY_GENERATOR_PROMPT.format(num_personas=num_personas)
        agent = create_agent(
            system_prompt=prompt,
            model_id=model_id,
            name="bystander_identity_generator",
        )

        input_text = (
            f"Generate {num_personas} diverse personas who live in the same "
            f"apartment complex for a bystander effect simulation."
        )
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
            agent_name="bystander_identity_generator",
            persona=None,
            system_prompt=prompt,
            input_text=input_text,
            output_text=output_text,
            model_id=model_id,
        )
        db_session.add(generator_record)

        personas = _parse_personas(output_text)
        if len(personas) < num_personas:
            logger.warning(
                "Generated %d personas but requested %d",
                len(personas),
                num_personas,
            )

        # Sort by proximity_score descending
        personas.sort(key=lambda p: p.get("proximity_score", 1), reverse=True)

        # Persist each persona as an AgentRecord
        for i, persona in enumerate(personas):
            record = AgentRecord(
                simulation_id=simulation_id,
                agent_index=i + 1,
                agent_name=f"witness_{persona.get('name', f'Witness_{i+1}')}",
                persona=persona,
                model_id=model_id,
            )
            db_session.add(record)
            await db_session.flush()
            persona["agent_record_id"] = record.id

        stage.status = SimulationStatus.COMPLETED
        stage.completed_at = datetime.now(timezone.utc)
        stage.output = {"total_personas": len(personas)}
        await db_session.commit()

        logger.info(
            "Generated %d bystander personas for simulation %s",
            len(personas),
            simulation_id,
        )
        return personas

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
    raise ValueError("Could not parse bystander personas JSON from agent output")
```

**Step 2: Commit**

```bash
git add app/engine/game_theory/bystander/identity_generator.py
git commit -m "feat(bystander): add identity generator for bystander personas"
```

---

### Task 3: Create scenario_runner.py — Run one condition

**Files:**
- Create: `app/engine/game_theory/bystander/scenario_runner.py`

**Step 1: Create the scenario runner**

This is the core module. It runs all witnesses for a single group-size condition in parallel, then optionally runs follow-up prompts for `observe_and_wait` agents.

```python
"""Scenario runner for one group-size condition of the Bystander Effect simulation."""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import create_agent
from app.config import settings
from app.engine.game_theory.bystander.prompts import (
    FOLLOW_UP_PROMPT_TEMPLATE,
    SCENARIO_TEXTS,
    WITNESS_SYSTEM_PROMPT_TEMPLATE,
)
from app.models.agent_record import AgentRecord
from app.models.simulation import SimulationStage, SimulationStatus

logger = logging.getLogger(__name__)


async def run_condition(
    group_size: int,
    personas: list[dict],
    scenario_type: str,
    include_second_decision_phase: bool,
    simulation_id: str,
    db_session: AsyncSession,
    model_id: str | None = None,
    max_concurrent: int | None = None,
    stage_order: int = 2,
) -> list[dict]:
    """Run one group-size condition of the bystander experiment.

    Args:
        group_size: Number of witnesses for this condition.
        personas: Full persona list sorted by proximity (descending). Top N selected.
        scenario_type: Key into SCENARIO_TEXTS.
        include_second_decision_phase: Whether to follow up with observe_and_wait agents.
        simulation_id: Simulation ID for DB persistence.
        db_session: Async DB session.
        model_id: Bedrock model ID override.
        max_concurrent: Max concurrent agent calls.
        stage_order: Stage ordering number for this condition.

    Returns:
        List of decision dicts, one per witness. Each contains:
        - persona fields (name, age, etc.)
        - decision, reasoning, confidence, time_to_decide_seconds
        - original_decision (if follow-up changed it)
        - agent_record_id
    """
    max_concurrent = max_concurrent or settings.MAX_CONCURRENT_AGENTS
    scenario_text = SCENARIO_TEXTS[scenario_type]
    witnesses = personas[:group_size]

    stage = SimulationStage(
        simulation_id=simulation_id,
        stage_name=f"scenario_condition_{group_size}",
        stage_order=stage_order,
        status=SimulationStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stage)
    await db_session.commit()

    try:
        semaphore = asyncio.Semaphore(max_concurrent)
        num_other_witnesses = group_size - 1

        # Phase 1: All witnesses decide in parallel
        tasks = [
            _run_witness_decision(
                semaphore,
                witness,
                scenario_text,
                num_other_witnesses,
                simulation_id,
                model_id,
                db_session,
            )
            for witness in witnesses
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        decisions: list[dict] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Witness %s failed: %s",
                    witnesses[i].get("name", f"Witness_{i}"),
                    result,
                )
            else:
                decisions.append(result)

        # Phase 2: Follow-up for observe_and_wait agents
        if include_second_decision_phase:
            waiters = [d for d in decisions if d.get("decision") == "observe_and_wait"]
            if waiters:
                follow_up_tasks = [
                    _run_follow_up(
                        semaphore,
                        decision,
                        scenario_text,
                        num_other_witnesses,
                        simulation_id,
                        model_id,
                        db_session,
                    )
                    for decision in waiters
                ]
                follow_up_results = await asyncio.gather(
                    *follow_up_tasks, return_exceptions=True
                )
                for i, result in enumerate(follow_up_results):
                    if isinstance(result, Exception):
                        logger.error("Follow-up failed for %s: %s", waiters[i].get("name"), result)

        stage.status = SimulationStatus.COMPLETED
        stage.completed_at = datetime.now(timezone.utc)
        stage.output = {
            "group_size": group_size,
            "num_decisions": len(decisions),
            "decisions_summary": _summarize_decisions(decisions),
        }
        await db_session.commit()

        logger.info(
            "Condition (group_size=%d) complete: %d decisions for simulation %s",
            group_size,
            len(decisions),
            simulation_id,
        )
        return decisions

    except Exception as e:
        stage.status = SimulationStatus.FAILED
        stage.error = str(e)
        stage.completed_at = datetime.now(timezone.utc)
        await db_session.commit()
        raise


async def _run_witness_decision(
    semaphore: asyncio.Semaphore,
    witness: dict,
    scenario_text: str,
    num_other_witnesses: int,
    simulation_id: str,
    model_id: str | None,
    db_session: AsyncSession,
) -> dict:
    """Run a single witness agent and return the parsed decision."""
    async with semaphore:
        system_prompt = WITNESS_SYSTEM_PROMPT_TEMPLATE.format(
            name=witness.get("name", "Witness"),
            age=witness.get("age", "unknown"),
            gender=witness.get("gender", "unknown"),
            occupation=witness.get("occupation", "unknown"),
            background_description=witness.get("background_description", ""),
            living_situation=witness.get("living_situation", "lives alone"),
            years_in_neighbourhood=witness.get("years_in_neighbourhood", 0),
            proximity_score=witness.get("proximity_score", 5),
            scenario_text=scenario_text,
            num_other_witnesses=num_other_witnesses,
        )

        agent = create_agent(
            system_prompt=system_prompt,
            model_id=model_id,
            name=f"witness_{witness.get('name', 'unknown')}",
        )
        input_text = (
            f"You witness this event. There are {num_other_witnesses} other witnesses. "
            f"What do you do?"
        )
        result = agent(input_text)
        output_text = (
            str(result.message.get("content", [{}])[0].get("text", ""))
            if result.message
            else str(result)
        )

        # Update agent record
        await _update_agent_record(
            witness, system_prompt, input_text, output_text,
            simulation_id, model_id, db_session,
        )

        parsed = _parse_json_response(output_text)

        return {
            "name": witness.get("name"),
            "age": witness.get("age"),
            "gender": witness.get("gender"),
            "occupation": witness.get("occupation"),
            "living_situation": witness.get("living_situation"),
            "years_in_neighbourhood": witness.get("years_in_neighbourhood"),
            "background_description": witness.get("background_description"),
            "proximity_score": witness.get("proximity_score"),
            "agent_record_id": witness.get("agent_record_id"),
            "decision": parsed.get("decision", "unknown"),
            "reasoning": parsed.get("reasoning", ""),
            "confidence": parsed.get("confidence", 5),
            "time_to_decide_seconds": parsed.get("time_to_decide_seconds", 60),
        }


async def _run_follow_up(
    semaphore: asyncio.Semaphore,
    decision: dict,
    scenario_text: str,
    num_other_witnesses: int,
    simulation_id: str,
    model_id: str | None,
    db_session: AsyncSession,
) -> None:
    """Run follow-up prompt for an observe_and_wait agent. Mutates decision dict in place."""
    async with semaphore:
        # Rebuild the witness system prompt so the agent has full context
        witness_context = WITNESS_SYSTEM_PROMPT_TEMPLATE.format(
            name=decision.get("name", "Witness"),
            age=decision.get("age", "unknown"),
            gender=decision.get("gender", "unknown"),
            occupation=decision.get("occupation", "unknown"),
            background_description=decision.get("background_description", ""),
            living_situation=decision.get("living_situation", "lives alone"),
            years_in_neighbourhood=decision.get("years_in_neighbourhood", 0),
            proximity_score=decision.get("proximity_score", 5),
            scenario_text=scenario_text,
            num_other_witnesses=num_other_witnesses,
        )

        agent = create_agent(
            system_prompt=witness_context,
            model_id=model_id,
            name=f"witness_{decision.get('name', 'unknown')}_followup",
        )
        input_text = FOLLOW_UP_PROMPT_TEMPLATE
        result = agent(input_text)
        output_text = (
            str(result.message.get("content", [{}])[0].get("text", ""))
            if result.message
            else str(result)
        )

        parsed = _parse_json_response(output_text)

        # Store original decision before overwriting
        decision["original_decision"] = decision["decision"]
        decision["original_reasoning"] = decision["reasoning"]
        decision["decision"] = parsed.get("decision", "observe_and_wait")
        decision["reasoning"] = parsed.get("reasoning", decision["reasoning"])
        decision["confidence"] = parsed.get("confidence", decision["confidence"])
        decision["time_to_decide_seconds"] = parsed.get(
            "time_to_decide_seconds", decision["time_to_decide_seconds"]
        )
        decision["had_follow_up"] = True


async def _update_agent_record(
    persona: dict,
    system_prompt: str,
    input_text: str,
    output_text: str,
    simulation_id: str,
    model_id: str | None,
    db_session: AsyncSession,
) -> None:
    """Update the existing agent record with the latest interaction."""
    from sqlalchemy import select

    agent_record_id = persona.get("agent_record_id")
    if not agent_record_id:
        return

    stmt = select(AgentRecord).where(AgentRecord.id == agent_record_id)
    result = await db_session.execute(stmt)
    record = result.scalar_one_or_none()

    if record:
        record.system_prompt = system_prompt
        record.input_text = input_text
        record.output_text = output_text
        record.model_id = model_id or settings.DEFAULT_MODEL_ID
        await db_session.flush()


def _summarize_decisions(decisions: list[dict]) -> dict:
    """Create a summary count of decision types."""
    counts: dict[str, int] = {}
    for d in decisions:
        decision = d.get("decision", "unknown")
        counts[decision] = counts.get(decision, 0) + 1
    return counts


def _parse_json_response(output_text: str) -> dict:
    """Extract a JSON object from agent output."""
    try:
        parsed = json.loads(output_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", output_text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    start = output_text.find("{")
    end = output_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(output_text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse JSON from witness output: %s", output_text[:200])
    return {
        "decision": "unknown",
        "reasoning": output_text[:200],
        "confidence": 1,
        "time_to_decide_seconds": 999,
    }
```

**Step 2: Commit**

```bash
git add app/engine/game_theory/bystander/scenario_runner.py
git commit -m "feat(bystander): add scenario runner for parallel witness decisions with follow-up phase"
```

---

### Task 4: Create analysis.py — Synthesis agent

**Files:**
- Create: `app/engine/game_theory/bystander/analysis.py`

**Step 1: Create the analysis module**

```python
"""Analysis module for the Bystander Effect simulation."""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.factory import create_agent
from app.engine.game_theory.bystander.prompts import ANALYSIS_PROMPT
from app.models.agent_record import AgentRecord
from app.models.simulation import SimulationStage, SimulationStatus

logger = logging.getLogger(__name__)


async def analyze_bystander_results(
    all_condition_results: dict[int, list[dict]],
    simulation_id: str,
    db_session: AsyncSession,
    model_id: str | None = None,
    total_personas: int = 0,
) -> str:
    """Analyze all condition results and produce a comparative report.

    Args:
        all_condition_results: Dict mapping group_size -> list of decision dicts.
        simulation_id: Simulation ID.
        db_session: Async DB session.
        model_id: Bedrock model ID override.
        total_personas: Total personas generated (for agent_index).

    Returns:
        The analysis summary text.
    """
    stage = SimulationStage(
        simulation_id=simulation_id,
        stage_name="analysis",
        stage_order=99,
        status=SimulationStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(stage)
    await db_session.commit()

    try:
        decision_data = _format_decisions_for_analysis(all_condition_results)
        group_sizes = sorted(all_condition_results.keys())

        system_prompt = ANALYSIS_PROMPT.format(
            num_conditions=len(group_sizes),
            group_sizes=", ".join(str(s) for s in group_sizes),
            decision_data=decision_data,
        )

        agent = create_agent(
            system_prompt=system_prompt,
            model_id=model_id,
            name="bystander_analyst",
        )
        input_text = (
            "Analyze the bystander effect data across all conditions and produce "
            "a comprehensive comparative report with intervention rates, demographic "
            "correlations, and comparison to Darley & Latané's findings."
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
            agent_index=total_personas + 1,
            agent_name="bystander_analyst",
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


def _format_decisions_for_analysis(
    all_condition_results: dict[int, list[dict]],
) -> str:
    """Format all decisions grouped by condition for the analysis prompt."""
    lines = []

    for group_size in sorted(all_condition_results.keys()):
        decisions = all_condition_results[group_size]
        lines.append(f"\n## Condition: Group Size = {group_size}")
        lines.append(f"({len(decisions)} witnesses)\n")

        for d in decisions:
            lines.append(
                f"- **{d.get('name', '?')}** (age {d.get('age', '?')}, "
                f"{d.get('gender', '?')}, {d.get('occupation', '?')})"
            )
            lines.append(f"  Living situation: {d.get('living_situation', '?')}")
            lines.append(
                f"  Years in neighbourhood: {d.get('years_in_neighbourhood', '?')}, "
                f"Proximity: {d.get('proximity_score', '?')}/10"
            )
            lines.append(f"  Decision: **{d.get('decision', '?')}**")
            lines.append(f"  Reasoning: {d.get('reasoning', '?')}")
            lines.append(
                f"  Confidence: {d.get('confidence', '?')}/10, "
                f"Time to decide: {d.get('time_to_decide_seconds', '?')}s"
            )
            if d.get("had_follow_up"):
                lines.append(
                    f"  [FOLLOW-UP] Original decision: {d.get('original_decision', '?')} "
                    f"-> Changed to: {d.get('decision', '?')}"
                )
                lines.append(
                    f"  Original reasoning: {d.get('original_reasoning', '?')}"
                )
            lines.append("")

    return "\n".join(lines)
```

**Step 2: Commit**

```bash
git add app/engine/game_theory/bystander/analysis.py
git commit -m "feat(bystander): add analysis module for cross-condition bystander effect report"
```

---

### Task 5: Update simulation.py — Wire everything together

**Files:**
- Modify: `app/engine/game_theory/bystander/simulation.py` (replace entire file)

**Step 1: Update the simulation orchestrator**

Replace the existing stub with the full implementation:

```python
"""Bystander Effect simulation orchestrator."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.engine.game_theory.base_game import BaseGameSimulation
from app.engine.game_theory.bystander.analysis import analyze_bystander_results
from app.engine.game_theory.bystander.identity_generator import (
    generate_bystander_identities,
)
from app.engine.game_theory.bystander.scenario_runner import run_condition
from app.engine.registry import SimulationRegistry

logger = logging.getLogger(__name__)

DEFAULT_GROUP_SIZES = [1, 5, 15]


@SimulationRegistry.register("bystander_effect")
class BystanderEffectSimulation(BaseGameSimulation):
    """Bystander Effect: tests diffusion of responsibility across group sizes."""

    def validate_config(self, config: dict) -> dict:
        group_sizes = config.get("group_sizes", DEFAULT_GROUP_SIZES)
        if not isinstance(group_sizes, list) or not group_sizes:
            raise ValueError("config.group_sizes must be a non-empty list of integers")
        for size in group_sizes:
            if not isinstance(size, int) or size < 1 or size > 50:
                raise ValueError(
                    f"Each group size must be an integer between 1 and 50, got {size}"
                )

        scenario_type = config.get("scenario_type", "emergency")
        valid_scenarios = ["emergency", "theft", "harassment", "medical"]
        if scenario_type not in valid_scenarios:
            raise ValueError(
                f"config.scenario_type must be one of {valid_scenarios}"
            )

        include_second = config.get("include_second_decision_phase", True)
        max_concurrent = config.get("max_concurrent", settings.MAX_CONCURRENT_AGENTS)

        return {
            "group_sizes": sorted(group_sizes),
            "scenario_type": scenario_type,
            "include_second_decision_phase": bool(include_second),
            "max_concurrent": max_concurrent,
            "model_id": config.get("model_id", settings.DEFAULT_MODEL_ID),
        }

    def get_num_agents(self, config: dict) -> int:
        group_sizes = config.get("group_sizes", DEFAULT_GROUP_SIZES)
        return max(group_sizes) if group_sizes else 15

    async def run(
        self, simulation_id: str, config: dict, db_session: AsyncSession
    ) -> str:
        model_id = config.get("model_id")
        max_concurrent = config.get("max_concurrent")
        group_sizes = config["group_sizes"]
        scenario_type = config["scenario_type"]
        include_second = config["include_second_decision_phase"]
        num_personas = max(group_sizes)

        # Stage 1: Generate identities
        logger.info(
            "Stage 1: Generating %d bystander identities for simulation %s",
            num_personas,
            simulation_id,
        )
        personas = await generate_bystander_identities(
            num_personas, simulation_id, db_session, model_id
        )

        # Stage 2: Run each group-size condition
        all_condition_results: dict[int, list[dict]] = {}
        for i, group_size in enumerate(group_sizes):
            logger.info(
                "Stage 2.%d: Running condition (group_size=%d) for simulation %s",
                i + 1,
                group_size,
                simulation_id,
            )
            decisions = await run_condition(
                group_size=group_size,
                personas=personas,
                scenario_type=scenario_type,
                include_second_decision_phase=include_second,
                simulation_id=simulation_id,
                db_session=db_session,
                model_id=model_id,
                max_concurrent=max_concurrent,
                stage_order=i + 2,
            )
            all_condition_results[group_size] = decisions

        # Stage 3: Analyze results
        logger.info(
            "Stage 3: Analyzing results for simulation %s", simulation_id
        )
        summary = await analyze_bystander_results(
            all_condition_results,
            simulation_id,
            db_session,
            model_id,
            total_personas=num_personas,
        )

        return summary

    def describe(self) -> dict:
        return {
            "name": "Bystander Effect",
            "description": (
                "Simulates the bystander effect — tests how group size affects "
                "individual willingness to intervene in emergencies. Runs the same "
                "scenario across multiple group-size conditions and compares "
                "intervention rates to Darley & Latané's findings."
            ),
            "config_schema": {
                "group_sizes": {
                    "type": "array",
                    "default": [1, 5, 15],
                    "description": "List of group sizes to test as conditions",
                },
                "scenario_type": {
                    "type": "string",
                    "default": "emergency",
                    "enum": ["emergency", "theft", "harassment", "medical"],
                    "description": "Type of emergency scenario",
                },
                "include_second_decision_phase": {
                    "type": "boolean",
                    "default": True,
                    "description": "Follow up with observe_and_wait agents after 2 min",
                },
                "max_concurrent": {
                    "type": "integer",
                    "default": settings.MAX_CONCURRENT_AGENTS,
                    "description": "Max concurrent agent calls",
                },
                "model_id": {
                    "type": "string",
                    "default": settings.DEFAULT_MODEL_ID,
                    "description": "Bedrock model ID",
                },
            },
        }
```

**Step 2: Commit**

```bash
git add app/engine/game_theory/bystander/simulation.py
git commit -m "feat(bystander): implement full bystander effect simulation orchestrator"
```

---

### Task 6: Update frontend — Add bystander-specific result rendering

**Files:**
- Modify: `static/index.html`

**Step 1: Add bystander result renderer**

In `static/index.html`, find the `renderResults` function (around line 1214) and add a bystander branch before the default fallback. Also find the simulation launch form area and add the bystander config UI.

In `renderResults(sim)`, add after the `stanford_prison` check:

```javascript
if (sim.simulation_type === 'bystander_effect') {
    return await renderBystanderResults(sim);
}
```

Then add the `renderBystanderResults` function after `renderPrisonResults`:

```javascript
async function renderBystanderResults(sim) {
    let html = '';

    // Analysis report
    if (sim.summary) {
        html += `
            <div class="section-title">Bystander Effect Analysis</div>
            <div class="report-panel">
                <div class="report-content">${simpleMarkdown(sim.summary)}</div>
            </div>`;
    }

    // Witness agents grouped by condition
    try {
        const agents = await api('/simulations/' + sim.id + '/agents');
        const witnesses = agents.filter(a =>
            a.agent_name !== 'bystander_identity_generator' &&
            a.agent_name !== 'bystander_analyst'
        );

        if (witnesses.length > 0) {
            html += `
                <div class="section-title">Witnesses (${witnesses.length})</div>
                <div class="agent-cards">
                    ${witnesses.map(agent => renderAgentCard(agent)).join('')}
                </div>`;
        }
    } catch {}

    return html;
}
```

Also locate the simulation type selector/form and ensure `bystander_effect` is listed. Look for where `stanford_prison` and `policy` are defined as options and add `bystander_effect` alongside them with config fields for `group_sizes`, `scenario_type`, and `include_second_decision_phase`.

**Step 2: Commit**

```bash
git add static/index.html
git commit -m "feat(bystander): add frontend result rendering for bystander effect simulation"
```

---

### Task 7: Smoke test — Run the simulation end-to-end

**Step 1: Start the server**

```bash
cd C:/Users/Rex/social-simulation-engine
uvicorn app.main:app --reload
```

**Step 2: Trigger a bystander simulation via API**

```bash
curl -X POST http://localhost:8000/api/v1/simulations \
  -H "Content-Type: application/json" \
  -d '{
    "simulation_type": "bystander_effect",
    "config": {
      "group_sizes": [1, 5, 15],
      "scenario_type": "emergency",
      "include_second_decision_phase": true
    }
  }'
```

**Step 3: Monitor progress**

Poll the simulation status:

```bash
curl http://localhost:8000/api/v1/simulations/{simulation_id}
```

Expected: status progresses `pending` → `running` → `completed`. Stages: `identity_generation`, `scenario_condition_1`, `scenario_condition_5`, `scenario_condition_15`, `analysis`.

**Step 4: Verify results**

Check the completed simulation has:
- A summary with intervention rates per group size
- Agent records for all witnesses + generator + analyst
- Stage records for all 5 stages (all COMPLETED status)

**Step 5: Open the frontend**

Navigate to `http://localhost:8000` and verify the bystander simulation appears in the history and renders properly with the analysis report and witness cards.
