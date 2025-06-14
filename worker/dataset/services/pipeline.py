# worker/dataset/services/pipeline.py
import asyncio
import logging
from typing import List, Type

from shared.schemas.enums import JobStatusEnum
from shared.utils.pipeline_logging import StepLogger

from .context import DatasetContext  # Import Context
from .dependencies import DependencyProvider, StepRegistry  # Import DI classes
from .interfaces import IDatasetGeneratorStep  # Import Step interface
from .strategies import IDatasetGenerationStrategy  # Import Strategy interface

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Runs the dataset generation pipeline defined by a strategy."""

    def __init__(
        self,
        strategy: IDatasetGenerationStrategy,
        step_registry: StepRegistry,
        dependency_provider: DependencyProvider,
    ):
        self.strategy = strategy
        self.step_registry = step_registry
        self.dependency_provider = dependency_provider
        self.current_step_instance: IDatasetGeneratorStep | None = None
        logger.debug(
            f"PipelineRunner initialized with strategy: {type(strategy).__name__}"
        )

    async def run(self, initial_context: DatasetContext) -> DatasetContext:
        """Executes the pipeline steps sequentially."""
        context = initial_context
        steps_to_run: List[Type[IDatasetGeneratorStep]] = self.strategy.get_steps()
        total_steps = len(steps_to_run)
        step_key = "Initialization"  # For error reporting

        log_prefix_base = f"Task {context.task_instance.request.id} - Pipeline"
        pipeline_logger = StepLogger(logger, log_prefix=log_prefix_base)
        pipeline_logger.info(f"Starting pipeline execution with {total_steps} steps...")

        try:
            for i, step_class in enumerate(steps_to_run):
                self.current_step_instance = self.step_registry.get_step(step_class)
                step_key = self.current_step_instance.name  # Use step's name

                pipeline_logger.info(
                    f"Executing step {i+1}/{total_steps} [{step_key}]..."
                )

                # Inject dependencies
                # Session scope management happens within repositories/services accessed via provider
                dependencies = self.dependency_provider.get_dependencies_for_step(
                    self.current_step_instance, context
                )

                # Execute the step - check if result is awaitable
                result = self.current_step_instance.execute(context, **dependencies)
                if asyncio.iscoroutine(result):
                    context = await result
                else:
                    context = result

                pipeline_logger.info(
                    f"Completed step {i+1}/{total_steps} [{step_key}]."
                )

                # Update overall progress based on step completion
                runner_progress = min(99, int(100 * ((i + 1) / total_steps)))
                if context.task_instance:
                    await context.task_instance.update_task_state(
                        state=JobStatusEnum.RUNNING.value,
                        progress=runner_progress,
                        status_message=f"Pipeline: Completed step {self.current_step_instance.name}",
                        job_type=context.event_job_type,
                        entity_id=context.event_entity_id,
                        entity_type=context.event_entity_type,
                        user_id=context.event_user_id,
                    )

            pipeline_logger.info("Pipeline execution finished successfully.")
            return context

        except Exception as e:
            step_name_failed = (
                self.current_step_instance.name
                if self.current_step_instance
                else step_key
            )
            error_msg = f"Pipeline failed at step [{step_name_failed}]"
            full_error_details = f"{error_msg}: {type(e).__name__}: {str(e)[:500]}"
            # pipeline_logger.error(...)

            context.warnings.append(
                f"Pipeline critical failure at {step_name_failed}: {type(e).__name__}"
            )

            if context.task_instance:
                try:
                    await context.task_instance.update_task_state(
                        state=JobStatusEnum.FAILED.value,
                        status_message=error_msg,
                        error_details=full_error_details,
                        job_type=context.event_job_type,
                        entity_id=context.event_entity_id,
                        entity_type=context.event_entity_type,
                        user_id=context.event_user_id,
                    )
                except Exception as final_update_err:
                    logger.error(
                        f"Failed to update task to FAILED state after pipeline error: {final_update_err}"
                    )
            raise
