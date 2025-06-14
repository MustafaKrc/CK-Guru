# shared/services/interfaces/i_job_status_updater.py
from abc import ABC, abstractmethod
from typing import Dict, Optional, Type, Union

from shared.db.models import (
    Dataset,
    HyperparameterSearchJob,  # Add Dataset
    InferenceJob,
    TrainingJob,
)
from shared.schemas.enums import (
    DatasetStatusEnum,  # Add DatasetStatusEnum
    JobStatusEnum,
)

# Type alias for job models
JobModel = Union[
    TrainingJob, HyperparameterSearchJob, InferenceJob, Dataset
]  # Add Dataset


class IJobStatusUpdater(ABC):
    """Interface for updating job/dataset statuses in the database."""

    # --- Generic Methods ---
    @abstractmethod
    def update_job_start(
        self, job_id: int, job_type: Union[str, Type[JobModel]], task_id: str
    ) -> bool:
        """Updates job/dataset status to RUNNING/GENERATING, records task ID and start time."""
        pass

    @abstractmethod
    def update_job_progress(
        self, job_id: int, job_type: Union[str, Type[JobModel]], message: str
    ) -> bool:
        """Updates only the status message of a job/dataset."""
        pass

    @abstractmethod
    def update_job_completion(
        self,
        job_id: int,
        job_type: Union[str, Type[JobModel]],
        status: Union[JobStatusEnum, DatasetStatusEnum],  # Allow either enum
        message: str,
        results: Optional[Dict] = None,
    ) -> bool:
        """Updates final job/dataset status, message, completion time, and potentially results."""
        pass

    # --- Specific Methods ---
    # (Keep inference-specific method if still used elsewhere)
    @abstractmethod
    def update_inference_feature_path(self, job_id: int, feature_path: str) -> bool:
        """Updates the feature artifact path for an InferenceJob."""
        pass

    # Add Dataset-specific convenience methods
    @abstractmethod
    def update_dataset_start(self, dataset_id: int, task_id: str) -> bool:
        """Convenience method to set Dataset status to GENERATING."""
        pass

    @abstractmethod
    def update_dataset_progress(self, dataset_id: int, message: str) -> bool:
        """Convenience method to update Dataset status message."""
        pass

    @abstractmethod
    def update_dataset_completion(
        self,
        dataset_id: int,
        status: DatasetStatusEnum,
        message: str,
        storage_path: Optional[str] = None,
        background_data_path: Optional[str] = None,
        num_rows: Optional[int] = None,
    ) -> bool:
        """Convenience method to update final Dataset status and paths."""
        pass
