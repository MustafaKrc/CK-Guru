# worker/dataset/services/cleaning_service_base.py
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List # Add List
import pandas as pd

logger = logging.getLogger(__name__)

class BaseCleaningService(ABC):
    """Abstract base class for different dataset cleaning strategies."""

    def __init__(self, cleaning_rules_config: List[Dict], dataset_config: Dict):
        self.cleaning_rules_config = cleaning_rules_config
        self.dataset_config = dataset_config
        logger.info(f"Initializing Cleaning Service: {self.__class__.__name__}")

    @abstractmethod
    def apply_batch_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        pass

    @abstractmethod
    def apply_global_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        pass