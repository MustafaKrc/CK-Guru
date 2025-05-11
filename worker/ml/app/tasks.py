# worker/ml/app/tasks.py
import logging

from celery import Task, shared_task
from celery.exceptions import Ignore, Reject, Terminated

# --- Import Dependency Provider ---
from services.dependencies import DependencyProvider
from services.handlers.hp_search_handler import HPSearchJobHandler
from services.handlers.inference_handler import InferenceJobHandler

# --- Import Handlers ---
from services.handlers.training_handler import TrainingJobHandler
from services.handlers.xai_explanation_handler import XAIExplanationHandler
from services.handlers.xai_orchestration_handler import XAIOrchestrationHandler

from shared.core.config import settings

# --- Import DB Models and Enums ---
from shared.db.models import JobStatusEnum  # Keep if needed for logic below

# --- Import Session Factory ---
from shared.db_session import SyncSessionLocal
from shared.exceptions import InternalError, build_failure_meta

# Import Celery app instance if needed for dispatching other tasks
from .main import celery_app

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


# === Training Task ===
@shared_task(bind=True, name="tasks.train_model", acks_late=True)
def train_model_task(self: Task, training_job_id: int):
    """Celery task facade for training jobs, using Dependency Injection."""
    task_id = self.request.id
    logger.info(
        f"Task {task_id}: Received training request for Job ID {training_job_id}"
    )
    # Default result in case of early failure before handler processing
    final_task_result = {
        "job_id": training_job_id,
        "status": JobStatusEnum.FAILED,
        "message": "Task failed during initialization.",
    }

    try:
        # --- Instantiate Provider and Handler ---
        provider = DependencyProvider(session_factory=SyncSessionLocal)
        handler = TrainingJobHandler(
            job_id=training_job_id,
            task_instance=self,
            # --- Inject Concrete Dependencies ---
            status_updater=provider.get_job_status_updater(),
            model_repo=provider.get_model_repository(),
            xai_repo=provider.get_xai_result_repository(),
            feature_repo=provider.get_ml_feature_repository(),
            artifact_service=provider.get_artifact_service(),
            dataset_repo=provider.get_dataset_repository(),
            training_job_repo=provider.get_training_job_repository(),
        )

        # --- Execute Handler ---
        # Handler manages DB status updates internally via status_updater
        # It returns a result dict for the Celery task
        final_task_result = handler.process_job()  # This blocks until handler finishes

        # --- Update Celery Task State (based on handler result) ---
        handler_status = final_task_result.get("status")
        handler_message = final_task_result.get("message", "Handler finished.")

        if handler_status == JobStatusEnum.SUCCESS:
            self.update_state(state=JobStatusEnum.SUCCESS, meta=final_task_result)
            logger.info(
                f"Task {task_id}: Training Job {training_job_id} reported SUCCESS by handler."
            )
        elif handler_status == JobStatusEnum.SKIPPED:
            logger.info(
                f"Task {task_id}: Training Job {training_job_id} was skipped by handler: {handler_message}"
            )
            self.update_state(
                state=JobStatusEnum.SUCCESS, meta=final_task_result
            )  # Treat skip as celery success
        else:  # Handler indicated failure
            logger.error(
                f"Task {task_id}: Training Job {training_job_id} reported FAILURE by handler: {final_task_result.get('error', handler_message)}"
            )
            self.update_state(
                state=JobStatusEnum.FAILED,
                meta=build_failure_meta(
                    InternalError(handler_message), final_task_result
                ),
            )

        return final_task_result  # Return result dict for Celery

    # --- Exception Handling for Celery Control/Unexpected Errors ---
    except Terminated as e:
        logger.warning(f"Task {task_id}: Terminated.")
        # Handler's finally should have tried to update DB status to FAILED
        self.update_state(
            state="REVOKED", meta=build_failure_meta(e, final_task_result)
        )
        raise  # Re-raise for Celery
    except Ignore as e:
        logger.info(f"Task {task_id}: Ignored. Reason: {e}")
        self.update_state(
            state=JobStatusEnum.SUCCESS, meta={"status": "IGNORED", "message": str(e)}
        )
        return {"status": "IGNORED", "message": str(e)}  # Return ignore info
    except Reject as e:
        logger.error(f"Task {task_id}: Rejected. Reason: {e}")
        # DB status likely handled where Reject was raised
        self.update_state(
            state=JobStatusEnum.FAILED, meta=build_failure_meta(e, final_task_result)
        )
        raise  # Re-raise reject
    except Exception as e:
        error_msg = f"Unhandled exception in task {task_id} for job {training_job_id}: {type(e).__name__}: {e}"
        logger.critical(error_msg, exc_info=True)
        # Attempt final DB update as last resort
        try:
            provider = DependencyProvider(session_factory=SyncSessionLocal)
            status_updater = provider.get_job_status_updater()
            # Use the correct Model class here
            from shared.db.models import TrainingJob

            status_updater.update_job_completion(
                training_job_id, TrainingJob, JobStatusEnum.FAILED, error_msg[:1000]
            )
        except Exception as final_db_err:
            logger.error(
                f"Task {task_id}: Failed last resort DB update: {final_db_err}"
            )
        # Ensure Celery knows
        self.update_state(
            state=JobStatusEnum.FAILED, meta=build_failure_meta(e, final_task_result)
        )
        raise Reject(error_msg, requeue=False) from e  # Reject unhandled errors


