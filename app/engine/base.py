from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession


class BaseSimulation(ABC):
    simulation_type: str = ""

    @abstractmethod
    def validate_config(self, config: dict) -> dict:
        """Validate and return normalized config. Raise ValueError on invalid config."""

    @abstractmethod
    async def run(self, simulation_id: str, config: dict, db_session: AsyncSession) -> str:
        """Execute the simulation. Returns a summary string."""

    @abstractmethod
    def describe(self) -> dict:
        """Return a description of this simulation type including its config schema."""
