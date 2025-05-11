# worker/dataset/services/interfaces/i_data_loader.py
from abc import ABC, abstractmethod
from typing import Generator

import pandas as pd


class IDataLoader(ABC):
    """Interface for fetching and streaming data batches."""

    @abstractmethod
    def estimate_total_rows(self) -> int:
        """Estimates the total number of rows the underlying query will return."""
        pass

    @abstractmethod
    def stream_batches(self, batch_size: int) -> Generator[pd.DataFrame, None, None]:
        """Executes the query and yields data in Pandas DataFrame batches."""
        pass
