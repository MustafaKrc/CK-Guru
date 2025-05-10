# worker/ml/services/handlers/inference_handler.py
import logging
import traceback
from typing import Any, List, Tuple, Dict, Optional
import pandas as pd
import numpy as np

from .base_handler import BaseMLJobHandler
from ..factories.model_strategy_factory import create_model_strategy
from ..strategies.base_strategy import BaseModelStrategy

from shared.db.models import InferenceJob, MLModel
from shared.schemas.enums import JobStatusEnum
from shared.schemas.inference_job import InferenceResultPackage # Use structured result
from shared.schemas.xai import FilePredictionDetail
from shared import schemas

# Import Concrete types for type hints/injection
from shared.services import JobStatusUpdater
from shared.repositories import ModelRepository, MLFeatureRepository, InferenceJobRepository, XaiResultRepository
from services.artifact_service import ArtifactService
# Import others needed by base class init

from shared.core.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class InferenceJobHandler(BaseMLJobHandler):
    """Handles the execution of inference prediction jobs using injected dependencies."""

    # Inject specific repositories needed
    def __init__(self, job_id: int, task_instance: Any, *,
                 status_updater: JobStatusUpdater,
                 model_repo: ModelRepository,
                 xai_repo: XaiResultRepository, 
                 feature_repo: MLFeatureRepository,
                 artifact_service: ArtifactService,
                 inference_job_repo: InferenceJobRepository,
                 **kwargs):
        super().__init__(job_id, task_instance,
                         status_updater=status_updater,
                         model_repo=model_repo,
                         xai_repo=xai_repo,
                         feature_repo=feature_repo, # Store feature_repo
                         artifact_service=artifact_service)
        self.inference_job_repo = inference_job_repo # Store inference job repo
        self.input_reference: Dict[str, Any] = {}
        self.ml_model_id: Optional[int] = None
        self.model_strategy: Optional[BaseModelStrategy] = None # To store the strategy

    @property
    def job_type_name(self) -> str:
        return 'InferenceJob'

    @property
    def job_model_class(self) -> type:
        return InferenceJob

    def _load_and_validate_job_details(self) -> bool:
        """Loads inference job record and ensures model exists."""
        try:
            job_record = self.inference_job_repo.get_by_id(self.job_id)
            if not job_record:
                logger.error(f"{self.job_type_name} {self.job_id} not found.")
                self.status_updater.update_job_completion(self.job_id, self.job_model_class, JobStatusEnum.FAILED, f"Job record {self.job_id} not found.")
                return False

            if job_record.status not in [JobStatusEnum.PENDING, JobStatusEnum.RUNNING]:
                logger.warning(f"Job {self.job_id} terminal state {job_record.status.value}. Skipping.")
                return False

            self.job_db_record = job_record
            self.input_reference = dict(job_record.input_reference or {})
            self.ml_model_id = job_record.ml_model_id

            if not self.ml_model_id: raise ValueError("ml_model_id missing.")
            if not self.input_reference.get('commit_hash') or not self.input_reference.get('repo_id'):
                raise ValueError(f"input_reference incomplete: {self.input_reference}")

            model_record = self.model_repo.get_by_id(self.ml_model_id)
            if not model_record: raise ValueError(f"MLModel {self.ml_model_id} not found.")
            if not model_record.s3_artifact_path: raise ValueError(f"MLModel {self.ml_model_id} artifact path missing.")

            # Update status to RUNNING
            updated = self.status_updater.update_job_start(
                job_id=self.job_id, job_type=self.job_model_class, task_id=self.task.request.id
            )
            if not updated: raise RuntimeError("Failed status update to RUNNING.")

            logger.info(f"{self.job_type_name} {self.job_id} details loaded, status RUNNING.")
            return True

        except ValueError as ve:
             logger.error(f"Validation failed Job {self.job_id}: {ve}")
             self.status_updater.update_job_completion(
                 self.job_id, self.job_model_class, JobStatusEnum.FAILED, str(ve)
             )
             return False
        except Exception as e:
             logger.error(f"Error loading job details {self.job_id}: {e}", exc_info=True)
             try:
                  self.status_updater.update_job_completion(
                       self.job_id, self.job_model_class, JobStatusEnum.FAILED, f"Failed load: {e}"
                  )
             except Exception as db_err: logger.error(f"Failed DB update: {db_err}")
             return False

    def _load_model_strategy(self) -> BaseModelStrategy:
         """Loads the model and creates the strategy."""
         if self.ml_model_id is None: raise ValueError("ml_model_id not set.")

         model_record = self.model_repo.get_by_id(self.ml_model_id) 
         if not model_record or not model_record.s3_artifact_path:
             raise ValueError(f"MLModel {self.ml_model_id} or path missing.")

         try: model_type_enum = schemas.ModelTypeEnum(model_record.model_type)
         except ValueError: raise ValueError(f"Unsupported model_type '{model_record.model_type}'")

         artifact_path = model_record.s3_artifact_path
         self._update_progress("Loading model artifact...", 25)
         # Use injected artifact_service
         strategy = create_model_strategy(model_type_enum, model_record.hyperparameters or {}, {}, self.artifact_service)
         strategy.load_model(artifact_path) # Strategy uses self.artifact_service internally
         self.model_strategy = strategy # Store strategy instance
         logger.info(f"Model {self.ml_model_id} loaded into strategy.")
         return strategy

    def _get_features(self) -> pd.DataFrame:
         """Gets features using the injected feature repository."""
         repo_id = self.input_reference.get('repo_id')
         commit_hash = self.input_reference.get('commit_hash')
         if not repo_id or not commit_hash: raise ValueError("repo_id/commit_hash missing in input_ref.")

         self._update_progress("Retrieving features...", 10)
         # Use injected feature_repo with its own session scope
         features_df = self.feature_repo.get_features_for_commit(repo_id, commit_hash) # Needs session factory access
         if features_df is None or features_df.empty:
             raise ValueError(f"Failed to retrieve features for Repo={repo_id}, Commit={commit_hash[:7]}.")
         logger.info(f"Features retrieved, shape: {features_df.shape}")
         return features_df

    def _prepare_data(self, features_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prepares data for inference (separates features/identifiers)."""
        # --- Logic remains the same as previous implementation ---
        if self.model_strategy is None or self.model_strategy.model is None:
            raise RuntimeError("Model strategy/model not loaded.")
        if features_df is None or features_df.empty:
             raise ValueError("Empty features DataFrame.")

        logger.info(f"Preparing data for inference ({features_df.shape})...")
        identifier_cols = ['file', 'class_name'] # Original DB names
        missing_ids = [c for c in identifier_cols if c not in features_df.columns]
        if missing_ids: raise ValueError(f"Missing identifier columns: {missing_ids}")
        identifiers_df = features_df[identifier_cols].copy()

        expected_features = []
        try:
            if hasattr(self.model_strategy.model, 'feature_names_in_'):
                expected_features = self.model_strategy.model.feature_names_in_.tolist()
            if not expected_features:
                logger.warning("Inferring features from data.")
                expected_features = features_df.select_dtypes(include=np.number).columns.difference(identifier_cols).tolist()
                if not expected_features: raise ValueError("No numeric features found.")
        except Exception as e: raise ValueError(f"Failed get expected features: {e}") from e

        missing_features = set(expected_features) - set(features_df.columns)
        if missing_features: raise ValueError(f"Missing columns expected by model: {sorted(list(missing_features))}")

        X = features_df[expected_features].copy().fillna(0) # Simple fillna
        logger.info(f"Data prepared. Features: {X.shape}, Identifiers: {identifiers_df.shape}")
        return X, identifiers_df

    def _execute_prediction(self, X_inference: pd.DataFrame) -> Dict[str, Any]:
         """Executes prediction using the loaded strategy."""
         if self.model_strategy is None: raise RuntimeError("Model strategy not loaded.")
         self._update_progress("Executing prediction...", 45)
         prediction_result = self.model_strategy.predict(X_inference)
         logger.info("Prediction execution complete.")
         return prediction_result

    def _package_results(self, ml_result: Dict[str, Any], identifiers_df: pd.DataFrame) -> Tuple[Dict, Optional[str]]:
         """Packages prediction results into the InferenceResultPackage structure."""
         # --- Logic remains the same as previous implementation ---
         logger.info("Aggregating prediction results...")
         row_predictions = ml_result.get('predictions')
         row_probabilities = ml_result.get('probabilities')
         error_msg = None; commit_prediction = -1; max_bug_probability = -1.0
         detailed_results: List[FilePredictionDetail] = []
         num_files_analyzed = len(identifiers_df) if identifiers_df is not None else 0

         if row_predictions is None or len(row_predictions) != num_files_analyzed:
             error_msg = "Prediction results missing or length mismatch."
         else:
             commit_prediction = 0; max_bug_probability = 0.0
             try:
                 for i in range(num_files_analyzed):
                     prediction = int(row_predictions[i])
                     prob_class_1 = 0.0
                     if row_probabilities and i < len(row_probabilities):
                         probs = row_probabilities[i]
                         if isinstance(probs, (list, np.ndarray)) and len(probs) > 1: prob_class_1 = float(probs[1])
                         elif isinstance(probs, (float, np.float_)): prob_class_1 = float(probs) if prediction == 1 else (1.0-float(probs))
                     if prediction == 1: commit_prediction = 1
                     max_bug_probability = max(max_bug_probability, prob_class_1)
                     detailed_results.append(FilePredictionDetail(
                         file=identifiers_df.iloc[i].get('file'),
                         class_name=identifiers_df.iloc[i].get('class_name'),
                         prediction=prediction, probability=round(prob_class_1, 4)))
             except Exception as e:
                  logger.error(f"Error processing results: {e}", exc_info=True)
                  error_msg = f"Failed process results: {e}"; commit_prediction = -1; max_bug_probability = -1.0; detailed_results = []; num_files_analyzed = 0

         prediction_package = InferenceResultPackage(
             commit_prediction=commit_prediction, max_bug_probability=round(max_bug_probability, 4) if max_bug_probability >= 0 else -1.0,
             num_files_analyzed=num_files_analyzed, details=detailed_results if not error_msg else None, error=error_msg)
         logger.info("Inference result packaged.")
         return prediction_package.model_dump(exclude_none=True), error_msg # Return dict and error

    def process_job(self) -> Dict:
        """Orchestrates the inference job execution."""
        final_status = JobStatusEnum.FAILED
        status_message = "Processing failed"
        # Initialize result package structure with default error state
        results_payload = {
            'job_id': self.job_id,
            'status': JobStatusEnum.FAILED,
            'prediction_result': InferenceResultPackage(commit_prediction=-1, max_bug_probability=-1.0, num_files_analyzed=0, error="Handler initialization failed").model_dump()
        }

        try:
            # Step 1: Load Job Details & Validate & Set Running Status
            if not self._load_and_validate_job_details():
                 results_payload['message'] = f"Job {self.job_id} skipped or failed loading."
                 results_payload['status'] = JobStatusEnum.SKIPPED if self.job_db_record and self.job_db_record.status != JobStatusEnum.FAILED else JobStatusEnum.FAILED
                 return results_payload

            # Step 2: Load Model Strategy
            self._load_model_strategy() # Stores strategy in self.model_strategy

            # Step 3: Get Features
            features_df = self._get_features()

            # Step 4: Prepare Data
            self._update_progress("Preparing data...", 35)
            X_inference, identifiers_df = self._prepare_data(features_df)

            # Step 5: Execute Prediction
            ml_result = self._execute_prediction(X_inference)

            # Step 6: Package Results
            self._update_progress("Packaging results...", 90)
            packaged_result_dict, error_msg = self._package_results(ml_result, identifiers_df)
            results_payload['prediction_result'] = packaged_result_dict # Store packaged result dict

            # Determine final status based on packaging result
            if error_msg:
                 final_status = JobStatusEnum.FAILED
                 status_message = f"Prediction failed: {error_msg}"
                 results_payload['status'] = JobStatusEnum.FAILED
                 results_payload['error'] = status_message
            else:
                 final_status = JobStatusEnum.SUCCESS
                 status_message = f"Inference successful. Commit prediction: {packaged_result_dict.get('commit_prediction')}."
                 results_payload['status'] = JobStatusEnum.SUCCESS
                 results_payload['message'] = status_message

        except Exception as e:
            final_status = JobStatusEnum.FAILED
            status_message = f"Job failed: {type(e).__name__}: {e}"
            logger.critical(f"Inference Job {self.job_id} failed: {status_message}", exc_info=True)
            # Update result payload with error
            results_payload['status'] = JobStatusEnum.FAILED
            results_payload['error'] = status_message
            # Ensure prediction_result reflects failure if error happened before packaging
            if 'prediction_result' not in results_payload or not results_payload['prediction_result'].get('error'):
                 results_payload['prediction_result'] = InferenceResultPackage(commit_prediction=-1, max_bug_probability=-1.0, num_files_analyzed=0, error=status_message[:500]).model_dump()


        finally:
            # --- Final DB Status Update ---
            logger.info(f"Attempting final DB status update Job {self.job_id} to {final_status.value}")
            # Pass the potentially updated results_payload['prediction_result'] dict
            completion_results = {'prediction_result': results_payload.get('prediction_result')}
            try:
                 self.status_updater.update_job_completion(
                      job_id=self.job_id, job_type=self.job_model_class, status=final_status,
                      message=status_message, results=completion_results
                 )
            except Exception as db_err:
                  logger.critical(f"CRITICAL: Failed final DB update Job {self.job_id}: {db_err}", exc_info=True)

        return results_payload # Return payload for Celery task
    