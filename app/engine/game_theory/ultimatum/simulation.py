from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.engine.game_theory.base_game import BaseGameSimulation
from app.engine.registry import SimulationRegistry


@SimulationRegistry.register("ultimatum_game")
class UltimatumGameSimulation(BaseGameSimulation):
    """Ultimatum Game: one player proposes a split, the other accepts or rejects."""

    def validate_config(self, config: dict) -> dict:
        num_pairs = config.get("num_pairs", 5)
        if not isinstance(num_pairs, int) or num_pairs < 1 or num_pairs > 50:
            raise ValueError("config.num_pairs must be an integer between 1 and 50")

        total_amount = config.get("total_amount", 100.0)
        if not isinstance(total_amount, (int, float)) or total_amount <= 0:
            raise ValueError("config.total_amount must be a positive number")

        num_rounds = config.get("num_rounds", 3)
        if not isinstance(num_rounds, int) or num_rounds < 1:
            raise ValueError("config.num_rounds must be a positive integer")

        return {
            "num_pairs": num_pairs,
            "total_amount": float(total_amount),
            "num_rounds": num_rounds,
            "model_id": config.get("model_id", settings.DEFAULT_MODEL_ID),
        }

    def get_num_agents(self, config: dict) -> int:
        return config.get("num_pairs", 5) * 2

    async def run(self, simulation_id: str, config: dict, db_session: AsyncSession) -> str:
        raise NotImplementedError("Ultimatum Game simulation not yet implemented")

    def describe(self) -> dict:
        return {
            "name": "Ultimatum Game",
            "description": (
                "Classic game theory experiment where one player proposes how to split "
                "a sum of money and the other can accept or reject. Tests fairness norms."
            ),
            "config_schema": {
                "num_pairs": {"type": "integer", "default": 5, "description": "Number of proposer/responder pairs"},
                "total_amount": {"type": "number", "default": 100.0, "description": "Total amount to split"},
                "num_rounds": {"type": "integer", "default": 3, "description": "Number of rounds per pair"},
                "model_id": {"type": "string", "default": settings.DEFAULT_MODEL_ID, "description": "Bedrock model ID"},
            },
            "status": "stub",
        }
