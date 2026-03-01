import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.engine.base import BaseSimulation
from app.engine.policy.distribution_agent import generate_distribution
from app.engine.policy.respondent_agent import run_respondent_swarm
from app.engine.policy.synthesis_agent import synthesize_responses
from app.engine.registry import SimulationRegistry

logger = logging.getLogger(__name__)


@SimulationRegistry.register("policy")
class PolicySimulation(BaseSimulation):
    """3-stage policy simulation: distribution → respondent swarm → synthesis."""

    def validate_config(self, config: dict) -> dict:
        if not config.get("policy_text"):
            raise ValueError("config.policy_text is required")

        sample_size = config.get("sample_size", 10)
        if not isinstance(sample_size, int) or sample_size < 1 or sample_size > 100:
            raise ValueError("config.sample_size must be an integer between 1 and 100")

        return {
            "policy_text": config["policy_text"],
            "sample_size": sample_size,
            "model_id": config.get("model_id", settings.DEFAULT_MODEL_ID),
            "max_concurrent": config.get("max_concurrent", settings.MAX_CONCURRENT_AGENTS),
        }

    async def run(self, simulation_id: str, config: dict, db_session: AsyncSession) -> str:
        model_id = config.get("model_id")
        policy_text = config["policy_text"]

        # Stage 1: Generate persona distribution
        logger.info("Stage 1: Generating distribution for simulation %s", simulation_id)
        personas = await generate_distribution(config, simulation_id, db_session, model_id)

        # Stage 2: Run respondent swarm
        logger.info("Stage 2: Running respondent swarm for simulation %s", simulation_id)
        responses = await run_respondent_swarm(
            personas=personas,
            policy_text=policy_text,
            simulation_id=simulation_id,
            db_session=db_session,
            model_id=model_id,
            max_concurrent=config.get("max_concurrent"),
        )

        # Stage 3: Synthesize responses
        logger.info("Stage 3: Synthesizing responses for simulation %s", simulation_id)
        summary = await synthesize_responses(responses, simulation_id, db_session, model_id)

        return summary

    def describe(self) -> dict:
        return {
            "name": "Policy Simulation",
            "description": (
                "Simulates public response to a policy proposal. "
                "Generates diverse personas, collects their reactions, "
                "and synthesizes findings into an analytical report."
            ),
            "config_schema": {
                "policy_text": {"type": "string", "required": True, "description": "The policy text to evaluate"},
                "sample_size": {"type": "integer", "default": 10, "description": "Number of personas (1-100)"},
                "model_id": {"type": "string", "default": settings.DEFAULT_MODEL_ID, "description": "Bedrock model ID override"},
                "max_concurrent": {"type": "integer", "default": settings.MAX_CONCURRENT_AGENTS, "description": "Max concurrent agent calls"},
            },
        }
