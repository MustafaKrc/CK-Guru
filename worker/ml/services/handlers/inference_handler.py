# worker/ml/services/handlers/inference_handler.py
import logging
from typing import Any, Tuple, Dict, Optional
from celery import Task
import numpy as np
import pandas as pd
from sklearn.exceptions import NotFittedError
from sqlalchemy.orm import Session

from .base_handler import BaseMLJobHandler
from ..factories.strategy_factory import create_model_strategy
from ..strategies.base_strategy import BaseModelStrategy
from shared.db.models import InferenceJob, MLModel
from shared import schemas
from shared.core.config import settings
from .. import feature_db_service
from .. import model_db_service
from .. import job_db_service


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper()) # Use settings level

class InferenceJobHandler(BaseMLJobHandler):
    """Handles the execution of inference jobs."""

    def __init__(self, job_id: int, task_instance: Task):
        super().__init__(job_id, task_instance)
        self.input_reference: Dict[str, Any] = {}
        self.ml_model_id: Optional[int] = None
        self.target_commit_hash: Optional[str] = None # Store commit hash
        self.repo_id: Optional[int] = None # Store repo id

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
        self.target_commit_hash = self.input_reference.get('commit_hash')
        self.repo_id = self.input_reference.get('repo_id')

        if self.ml_model_id is None:
            raise ValueError(f"ml_model_id is missing from InferenceJob record {self.job_id}")
        if self.target_commit_hash is None:
            raise ValueError(f"commit_hash is missing from input_reference in InferenceJob {self.job_id}")
        if self.repo_id is None:
             raise ValueError(f"repo_id is missing from input_reference in InferenceJob {self.job_id}")

        logger.info(f"InferenceJob {self.job_id} details loaded: Model={self.ml_model_id}, Repo={self.repo_id}, Commit={self.target_commit_hash[:7]}")


    def _load_data(self, session: Session) -> pd.DataFrame:
        """Loads features for the target commit hash from the database."""
        if self.target_commit_hash is None or self.repo_id is None:
            raise RuntimeError("Commit hash or repo ID not available for loading features.")

        logger.info(f"Loading features from DB for Repo={self.repo_id}, Commit={self.target_commit_hash[:7]}...")

        # Use the dedicated feature service function
        features_df = feature_db_service.get_features_for_commit(
            session=session,
            repo_id=self.repo_id,
            commit_hash=self.target_commit_hash
        )

        if features_df is None or features_df.empty:
            # Handle case where features couldn't be found or constructed
            raise ValueError(f"Failed to load features from DB for commit {self.target_commit_hash[:7]}. Check if feature extraction completed successfully.")

        logger.info(f"Features loaded successfully, shape: {features_df.shape}")
        return features_df # Return the single-row DataFrame


    def _prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Validates and prepares the potentially multi-row feature DataFrame for inference.
        Ensures columns match the order expected by the loaded model.
        Does NOT aggregate rows.
        """
        if self.model_strategy is None or self.model_strategy.model is None:
            raise RuntimeError("Model strategy or internal model not loaded before _prepare_data.")

        logger.info("Preparing potentially multi-row data for prediction using loaded model strategy...")

        # --- Get Expected Features from Strategy/Model ---
        expected_features: Optional[list[str]] = None
        try:
            # Prefer a dedicated method on the strategy if you implement one
            if hasattr(self.model_strategy, 'get_feature_names_out'): # Check Strategy first
                expected_features = self.model_strategy.get_feature_names_out()
            # Fallback for sklearn models if strategy doesn't provide it
            elif hasattr(self.model_strategy.model, 'feature_names_in_'):
                expected_features = self.model_strategy.model.feature_names_in_.tolist()

            if expected_features:
                logger.debug(f"Model expects features: {expected_features}")
            else:
                logger.warning("Could not determine expected features from model/strategy. Using input columns.")
                expected_features = data.columns.tolist() # Use input columns as fallback

        except NotFittedError:
             logger.warning("Model is loaded but reports as not fitted. Cannot get feature names. Using input columns.")
             expected_features = data.columns.tolist()
        except Exception as e:
            logger.warning(f"Error getting expected features from model: {e}. Using input columns.", exc_info=True)
            expected_features = data.columns.tolist()

        # --- Validate and Reorder Input Data ---
        missing_features = set(expected_features) - set(data.columns)
        if missing_features:
             raise ValueError(f"Loaded features are missing columns expected by the model: {sorted(list(missing_features))}")

        extra_features = set(data.columns) - set(expected_features)
        if extra_features:
            logger.warning(f"Input data has extra columns not expected by model (will be dropped): {sorted(list(extra_features))}")

        # Select and reorder columns to match model expectation
        X = data[expected_features].copy()

        # --- Apply Preprocessing (Example: Fill NaNs) ---
        # Ensure row-wise preprocessing is applied correctly if needed.
        if X.isnull().values.any():
            logger.warning("Input data contains NaN values. Applying simple fillna(0). Ensure this matches training preprocessing.")
            X = X.fillna(0) # Basic NaN handling - replace with appropriate strategy used during training

        logger.info(f"Data prepared for inference, final feature shape: {X.shape}")
        return X # Return the potentially multi-row DataFrame

    def _create_strategy(self) -> BaseModelStrategy:
        """Loads the specified ML model artifact into the appropriate strategy."""
        session = self.current_session
        if not session: raise RuntimeError("DB Session not available in _create_strategy")
        if self.ml_model_id is None: raise ValueError("ml_model_id not set.")

        logger.info(f"Fetching model record for ID: {self.ml_model_id}")
        model_record = session.get(MLModel, self.ml_model_id)
        if not model_record: raise ValueError(f"MLModel record {self.ml_model_id} not found.")
        if not model_record.s3_artifact_path: raise ValueError(f"MLModel {self.ml_model_id} has no artifact path.")

        model_type_str = model_record.model_type
        try:
            model_type_enum = schemas.ModelTypeEnum(model_type_str)
        except ValueError:
            raise ValueError(f"Model record {self.ml_model_id} has unsupported model_type '{model_type_str}'")

        artifact_path = model_record.s3_artifact_path

        logger.info(f"Creating strategy for model type '{model_type_enum.value}' and loading artifact {artifact_path}")
        strategy = create_model_strategy(model_type_enum, model_record.hyperparameters or {}, self.job_config) # Pass HPs too
        strategy.load_model(artifact_path)
        logger.info("Model loaded into strategy successfully.")
        return strategy

    def _prepare_data(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]: # Return tuple
        """
        Separates features and identifiers, validates features, and returns both.
        """
        if self.model_strategy is None or self.model_strategy.model is None:
            raise RuntimeError("Model strategy or internal model not loaded before _prepare_data.")

        logger.info("Separating identifiers and preparing features for prediction...")

        # --- Define Identifier Columns ---
        # These columns are present in the input `data` DataFrame
        identifier_cols = ['file', 'class_name'] # Adjust if needed (e.g., use db model attribute names)
        missing_ids = [col for col in identifier_cols if col not in data.columns]
        if missing_ids:
             # If these are crucial for reporting, raise an error.
             raise ValueError(f"Input data from DB is missing required identifier columns: {missing_ids}")
        identifiers_df = data[identifier_cols].copy()

        # --- Get Expected Features ---
        expected_features: Optional[list[str]] = None
        try:
            if hasattr(self.model_strategy, 'get_feature_names_out'):
                expected_features = self.model_strategy.get_feature_names_out()
            elif hasattr(self.model_strategy.model, 'feature_names_in_'):
                expected_features = self.model_strategy.model.feature_names_in_.tolist()

            if not expected_features: # If still None after trying
                logger.warning("Could not determine expected features from model/strategy. Using all non-identifier numeric columns.")
                # Fallback: Use all numeric columns not in identifier_cols
                expected_features = data.select_dtypes(include=np.number).columns.difference(identifier_cols).tolist()
                if not expected_features: raise ValueError("No numeric feature columns found after excluding identifiers.")
            logger.debug(f"Model expects features: {expected_features}")

        except Exception as e:
            logger.error(f"Error determining expected features: {e}. Cannot proceed.", exc_info=True)
            raise ValueError(f"Failed to determine expected model features: {e}") from e


        # --- Validate, Select, Preprocess Features ---
        missing_features = set(expected_features) - set(data.columns)
        if missing_features:
             raise ValueError(f"Loaded features are missing columns expected by the model: {sorted(list(missing_features))}")

        extra_features = set(data.columns.difference(identifier_cols)) - set(expected_features)
        if extra_features:
            logger.warning(f"Input data has extra columns not expected by model (will be dropped): {sorted(list(extra_features))}")

        X = data[expected_features].copy() # Select only feature columns

        if X.isnull().values.any():
            logger.warning("Feature data contains NaN values. Applying simple fillna(0). Ensure this matches training preprocessing.")
            X = X.fillna(0) # Basic NaN handling

        logger.info(f"Data prepared for inference. Features shape: {X.shape}, Identifiers shape: {identifiers_df.shape}")

        # --- Return Features and Identifiers ---
        return X, identifiers_df

    def _execute_core_ml_task(self, prepared_data_package: Tuple[pd.DataFrame, pd.DataFrame]) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """Executes prediction and returns results along with identifiers."""
        X_inference, identifiers_df = prepared_data_package # Unpack tuple
        if self.model_strategy is None:
            raise RuntimeError("Model strategy was not created or loaded.")

        logger.info(f"Executing inference via strategy: {self.model_strategy.__class__.__name__} on {X_inference.shape[0]} instances.")
        prediction_result = self.model_strategy.predict(X_inference) # Returns dict e.g. {'predictions': [...]}
        logger.info(f"Inference execution complete.")

        # Return prediction results AND the corresponding identifiers
        return prediction_result, identifiers_df

    # Modify _prepare_final_results signature and implementation
    def _prepare_final_results(self, ml_result_package: Tuple[Dict[str, Any], pd.DataFrame]):
        """
        Processes the prediction results and identifiers, aggregates them,
        and stores detailed info in self.final_db_results.
        """
        ml_result, identifiers_df = ml_result_package # Unpack tuple
        logger.info("Aggregating row-level predictions with identifiers into commit-level result...")

        row_predictions = ml_result.get('predictions')
        row_probabilities = ml_result.get('probabilities') # List of lists [[P(0), P(1)], ...]

        if row_predictions is None or len(row_predictions) != len(identifiers_df):
            logger.error("Prediction results are missing or length mismatch with identifiers.")
            self.final_db_results['prediction_result'] = {"error": "Prediction length mismatch or missing."}
            self.final_db_results['status_message'] = "Inference failed: Prediction results invalid."
            return

        commit_prediction = 0
        max_bug_probability = 0.0
        detailed_results = []

        try:
            for i in range(len(identifiers_df)):
                prediction = row_predictions[i]
                # Safely get probability for class 1 (buggy)
                probability_class_1 = 0.0
                if row_probabilities and i < len(row_probabilities) and isinstance(row_probabilities[i], list) and len(row_probabilities[i]) > 1:
                     probability_class_1 = row_probabilities[i][1]

                # Update commit-level aggregates
                if prediction == 1:
                    commit_prediction = 1
                max_bug_probability = max(max_bug_probability, probability_class_1)

                # Append details for this row
                detailed_results.append({
                    "file": identifiers_df.iloc[i].get('file', 'N/A'),
                    "class": identifiers_df.iloc[i].get('class_name', 'N/A'), # Use class_name from identifier
                    "prediction": prediction,
                    "probability": round(probability_class_1, 4) # Store probability of being buggy
                })

            # Store the final aggregated and detailed result
            final_result_package = {
                "commit_prediction": commit_prediction,
                "max_bug_probability": round(max_bug_probability, 4),
                "num_files_analyzed": len(detailed_results),
                "details": detailed_results # Store the list of detailed results
            }
            self.final_db_results['prediction_result'] = final_result_package
            self.final_db_results['status_message'] = f"Inference successful. Commit prediction: {commit_prediction} (Max Prob: {max_bug_probability:.4f})."
            logger.info(f"Aggregated inference result with details prepared.")

        except Exception as e:
             logger.error(f"Error during prediction result aggregation/mapping: {e}", exc_info=True)
             self.final_db_results['prediction_result'] = {"error": f"Failed to process detailed results: {e}"}
             self.final_db_results['status_message'] = f"Inference failed during result processing: {e}"