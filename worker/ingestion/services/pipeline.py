# worker/ingestion/services/pipeline.py
import logging

from services.dependencies import DependencyProvider, StepRegistry
from services.steps.base import IngestionContext
from services.strategies import IngestionStrategy
from shared.core.config import settings
from shared.schemas.enums import JobStatusEnum

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
        logger.debug(
            f"PipelineRunner initialized with strategy: {type(strategy).__name__}"
        )

    async def run(self, initial_context: IngestionContext) -> IngestionContext:
        context = initial_context
        steps = self.strategy.get_steps()
        total = len(steps)
        try:
            for idx, StepCls in enumerate(steps, start=1):
                step = self.step_registry.get_step(StepCls)
                context = await step.execute(
                    context,
                    **self.dependency_provider.get_dependencies_for_step(step, context),
                )
                runner_progress = int(100 * (idx / total))
                await context.task_instance.update_task_state(
                    state=JobStatusEnum.RUNNING.value,
                    status_message=f"Pipeline: Completed step {step.name}",
                    progress=runner_progress,
                    job_type=context.event_job_type,
                    entity_id=context.event_entity_id,
                    entity_type=context.event_entity_type,
                    user_id=context.event_user_id,
                )
            self.dependency_provider.commit_unit_of_work()
            return context
        except Exception as e:
            self.dependency_provider.rollback_unit_of_work()
            await context.task_instance.update_task_state(
                state=JobStatusEnum.FAILED.value,
                status_message=f"Pipeline failed at {step.name}: {e}",
                error_details=str(e),
                progress=0,
                job_type=context.event_job_type,
                entity_id=context.event_entity_id,
                entity_type=context.event_entity_type,
                user_id=context.event_user_id,
            )
            raise
