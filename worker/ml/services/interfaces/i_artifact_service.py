# worker/ml/services/interfaces/i_artifact_service.py
from abc import ABC, abstractmethod
from typing import Any, Optional
import pandas as pd

class IArtifactService(ABC):
    """Interface for saving and loading ML artifacts."""

    @abstractmethod
    def save_artifact(self, artifact: Any, uri: str) -> bool:
        """Saves a Python object artifact."""
        pass

    @abstractmethod
    def load_artifact(self, uri: str) -> Optional[Any]:
        """Loads a Python object artifact."""
        pass

    @abstractmethod
    def delete_artifact(self, uri: str) -> bool:
        """Deletes an artifact."""
        pass

    @abstractmethod
    def load_dataframe_artifact(self, uri: str) -> Optional[pd.DataFrame]:
        """Loads a DataFrame artifact (e.g., from Parquet)."""
        pass