# worker/ml/services/handlers/inference_handler.py
import logging
from typing import Any, Dict, List, Optional, Tuple
import asyncio

import numpy as np
import pandas as pd

from services.artifact_service import ArtifactService
from shared.core.config import settings
from shared.db.models import InferenceJob
from shared.repositories import (
    InferenceJobRepository,
    MLFeatureRepository,
    ModelRepository,
    XaiResultRepository,
)
from shared.schemas.enums import JobStatusEnum, ModelTypeEnum
from shared.schemas.inference_job import InferenceResultPackage
from shared.schemas.xai import FilePredictionDetail
from shared.services import JobStatusUpdater

from ..factories.model_strategy_factory import create_model_strategy
from ..strategies.base_strategy import BaseModelStrategy
from .base_handler import BaseMLJobHandler

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class InferenceJobHandler(BaseMLJobHandler):
    """Handles the execution of inference prediction jobs using injected dependencies and strategies."""

    def __init__(
        self,
        job_id: int,
        task_instance: Any,
        *,
        status_updater: JobStatusUpdater,
        model_repo: ModelRepository,
        xai_repo: XaiResultRepository,
        feature_repo: MLFeatureRepository,
        artifact_service: ArtifactService,
        inference_job_repo: InferenceJobRepository,
        **kwargs,
    ):
        super().__init__(
            job_id,
            task_instance,
            status_updater=status_updater,
            model_repo=model_repo,
            xai_repo=xai_repo,
            feature_repo=feature_repo,
            artifact_service=artifact_service,
        )
        # self.feature_repo is already set by base if we ensure base class stores it.
        # For clarity, it's fine to explicitly set it again if base doesn't expose it directly.
        # self.feature_repo = feature_repo
        self.inference_job_repo = inference_job_repo
        self.input_reference: Dict[str, Any] = {}  # Will be loaded
        self.ml_model_id: Optional[int] = None  # Will be loaded
        self.model_strategy: Optional[BaseModelStrategy] = (
            None  # To store the loaded strategy
        )

    @property
    def job_type_name(self) -> str:
        return "InferenceJob"

    @property
    def job_model_class(self) -> type:
        return InferenceJob

    def _load_and_validate_job_details(self) -> bool:
        """Loads inference job record and ensures the specified MLModel exists and is ready."""
        try:
            job_record = self.inference_job_repo.get_by_id(self.job_id)
            if not job_record:
                logger.error(f"{self.job_type_name} {self.job_id} not found.")
                self.status_updater.update_job_completion(
                    self.job_id,
                    self.job_model_class,
                    JobStatusEnum.FAILED,
                    f"Job record {self.job_id} not found.",
                )
                return False

            if job_record.status not in [JobStatusEnum.PENDING, JobStatusEnum.RUNNING]:
                logger.warning(
                    f"Inference Job {self.job_id} is in a terminal state ({job_record.status.value}). Skipping."
                )
                return False  # Skip if already terminal

            self.job_db_record = job_record
            self.input_reference = dict(job_record.input_reference or {})
            self.ml_model_id = job_record.ml_model_id

            if not self.ml_model_id:
                raise ValueError("ml_model_id missing from InferenceJob record.")
            if not self.input_reference.get(
                "commit_hash"
            ) or not self.input_reference.get("repo_id"):
                raise ValueError(
                    f"input_reference incomplete in InferenceJob: {self.input_reference}"
                )

            # Validate the MLModel using self.model_repo (already available from base class)
            model_record = self.model_repo.get_by_id(self.ml_model_id)
            if not model_record:
                raise ValueError(f"MLModel with ID {self.ml_model_id} not found.")
            if not model_record.s3_artifact_path:
                raise ValueError(
                    f"MLModel ID {self.ml_model_id} has no S3 artifact path (not ready)."
                )

            # Update status to RUNNING
            updated = self.status_updater.update_job_start(
                job_id=self.job_id,
                job_type=self.job_model_class,
                task_id=self.task.request.id,
            )
            if not updated:
                raise RuntimeError(
                    "Failed to update InferenceJob status to RUNNING in DB."
                )

            logger.info(
                f"{self.job_type_name} {self.job_id} details loaded, status RUNNING."
            )
            return True

        except ValueError as ve:
            logger.error(f"Validation failed for Inference Job {self.job_id}: {ve}")
            if self.job_id:
                self.status_updater.update_job_completion(
                    self.job_id, self.job_model_class, JobStatusEnum.FAILED, str(ve)
                )
            return False
        except RuntimeError as rte:
            logger.error(f"Runtime error for Inference Job {self.job_id}: {rte}")
            return False
        except Exception as e:
            logger.error(
                f"Error loading Inference Job {self.job_id} details: {e}", exc_info=True
            )
            if self.job_id:
                try:
                    self.status_updater.update_job_completion(
                        self.job_id,
                        self.job_model_class,
                        JobStatusEnum.FAILED,
                        f"Failed to load job details: {str(e)[:200]}",
                    )
                except Exception as db_err:
                    logger.error(
                        f"Failed to update DB status after loading error: {db_err}"
                    )
            return False

    def _load_model_strategy(self) -> BaseModelStrategy:
        """Loads the model artifact and creates the appropriate strategy."""
        if self.ml_model_id is None:  # Should be set by _load_and_validate_job_details
            raise ValueError("Cannot load model strategy: ml_model_id is not set.")

        model_record = self.model_repo.get_by_id(self.ml_model_id)
        if not model_record or not model_record.s3_artifact_path:
            # This should have been caught in _load_and_validate_job_details
            raise ValueError(
                f"MLModel {self.ml_model_id} or its artifact path is missing."
            )

        try:
            model_type_enum = ModelTypeEnum(model_record.model_type)
        except ValueError:
            raise ValueError(
                f"Unsupported model_type '{model_record.model_type}' found in MLModel record {self.ml_model_id}."
            )

        model_hyperparams = (
            model_record.hyperparameters
            if isinstance(model_record.hyperparameters, dict)
            else {}
        )

        self._update_progress("Loading model artifact...", 25)

        # For inference, job_config for the strategy might be minimal or empty,
        # as random_seed for the model itself is part of its saved state or hyperparameters.
        # Pass an empty dict for job_config if no specific inference-time job configs are needed by strategies.
        strategy = create_model_strategy(
            model_type_enum,
            model_config=model_hyperparams,  # HPs from the saved model record
            job_config={},  # Minimal job_config for inference strategy
            artifact_service=self.artifact_service,
        )

        strategy.load_model(
            model_record.s3_artifact_path
        )  # Strategy uses its artifact_service
        self.model_strategy = strategy  # Store the loaded strategy instance

        logger.info(
            f"Model {self.ml_model_id} (type: {model_type_enum.value}) loaded into strategy."
        )
        return strategy

    def _get_features(self) -> pd.DataFrame:
        """Gets features for the target commit using the feature repository."""
        repo_id = self.input_reference.get("repo_id")
        commit_hash = self.input_reference.get("commit_hash")
        if not repo_id or not commit_hash:
            # Should be caught by _load_and_validate_job_details
            raise ValueError("repo_id or commit_hash missing in input_reference.")

        self._update_progress("Retrieving features for inference...", 10)
        # self.feature_repo is inherited from BaseMLJobHandler
        features_df = self.feature_repo.get_features_for_commit(repo_id, commit_hash)

        if features_df is None or features_df.empty:
            raise ValueError(
                f"Failed to retrieve or empty features for Repo ID {repo_id}, Commit {commit_hash[:7]}."
            )
        logger.info(f"Inference features retrieved, shape: {features_df.shape}")
        return features_df

    def _prepare_data(
        self, features_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prepares data for inference, separating features and identifiers."""
        if self.model_strategy is None or self.model_strategy.model is None:
            raise RuntimeError(
                "Model strategy or model not loaded. Cannot prepare data."
            )
        if features_df.empty:
            raise ValueError("Cannot prepare empty features DataFrame for inference.")

        logger.info(
            f"Preparing data for inference (input shape: {features_df.shape})..."
        )

        identifier_cols = ["file", "class_name"]  # Expected identifier columns
        available_identifiers = [
            col for col in identifier_cols if col in features_df.columns
        ]
        if not available_identifiers:
            logger.warning(
                "No standard identifier columns ('file', 'class_name') found in features_df."
            )
            # Create a dummy identifiers_df if absolutely necessary, or error out if they are crucial
            identifiers_df = pd.DataFrame(
                index=features_df.index
            )  # Empty but preserves index
        else:
            identifiers_df = features_df[available_identifiers].copy()

        # Get expected feature names from the loaded model strategy/model
        expected_features: List[str] = []
        try:
            # Scikit-learn models often have feature_names_in_
            if hasattr(self.model_strategy.model, "feature_names_in_"):
                expected_features = self.model_strategy.model.feature_names_in_.tolist()
            # XGBoost might use feature_names (older versions) or booster().feature_names
            elif hasattr(self.model_strategy.model, "feature_names") and isinstance(self.model_strategy.model.feature_names, list):  # type: ignore
                expected_features = self.model_strategy.model.feature_names  # type: ignore
            elif hasattr(self.model_strategy.model, "booster") and hasattr(self.model_strategy.model.booster(), "feature_names"):  # type: ignore
                expected_features = self.model_strategy.model.booster().feature_names  # type: ignore

            if not expected_features:
                logger.warning(
                    "Could not reliably determine expected feature names from the loaded model. "
                    "Attempting to use all columns from features_df not in identifiers as features."
                )
                # Fallback: use all columns not in available_identifiers
                # This is risky if features_df contains unexpected columns.
                potential_features = features_df.columns.difference(
                    available_identifiers
                ).tolist()
                if not potential_features:
                    raise ValueError(
                        "No potential feature columns found after excluding identifiers."
                    )
                logger.warning(f"Using inferred features: {potential_features}")
                expected_features = potential_features

        except Exception as e:
            raise ValueError(
                f"Failed to get expected feature names from model: {e}"
            ) from e

        # Check for missing features in the input DataFrame
        missing_model_features = set(expected_features) - set(features_df.columns)
        if missing_model_features:
            raise ValueError(
                f"Input features_df is missing columns expected by the model: {sorted(list(missing_model_features))}"
            )

        X_inference = features_df[expected_features].copy()

        # Handle NaNs - simple fillna(0) for inference
        if X_inference.isnull().values.any():
            logger.warning(
                "Inference feature data contains NaN values. Filling with 0."
            )
            X_inference = X_inference.fillna(0)

        logger.info(
            f"Data prepared for inference. Features shape: {X_inference.shape}, Identifiers shape: {identifiers_df.shape}"
        )
        return X_inference, identifiers_df

    def _execute_prediction(self, X_inference: pd.DataFrame) -> Dict[str, Any]:
        """Executes prediction using the loaded model strategy."""
        if self.model_strategy is None:  # Should be loaded by _load_model_strategy
            raise RuntimeError("Model strategy not loaded. Cannot execute prediction.")

        self._update_progress("Executing prediction...", 45)
        prediction_result_dict = self.model_strategy.predict(X_inference)
        logger.info("Prediction execution complete via strategy.")
        return prediction_result_dict

    def _package_results(
        self, ml_result_dict: Dict[str, Any], identifiers_df: pd.DataFrame
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """Packages prediction results into the InferenceResultPackage structure."""
        logger.info("Packaging inference results...")

        # Extract predictions and probabilities from the strategy's output
        # The strategy's predict method returns a dict like:
        # {"predictions": [...], "probabilities": [[prob_class_0, prob_class_1], ...]}
        row_predictions: Optional[List[int]] = ml_result_dict.get("predictions")
        # Probabilities for binary classification are often [prob_class_0, prob_class_1]
        row_probabilities_raw: Optional[List[List[float]]] = ml_result_dict.get(
            "probabilities"
        )

        error_msg: Optional[str] = None
        commit_overall_prediction: int = 0  # Default to not buggy
        max_defect_probability: float = 0.0
        detailed_results_list: List[FilePredictionDetail] = []
        num_files_analyzed = len(identifiers_df) if identifiers_df is not None else 0

        if row_predictions is None or (
            num_files_analyzed > 0 and len(row_predictions) != num_files_analyzed
        ):
            error_msg = "Prediction results (labels) missing or length mismatch with input instances."
            logger.error(error_msg)
            commit_overall_prediction = -1  # Indicate error
            max_defect_probability = -1.0
            num_files_analyzed = 0  # Reset if predictions are unreliable
        else:
            try:
                for i in range(num_files_analyzed):
                    prediction_label = int(row_predictions[i])

                    prob_class_1 = 0.0  # Probability of being defect-prone (class 1)
                    if row_probabilities_raw and i < len(row_probabilities_raw):
                        instance_probs = row_probabilities_raw[i]
                        if (
                            isinstance(instance_probs, (list, np.ndarray))
                            and len(instance_probs) == 2
                        ):
                            prob_class_1 = float(
                                instance_probs[1]
                            )  # Assuming class 1 is the positive/defect class
                        elif isinstance(
                            instance_probs, (float, np.float_)
                        ):  # Single probability often implies positive class
                            prob_class_1 = (
                                float(instance_probs)
                                if prediction_label == 1
                                else (1.0 - float(instance_probs))
                            )
                        else:
                            logger.warning(
                                f"Unexpected probability format for instance {i}: {instance_probs}"
                            )

                    if prediction_label == 1:
                        commit_overall_prediction = (
                            1  # If any file is predicted as buggy, mark commit as buggy
                        )

                    max_defect_probability = max(max_defect_probability, prob_class_1)

                    detailed_results_list.append(
                        FilePredictionDetail(
                            file=identifiers_df.iloc[i].get("file"),
                            class_name=identifiers_df.iloc[i].get("class_name"),
                            prediction=prediction_label,
                            probability=round(prob_class_1, 4),
                        )
                    )
            except Exception as e:
                error_msg = f"Error processing individual prediction results: {e}"
                logger.error(error_msg, exc_info=True)
                commit_overall_prediction = -1
                max_defect_probability = -1.0
                detailed_results_list = []  # Clear partial results on error
                # num_files_analyzed remains as is, indicating how many were attempted

        prediction_package = InferenceResultPackage(
            commit_prediction=commit_overall_prediction,
            max_bug_probability=(
                round(max_defect_probability, 4)
                if max_defect_probability >= 0
                else -1.0
            ),
            num_files_analyzed=num_files_analyzed,
            details=(
                detailed_results_list if not error_msg else None
            ),  # Only include details if no major error
            error=error_msg,
        )
        logger.info("Inference result packaged successfully.")
        return prediction_package.model_dump(exclude_none=True), error_msg

    async def process_job(self) -> Dict:
        """Orchestrates the inference job execution."""
        final_status = JobStatusEnum.FAILED
        status_message = "Inference processing failed during initialization."
        # Initialize with a default error state for prediction_result
        results_payload = {
            "job_id": self.job_id,
            "status": final_status,
            "message": status_message,
            "prediction_result": InferenceResultPackage(
                commit_prediction=-1,
                max_bug_probability=-1.0,
                num_files_analyzed=0,
                error="Handler initialization failed",
            ).model_dump(),
        }

        try:
            if not self._load_and_validate_job_details():
                if self.job_db_record and self.job_db_record.status not in [
                    JobStatusEnum.PENDING,
                    JobStatusEnum.RUNNING,
                    JobStatusEnum.FAILED,
                ]:
                    results_payload["status"] = JobStatusEnum.SKIPPED
                    results_payload["message"] = (
                        f"Job {self.job_id} was in a terminal state ({self.job_db_record.status.value}) and skipped."
                    )
                else:
                    results_payload["message"] = (
                        f"Job {self.job_id} failed validation or loading."
                    )
                return results_payload

            self._load_model_strategy()  # Loads model into self.model_strategy

            features_df = self._get_features()

            await self._update_progress("Preparing data for inference...", 35)
            X_inference, identifiers_df = self._prepare_data(features_df)

            ml_output_dict = self._execute_prediction(X_inference)

            await self._update_progress("Packaging prediction results...", 90)
            packaged_results_dict, packaging_error_msg = self._package_results(
                ml_output_dict, identifiers_df
            )
            results_payload["prediction_result"] = (
                packaged_results_dict  # Update with actual or error-packaged results
            )

            if packaging_error_msg:
                final_status = JobStatusEnum.FAILED
                status_message = (
                    f"Inference failed during result packaging: {packaging_error_msg}"
                )
                results_payload["error"] = status_message  # For Celery result
            else:
                final_status = JobStatusEnum.SUCCESS
                status_message = f"Inference successful. Commit prediction: {packaged_results_dict.get('commit_prediction')}."

            results_payload["status"] = final_status
            results_payload["message"] = status_message

        except Exception as e:
            final_status = JobStatusEnum.FAILED
            status_message = (
                f"Inference Job {self.job_id} failed: {type(e).__name__}: {e}"
            )
            logger.critical(status_message, exc_info=True)

            results_payload["error"] = str(e)
            results_payload["status"] = JobStatusEnum.FAILED
            results_payload["message"] = status_message
            # Ensure prediction_result reflects this top-level failure
            results_payload["prediction_result"] = InferenceResultPackage(
                commit_prediction=-1,
                max_bug_probability=-1.0,
                num_files_analyzed=0,
                error=status_message[:500],
            ).model_dump()

        finally:
            logger.info(
                f"Attempting final DB status update for Inference Job {self.job_id} to {final_status.value}"
            )
            # Pass the packaged prediction_result (which includes errors if any) to be stored in DB
            db_completion_results = {
                "prediction_result": results_payload.get("prediction_result")
            }
            try:
                await asyncio.to_thread(
                    self.status_updater.update_job_completion,
                    job_id=self.job_id,
                    job_type=self.job_model_class,
                    status=final_status,
                    message=status_message[:1000],
                    results=db_completion_results,
                )
            except Exception as db_err:
                logger.critical(
                    f"CRITICAL: Failed final DB update for Inference Job {self.job_id} to status {final_status.value}: {db_err}",
                    exc_info=True,
                )

        return results_payload
