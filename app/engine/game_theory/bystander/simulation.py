from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.engine.game_theory.base_game import BaseGameSimulation
from app.engine.registry import SimulationRegistry


@SimulationRegistry.register("bystander_effect")
class BystanderEffectSimulation(BaseGameSimulation):
    """Bystander Effect: simulates group inaction in emergency scenarios."""

    def validate_config(self, config: dict) -> dict:
        num_bystanders = config.get("num_bystanders", 8)
        if not isinstance(num_bystanders, int) or num_bystanders < 1 or num_bystanders > 50:
            raise ValueError("config.num_bystanders must be an integer between 1 and 50")

        scenario_type = config.get("scenario_type", "emergency")
        valid_scenarios = ["emergency", "theft", "harassment", "medical"]
        if scenario_type not in valid_scenarios:
            raise ValueError(f"config.scenario_type must be one of {valid_scenarios}")

        num_rounds = config.get("num_rounds", 3)
        if not isinstance(num_rounds, int) or num_rounds < 1:
            raise ValueError("config.num_rounds must be a positive integer")

        return {
            "num_bystanders": num_bystanders,
            "scenario_type": scenario_type,
            "num_rounds": num_rounds,
            "model_id": config.get("model_id", settings.DEFAULT_MODEL_ID),
        }

    def get_num_agents(self, config: dict) -> int:
        return config.get("num_bystanders", 8)

    async def run(self, simulation_id: str, config: dict, db_session: AsyncSession) -> str:
        raise NotImplementedError("Bystander Effect simulation not yet implemented")

    def describe(self) -> dict:
        return {
            "name": "Bystander Effect",
            "description": (
                "Simulates the bystander effect — how group size and dynamics "
                "influence individual willingness to intervene in emergencies."
            ),
            "config_schema": {
                "num_bystanders": {"type": "integer", "default": 8, "description": "Number of bystander agents"},
                "scenario_type": {
                    "type": "string",
                    "default": "emergency",
                    "enum": ["emergency", "theft", "harassment", "medical"],
                    "description": "Type of scenario",
                },
                "num_rounds": {"type": "integer", "default": 3, "description": "Number of observation rounds"},
                "model_id": {"type": "string", "default": settings.DEFAULT_MODEL_ID, "description": "Bedrock model ID"},
            },
            "status": "stub",
        }
