from abc import ABC, abstractmethod
from typing import Dict, Optional, Type, Union

from shared.schemas.enums import JobStatusEnum
from shared.db.models import TrainingJob, HyperparameterSearchJob, InferenceJob


# Type alias for job models
JobModel = Union[TrainingJob, HyperparameterSearchJob, InferenceJob]



class IJobStatusUpdater(ABC):
    """Interface for updating job statuses in the database."""

    @abstractmethod
    def update_job_start(self, job_id: int, job_type: Union[str, Type[JobModel]], task_id: str) -> bool:
        """Updates job status to RUNNING, records task ID and start time."""
        pass

    @abstractmethod
    def update_job_progress(self, job_id: int, job_type: Union[str, Type[JobModel]], message: str) -> bool:
        """Updates only the status message of a job."""
        pass

    @abstractmethod
    def update_job_completion(
        self,
        job_id: int,
        job_type: Union[str, Type[JobModel]],
        status: JobStatusEnum,
        message: str,
        results: Optional[Dict] = None
    ) -> bool:
        """Updates final job status, message, completion time, and potentially results."""
        pass

    # Add other methods if needed, e.g., for specific fields like feature path
    @abstractmethod
    def update_inference_feature_path(self, job_id: int, feature_path: str) -> bool:
        """Updates the feature artifact path for an InferenceJob."""
        pass