# worker/ml/services/handlers/xai_explanation_handler.py
import logging
import traceback
from typing import Dict, Optional, Any, Tuple

import pandas as pd
import numpy as np # Import numpy for checking feature types
from celery import Task
from celery.exceptions import Ignore, Reject

# Import Concrete Repositories and Services needed
from shared.repositories import XaiResultRepository, ModelRepository, MLFeatureRepository, InferenceJobRepository, DatasetRepository
from shared.services import JobStatusUpdater 
from services.artifact_service import ArtifactService # Note: This is the CONCRETE class

# Import DB Models and Enums
from shared.db.models import InferenceJob, MLModel, XAIResult, Dataset
from shared.schemas.enums import XAIStatusEnum, XAITypeEnum

# Import XAI Factory and helpers
from services.factories.xai_strategy_factory import XAIStrategyFactory
from services.strategies.base_xai_strategy import BaseXAIStrategy


logger = logging.getLogger(__name__)

class XAIExplanationHandler:
    """Handles the generation of a specific XAI explanation."""

    def __init__(
        self,
        xai_result_id: int,
        task_instance: Task,
        # --- Inject Dependencies ---
        xai_repo: XaiResultRepository,
        model_repo: ModelRepository,
        feature_repo: MLFeatureRepository,
        artifact_service: ArtifactService,
        inference_job_repo: InferenceJobRepository,
        dataset_repo: DatasetRepository,
    ):
        self.xai_result_id = xai_result_id
        self.task = task_instance
        self.xai_repo = xai_repo
        self.model_repo = model_repo
        self.feature_repo = feature_repo
        self.artifact_service = artifact_service 
        self.inference_job_repo = inference_job_repo
        self.dataset_repo = dataset_repo
        self.model: Optional[Any] = None # Initialize model attribute
        logger.debug(f"Initialized XAIExplanationHandler for Result ID {xai_result_id}")


    def _prepare_data_for_xai(self, features_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Separates features and identifiers, validates features. Uses self.model."""
        if self.model is None:
            raise RuntimeError("Model has not been loaded before preparing data for XAI.")
        if features_df is None or features_df.empty:
            raise ValueError("Cannot prepare empty features DataFrame.")

        logger.debug(f"Preparing data for XAI (Initial shape: {features_df.shape})...")
        identifier_cols = ['file', 'class_name'] # Original DB names
        available_identifiers = [col for col in identifier_cols if col in features_df.columns]
        if not available_identifiers:
             # If even 'file' is missing, something is wrong upstream
             raise ValueError(f"Input features missing required identifier columns (at least 'file' or 'class_name').")
        identifiers_df = features_df[available_identifiers].copy()

        expected_features = []
        # Attempt to get expected features from the loaded model
        if hasattr(self.model, 'feature_names_in_'):
            expected_features = self.model.feature_names_in_.tolist()
        elif hasattr(self.model, 'feature_names_'): # Some models might use this
             expected_features = self.model.feature_names_
        elif hasattr(self.model, 'feature_importances_'): # Check length as fallback
             num_features_expected = len(self.model.feature_importances_)
             # Try to infer from input, excluding identifiers
             potential_features = features_df.columns.difference(available_identifiers).tolist()
             if len(potential_features) == num_features_expected:
                  expected_features = potential_features
                  logger.warning(f"Inferred {num_features_expected} expected features from data columns based on feature_importances_ length.")
             else:
                  logger.warning("Could not reliably determine expected features from model. Trying all numeric non-identifiers.")


        if not expected_features:
            # Fallback: Use all numeric columns excluding identifiers
            expected_features = features_df.select_dtypes(include=np.number).columns.difference(available_identifiers).tolist()
            logger.warning("Using all numeric, non-identifier columns as features.")
            if not expected_features:
                raise ValueError("No numeric feature columns found after attempting inference.")

        missing_features = set(expected_features) - set(features_df.columns)
        if missing_features:
            raise ValueError(f"Features DataFrame missing columns expected by model: {sorted(list(missing_features))}")

        logger.debug(f"Using features for XAI: {expected_features}")
        X_inference = features_df[expected_features].copy()

        # Handle NaNs - Basic fillna(0) is often insufficient for XAI.
        # Consider more sophisticated imputation or strategy-specific handling.
        if X_inference.isnull().values.any():
            logger.warning("XAI input features contain NaN values. Applying simple fillna(0). Explanation quality may be affected.")
            X_inference = X_inference.fillna(0)

        return X_inference, identifiers_df

    def _load_background_data_for_xai(self, dataset_id: Optional[int], X_inference: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Loads background data. Uses self.artifact_service and provided session."""
        # Need concrete ArtifactService instance -> use self.artifact_service
        if not dataset_id:
            logger.warning("No training dataset ID linked. Using inference data sample for background.")
            # Ensure sampling doesn't fail on very small inference sets
            sample_n = min(100, len(X_inference)) if len(X_inference) > 0 else 0
            return X_inference.sample(n=sample_n, random_state=42) if sample_n > 0 else None

        dataset_record = self.dataset_repo.get_record(dataset_id)
        if not dataset_record:
            logger.warning(f"Dataset record {dataset_id} not found. Using inference data sample.")
            sample_n = min(100, len(X_inference)) if len(X_inference) > 0 else 0
            return X_inference.sample(n=sample_n, random_state=42) if sample_n > 0 else None

        background_path = dataset_record.background_data_path
        if not background_path:
            logger.warning(f"No background data path for dataset {dataset_id}. Using inference data sample.")
            sample_n = min(100, len(X_inference)) if len(X_inference) > 0 else 0
            return X_inference.sample(n=sample_n, random_state=42) if sample_n > 0 else None

        logger.info(f"Loading background data sample from: {background_path}")
        try:
            background_df = self.artifact_service.load_dataframe_artifact(background_path) # Use injected service
            if background_df is None or background_df.empty: 
                raise ValueError("Loaded background data empty.")
            
            target_column = dataset_record.config.get('target_column') if isinstance(dataset_record.config, dict) else None
            if target_column and target_column in background_df.columns:
                background_df = background_df.drop(columns=[target_column])

            logger.info(f"Loaded background data ({background_df.shape})")
            if background_df.isnull().values.any(): 
                logger.warning("Background data has NaNs. Filling with 0.")
                background_df = background_df.fillna(0)

            return background_df
        except Exception as e:
            logger.error(f"Failed load background data {background_path}: {e}", exc_info=True)
            logger.warning("Using inference data sample as fallback.")
            sample_n = min(100, len(X_inference)) if len(X_inference) > 0 else 0
            return X_inference.sample(n=sample_n, random_state=42) if sample_n > 0 else None

    def process_explanation(self) -> Optional[Dict]:
        task_id = self.task.request.id if self.task else "N/A"
        logger.info(f"Handler: Starting explanation generation for XAIResult ID {self.xai_result_id} (Task: {task_id})")
        final_status = XAIStatusEnum.FAILED; status_message = "Generation failed."; result_data_json: Optional[Dict] = None
        xai_record: Optional[XAIResult] = None

        try:
            # --- Initial XAI record load and validation using XaiResultRepository ---
            xai_record = self.xai_repo.get_xai_result_sync(self.xai_result_id)
            if not xai_record: raise Ignore(f"XAIResult {self.xai_result_id} not found.")
            if xai_record.status == XAIStatusEnum.RUNNING and xai_record.celery_task_id != task_id: raise Ignore("Already running.")
            if xai_record.status in [XAIStatusEnum.SUCCESS, XAIStatusEnum.FAILED, XAIStatusEnum.REVOKED]: raise Ignore("Already terminal.")

            # --- Load related records using their respective repositories ---
            inference_job = self.inference_job_repo.get_by_id(xai_record.inference_job_id)
            if not inference_job: raise ValueError("InferenceJob not found.")
            ml_model_record = self.model_repo.get_by_id(inference_job.ml_model_id)
            if not ml_model_record or not ml_model_record.s3_artifact_path: raise ValueError("MLModel/path not found.")

            input_ref = inference_job.input_reference if isinstance(inference_job.input_reference, dict) else {}
            repo_id = input_ref.get('repo_id'); commit_hash = input_ref.get('commit_hash')
            if not repo_id or not commit_hash: raise ValueError("Missing repo/commit info.")

            # --- Stage 1: Update XAI record to RUNNING (loading data) ---
            # This call handles its own session via xai_repo
            self.xai_repo.update_xai_result_sync(self.xai_result_id, XAIStatusEnum.RUNNING, "Loading model/data", task_id=task_id, is_start=True, commit=True)

            # --- Load Model & Features ---
            self.model = self.artifact_service.load_artifact(ml_model_record.s3_artifact_path)
            if not self.model: raise RuntimeError(f"Failed load model: {ml_model_record.s3_artifact_path}")
            features_df = self.feature_repo.get_features_for_commit(repo_id, commit_hash) # repo handles session
            if features_df is None or features_df.empty: raise ValueError("Failed get features.")

            X_inference, identifiers_df = self._prepare_data_for_xai(features_df)
            # For background data, we need session only if reading from Dataset table.
            # The method _load_background_data_for_xai now uses self.dataset_repo.
            background_data_df = self._load_background_data_for_xai(ml_model_record.dataset_id, X_inference)


            # --- Stage 2: Update XAI record to RUNNING (generating explanation) ---
            # This call handles its own session via xai_repo
            self.xai_repo.update_xai_result_sync(self.xai_result_id, XAIStatusEnum.RUNNING, "Generating explanation", commit=True)
            logger.info(f"Handler: XAIResult {self.xai_result_id} status updated to RUNNING (generating).")

            xai_type = xai_record.xai_type
            strategy: BaseXAIStrategy = XAIStrategyFactory.create(xai_type, self.model, background_data_df)
            logger.info(f"Handler: Executing strategy {strategy.__class__.__name__}")
            result_data_obj = strategy.explain(X_inference, identifiers_df)

            if result_data_obj:
                result_data_json = result_data_obj.model_dump(exclude_none=True, mode='json')
                final_status = XAIStatusEnum.SUCCESS
                status_message = f"{xai_type.value} explanation generated."
            else:
                final_status = XAIStatusEnum.FAILED
                status_message = f"{xai_type.value} generation returned no data or failed internally."

        except (Ignore, Reject) as e: logger.info(f"Handler: Ignoring/Rejecting task for XAIResult {self.xai_result_id}: {e}"); raise e
        except Exception as e:
            status_message = f"Generation failed: {type(e).__name__}: {e}"
            logger.critical(f"Handler: XAI generation failed for {self.xai_result_id}: {status_message}", exc_info=True)
            final_status = XAIStatusEnum.FAILED
        finally:
            logger.info(f"Handler: Attempting final DB update XAIResult {self.xai_result_id} to {final_status.value}")
            try:
                self.xai_repo.update_xai_result_sync(self.xai_result_id, final_status, status_message, result_data_json, commit=True)
            except Exception as db_err:
                logger.critical(f"CRITICAL: Failed final DB update for XAIResult {self.xai_result_id}: {db_err}", exc_info=True)
        return result_data_json