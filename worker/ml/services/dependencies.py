# worker/ml/services/dependencies.py
import logging
from typing import Any, Callable, Dict, Type

from sqlalchemy.orm import Session

# --- Import Concrete Implementations ---
from services.artifact_service import ArtifactService

# --- Import Interfaces ---
from services.interfaces import IArtifactService  # Local interface
from shared.db_session import SyncSessionLocal  # Assuming sync for worker
from shared.repositories import (
    DatasetRepository,
    HPSearchJobRepository,
    InferenceJobRepository,
    MLFeatureRepository,
    ModelRepository,
    TrainingJobRepository,
    XaiResultRepository,
)
from shared.services import JobStatusUpdater
from shared.services.interfaces import IJobStatusUpdater  # Shared interface

logger = logging.getLogger(__name__)


class DependencyProvider:
    """
    Provides instances of services and repositories needed by ML worker handlers.
    Injects concrete implementations, uses interfaces as cache keys where available.
    """

    def __init__(self, session_factory: Callable[[], Session] = SyncSessionLocal):
        self.session_factory = session_factory
        # Use Interface type as cache key where available, otherwise concrete class
        self._cache: Dict[Type, Any] = {}
        logger.debug("ML Worker DependencyProvider initialized.")

    def _get_or_create(
        self, lookup_key_type: Type, concrete_class: Type, *args, **kwargs
    ) -> Any:
        """
        Helper to get from cache or create and cache.
        Uses lookup_key_type for the cache dictionary key.
        """
        if lookup_key_type not in self._cache:
            logger.debug(
                f"Creating instance of {concrete_class.__name__} (for key {lookup_key_type.__name__})"
            )
            try:
                # Pass session_factory to repositories/updaters that need it
                if issubclass(
                    concrete_class,
                    (
                        ModelRepository,
                        XaiResultRepository,
                        MLFeatureRepository,
                        JobStatusUpdater,
                        DatasetRepository,
                        InferenceJobRepository,
                        TrainingJobRepository,
                        HPSearchJobRepository,
                    ),
                ):
                    instance = concrete_class(self.session_factory, *args, **kwargs)
                else:
                    instance = concrete_class(
                        *args, **kwargs
                    )  # For services like ArtifactService
                self._cache[lookup_key_type] = instance
            except Exception as e:
                logger.error(
                    f"Failed to instantiate {concrete_class.__name__}: {e}",
                    exc_info=True,
                )
                raise RuntimeError(
                    f"Failed to create dependency: {concrete_class.__name__}"
                ) from e
        return self._cache[lookup_key_type]

    # --- Getter Methods---

    def get_artifact_service(self) -> ArtifactService:
        return self._get_or_create(IArtifactService, ArtifactService)

    def get_ml_feature_repository(self) -> MLFeatureRepository:
        return self._get_or_create(MLFeatureRepository, MLFeatureRepository)

    def get_model_repository(self) -> ModelRepository:
        return self._get_or_create(ModelRepository, ModelRepository)

    def get_xai_result_repository(self) -> XaiResultRepository:
        return self._get_or_create(XaiResultRepository, XaiResultRepository)

    def get_job_status_updater(self) -> JobStatusUpdater:
        return self._get_or_create(IJobStatusUpdater, JobStatusUpdater)

    def get_dataset_repository(self) -> DatasetRepository:
        return self._get_or_create(DatasetRepository, DatasetRepository)

    def get_inference_job_repository(self) -> InferenceJobRepository:
        return self._get_or_create(InferenceJobRepository, InferenceJobRepository)

    def get_training_job_repository(self) -> TrainingJobRepository:
        return self._get_or_create(TrainingJobRepository, TrainingJobRepository)

    def get_hp_search_job_repository(self) -> HPSearchJobRepository:
        return self._get_or_create(HPSearchJobRepository, HPSearchJobRepository)
