# worker/ml/services/inference_service.py
import logging
from typing import Any, Dict, Optional, List

import pandas as pd
# Import ML library specific prediction functions if needed
# from sklearn.base import BaseEstimator

from .artifact_service import artifact_service # Use the shared instance

logger = logging.getLogger(__name__)
# logger.setLevel(settings.LOG_LEVEL.upper()) # Assuming settings accessible

class InferenceService:
    """Handles model loading and prediction generation."""

    def __init__(self, model_id: int, artifact_path: Optional[str]):
        self.model_id = model_id
        self.artifact_path = artifact_path
        self._model: Optional[Any] = None # Lazy-loaded model

    def _load_model(self):
        """Loads the model artifact from S3."""
        if self._model is not None:
            return # Already loaded

        if not self.artifact_path:
            logger.error(f"Cannot load model for inference: Artifact path is missing for model ID {self.model_id}.")
            raise ValueError(f"Missing artifact path for model ID {self.model_id}")

        logger.info(f"Loading model artifact from: {self.artifact_path}")
        self._model = artifact_service.load_artifact(self.artifact_path)

        if self._model is None:
            logger.error(f"Failed to load model artifact from {self.artifact_path}.")
            raise IOError(f"Failed to load model artifact for model ID {self.model_id}")

        logger.info(f"Model ID {self.model_id} loaded successfully.")

    def predict(self, input_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Generates predictions using the loaded model.

        Args:
            input_data: A Pandas DataFrame containing the features required by the model.

        Returns:
            A dictionary containing the predictions. Structure depends on the model
            (e.g., {'predictions': [0, 1, 0], 'probabilities': [[0.9, 0.1], ...]})
        """
        self._load_model() # Ensure model is loaded

        if self._model is None: # Check again after load attempt
             raise RuntimeError(f"Model ID {self.model_id} could not be loaded for prediction.")

        logger.info(f"Generating predictions for {len(input_data)} samples using model ID {self.model_id}.")

        # --- Preprocessing (if needed and not part of dataset) ---
        # Example: Ensure columns match training, scaling, etc.
        # This should ideally be minimal if datasets are well-prepared.
        # try:
        #    input_data = self._preprocess_input(input_data)
        # except Exception as e:
        #     logger.error(f"Error preprocessing input data for prediction: {e}", exc_info=True)
        #     raise

        # --- Prediction ---
        try:
            # Example for scikit-learn classifier
            if hasattr(self._model, 'predict'):
                predictions = self._model.predict(input_data).tolist() # Convert numpy array to list
                result = {'predictions': predictions}
                if hasattr(self._model, 'predict_proba'):
                     probabilities = self._model.predict_proba(input_data).tolist() # Convert numpy array to list
                     result['probabilities'] = probabilities
                return result
            else:
                 raise TypeError(f"Loaded model object (type: {type(self._model)}) does not have a 'predict' method.")

            # Add logic for other model types (PyTorch, TensorFlow) here
            # elif isinstance(self._model, torch.nn.Module):
            #     # PyTorch inference logic
            #     pass
        except Exception as e:
            logger.error(f"Error during prediction generation: {e}", exc_info=True)
            raise # Re-raise to fail the task

    # Optional: Add preprocessing method if needed
    # def _preprocess_input(self, data: pd.DataFrame) -> pd.DataFrame:
    #     # Apply necessary scaling, feature selection/ordering, etc.
    #     # Load scaler from artifact if needed
    #     logger.debug("Preprocessing input data for inference...")
    #     # ... implementation ...
    #     return processed_data