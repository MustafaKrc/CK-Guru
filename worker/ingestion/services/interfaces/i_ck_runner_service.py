from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class ICKRunnerService(ABC):
    """Interface for running the CK metric tool."""

    @abstractmethod
    def run(self, repo_dir: Path, commit_hash: str) -> pd.DataFrame:
        """Runs CK tool and returns metrics as a DataFrame."""
        pass

