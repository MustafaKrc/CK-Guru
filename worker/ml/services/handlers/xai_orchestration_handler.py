# worker/ml/services/handlers/xai_orchestration_handler.py
import logging
from typing import Any, Dict, List

# Import Celery App from main to dispatch tasks
from app.main import celery_app
from celery import Task  # Keep Task for type hint
from celery.exceptions import Ignore, Reject  # Import Celery exceptions

# Import DB Models and Enums
# Import Concrete Repositories and Services needed
from shared.repositories import (
    InferenceJobRepository,
    ModelRepository,
    XaiResultRepository,
)
from shared.schemas.enums import JobStatusEnum, ModelTypeEnum, XAITypeEnum

logger = logging.getLogger(__name__)


class XAIOrchestrationHandler:  # Doesn't need full BaseMLJobHandler complexity
    """Handles the orchestration of XAI task dispatching."""

    def __init__(
        self,
        inference_job_id: int,
        task_instance: Task,  # Keep task instance for logging context
        # --- Inject Dependencies ---
        xai_repo: XaiResultRepository,
        model_repo: ModelRepository,
        inference_job_repo: InferenceJobRepository,
    ):
        self.inference_job_id = inference_job_id
        self.task = task_instance  # For logging context primarily
        self.xai_repo = xai_repo
        self.model_repo = model_repo
        self.inference_job_repo = inference_job_repo
        logger.debug(
            f"Initialized XAIOrchestrationHandler for Inference Job ID {inference_job_id}"
        )

    def process_orchestration(self) -> Dict:
        """
        Orchestrates XAI: checks status, creates records, dispatches tasks.
        Returns a summary dict for the Celery task.
        """
        task_id = self.task.request.id if self.task else "N/A"
        logger.info(
            f"Handler: Starting XAI orchestration for Job {self.inference_job_id} "
            f"(Task: {task_id})"
        )
        dispatched_count = 0
        failed_dispatches = []
        final_status = "FAILURE"  # Default
        message = "Orchestration failed"

        try:
            # Get job and model using injected repositories
            inference_job = self.inference_job_repo.get_by_id(self.inference_job_id)
            if not inference_job:
                raise Ignore("Inference job not found.")
            if inference_job.status != JobStatusEnum.SUCCESS:
                raise Ignore("Inference job not successful.")

            model_record = self.model_repo.get_by_id(inference_job.ml_model_id)
            if not model_record:
                raise Reject("Associated ML Model not found.", requeue=False)

            # --- Determine Supported XAI Types ---
            supported_types = [
                XAITypeEnum.SHAP,
                XAITypeEnum.FEATURE_IMPORTANCE,
                XAITypeEnum.LIME,
                XAITypeEnum.COUNTERFACTUALS,
            ]
            if model_record.model_type == ModelTypeEnum.SKLEARN_RANDOMFOREST.value:
                if XAITypeEnum.DECISION_PATH not in supported_types:
                    supported_types.append(XAITypeEnum.DECISION_PATH)
            logger.info(f"Supported XAI types: {[t.value for t in supported_types]}")

            # --- Create Pending Records & Prepare Dispatch Info ---
            created_xai_ids_map: Dict[XAITypeEnum, int] = {}
            tasks_to_dispatch: List[Dict[str, Any]] = []

            for xai_type in supported_types:
                # Use injected repository for find/create operations
                existing_id = self.xai_repo.find_existing_xai_result_id_sync(
                    self.inference_job_id, xai_type
                )
                if existing_id:
                    logger.warning(
                        f"XAI record type {xai_type.value} exists (ID: {existing_id})."
                    )
                    continue

                xai_result_id = self.xai_repo.create_pending_xai_result_sync(
                    self.inference_job_id, xai_type
                )
                if xai_result_id:
                    created_xai_ids_map[xai_type] = xai_result_id
                    tasks_to_dispatch.append(
                        {"xai_result_id": xai_result_id, "xai_type": xai_type}
                    )
                else:
                    logger.error(f"Failed create pending record for {xai_type.value}.")

            # Dispatch tasks
            task_name = "tasks.generate_explanation"
            xai_queue = "xai_queue"
            for task_info in tasks_to_dispatch:
                xai_result_id = task_info["xai_result_id"]
                xai_type = task_info["xai_type"]
                args = [xai_result_id]
                try:
                    task = celery_app.send_task(task_name, args=args, queue=xai_queue)
                    if task and task.id:
                        self.xai_repo.update_xai_task_id_sync(
                            xai_result_id, task.id
                        )  # Implies no commit by hand
                        dispatched_count += 1
                        logger.info(
                            f"Dispatched XAI task {task.id} for Result {xai_result_id} ({xai_type.value})."
                        )
                    else:
                        logger.error(
                            f"Dispatch for XAI Result {xai_result_id} failed (invalid task)."
                        )
                        failed_dispatches.append(xai_result_id)
                except Exception as dispatch_err:
                    logger.error(
                        f"Failed dispatch XAI Result {xai_result_id}: {dispatch_err}",
                        exc_info=True,
                    )
                    failed_dispatches.append(xai_result_id)

            # Mark failed dispatches
            if failed_dispatches:
                self.xai_repo.mark_xai_results_failed_sync(
                    failed_dispatches, "Task dispatch failed"
                )

            final_status = "SUCCESS"
            message = (
                f"XAI Orchestration complete. Dispatched: {dispatched_count}, "
                f"Failed Dispatches: {len(failed_dispatches)}."
            )
            logger.info(f"Handler: {message}")
            return {
                "status": final_status,
                "dispatched_count": dispatched_count,
                "failed_dispatch_count": len(failed_dispatches),
                "message": message,
            }

        except (Ignore, Reject) as e:
            logger.info(f"Handler: XAI Orchestration task ignored or rejected: {e}")
            raise e  # Re-raise for Celery task to handle state
        except Exception as e:
            message = f"XAI orchestration failed critically: {e}"
            logger.critical(f"Handler: {message}", exc_info=True)
            # This is a final error for this workflow, so reject the task
            raise Reject(message, requeue=False) from e
