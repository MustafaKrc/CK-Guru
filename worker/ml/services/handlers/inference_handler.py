# worker/ml/services/handlers/inference_handler.py
import logging
from typing import Any, Tuple, Dict, Optional
from celery import Task
import pandas as pd
from sqlalchemy.orm import Session
from services.factories.strategy_factory import create_model_strategy

from .base_handler import BaseMLJobHandler
from ..strategies.base_strategy import BaseModelStrategy
from shared.db.models import InferenceJob, MLModel # Import specific job and related models

logger = logging.getLogger(__name__)

class InferenceJobHandler(BaseMLJobHandler):
    """Handles the execution of inference jobs."""

    def __init__(self, job_id: int, task_instance: Task):
        super().__init__(job_id, task_instance)
        # Specific attributes for inference
        self.input_reference: Dict[str, Any] = {}
        self.ml_model_id: Optional[int] = None

    @property
    def job_type_name(self) -> str:
        return 'InferenceJob'

    @property
    def job_model_class(self) -> type:
        return InferenceJob

    def _load_job_details(self, session: Session):
        """Loads inference job details and the associated model ID."""
        # Use base method first, then extract inference-specific fields
        super()._load_job_details(session) # Loads job_db_record, sets RUNNING status, commits

        # Now extract inference-specific info
        self.input_reference = self.job_db_record.input_reference if isinstance(self.job_db_record.input_reference, dict) else {}
        self.ml_model_id = self.job_db_record.ml_model_id
        if self.ml_model_id is None:
            raise ValueError(f"ml_model_id is missing from InferenceJob record {self.job_id}")
        logger.info(f"Inference job details loaded: Model ID = {self.ml_model_id}, Input Ref = {str(self.input_reference)[:100]}...")


    def _load_data(self, session: Session) -> pd.DataFrame:
        """
        Loads or prepares the input data based on the `input_reference`.
        This step doesn't use `dataset_id` like training/HP search.
        """
        logger.info(f"Preparing input data from reference: {str(self.input_reference)[:100]}...")

        # --- TODO: Implement robust input handling based on expected formats ---
        # Example 1: Direct features in the reference
        if isinstance(self.input_reference, dict) and 'features' in self.input_reference:
            # Expect 'features' to be a dict {feature_name: value}
            features_dict = self.input_reference['features']
            if not isinstance(features_dict, dict):
                raise ValueError("input_reference['features'] must be a dictionary.")
            # Convert single instance dict to DataFrame
            input_df = pd.DataFrame([features_dict])
            logger.info(f"Prepared DataFrame from feature dictionary, shape: {input_df.shape}")
            return input_df

        # Example 2: Reference to data in S3 (needs implementation)
        # elif isinstance(self.input_reference, dict) and 's3_path' in self.input_reference:
        #     s3_path = self.input_reference['s3_path']
        #     logger.info(f"Loading input data from S3: {s3_path}")
        #     try:
        #         input_df = pd.read_parquet(s3_path, storage_options=settings.s3_storage_options)
        #         if input_df.empty: raise ValueError("Loaded input data from S3 is empty.")
        #         return input_df
        #     except Exception as e:
        #         raise IOError(f"Failed to load input data from {s3_path}: {e}") from e

        # Example 3: Commit hash requiring feature extraction (complex, needs separate service)
        # elif isinstance(self.input_reference, dict) and 'commit_hash' in self.input_reference:
        #     # Call a feature extraction service/logic here
        #     raise NotImplementedError("Feature extraction from commit hash not yet implemented.")

        else:
            raise ValueError(f"Unsupported input_reference format for inference: {self.input_reference}")

    def _prepare_data(self, data: pd.DataFrame) -> Any:
        """
        Applies necessary preprocessing for inference.
        For inference, we typically only return the features (X).
        """
        # --- TODO: Add preprocessing steps if required ---
        # This might involve scaling, ensuring column order matches training, etc.
        # Ideally, preprocessing steps are part of the saved model (e.g., sklearn Pipeline)
        # If not, they need to be loaded/replicated here based on the loaded model.
        logger.info("Preparing data for prediction (applying model-specific preprocessing if needed)...")

        # Example: Ensure column order matches model expectation (if known)
        # expected_features = self.model_strategy.get_feature_names() # Requires strategy method
        # X = data[expected_features]

        # For now, assume data loaded by _load_data is ready or model handles preprocessing
        X = data.fillna(0) # Basic NaN handling example
        return X # Return only the features DataFrame

    def _create_strategy(self) -> Optional[BaseModelStrategy]:
        """Loads the specified ML model artifact into the appropriate strategy."""
        session = self.current_session
        if not session: raise RuntimeError("DB Session not available in _create_strategy")
        if self.ml_model_id is None: raise ValueError("ml_model_id not set.")

        logger.info(f"Fetching model record for ID: {self.ml_model_id}")
        model_record = session.get(MLModel, self.ml_model_id)
        if not model_record:
            raise ValueError(f"MLModel record {self.ml_model_id} not found.")
        if not model_record.s3_artifact_path:
            raise ValueError(f"MLModel {self.ml_model_id} does not have a saved artifact path.")

        model_type = model_record.model_type
        artifact_path = model_record.s3_artifact_path

        logger.info(f"Creating strategy for model type '{model_type}' and loading artifact {artifact_path}")
        # Create strategy instance - config might be empty if predict doesn't need it
        strategy = create_model_strategy(model_type, {}, {}) # Pass empty configs for inference
        strategy.load_model(artifact_path) # Load the actual model object
        logger.info("Model loaded into strategy successfully.")
        return strategy

    def _execute_core_ml_task(self, prepared_data: Any) -> Dict[str, Any]:
        """Executes prediction using the loaded model strategy."""
        # prepared_data is the features DataFrame (X) in this case
        X_inference = prepared_data
        if self.model_strategy is None:
            raise RuntimeError("Model strategy was not created or loaded.")

        logger.info(f"Executing inference via strategy: {self.model_strategy.__class__.__name__}")
        prediction_result = self.model_strategy.predict(X_inference) # Returns dict e.g. {'predictions': [...]}
        logger.info(f"Inference execution complete. Result snippet: {str(prediction_result)[:200]}...")
        return prediction_result # Should be JSON-serializable

    def _prepare_final_results(self, ml_result: Any):
        """Stores the prediction result to be updated in the DB."""
        # ml_result is the prediction dictionary from the strategy
        logger.info("Storing prediction results for DB update...")
        if not isinstance(ml_result, dict):
             logger.warning(f"Prediction result is not a dictionary: {type(ml_result)}. Storing as is.")
        # Store the entire result dict to be saved in the job record
        self.final_db_results['prediction_result'] = ml_result
        self.final_db_results['status_message'] = "Inference successful." # Set success message