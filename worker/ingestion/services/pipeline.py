# worker/ingestion/services/pipeline.py
import logging
from typing import List, Type

from services.dependencies import DependencyProvider, StepRegistry
from services.steps.base import IngestionContext, IngestionStep
from services.strategies import IngestionStrategy
from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class PipelineRunner:
    """Runs an ingestion pipeline defined by a strategy."""

    def __init__(
        self,
        strategy: IngestionStrategy,
        step_registry: StepRegistry,
        dependency_provider: DependencyProvider,
    ):
        self.strategy = strategy
        self.step_registry = step_registry
        self.dependency_provider = dependency_provider
        self.current_step_instance: IngestionStep | None = None
        logger.debug(
            f"PipelineRunner initialized with strategy: {type(strategy).__name__}"
        )

    def run(self, initial_context: IngestionContext) -> IngestionContext:
        """Executes the pipeline steps sequentially."""
        context = initial_context
        steps_to_run: List[Type[IngestionStep]] = self.strategy.get_steps()
        total_steps = len(steps_to_run)
        step_key = "Initialization"  # For error reporting

        try:
            for i, step_class in enumerate(steps_to_run):
                step_key = step_class.__name__  # Use class name as key for now
                self.current_step_instance = self.step_registry.get_step(step_class)

                # Log entry into the step using the step's own logger/methods if available
                logger.info(
                    f"PipelineRunner: Executing step {i+1}/{total_steps} [{self.current_step_instance.name}]..."
                )

                # Inject dependencies needed by this specific step
                # The provider pattern allows centralizing dependency logic
                dependencies = self.dependency_provider.get_dependencies_for_step(
                    self.current_step_instance, context
                )

                # Execute the step
                context = self.current_step_instance.execute(context, **dependencies)

                logger.info(
                    f"PipelineRunner: Completed step {i+1}/{total_steps} [{self.current_step_instance.name}]."
                )

                # Update overall progress based on step completion
                runner_progress = int(100 * ((i + 1) / total_steps))
                context.task_instance.update_state(
                    state="PROGRESS",
                    meta={"progress": runner_progress, "step": f"Completed {step_key}"},
                )

            # Optional: Commit Unit of Work if implemented in DependencyProvider
            self.dependency_provider.commit_unit_of_work()

            logger.info("PipelineRunner: Pipeline execution finished successfully.")
            return context

        except Exception as e:
            # Optional: Rollback Unit of Work if implemented
            self.dependency_provider.rollback_unit_of_work()

            step_name_failed = (
                self.current_step_instance.name
                if self.current_step_instance
                else step_key
            )
            logger.error(
                f"Pipeline execution failed at step [{step_name_failed}]: {e}",
                exc_info=True,
            )
            # Add failure info to context warnings? Or rely on exception propagation?
            context.warnings.append(
                f"Pipeline failed at step [{step_name_failed}]: {type(e).__name__}"
            )
            raise  # Re-raise the exception for the Celery task handler
