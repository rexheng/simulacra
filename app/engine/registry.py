from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.base import BaseSimulation


class SimulationRegistry:
    _registry: dict[str, type["BaseSimulation"]] = {}

    @classmethod
    def register(cls, simulation_type: str):
        """Decorator to register a simulation class."""

        def decorator(sim_class: type["BaseSimulation"]):
            sim_class.simulation_type = simulation_type
            cls._registry[simulation_type] = sim_class
            return sim_class

        return decorator

    @classmethod
    def get(cls, simulation_type: str) -> type["BaseSimulation"] | None:
        return cls._registry.get(simulation_type)

    @classmethod
    def list_all(cls) -> dict[str, dict]:
        result = {}
        for sim_type, sim_class in cls._registry.items():
            instance = sim_class()
            result[sim_type] = instance.describe()
        return result