# === HP Search Task ===
@shared_task(bind=True, name="tasks.hyperparameter_search", acks_late=True)
def hyperparameter_search_task(self: Task, hp_search_job_id: int):
    """Celery task facade for hyperparameter search jobs, using DI."""
    task_id = self.request.id
    logger.info(
        f"Task {task_id}: Received HP search request for Job ID {hp_search_job_id}"
    )
    final_task_result = {
        "job_id": hp_search_job_id,
        "status": JobStatusEnum.FAILED,
        "message": "Task failed during initialization.",
    }

    try:
        # --- Instantiate Provider and Handler ---
        provider = DependencyProvider()
        handler = HPSearchJobHandler(
            job_id=hp_search_job_id,
            task_instance=self,
            # --- Inject Dependencies ---
            status_updater=provider.get_job_status_updater(),
            model_repo=provider.get_model_repository(),
            xai_repo=provider.get_xai_result_repository(),
            feature_repo=provider.get_ml_feature_repository(),
            artifact_service=provider.get_artifact_service(),
            dataset_repo=provider.get_dataset_repository(),
            hp_search_job_repo=provider.get_hp_search_job_repository(),
        )

        # --- Execute Handler ---
        final_task_result = handler.process_job()

        # --- Update Celery Task State (based on handler result) ---
        handler_status = final_task_result.get("status")
        if handler_status == JobStatusEnum.SUCCESS:
            self.update_state(state=JobStatusEnum.SUCCESS, meta=final_task_result)
            logger.info(
                f"Task {task_id}: HP Search Job {hp_search_job_id} reported SUCCESS by handler."
            )
        elif handler_status == JobStatusEnum.SKIPPED:
            logger.info(
                f"Task {task_id}: HP Search Job {hp_search_job_id} was skipped by handler."
            )
            self.update_state(state=JobStatusEnum.SUCCESS, meta=final_task_result)
        else:  # Handler indicated failure
            logger.error(
                f"Task {task_id}: HP Search Job {hp_search_job_id} reported FAILURE by handler: {final_task_result.get('error', 'Unknown handler error')}"
            )
            self.update_state(
                state=JobStatusEnum.FAILED,
                meta=build_failure_meta(
                    InternalError(final_task_result.get("error", "handler failure")),
                    final_task_result,
                ),
            )

        return final_task_result

    # --- Exception Handling (Similar to train_model_task) ---
    except Terminated as e:
        logger.warning(f"Task {task_id}: Terminated.")
        self.update_state(
            state="REVOKED",
            meta={"exc_type": "Terminated", "exc_message": "Task terminated."},
        )
        raise e
    except Ignore as e:
        logger.info(f"Task {task_id}: Ignored. Reason: {e}")
        self.update_state(
            state=JobStatusEnum.SUCCESS, meta={"status": "IGNORED", "message": str(e)}
        )
        return {"status": "IGNORED", "message": str(e)}
    except Reject as e:
        logger.error(f"Task {task_id}: Rejected. Reason: {e}")
        self.update_state(
            state=JobStatusEnum.FAILED, meta=build_failure_meta(e, final_task_result)
        )
        raise e
    except Exception as e:
        error_msg = f"Unhandled exception in task {task_id} for job {hp_search_job_id}: {type(e).__name__}: {e}"
        logger.critical(error_msg, exc_info=True)
        try:  # Last resort DB update
            provider = DependencyProvider()
            status_updater = provider.get_job_status_updater()
            from shared.db.models import HyperparameterSearchJob

            status_updater.update_job_completion(
                hp_search_job_id,
                HyperparameterSearchJob,
                JobStatusEnum.FAILED,
                error_msg[:1000],
            )
        except Exception as final_db_err:
            logger.error(
                f"Task {task_id}: Failed last resort DB update: {final_db_err}"
            )
        self.update_state(
            state=JobStatusEnum.FAILED, meta=build_failure_meta(e, final_task_result)
        )
        raise Reject(error_msg, requeue=False) from e


