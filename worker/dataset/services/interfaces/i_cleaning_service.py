# worker/dataset/services/interfaces/i_cleaning_service.py
from abc import ABC, abstractmethod
import pandas as pd

class ICleaningService(ABC):
    """Interface for applying cleaning rules to a dataset."""

    @abstractmethod
    def apply_batch_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies batch-safe cleaning rules to a DataFrame batch."""
        pass

    @abstractmethod
    def apply_global_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies global (non-batch-safe) cleaning rules to the entire DataFrame."""
        pass