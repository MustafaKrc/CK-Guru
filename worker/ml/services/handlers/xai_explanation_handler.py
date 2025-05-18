# worker/ml/services/handlers/xai_explanation_handler.py
import logging
from typing import Any, Dict, List, Optional, Tuple  # Added Tuple
import asyncio

import pandas as pd
from celery import Task
from celery.exceptions import Ignore, Reject

from services.artifact_service import ArtifactService
from services.factories.xai_strategy_factory import XAIStrategyFactory
from services.strategies.base_xai_strategy import BaseXAIStrategy
from shared.exceptions import InternalError
from shared.repositories import (
    DatasetRepository,
    InferenceJobRepository,
    MLFeatureRepository,
    ModelRepository,
    XaiResultRepository,
)

# Import ModelTypeEnum
from shared.schemas.enums import ModelTypeEnum, XAIStatusEnum

logger = logging.getLogger(__name__)


class XAIExplanationHandler:
    """Handles the generation of a specific XAI explanation."""

    def __init__(
        self,
        xai_result_id: int,
        task_instance: Task,
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
        self.loaded_model_instance: Optional[Any] = (
            None  # Stores the loaded model object
        )
        self.feature_names_for_xai: Optional[List[str]] = None  # Store feature names

        logger.debug(f"Initialized XAIExplanationHandler for Result ID {xai_result_id}")

    def _prepare_data_for_xai(
        self, features_df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Separates features and identifiers, validates features. Uses self.loaded_model_instance."""
        if self.loaded_model_instance is None:
            raise RuntimeError(
                "Model has not been loaded before preparing data for XAI."
            )
        if features_df is None or features_df.empty:
            raise ValueError("Cannot prepare empty features DataFrame.")

        logger.debug(f"Preparing data for XAI (Initial shape: {features_df.shape})...")

        identifier_cols = ["file", "class_name"]
        available_identifiers = [
            col for col in identifier_cols if col in features_df.columns
        ]
        identifiers_df = (
            features_df[available_identifiers].copy()
            if available_identifiers
            else pd.DataFrame(index=features_df.index)
        )

        # Determine expected features (self.feature_names_for_xai should be set by _load_model_and_features)
        if not self.feature_names_for_xai:
            # Fallback if not set - this indicates an issue in _load_model_and_features
            logger.error(
                "feature_names_for_xai was not set prior to _prepare_data_for_xai. This is an internal logic error."
            )
            raise RuntimeError("Feature names for XAI not determined.")

        expected_features = self.feature_names_for_xai

        missing_model_features = set(expected_features) - set(features_df.columns)
        if missing_model_features:
            raise ValueError(
                f"Input features_df is missing columns expected by the model/XAI: {sorted(list(missing_model_features))}"
            )

        logger.debug(f"Using features for XAI: {expected_features}")
        X_inference = features_df[expected_features].copy()

        if X_inference.isnull().values.any():
            logger.warning(
                "XAI input features contain NaN values. Applying simple fillna(0). Explanation quality may be affected."
            )
            X_inference = X_inference.fillna(0)

        return X_inference, identifiers_df

    def _load_model_and_determine_features(
        self, model_s3_path: str, X_input_features_df: pd.DataFrame
    ) -> None:
        """Loads the model and determines/stores feature names for XAI."""
        logger.info(
            f"XAIExplanationHandler: Attempting to load model from {model_s3_path}"
        )
        self.loaded_model_instance = self.artifact_service.load_artifact(model_s3_path)
        if not self.loaded_model_instance:
            logger.error(
                f"XAIExplanationHandler: CRITICAL - Failed to load model from: {model_s3_path}"
            )
            # This error should be caught by process_explanation and lead to FAILED state for XAIResult
            raise InternalError(
                f"Model loading failed from {model_s3_path}. Cannot proceed with XAI."
            )

        logger.info(
            f"XAIExplanationHandler: Model loaded successfully from {model_s3_path}. Type: {type(self.loaded_model_instance).__name__}"
        )

        # Determine feature names (model-specific)
        model = self.loaded_model_instance
        feature_names: Optional[List[str]] = None
        try:
            if hasattr(model, "feature_names_in_"):
                feature_names = model.feature_names_in_.tolist()
            elif hasattr(model, "feature_name_") and callable(
                getattr(model, "feature_name_", None)
            ):  # For LightGBM Booster if model is raw booster
                feature_names = model.feature_name_()
            elif hasattr(model, "feature_names") and isinstance(
                model.feature_names, list
            ):
                feature_names = model.feature_names
            elif hasattr(model, "booster") and hasattr(
                model.booster(), "feature_names"
            ):
                feature_names = model.booster().feature_names

            if feature_names:
                self.feature_names_for_xai = feature_names
                logger.info(
                    f"Determined feature names for XAI from model: {self.feature_names_for_xai}"
                )
            else:
                # Fallback: Infer from X_input_features_df columns (excluding known non-features)
                logger.warning(
                    "Model does not explicitly store feature names. Inferring from input DataFrame columns, excluding identifiers."
                )
                identifier_cols_to_exclude = [
                    "file",
                    "class_name",
                    "commit_hash",
                    "is_buggy",
                ]  # Add more if necessary
                # Ensure X_input_features_df is available and has columns
                if X_input_features_df is not None and hasattr(
                    X_input_features_df, "columns"
                ):
                    self.feature_names_for_xai = [
                        col
                        for col in X_input_features_df.columns
                        if col not in identifier_cols_to_exclude
                    ]
                    if not self.feature_names_for_xai:
                        logger.error(
                            "XAIExplanationHandler: CRITICAL - Could not determine feature names from model, and no columns left in input DataFrame after excluding identifiers."
                        )
                        raise InternalError(
                            "Feature names for XAI could not be determined."
                        )
                    logger.info(
                        f"Inferred feature names for XAI: {self.feature_names_for_xai}"
                    )
                else:
                    logger.error(
                        "XAIExplanationHandler: CRITICAL - X_input_features_df is None or has no columns, cannot infer feature names."
                    )
                    raise InternalError(
                        "Cannot infer feature names for XAI from missing/empty input DataFrame."
                    )

        except Exception as e:
            logger.error(
                f"Error determining feature names from model: {e}", exc_info=True
            )
            raise InternalError(f"Could not determine feature names for XAI: {e}")

    def _load_background_data_for_xai(
        self, dataset_id: Optional[int], X_inference_features_only: pd.DataFrame
    ) -> Optional[pd.DataFrame]:
        """Loads background data. Uses self.dataset_repo and self.artifact_service."""
        if not dataset_id:
            logger.warning(
                "No training dataset ID linked to the model. Using a sample of inference data for XAI background."
            )
            sample_n = (
                min(100, len(X_inference_features_only))
                if len(X_inference_features_only) > 0
                else 0
            )
            return (
                X_inference_features_only.sample(n=sample_n, random_state=42)
                if sample_n > 0
                else None
            )

        dataset_record = self.dataset_repo.get_record(dataset_id)
        if not dataset_record:
            logger.warning(
                f"Dataset record {dataset_id} not found. Using inference data sample for XAI background."
            )
            sample_n = (
                min(100, len(X_inference_features_only))
                if len(X_inference_features_only) > 0
                else 0
            )
            return (
                X_inference_features_only.sample(n=sample_n, random_state=42)
                if sample_n > 0
                else None
            )

        background_path = dataset_record.background_data_path
        if not background_path:
            logger.warning(
                f"No background data path specified for dataset {dataset_id}. Using inference data sample."
            )
            sample_n = (
                min(100, len(X_inference_features_only))
                if len(X_inference_features_only) > 0
                else 0
            )
            return (
                X_inference_features_only.sample(n=sample_n, random_state=42)
                if sample_n > 0
                else None
            )

        logger.info(f"Loading XAI background data sample from: {background_path}")
        try:
            background_df_raw = self.artifact_service.load_dataframe_artifact(
                background_path
            )
            if background_df_raw is None or background_df_raw.empty:
                raise ValueError("Loaded XAI background data is empty or None.")

            # Ensure background_df only contains the features expected by the model
            if not self.feature_names_for_xai:
                raise RuntimeError(
                    "Feature names for XAI must be determined before loading background data effectively."
                )

            missing_bg_features = set(self.feature_names_for_xai) - set(
                background_df_raw.columns
            )
            if missing_bg_features:
                logger.error(
                    f"Background data is missing expected features: {missing_bg_features}. Cannot use for XAI."
                )
                # Fallback to inference data sample
                sample_n = (
                    min(100, len(X_inference_features_only))
                    if len(X_inference_features_only) > 0
                    else 0
                )
                return (
                    X_inference_features_only.sample(n=sample_n, random_state=42)
                    if sample_n > 0
                    else None
                )

            background_df_features_only = background_df_raw[
                self.feature_names_for_xai
            ].copy()

            if background_df_features_only.isnull().values.any():
                logger.warning(
                    "XAI background data contains NaN values. Filling with 0."
                )
                background_df_features_only = background_df_features_only.fillna(0)

            logger.info(
                f"Loaded and processed XAI background data (shape: {background_df_features_only.shape})"
            )
            return background_df_features_only
        except Exception as e:
            logger.error(
                f"Failed to load or process XAI background data from {background_path}: {e}",
                exc_info=True,
            )
            logger.warning(
                "Using inference data sample as fallback for XAI background."
            )
            sample_n = (
                min(100, len(X_inference_features_only))
                if len(X_inference_features_only) > 0
                else 0
            )
            return (
                X_inference_features_only.sample(n=sample_n, random_state=42)
                if sample_n > 0
                else None
            )

    async def process_explanation(self) -> Optional[Dict[str, Any]]:
        task_id_str = self.task.request.id if self.task else "N/A"
        logger.info(
            f"Handler: Starting XAI explanation generation for XAIResult ID {self.xai_result_id} (Task: {task_id_str})"
        )

        final_xai_status = XAIStatusEnum.FAILED
        status_update_message = "XAI generation failed during initialization."
        explanation_result_data_json: Optional[Dict[str, Any]] = None

        try:
            xai_record = await asyncio.to_thread(self.xai_repo.get_xai_result_sync, self.xai_result_id)
            if not xai_record:
                raise Ignore(f"XAIResult record {self.xai_result_id} not found in DB.")
            if (
                xai_record.status == XAIStatusEnum.RUNNING
                and xai_record.celery_task_id != task_id_str
            ):
                raise Ignore(
                    f"XAIResult {self.xai_result_id} is already being processed by another task ({xai_record.celery_task_id})."
                )
            if xai_record.status in [
                XAIStatusEnum.SUCCESS,
                XAIStatusEnum.FAILED,
                XAIStatusEnum.REVOKED,
            ]:
                raise Ignore(
                    f"XAIResult {self.xai_result_id} is already in a terminal state ({xai_record.status.value})."
                )

            await asyncio.to_thread(
                self.xai_repo.update_xai_result_sync,
                self.xai_result_id,
                XAIStatusEnum.RUNNING,
                "Loading model and data...",
                task_id=task_id_str,
                is_start=True,
            )

            inference_job = await asyncio.to_thread(self.inference_job_repo.get_by_id,
                xai_record.inference_job_id
            )
            if not inference_job:
                raise ValueError(
                    f"Parent InferenceJob ID {xai_record.inference_job_id} not found."
                )

            ml_model_db_record = await asyncio.to_thread(self.model_repo.get_by_id, inference_job.ml_model_id)
            if not ml_model_db_record or not ml_model_db_record.s3_artifact_path:
                raise ValueError(
                    f"MLModel {inference_job.ml_model_id} or its S3 artifact path not found."
                )

            # Convert DB model_type string to ModelTypeEnum
            try:
                model_type_enum_for_xai = ModelTypeEnum(ml_model_db_record.model_type)
            except ValueError:
                raise ValueError(
                    f"Invalid model_type '{ml_model_db_record.model_type}' in MLModel record {ml_model_db_record.id} for XAI."
                )

            input_ref = dict(inference_job.input_reference or {})
            repo_id = input_ref.get("repo_id")
            commit_hash = input_ref.get("commit_hash")
            if not repo_id or not commit_hash:
                raise ValueError(
                    "Missing repo_id or commit_hash in InferenceJob input_reference."
                )

            # Load features first to help determine feature names if model doesn't store them
            raw_features_df = await asyncio.to_thread(self.feature_repo.get_features_for_commit,
                repo_id, commit_hash
            )
            if raw_features_df is None or raw_features_df.empty:
                raise ValueError(
                    f"Failed to retrieve features for Repo {repo_id}, Commit {commit_hash}."
                )

            # Load model and determine feature names
            self._load_model_and_determine_features(
                ml_model_db_record.s3_artifact_path, raw_features_df
            )

            # Prepare data (X_inference will only contain self.feature_names_for_xai)
            X_inference_features_only, identifiers_df = self._prepare_data_for_xai(
                raw_features_df
            )

            # Load background data (pass X_inference_features_only for sampling fallback)
            background_data_df = self._load_background_data_for_xai(
                ml_model_db_record.dataset_id, X_inference_features_only
            )

            await asyncio.to_thread(
                self.xai_repo.update_xai_result_sync,
                self.xai_result_id, XAIStatusEnum.RUNNING, "Generating explanation..."
            )

            xai_strategy: BaseXAIStrategy = XAIStrategyFactory.create(
                xai_type=xai_record.xai_type,
                model=self.loaded_model_instance,
                model_type_enum=model_type_enum_for_xai,
                background_data=background_data_df,
                feature_names=self.feature_names_for_xai,
            )

            logger.info(
                f"Handler: Executing XAI strategy {xai_strategy.__class__.__name__} for XAIResult {self.xai_result_id}."
            )
            explanation_result_object = xai_strategy.explain(
                X_inference_features_only, identifiers_df
            )

            if explanation_result_object:
                explanation_result_data_json = explanation_result_object.model_dump(
                    exclude_none=True, mode="json"
                )
                final_xai_status = XAIStatusEnum.SUCCESS
                status_update_message = (
                    f"{xai_record.xai_type.value} explanation generated successfully."
                )
            else:
                final_xai_status = XAIStatusEnum.FAILED
                status_update_message = f"{xai_record.xai_type.value} strategy execution returned no data or failed."

        except Ignore as e:
            logger.info(
                f"Handler: Ignoring XAI task for Result ID {self.xai_result_id}. Reason: {e}"
            )
            raise  # Re-raise for Celery to handle task state
        except (
            Reject
        ) as e:  # Should not be raised directly by this handler's logic, but by Celery if needed
            logger.error(
                f"Handler: XAI task for Result ID {self.xai_result_id} was rejected. Reason: {e}"
            )
            raise
        except Exception as e:
            status_update_message = f"XAI generation critically failed for Result ID {self.xai_result_id}: {type(e).__name__}: {str(e)[:250]}"
            logger.critical(status_update_message, exc_info=True)
            final_xai_status = XAIStatusEnum.FAILED
        finally:
            logger.info(
                f"Handler: Attempting final DB update for XAIResult {self.xai_result_id} to status {final_xai_status.value}"
            )
            try:
                await asyncio.to_thread(
                    self.xai_repo.update_xai_result_sync,
                    xai_result_id=self.xai_result_id,
                    status=final_xai_status,
                    message=status_update_message,
                    result_data=explanation_result_data_json,  # This will be None if generation failed
                )
            except Exception as db_update_err:
                logger.critical(
                    f"CRITICAL: Failed final DB update for XAIResult {self.xai_result_id} "
                    f"after attempting to set status to {final_xai_status.value}: {db_update_err}",
                    exc_info=True,
                )

        # The Celery task should return the result data or an error structure.
        # If an exception was raised (Ignore, Reject, or unhandled), Celery handles it.
        # If we reach here, it means the try block completed (successfully or with a caught error).
        if final_xai_status == XAIStatusEnum.SUCCESS:
            return explanation_result_data_json  # Return the data on success
        else:
            # For Celery, it's often better to raise an exception if the task logically failed,
            # so Celery marks it as FAILED. Returning None might make Celery mark it as SUCCESS.
            # However, since we're updating DB status, and process_explanation is called by a Celery task wrapper...
            # The wrapper will handle raising Reject or updating Celery state based on this handler's outcome.
            # For now, let's return None to signify an issue if not SUCCESS.
            # The task wrapper in app/tasks.py should interpret this.
            return None