# === Inference Prediction Task ===
@shared_task(bind=True, name="tasks.inference_predict", acks_late=True)
def inference_predict_task(self: Task, inference_job_id: int):
    """Performs prediction using the DI handler and triggers XAI orchestration."""
    task_id = self.request.id
    logger.info(
        f"Task {task_id}: Starting prediction task for InferenceJob ID {inference_job_id}"
    )
    final_task_result = {
        "job_id": inference_job_id,
        "status": JobStatusEnum.FAILED,
        "message": "Task failed during initialization.",
    }
    prediction_successful = False  # Flag to track if prediction part succeeded

    try:
        # --- Instantiate Provider and Handler ---
        provider = DependencyProvider()
        handler = InferenceJobHandler(
            job_id=inference_job_id,
            task_instance=self,
            # --- Inject Dependencies ---
            status_updater=provider.get_job_status_updater(),
            model_repo=provider.get_model_repository(),
            xai_repo=provider.get_xai_result_repository(),
            feature_repo=provider.get_ml_feature_repository(),  # Inference needs feature repo
            artifact_service=provider.get_artifact_service(),
            inference_job_repo=provider.get_inference_job_repository(),
        )

        # --- Execute Handler ---
        # Handler returns prediction result package dict on success/handled failure
        final_task_result = (
            handler.process_job()
        )  # This runs prediction AND updates DB status

        handler_status = final_task_result.get("status")
        if handler_status == JobStatusEnum.SUCCESS:
            prediction_successful = True  # Mark prediction as successful
            logger.info(
                f"Task {task_id}: Inference Job {inference_job_id} prediction reported SUCCESS by handler."
            )
        elif handler_status == JobStatusEnum.SKIPPED:
            logger.info(
                f"Task {task_id}: Inference Job {inference_job_id} was skipped by handler."
            )
        else:  # Handler indicated failure
            logger.error(
                f"Task {task_id}: Inference Job {inference_job_id} reported FAILURE by handler: {final_task_result.get('error', 'Unknown handler error')}"
            )
            # No need to update Celery state to FAILURE here, wait until after XAI dispatch attempt

        # --- Dispatch XAI Orchestration (ONLY if prediction successful) ---
        if prediction_successful:
            logger.info(
                f"Task {task_id}: Prediction successful for job {inference_job_id}. Triggering XAI orchestration."
            )
            orchestration_task_name = "tasks.orchestrate_xai"
            args = [inference_job_id]
            try:
                orchestration_task = celery_app.send_task(
                    orchestration_task_name, args=args, queue="ml_queue"
                )
                if orchestration_task and orchestration_task.id:
                    logger.info(
                        f"Task {task_id}: Dispatched XAI orchestration task {orchestration_task.id}"
                    )
                    final_task_result["xai_orchestration_task_id"] = (
                        orchestration_task.id
                    )
                else:
                    logger.error(
                        f"Task {task_id}: Failed to dispatch XAI task (invalid task returned)."
                    )
                    final_task_result["xai_dispatch_error"] = (
                        "Invalid task object returned by celery"
                    )
            except Exception as dispatch_err:
                logger.error(
                    f"Task {task_id}: Failed to dispatch XAI task: {dispatch_err}",
                    exc_info=True,
                )
                final_task_result["xai_dispatch_error"] = str(dispatch_err)

        # --- Update Celery Task State ---
        # Final Celery state depends ONLY on whether the prediction itself succeeded or failed
        # We don't fail this task if XAI dispatch fails.
        if prediction_successful:
            self.update_state(state=JobStatusEnum.SUCCESS, meta=final_task_result)
        else:
            self.update_state(
                state=JobStatusEnum.FAILED,
                meta=build_failure_meta(
                    InternalError(final_task_result.get("error", "prediction failed")),
                    final_task_result,
                ),
            )

        return final_task_result  # Return prediction result and any dispatch info/error

    # --- Exception Handling ---
    except Terminated as e:
        logger.warning(f"Task {task_id}: Terminated.")
        self.update_state(
            state="REVOKED",
            meta={"exc_type": "Terminated", "exc_message": "Task terminated."},
        )
        raise e
    except Ignore as e:
        logger.info(f"Task {task_id}: Ignored. Reason: {e}")
        self.update_state(
            state=JobStatusEnum.SUCCESS, meta={"status": "IGNORED", "message": str(e)}
        )
        return {"status": "IGNORED", "message": str(e)}
    except Reject as e:
        logger.error(f"Task {task_id}: Rejected. Reason: {e}")
        self.update_state(
            state=JobStatusEnum.FAILED,
            meta={"exc_type": "Reject", "exc_message": str(e)},
        )
        raise e
    except Exception as e:
        error_msg = f"Unhandled exception in task {task_id} for job {inference_job_id}: {type(e).__name__}: {e}"
        logger.critical(error_msg, exc_info=True)
        try:  # Last resort DB update
            provider = DependencyProvider()
            status_updater = provider.get_job_status_updater()
            from shared.db.models import InferenceJob

            status_updater.update_job_completion(
                inference_job_id, InferenceJob, JobStatusEnum.FAILED, error_msg[:1000]
            )
        except Exception as final_db_err:
            logger.error(
                f"Task {task_id}: Failed last resort DB update: {final_db_err}"
            )
        self.update_state(
            state=JobStatusEnum.FAILED, meta=build_failure_meta(e, final_task_result)
        )
        raise Reject(error_msg, requeue=False) from e


