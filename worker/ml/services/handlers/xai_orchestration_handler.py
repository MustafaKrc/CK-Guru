# worker/ml/services/handlers/xai_orchestration_handler.py
import asyncio  # Add asyncio import
import logging
from typing import Any, Dict, List

from app.main import celery_app  # Celery app for dispatching
from celery import Task
from celery.exceptions import Ignore, Reject

from shared.repositories import (
    InferenceJobRepository,
    ModelRepository,
    XaiResultRepository,
)
from shared.schemas.enums import (
    JobStatusEnum,
    ModelTypeEnum,
    XAIStatusEnum,
    XAITypeEnum,
)

from ..factories.xai_strategy_factory import XAIStrategyFactory

logger = logging.getLogger(__name__)


class XAIOrchestrationHandler:
    def __init__(
        self,
        inference_job_id: int,
        task_instance: Task,
        xai_repo: XaiResultRepository,
        model_repo: ModelRepository,
        inference_job_repo: InferenceJobRepository,
    ):
        self.inference_job_id = inference_job_id
        self.task = task_instance
        self.xai_repo = xai_repo
        self.model_repo = model_repo
        self.inference_job_repo = inference_job_repo
        logger.debug(
            f"Initialized XAIOrchestrationHandler for Inference Job ID {inference_job_id}"
        )

    async def process_orchestration(self) -> Dict[str, Any]:
        task_id_str = self.task.request.id if self.task else "N/A"
        logger.info(
            f"Handler: Starting XAI orchestration for InferenceJob ID {self.inference_job_id} (Task: {task_id_str})"
        )

        dispatched_tasks_count = 0
        failed_dispatch_details: List[Dict[str, Any]] = []
        overall_status = (
            JobStatusEnum.FAILED
        )  # Default for the orchestration task itself
        summary_message = "XAI orchestration failed during initialization."

        try:
            inference_job = await asyncio.to_thread(
                self.inference_job_repo.get_by_id, self.inference_job_id
            )
            if not inference_job:
                raise Ignore(f"InferenceJob ID {self.inference_job_id} not found.")
            if inference_job.status != JobStatusEnum.SUCCESS:
                raise Ignore(
                    f"InferenceJob ID {self.inference_job_id} is not in SUCCESS state (current: {inference_job.status.value}). Cannot orchestrate XAI."
                )

            ml_model_db_record = await asyncio.to_thread(
                self.model_repo.get_by_id, inference_job.ml_model_id
            )
            if not ml_model_db_record:
                raise Reject(
                    f"Associated MLModel ID {inference_job.ml_model_id} for successful InferenceJob {self.inference_job_id} not found.",
                    requeue=False,
                )

            try:
                model_type_enum_of_model = ModelTypeEnum(ml_model_db_record.model_type)
            except ValueError:
                raise Reject(
                    f"Invalid model_type '{ml_model_db_record.model_type}' in MLModel record {ml_model_db_record.id}. Cannot determine supported XAI.",
                    requeue=False,
                )

            all_defined_xai_types = list(XAITypeEnum)
            supported_xai_types_for_this_model: List[XAITypeEnum] = []

            logger.debug(
                f"Checking XAI support for model type: {model_type_enum_of_model.value}"
            )
            for xai_tech in all_defined_xai_types:
                # Use the new static method from the factory for the support check
                if XAIStrategyFactory.is_supported(xai_tech, model_type_enum_of_model):
                    supported_xai_types_for_this_model.append(xai_tech)
                    logger.debug(
                        f"  -> {xai_tech.value}: Supported for {model_type_enum_of_model.value}"
                    )
                else:
                    logger.debug(
                        f"  -> {xai_tech.value}: Not supported by factory for {model_type_enum_of_model.value}"
                    )

            logger.info(
                f"Dynamically determined supported XAI types for model '{model_type_enum_of_model.value}': {[t.value for t in supported_xai_types_for_this_model]}"
            )

            if not supported_xai_types_for_this_model:
                overall_status = JobStatusEnum.SUCCESS
                summary_message = f"No XAI techniques are currently supported or applicable for model type '{model_type_enum_of_model.value}' used in InferenceJob {self.inference_job_id}."
                logger.warning(summary_message)
                return {
                    "status": overall_status.value,
                    "message": summary_message,  # Use .value for enum
                    "inference_job_id": self.inference_job_id,
                    "dispatched_xai_tasks_count": 0,
                    "failed_dispatch_details": [],
                }

            xai_generation_task_name = "tasks.generate_explanation"
            xai_task_queue = "xai_queue"

            for xai_type_to_run in supported_xai_types_for_this_model:
                existing_xai_record_id = await asyncio.to_thread(
                    self.xai_repo.find_existing_xai_result_id_sync,
                    self.inference_job_id,
                    xai_type_to_run,
                )
                should_create_new = True
                if existing_xai_record_id:
                    existing_xai_record = await asyncio.to_thread(
                        self.xai_repo.get_xai_result_sync, existing_xai_record_id
                    )
                    if existing_xai_record and existing_xai_record.status not in [
                        XAIStatusEnum.FAILED,
                        XAIStatusEnum.REVOKED,
                    ]:
                        logger.info(
                            f"XAIResult for type {xai_type_to_run.value} and job {self.inference_job_id} already exists with status {existing_xai_record.status.value} (ID: {existing_xai_record_id}). Skipping creation."
                        )
                        should_create_new = False
                    elif existing_xai_record:
                        logger.info(
                            f"XAIResult for type {xai_type_to_run.value} and job {self.inference_job_id} exists but FAILED/REVOKED (ID: {existing_xai_record_id}). Will attempt to recreate."
                        )

                if should_create_new:
                    xai_result_db_id = await asyncio.to_thread(
                        self.xai_repo.create_pending_xai_result_sync,
                        self.inference_job_id,
                        xai_type_to_run,
                    )
                    if xai_result_db_id:
                        try:
                            celery_task = celery_app.send_task(
                                xai_generation_task_name,
                                args=[xai_result_db_id],
                                queue=xai_task_queue,
                            )
                            if celery_task and celery_task.id:
                                await asyncio.to_thread(
                                    self.xai_repo.update_xai_task_id_sync,
                                    xai_result_db_id,
                                    celery_task.id,
                                )
                                dispatched_tasks_count += 1
                                logger.info(
                                    f"Dispatched XAI generation task {celery_task.id} for XAIResult {xai_result_db_id} (Type: {xai_type_to_run.value}) to queue '{xai_task_queue}'."
                                )
                            else:
                                raise RuntimeError(
                                    "Celery send_task returned invalid task object."
                                )
                        except Exception as dispatch_err:
                            logger.error(
                                f"Failed to dispatch XAI generation task for XAIResult {xai_result_db_id} (Type: {xai_type_to_run.value}): {dispatch_err}",
                                exc_info=True,
                            )
                            failed_dispatch_details.append(
                                {
                                    "xai_result_id": xai_result_db_id,
                                    "type": xai_type_to_run.value,
                                    "error": str(dispatch_err),
                                }
                            )
                            await asyncio.to_thread(
                                self.xai_repo.update_xai_result_sync,
                                xai_result_db_id,
                                XAIStatusEnum.FAILED,
                                f"Task dispatch failed: {dispatch_err}",
                            )
                    else:
                        logger.error(
                            f"Failed to create pending XAIResult record for type {xai_type_to_run.value} and job {self.inference_job_id}."
                        )
                        failed_dispatch_details.append(
                            {
                                "type": xai_type_to_run.value,
                                "error": "DB record creation failed",
                            }
                        )

            overall_status = JobStatusEnum.SUCCESS
            summary_message = f"XAI orchestration complete for InferenceJob {self.inference_job_id}. Dispatched: {dispatched_tasks_count} XAI tasks. Failed to dispatch: {len(failed_dispatch_details)}."
            logger.info(summary_message)

        except Ignore as e:
            overall_status = JobStatusEnum.SKIPPED
            summary_message = f"XAI orchestration for InferenceJob {self.inference_job_id} skipped: {e}"
            logger.info(summary_message)
            raise
        except Reject as e:
            overall_status = JobStatusEnum.FAILED
            summary_message = f"XAI orchestration for InferenceJob {self.inference_job_id} rejected: {e}"
            logger.error(summary_message)
            raise
        except Exception as e:
            overall_status = JobStatusEnum.FAILED
            summary_message = f"Critical error during XAI orchestration for InferenceJob {self.inference_job_id}: {type(e).__name__}: {str(e)[:250]}"
            logger.critical(summary_message, exc_info=True)
            raise Reject(summary_message, requeue=False) from e

        return {
            "status": overall_status.value,  # Use the enum's value
            "message": summary_message,
            "inference_job_id": self.inference_job_id,
            "dispatched_xai_tasks_count": dispatched_tasks_count,
            "failed_dispatch_details": failed_dispatch_details,
        }
