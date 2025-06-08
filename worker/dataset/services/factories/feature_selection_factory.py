# worker/dataset/services/feature_selection/factory.py
import logging
from typing import Dict, List, Type

from shared.feature_selection import (
    FeatureSelectionDefinition,
    FeatureSelectionStrategy,
)

# Import all concrete strategies
from services.feature_selection.strategies import (
    CbfsFeatureSelection,
    ModelBasedFeatureSelection,
    MrmrFeatureSelection,
)

logger = logging.getLogger(__name__)


class FeatureSelectionStrategyFactory:
    """
    Factory for creating feature selection strategy instances and providing their definitions.
    This acts as a registry for all available algorithms in this worker.
    """

    def __init__(self):
        self._strategies: Dict[str, Type[FeatureSelectionStrategy]] = {}
        self._register_strategies()

    def _register_strategies(self):
        """Register all known strategies. This is the single place to add new ones."""
        self.register_strategy(CbfsFeatureSelection)
        self.register_strategy(MrmrFeatureSelection)
        self.register_strategy(ModelBasedFeatureSelection)
        logger.info(f"Registered feature selection strategies: {list(self._strategies.keys())}")

    def register_strategy(self, strategy_class: Type[FeatureSelectionStrategy]):
        """Registers a new strategy class using its defined algorithm_name."""
        if not issubclass(strategy_class, FeatureSelectionStrategy):
            raise TypeError("Provided class is not a FeatureSelectionStrategy")
        self._strategies[strategy_class.algorithm_name] = strategy_class

    def get_strategy(self, name: str) -> FeatureSelectionStrategy:
        """Retrieves an instance of a registered strategy by name."""
        strategy_class = self._strategies.get(name)
        if not strategy_class:
            logger.error(f"Feature selection strategy '{name}' not found in factory.")
            raise ValueError(f"Feature selection strategy '{name}' not found.")
        return strategy_class()

    def get_all_definitions(self) -> List[FeatureSelectionDefinition]:
        """Returns the definitions of all registered strategies."""
        return [strategy().get_definition() for strategy in self._strategies.values()]