# === XAI Orchestration Task ===
@shared_task(bind=True, name="tasks.orchestrate_xai", acks_late=True)
def orchestrate_xai_task(self: Task, inference_job_id: int):
    """Celery task facade for XAI orchestration using a dedicated handler."""
    task_id = self.request.id
    logger.info(
        f"Task {task_id}: Received XAI orchestration request for InferenceJob ID {inference_job_id}"
    )
    final_task_result = {
        "inference_job_id": inference_job_id,
        "status": JobStatusEnum.FAILED,
        "message": "Orchestration failed",
    }

    try:
        # --- Instantiate Provider and Handler ---
        provider = DependencyProvider()
        handler = XAIOrchestrationHandler(
            inference_job_id=inference_job_id,
            task_instance=self,
            # --- Inject Dependencies ---
            xai_repo=provider.get_xai_result_repository(),
            model_repo=provider.get_model_repository(),
            inference_job_repo=provider.get_inference_job_repository(),
        )

        # --- Execute Handler ---
        final_task_result = handler.process_orchestration()  # Returns summary dict

        # --- Update Celery Task State ---
        if final_task_result.get("status") == JobStatusEnum.SUCCESS:
            self.update_state(state=JobStatusEnum.SUCCESS, meta=final_task_result)
            logger.info(
                f"Task {task_id}: XAI Orchestration reported SUCCESS by handler."
            )
        else:  # Should not happen unless Reject is caught differently now
            logger.error(
                f"Task {task_id}: XAI Orchestration reported unexpected status by handler: {final_task_result}"
            )
            self.update_state(
                state=JobStatusEnum.FAILED,
                meta=build_failure_meta(e, final_task_result),
            )

        return final_task_result

    # --- Exception Handling ---
    except Ignore as e:  # Handler raises Ignore if job not found/ready
        logger.info(f"Task {task_id}: Orchestration ignored. Reason: {e}")
        self.update_state(
            state=JobStatusEnum.SUCCESS, meta={"status": "IGNORED", "message": str(e)}
        )
        return {"status": "IGNORED", "message": str(e)}
    except Reject as e:  # Handler raises Reject on critical internal errors
        logger.error(f"Task {task_id}: Orchestration rejected. Reason: {e}")
        self.update_state(
            state=JobStatusEnum.FAILED, meta=build_failure_meta(e, final_task_result)
        )
        raise e  # Re-raise reject
    except Exception as e:  # Catch unexpected errors outside handler
        error_msg = f"Unhandled exception in XAI orchestration task {task_id}: {type(e).__name__}: {e}"
        logger.critical(error_msg, exc_info=True)
        self.update_state(
            state=JobStatusEnum.FAILED, meta=build_failure_meta(e, final_task_result)
        )
        raise Reject(error_msg, requeue=False) from e


