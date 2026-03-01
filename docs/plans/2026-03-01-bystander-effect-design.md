# Bystander Effect Simulation Design

## Overview

Implements the Bystander Effect experiment within the social-simulation-engine. Tests the Darley & Latané hypothesis: as group size increases, individual willingness to intervene in emergencies decreases (diffusion of responsibility).

A single simulation run generates a pool of diverse personas, then runs the same emergency scenario across multiple group-size conditions (1, 5, 15) using subsets of those personas. Witnesses decide independently and in parallel, unaware of others' decisions.

## Config Schema

```python
{
    "group_sizes": [1, 5, 15],              # conditions to test
    "scenario_type": "emergency",            # emergency | theft | harassment | medical
    "include_second_decision_phase": True,   # follow-up for observe_and_wait agents
    "model_id": "...",                       # Bedrock model ID
    "max_concurrent": 5                      # concurrent agent limit
}
```

- `group_sizes`: list of integers, each a condition. The largest determines persona count.
- `scenario_type`: selects the scenario text presented to witnesses.
- `include_second_decision_phase`: if true, agents who chose `observe_and_wait` receive a time-based escalation follow-up.

## Architecture

### Stage 1: Identity Generation

A single agent generates N personas (N = max of group_sizes) with:

| Field | Type | Description |
|-------|------|-------------|
| name | str | Full name |
| age | int | Age |
| gender | str | Gender |
| occupation | str | Current job/role |
| living_situation | str | e.g., "lives alone", "lives with partner and toddler" |
| years_in_neighbourhood | int | Community tenure |
| background_description | str | 2-3 sentences: temperament, daily routine, relationship to neighbourhood |
| proximity_score | int (1-10) | 10 = directly witnessing, 1 = barely audible |

Personas are sorted by `proximity_score` descending. For each condition, the top N personas are selected (so the closest witnesses are always included across conditions).

### Stage 2: Scenario Execution (per condition)

For each group size in `group_sizes`:

1. Select top N personas by proximity_score
2. Run all N witness agents **in parallel** (via `asyncio.Semaphore`)
3. Each witness receives:
   - Their full persona details
   - The scenario text
   - Awareness of how many others are witnessing (`num_other_witnesses = N - 1`)
4. Each responds with structured JSON:

```json
{
    "decision": "intervene_directly | call_emergency_services | alert_neighbor | observe_and_wait | ignore",
    "reasoning": "Internal thought process as this person (2-3 sentences)",
    "confidence": 7,
    "time_to_decide_seconds": 30
}
```

**Second Decision Phase** (if enabled):

Agents who chose `observe_and_wait` receive a follow-up:

> "It has been 2 minutes. The screaming continues and has become more desperate. No one appears to have intervened. What do you do now?"

Same JSON response format. Their updated decision is tracked alongside the original.

### Stage 3: Analysis

A synthesis agent receives all decisions across all conditions and produces:

1. **Intervention rate per group size** — the bystander effect curve
2. **Decision type breakdown** per condition (counts of each decision type)
3. **Demographic correlations** — caregiving backgrounds, long-term residents, high-proximity witnesses
4. **Second-phase shift analysis** — how many observe_and_wait agents changed their decision
5. **Comparison to Darley & Latané** — typical: ~85% intervene alone, ~31% in groups of 5+
6. **Notable individual analyses** — personas whose decisions were surprising given their profile

## Data Flow

```
[Config] → validate_config()
    ↓
[Stage 1: identity_generation] → 15 personas (JSON array)
    ↓
[Stage 2a: scenario_condition_1]  → 1 witness  → decision
[Stage 2b: scenario_condition_5]  → 5 witnesses (parallel) → decisions
[Stage 2c: scenario_condition_15] → 15 witnesses (parallel) → decisions
    ↓ (if include_second_decision_phase)
[Follow-up] → observe_and_wait agents → updated decisions
    ↓
[Stage 3: analysis] → structured report (summary)
```

## Database Records

- **SimulationStage**: `identity_generation`, `scenario_condition_{N}` (per group size), `analysis`
- **AgentRecord**: One per persona + 1 generator + 1 analyst. Updated with latest prompt/response per condition.
- **InteractionRecord**: Not used (witnesses decide independently, no agent-to-agent interaction)

## File Structure

```
app/engine/game_theory/bystander/
├── __init__.py              (existing, no changes)
├── simulation.py            (update existing stub - orchestrator)
├── identity_generator.py    (persona generation)
├── scenario_runner.py       (runs one condition - parallel witness decisions)
├── analysis.py              (synthesis agent)
└── prompts.py               (all prompt templates)
```

## Scenario Types

### Emergency (default — Kitty Genovese inspired)
A person is being violently attacked outside an apartment building late at night. Screaming for help. The attacker flees when confronted but returns.

### Theft
Someone's car is being broken into in the parking lot. The thief is smashing windows.

### Harassment
A person is being aggressively harassed at a bus stop visible from apartments. Verbal abuse escalating to physical intimidation.

### Medical
A person has collapsed on the sidewalk, appears to be having a seizure or cardiac event.

## Key Design Decisions

1. **Single persona pool across conditions**: Controlled variable. Same people, different group sizes. Subsets selected by proximity.
2. **Independent parallel decisions**: Matches Darley & Latané methodology. No social proof or information cascade.
3. **Time-based follow-up**: Simple escalation for observe_and_wait agents. Tests whether indecision converts to action under sustained pressure.
4. **Proximity sorting for subsets**: The solo witness is always the closest observer. Ensures the most "should intervene" person is tested in every condition.
