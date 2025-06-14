# worker/dataset/services/steps/feature_selection_step.py
import logging

from services.context import DatasetContext
from services.factories.feature_selection_factory import FeatureSelectionStrategyFactory
from services.interfaces import IDatasetGeneratorStep
from shared.utils.pipeline_logging import StepLogger

logger = logging.getLogger(__name__)


class FeatureSelectionStep(IDatasetGeneratorStep):
    """
    Pipeline step to apply a feature selection algorithm to the dataset.
    This step runs after all cleaning rules have been applied.
    """

    name = "Feature Selection"

    def execute(self, context: DatasetContext, **kwargs) -> DatasetContext:
        log_prefix = f"Task {context.task_instance.request.id} - Step [{self.name}]"
        step_logger = StepLogger(logger, log_prefix=log_prefix)

        if context.final_dataframe is None or context.final_dataframe.empty:
            step_logger.warning(
                "Input DataFrame is None or empty, skipping feature selection."
            )
            return context

        if not context.dataset_config:
            step_logger.error("Dataset configuration missing in context.")
            raise ValueError("Dataset configuration required for feature selection.")

        # Check if feature selection is configured
        fs_config = context.dataset_config.feature_selection
        if not fs_config or not fs_config.name:
            step_logger.info("No feature selection algorithm specified. Skipping step.")
            return context

        algorithm_name = fs_config.name
        params = fs_config.params or {}
        target_column_name = context.dataset_config.target_column

        step_logger.info(f"Applying feature selection algorithm: {algorithm_name}")

        if target_column_name not in context.final_dataframe.columns:
            raise ValueError(
                f"Target column '{target_column_name}' not found in DataFrame after cleaning."
            )

        try:
            factory = FeatureSelectionStrategyFactory()
            strategy = factory.get_strategy(algorithm_name)

            # Separate features and target
            current_features = [
                col
                for col in context.final_dataframe.columns
                if col != target_column_name
            ]
            features_df = context.final_dataframe[current_features]
            target_series = context.final_dataframe[target_column_name]

            step_logger.info(
                f"Selecting features from {len(current_features)} available features"
            )

            # Apply feature selection
            selected_features = strategy.select_features(
                features_df, target_series, params
            )

            if not selected_features:
                step_logger.warning(
                    f"Algorithm '{algorithm_name}' returned no features. Dataset will only contain target column."
                )
                selected_features = []  # Ensure it's an empty list
            else:
                step_logger.info(
                    f"Selected {len(selected_features)} features: {selected_features}"
                )

            # Update the DataFrame with only selected features and the target
            final_columns = selected_features + [target_column_name]
            context.final_dataframe = context.final_dataframe[final_columns]

            # Update the dataset configuration to reflect the selected features
            # this will be updated in the database later
            # context.dataset_config.feature_columns = selected_features

            step_logger.info(
                f"Feature selection complete. Final DataFrame shape: {context.final_dataframe.shape}"
            )

        except Exception as e:
            step_logger.error(f"Feature selection failed: {e}", exc_info=True)
            raise RuntimeError("Feature selection step failed.") from e

        return context
