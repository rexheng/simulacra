from abc import abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.base import BaseSimulation
from app.engine.game_theory.identity_generator import generate_identities


class BaseGameSimulation(BaseSimulation):
    """Base class for game theory simulations with shared identity generation."""

    @abstractmethod
    def get_num_agents(self, config: dict) -> int:
        """Return the number of agents needed for this game."""

    async def generate_game_identities(
        self,
        config: dict,
        simulation_id: str,
        db_session: AsyncSession,
        model_id: str | None = None,
    ) -> list[dict]:
        """Generate identities for all agents in the game."""
        num_agents = self.get_num_agents(config)
        return await generate_identities(num_agents, config, simulation_id, db_session, model_id)
