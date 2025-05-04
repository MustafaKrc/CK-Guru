# worker/dataset/services/interfaces/i_output_writer.py
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd

class IOutputWriter(ABC):
    """Interface for writing the final dataset."""

    @abstractmethod
    def clear_existing(self, s3_uri: str):
        """Deletes the object at the given S3 URI if it exists."""
        pass

    @abstractmethod
    def write_parquet(self, df: pd.DataFrame, s3_uri: str, target_column_name: Optional[str] = None):
        """Writes the DataFrame to a Parquet file in S3, optionally adding metadata."""
        pass