# worker/dataset/services/steps/base_dataset_step.py
import logging
from abc import ABC # IngestionStep was from ingestion worker
from services.interfaces.i_step import IDatasetGeneratorStep # Use dataset's interface
from services.context import DatasetContext
from typing import Optional, Any
from shared.schemas.enums import JobStatusEnum

logger = logging.getLogger(__name__)

class BaseDatasetStep(IDatasetGeneratorStep, ABC): # Inherit from ABC too
    # name property will be defined by subclasses

    def _get_task_id_str(self, context: DatasetContext) -> str:
        if context.task_instance and hasattr(context.task_instance, 'request') and context.task_instance.request:
            return str(context.task_instance.request.id)
        return "N/A"

    def _log_info(self, context: DatasetContext, message: str):
        logger.info(f"Task {self._get_task_id_str(context)} - Step [{self.name}]: {message}")

    def _log_warning(self, context: DatasetContext, message: str):
        logger.warning(f"Task {self._get_task_id_str(context)} - Step [{self.name}]: {message}")
        context.warnings.append(f"[{self.name}] {message}")

    def _log_error(self, context: DatasetContext, message: str, exc_info=True):
        logger.error(
            f"Task {self._get_task_id_str(context)} - Step [{self.name}]: {message}", exc_info=exc_info
        )

    async def _update_progress( # Now async
        self,
        context: DatasetContext,
        message: str,
        progress: int,
        warning: Optional[str] = None, 
    ):
        if context.task_instance:
            status_msg_for_event = message
            if warning:
                self._log_warning(context, warning)
            
            await context.task_instance.update_task_state(
                state=JobStatusEnum.RUNNING.value,
                status_message=status_msg_for_event,
                progress=progress,
                job_type=context.event_job_type,
                entity_id=context.event_entity_id,
                entity_type=context.event_entity_type,
                user_id=context.event_user_id,
                meta={'progress': progress, 'status_message': status_msg_for_event}
            )