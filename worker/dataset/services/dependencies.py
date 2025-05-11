# worker/dataset/services/dependencies.py
import logging
from typing import Any, Callable, Dict, List, Type

from sqlalchemy.orm import Session

# --- Config ---
from shared.core.config import settings
from shared.services import JobStatusUpdater  # Shared concrete implementation
from shared.services.interfaces import IJobStatusUpdater  # Shared interface
from shared.utils.pipeline_logging import StepLogger

# Import Context
from .context import DatasetContext

# --- Concrete Implementations & Factories ---
from .data_loader import DataLoader
from .factories import RepositoryFactory, get_cleaning_service

# --- Interfaces ---
from .interfaces import (
    ICleaningService,
    IDataLoader,
    IDatasetGeneratorStep,
    IOutputWriter,
    IRepositoryFactory,
)
from .output_writer import OutputWriter

# Import all step classes
from .steps import *

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class StepRegistry:
    """Instantiates and provides step instances."""

    def __init__(self):
        self._instances: Dict[Type[IDatasetGeneratorStep], IDatasetGeneratorStep] = {}
        # List all step classes known to this worker
        self._step_classes: List[Type[IDatasetGeneratorStep]] = [
            LoadConfigurationStep,
            StreamAndProcessBatchesStep,
            ProcessGloballyStep,
            SelectFinalColumnsStep,
            WriteOutputStep,
            # Include sub-steps if they needed direct instantiation/injection,
            # but currently they are instantiated within their orchestrator steps
        ]
        logger.debug(
            f"StepRegistry initialized with {len(self._step_classes)} known step types."
        )

    def get_step(
        self, step_class: Type[IDatasetGeneratorStep]
    ) -> IDatasetGeneratorStep:
        """Gets or creates an instance of the requested step."""
        if step_class not in self._instances:
            if step_class not in self._step_classes:
                raise ValueError(f"Unknown step class requested: {step_class.__name__}")
            try:
                self._instances[step_class] = step_class()  # Instantiate
                logger.debug(f"Instantiated step: {step_class.__name__}")
            except Exception as e:
                logger.error(
                    f"Failed to instantiate step {step_class.__name__}: {e}",
                    exc_info=True,
                )
                raise
        return self._instances[step_class]


class DependencyProvider:
    """Provides various dependencies needed by pipeline steps."""

    def __init__(self, session_factory: Callable[[], Session]):
        self.session_factory = session_factory

        # --- Cache for Singleton-like services within the provider's scope ---
        self._cached_services: Dict[Type, Any] = {}

        # --- Pre-instantiate repositories via factory ---
        # Store the factory itself
        self._repo_factory: IRepositoryFactory = RepositoryFactory(self.session_factory)
        self._cached_services[IRepositoryFactory] = self._repo_factory

        # --- Pre-instantiate other shared/common services ---
        # Adapt JobStatusUpdater for Dataset model
        self._job_status_updater = JobStatusUpdater(self.session_factory)
        self._cached_services[IJobStatusUpdater] = self._job_status_updater

        # --- Rule Registry (Loaded at worker startup) ---
        # Access the globally populated registry from the cleaning rules base
        from .cleaning_rules.base import WORKER_RULE_REGISTRY

        self.rule_registry = WORKER_RULE_REGISTRY
        if not self.rule_registry:
            logger.warning(
                "DependencyProvider initialized, but WORKER_RULE_REGISTRY is empty. Cleaning service might fail."
            )

    # --- Factory Method for IDataLoader (Context-Dependent) ---
    def _get_data_loader(self, context: DatasetContext) -> IDataLoader:
        """Creates a DataLoader instance."""
        if not context.repository_db:
            raise ValueError("Repository DB object missing for DataLoader.")
        # Pass session_factory, not a session instance
        return DataLoader(
            session_factory=self.session_factory,
            repository_id=context.repository_db.id,
            bot_patterns=context.bot_patterns_db,
        )

    # --- Factory Method for IOutputWriter ---
    def _get_output_writer(self) -> IOutputWriter:
        """Gets or creates the OutputWriter instance."""
        if IOutputWriter not in self._cached_services:
            self._cached_services[IOutputWriter] = OutputWriter(
                settings.s3_storage_options
            )
        return self._cached_services[IOutputWriter]

    # --- Factory Method for ICleaningService (Context-Dependent) ---
    def _get_cleaning_service(self, context: DatasetContext) -> ICleaningService:
        """Gets or creates the CleaningService instance using the factory."""
        # Cleaning service depends on config, which might change per run, so don't cache heavily?
        # Or assume config is stable for the lifetime of the provider instance (per task).
        # Let's not cache it for now to be safe.
        if not context.dataset_config:
            raise ValueError("DatasetConfig missing for CleaningService.")
        if not self.rule_registry:
            raise RuntimeError(
                "Rule Registry is empty, cannot create Cleaning Service."
            )

        return get_cleaning_service(
            dataset_config=context.dataset_config.model_dump(),  # Pass config dict
            rule_registry=self.rule_registry,
        )

    # --- Getter for IJobStatusUpdater ---
    def _get_job_status_updater(self) -> IJobStatusUpdater:
        return self._cached_services[IJobStatusUpdater]

    # --- Getter for IRepositoryFactory ---
    def _get_repository_factory(self) -> IRepositoryFactory:
        return self._cached_services[IRepositoryFactory]

    def get_dependencies_for_step(
        self, step: IDatasetGeneratorStep, context: DatasetContext
    ) -> Dict[str, Any]:
        """Returns a dictionary of dependencies required by the given step."""
        deps: Dict[str, Any] = {}
        step_type = type(step)

        # --- Provide common dependencies ---
        deps["job_status_updater"] = self._get_job_status_updater()
        deps["repo_factory"] = self._get_repository_factory()  # Provide the factory

        # --- Provide step-specific dependencies ---
        if step_type == LoadConfigurationStep:
            # Already has repo_factory and job_status_updater
            pass
        elif step_type == StreamAndProcessBatchesStep:
            # This step orchestrates sub-steps and needs deps for them
            deps["cleaning_service"] = self._get_cleaning_service(context)
            deps["session_factory"] = self.session_factory  # DataLoader needs factory
            # Repos needed by sub-steps are accessed via repo_factory inside execute
        elif step_type == ProcessGloballyStep:
            # This step orchestrates sub-steps
            deps["cleaning_service"] = self._get_cleaning_service(context)
            # Repos needed by sub-steps accessed via repo_factory
        elif step_type == SelectFinalColumnsStep:
            # Doesn't seem to need external dependencies beyond context
            pass
        elif step_type == WriteOutputStep:
            deps["output_writer"] = self._get_output_writer()
            # Already has repo_factory and job_status_updater
        elif step_type == GetParentCKMetricsStep:
            # This step is run *inside* StreamAndProcessBatchesStep,
            # its dependency (`ck_repo`) is provided there via the factory.
            # No need to provide directly here unless called independently.
            pass

        # Add dependencies for other steps if they are added later

        step_logger = StepLogger(
            logger, f"Task {context.task_instance.request.id} - DependencyProvider"
        )
        step_logger.debug(
            f"Providing dependencies for step {step.__class__.__name__}: {list(deps.keys())}"
        )
        return deps
