# worker/ml/services/handlers/inference_handler.py
import logging
import traceback
from typing import Any, List, Tuple, Dict, Optional
from celery import Task
import numpy as np
import pandas as pd
from sklearn.exceptions import NotFittedError
from sqlalchemy.orm import Session

from shared.db_session.sync_session import get_sync_db_session
from shared.schemas.enums import JobStatusEnum
from shared.schemas.inference_job import InferenceResultPackage
from shared.schemas.xai import FilePredictionDetail
from .base_handler import BaseMLJobHandler
from ..factories.strategy_factory import create_model_strategy
from ..strategies.base_strategy import BaseModelStrategy
from shared.db.models import InferenceJob, MLModel
from shared import schemas
from shared.core.config import settings

from services import job_db_service

from celery.exceptions import Terminated, Ignore, Reject


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper()) # Use settings level

class InferenceJobHandler(BaseMLJobHandler):
    """Handles the execution of inference prediction jobs."""

    def __init__(self, job_id: int, task_instance: Task):
        super().__init__(job_id, task_instance)
        self.input_reference: Dict[str, Any] = {}
        self.ml_model_id: Optional[int] = None

    @property
    def job_type_name(self) -> str:
        return 'InferenceJob'

    @property
    def job_model_class(self) -> type:
        return InferenceJob

    def _load_job_details(self, session: Session):
        """Loads inference job details including model ID and input reference."""
        super()._load_job_details(session) # Base method loads record, sets RUNNING

        self.input_reference = self.job_db_record.input_reference if isinstance(self.job_db_record.input_reference, dict) else {}
        self.ml_model_id = self.job_db_record.ml_model_id

        if self.ml_model_id is None:
            raise ValueError(f"ml_model_id is missing from InferenceJob record {self.job_id}")
        if not self.input_reference.get('commit_hash') or not self.input_reference.get('repo_id'):
             logger.warning(f"input_reference in job {self.job_id} might be incomplete: {self.input_reference}")

        logger.info(f"InferenceJobHandler {self.job_id}: Details loaded: Model={self.ml_model_id}, InputRef={self.input_reference}")


    def _create_strategy(self) -> BaseModelStrategy:
        """Loads the specified ML model artifact into the appropriate strategy."""
        session = self.current_session
        if not session: raise RuntimeError("DB Session not available in _create_strategy")
        if self.ml_model_id is None: raise ValueError("ml_model_id not set.")

        logger.info(f"InferenceJobHandler {self.job_id}: Fetching model record for ID: {self.ml_model_id}")
        model_record = session.get(MLModel, self.ml_model_id)
        if not model_record: raise ValueError(f"MLModel record {self.ml_model_id} not found.")
        if not model_record.s3_artifact_path: raise ValueError(f"MLModel {self.ml_model_id} has no artifact path.")

        model_type_str = model_record.model_type
        try:
            model_type_enum = schemas.ModelTypeEnum(model_type_str)
        except ValueError:
            raise ValueError(f"Unsupported model_type '{model_type_str}'")

        artifact_path = model_record.s3_artifact_path
        logger.info(f"InferenceJobHandler {self.job_id}: Creating strategy '{model_type_enum.value}', loading {artifact_path}")
        # Pass empty dicts if model/job config not needed or available here for inference
        strategy = create_model_strategy(model_type_enum, model_record.hyperparameters or {}, {})
        strategy.load_model(artifact_path)
        logger.info(f"InferenceJobHandler {self.job_id}: Model loaded into strategy successfully.")
        return strategy

    def _prepare_data(self, features_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepares data received from the task (originally from FeatureRetrievalService).
        Separates features and identifiers, validates features.
        """
        if self.model_strategy is None or self.model_strategy.model is None:
            raise RuntimeError("Model strategy or internal model not loaded before _prepare_data.")
        if features_df is None or features_df.empty:
             raise ValueError("Received empty features DataFrame for prediction.")

        logger.info(f"InferenceJobHandler {self.job_id}: Preparing data from features DataFrame ({features_df.shape})...")
        data = features_df

        # --- Define Identifier Columns ---
        identifier_cols = ['file', 'class_name'] 
        missing_ids = [col for col in identifier_cols if col not in data.columns]
        if missing_ids: raise ValueError(f"Input features missing required identifier columns: {missing_ids}")
        identifiers_df = data[identifier_cols].copy()

        # --- Get Expected Features ---
        expected_features: Optional[list[str]] = None
        try:
            if hasattr(self.model_strategy.model, 'feature_names_in_'):
                expected_features = self.model_strategy.model.feature_names_in_.tolist()
            if not expected_features:
                logger.warning("Could not determine expected features from model. Using all non-identifier numeric columns.")
                expected_features = data.select_dtypes(include=np.number).columns.difference(identifier_cols).tolist()
                if not expected_features: raise ValueError("No numeric feature columns found in input.")
            logger.debug(f"Model expects features: {expected_features}")
        except Exception as e:
            raise ValueError(f"Failed to determine expected model features: {e}") from e

        # --- Validate, Select, Preprocess Features ---
        missing_features = set(expected_features) - set(data.columns)
        if missing_features: raise ValueError(f"Input features missing columns expected by model: {sorted(list(missing_features))}")
        extra_features = set(data.columns.difference(identifier_cols)) - set(expected_features)
        if extra_features: logger.warning(f"Input features have extra columns (will be dropped): {sorted(list(extra_features))}")

        X = data[expected_features].copy()
        if X.isnull().values.any():
            logger.warning("Feature data contains NaN values. Applying simple fillna(0).")
            X = X.fillna(0)

        logger.info(f"Data prepared for inference. Features shape: {X.shape}, Identifiers shape: {identifiers_df.shape}")
        return X, identifiers_df

    def _execute_core_ml_task(self, prepared_data_package: Tuple[pd.DataFrame, pd.DataFrame]) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """Executes prediction and returns results along with identifiers."""
        X_inference, identifiers_df = prepared_data_package
        if self.model_strategy is None or self.model_strategy.model is None:
            raise RuntimeError("Model strategy or internal model not loaded.")

        logger.info(f"InferenceJobHandler {self.job_id}: Executing inference on {X_inference.shape[0]} instances.")
        prediction_result = self.model_strategy.predict(X_inference)
        logger.info(f"InferenceJobHandler {self.job_id}: Inference execution complete.")
        return prediction_result, identifiers_df

    def _prepare_final_results(self, ml_result_package: Tuple[Dict[str, Any], pd.DataFrame]):
        """Processes prediction results and stores in self.final_db_results."""
        ml_result, identifiers_df = ml_result_package
        logger.info(f"InferenceJobHandler {self.job_id}: Aggregating prediction results...")

        row_predictions = ml_result.get('predictions')
        row_probabilities = ml_result.get('probabilities')
        error_msg = None
        commit_prediction = -1 # Default to error
        max_bug_probability = -1.0
        detailed_results: List[FilePredictionDetail] = []
        num_files_analyzed = 0

        if row_predictions is None or len(row_predictions) != len(identifiers_df):
            error_msg = "Prediction results are missing or length mismatch with identifiers."
            logger.error(f"InferenceJobHandler {self.job_id}: {error_msg}")
        else:
            num_files_analyzed = len(identifiers_df)
            commit_prediction = 0 # Default to clean unless a 1 is found
            max_bug_probability = 0.0
            try:
                for i in range(num_files_analyzed):
                    prediction = int(row_predictions[i])
                    prob_class_1 = 0.0
                    # Safely access probabilities
                    if row_probabilities and i < len(row_probabilities):
                        probs_for_instance = row_probabilities[i]
                        if isinstance(probs_for_instance, (list, np.ndarray)) and len(probs_for_instance) > 1:
                             # Assume index 1 corresponds to the positive (defect) class
                             prob_class_1 = float(probs_for_instance[1])
                        elif isinstance(probs_for_instance, (float, np.float_)): # Handle single probability output?
                             prob_class_1 = float(probs_for_instance) if prediction == 1 else (1.0-float(probs_for_instance))

                    if prediction == 1: commit_prediction = 1
                    max_bug_probability = max(max_bug_probability, prob_class_1)

                    detailed_results.append(FilePredictionDetail(
                        file=identifiers_df.iloc[i].get('file'),
                        class_name=identifiers_df.iloc[i].get('class_name'),
                        prediction=prediction,
                        probability=round(prob_class_1, 4)
                    ))
            except Exception as e:
                 logger.error(f"InferenceJobHandler {self.job_id}: Error processing prediction results: {e}", exc_info=True)
                 error_msg = f"Failed to process prediction results: {e}"
                 commit_prediction = -1
                 max_bug_probability = -1.0
                 detailed_results = []
                 num_files_analyzed = 0

        # Create the final result package
        prediction_package = InferenceResultPackage(
            commit_prediction=commit_prediction,
            max_bug_probability=round(max_bug_probability, 4) if max_bug_probability >= 0 else -1.0,
            num_files_analyzed=num_files_analyzed,
            details=detailed_results if not error_msg else None,
            error=error_msg
        )

        # Use model_dump to get dict for JSON storage
        self.final_db_results['prediction_result'] = prediction_package.model_dump(exclude_none=True)
        if error_msg:
            self.final_db_results['status_message'] = f"Inference failed: {error_msg}"
        else:
            self.final_db_results['status_message'] = f"Inference successful. Commit prediction: {commit_prediction}."
        logger.info(f"InferenceJobHandler {self.job_id}: Aggregated inference result prepared.")


    # --- Override run_job to accept features ---
    def run_job(self, features_df: pd.DataFrame) -> Dict:
        """
        Executes the Inference job pipeline, accepting features DataFrame.
        """
        final_status = JobStatusEnum.FAILED
        final_db_status = JobStatusEnum.FAILED
        status_message = "Job processing started but did not complete."
        task_was_ignored = False
        self.final_db_results = {'job_id': self.job_id}

        try:
            with get_sync_db_session() as session:
                self.current_session = session
                # Step 1: Load Job Details (already done in base __init__ conceptually, but run here)
                # No need to update progress here, predict task updates state
                self._load_job_details(session) # Sets self.job_db_record, status to RUNNING

                # Step 2: Create Strategy (Load Model)
                self.model_strategy = self._create_strategy()
                if self.model_strategy is None:
                     raise RuntimeError("Failed to create or load model strategy.")

                # Step 3: Prepare Data (using passed features)
                prepared_data_package = self._prepare_data(features_df)

                # Step 4: Execute Core Task (Prediction)
                ml_result_package = self._execute_core_ml_task(prepared_data_package)

                # Step 5: Process & Prepare Final Results
                self._prepare_final_results(ml_result_package)

                # --- Step 6: Set Final Success Status & Commit Results ---
                # Check if _prepare_final_results indicated an error
                prediction_package_dict = self.final_db_results.get('prediction_result', {})
                if prediction_package_dict.get('error'):
                     final_status = JobStatusEnum.FAILED
                     final_db_status = JobStatusEnum.FAILED
                     status_message = self.final_db_results.get('status_message', "Prediction failed during result processing.")
                     logger.error(f"InferenceJobHandler {self.job_id}: Prediction failed during result prep: {prediction_package_dict.get('error')}")
                     # Re-raise or handle? Let's commit the FAILED state.
                else:
                     final_status = JobStatusEnum.SUCCESS
                     final_db_status = JobStatusEnum.SUCCESS
                     status_message = self.final_db_results.get('status_message', "Prediction completed successfully.")
                     self.final_db_results['status'] = 'SUCCESS'

                logger.info(f"InferenceJobHandler {self.job_id}: Committing final prediction results to DB (Status: {final_db_status.value})...")
                job_db_service.update_job_completion(
                    session, self.job_id, self.job_type_name.lower(), final_db_status, status_message, self.final_db_results
                )
                session.commit()

            logger.info(f"InferenceJobHandler {self.job_id}: Prediction job finished with status {final_db_status.value}.")
            # Return only the prediction_result part on success/failure handled here
            return self.final_db_results.get('prediction_result', {}) # Return the result package
        
        except Terminated as e:
            final_status = JobStatusEnum.REVOKED
            final_db_status = JobStatusEnum.FAILED
            status_message = "Job terminated by request."
            logger.warning(f"Task {self.task.request.id if self.task else 'N/A'}: {status_message}", exc_info=False)
            raise # Re-raise for Celery

        except Ignore as e:
             status_message = f"Job ignored: {e}"
             task_was_ignored = True
             logger.info(f"Task {self.task.request.id if self.task else 'N/A'}: {status_message}", exc_info=False)
             raise # Re-raise for Celery

        except Reject as e: # Handle reject from internal steps
             status_message = f"Job rejected: {e}"
             final_db_status = JobStatusEnum.FAILED
             logger.error(f"Task {self.task.request.id if self.task else 'N/A'}: {status_message}", exc_info=False)
             # DB status should be updated where Reject was raised
             raise # Re-raise

        except Exception as e:
            final_db_status = JobStatusEnum.FAILED
            status_message = f"Job failed: {type(e).__name__}: {e}"
            detailed_error = f"{status_message}\n{traceback.format_exc()}"
            logger.critical(f"Task {self.task.request.id if self.task else 'N/A'}: {detailed_error}", exc_info=False)
            self.final_db_results['error'] = detailed_error # Store error info

            raise # Re-raise exception to ensure Celery marks task as FAILURE

        finally:
             if self.current_session and not task_was_ignored:
                  try:
                      logger.info(f"InferenceJobHandler {self.job_id}: Attempting final DB status update in finally block to {final_db_status.value}")
                      # Use a new session just in case the old one is bad
                      with get_sync_db_session() as final_session:
                          # results dict might contain prediction_result even on failure
                          job_db_service.update_job_completion(
                               final_session, self.job_id, self.job_type_name.lower(), final_db_status, status_message, self.final_db_results
                          )
                          final_session.commit()
                  except Exception as db_err:
                      logger.critical(f"Task {self.task.request.id if self.task else 'N/A'}: CRITICAL - Failed final DB status update for Job {self.job_id} in finally: {db_err}", exc_info=True)
                      