# === Explanation Generation Task ===
@shared_task(bind=True, name="tasks.generate_explanation", acks_late=True)
def generate_explanation_task(self: Task, xai_result_id: int):
    """Celery task facade for generating specific XAI explanation using a handler."""
    task_id = self.request.id
    logger.info(
        f"Task {task_id}: Received explanation generation request for XAIResult ID {xai_result_id}"
    )
    final_task_result = None  # Handler returns the explanation data or None

    try:
        # --- Instantiate Provider and Handler ---
        provider = DependencyProvider()
        handler = XAIExplanationHandler(
            xai_result_id=xai_result_id,
            task_instance=self,
            # --- Inject Dependencies ---
            xai_repo=provider.get_xai_result_repository(),
            model_repo=provider.get_model_repository(),
            feature_repo=provider.get_ml_feature_repository(),
            artifact_service=provider.get_artifact_service(),
            inference_job_repo=provider.get_inference_job_repository(),
            dataset_repo=provider.get_dataset_repository(),
        )

        # --- Execute Handler ---
        # Handler manages DB status updates and returns result data (or None on failure)
        final_task_result = handler.process_explanation()

        # --- Update Celery Task State ---
        if final_task_result is not None:  # Assume success if handler returned data
            self.update_state(
                state=JobStatusEnum.SUCCESS,
                meta={"result_preview": str(final_task_result)[:200]},
            )  # Return preview
            logger.info(
                f"Task {task_id}: XAI Explanation generation reported SUCCESS by handler."
            )
        else:  # Handler failed internally and updated DB, likely returned None
            logger.error(
                f"Task {task_id}: XAI Explanation generation failed (handler returned None or error occurred before return)."
            )
            self.update_state(
                state=JobStatusEnum.FAILED,
                meta=build_failure_meta(e, final_task_result),
            )

        return final_task_result  # Return explanation data or None

    # --- Exception Handling ---
    except Terminated as e:
        logger.warning(f"Task {task_id}: Terminated.")
        # Handler's finally should have tried to update DB status to FAILED
        self.update_state(
            state="REVOKED",
            meta={"exc_type": "Terminated", "exc_message": "Task terminated."},
        )
        raise e
    except Ignore as e:
        logger.info(f"Task {task_id}: Ignored. Reason: {e}")
        self.update_state(
            state=JobStatusEnum.SUCCESS, meta={"status": "IGNORED", "message": str(e)}
        )
        return {"status": "IGNORED", "message": str(e)}
    except Reject as e:
        logger.error(f"Task {task_id}: Rejected. Reason: {e}")
        self.update_state(
            state=JobStatusEnum.FAILED, meta=build_failure_meta(e, final_task_result)
        )
        raise e
    except Exception as e:
        error_msg = f"Unhandled exception in task {task_id} for XAI result {xai_result_id}: {type(e).__name__}: {e}"
        logger.critical(error_msg, exc_info=True)
        # Last resort DB update
        try:
            provider = DependencyProvider()
            xai_repo = provider.get_xai_result_repository()
            from shared.schemas.enums import XAIStatusEnum

            xai_repo.update_xai_result_sync(
                xai_result_id, XAIStatusEnum.FAILED, error_msg[:1000], commit=True
            )
        except Exception as final_db_err:
            logger.error(
                f"Task {task_id}: Failed last resort DB update: {final_db_err}"
            )
        self.update_state(
            state=JobStatusEnum.FAILED, meta=build_failure_meta(e, final_task_result)
        )
        raise Reject(error_msg, requeue=False) from e
