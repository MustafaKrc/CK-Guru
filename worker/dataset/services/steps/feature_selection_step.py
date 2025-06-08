# worker/dataset/services/steps/feature_selection_step.py
import logging
import asyncio

from services.factories.feature_selection_factory import FeatureSelectionStrategyFactory
from services.interfaces import IDatasetGeneratorStep
from services.context import DatasetContext
logger = logging.getLogger(__name__)

class FeatureSelectionStep(IDatasetGeneratorStep):
    """
    Pipeline step to apply a feature selection algorithm to the dataset.
    This step runs after all cleaning rules have been applied.
    """
    name = "Feature Selection"

    async def execute(self, context: DatasetContext) -> DatasetContext:
        fs_config = context.dataset_db.config.get("feature_selection")

        if not fs_config or not fs_config.get("name"):
            self._log_info(context, "No feature selection algorithm specified. Skipping step.")
            return context

        algorithm_name = fs_config["name"]
        params = fs_config.get("params", {})
        target_column_name = context.dataset_db.config.get("target_column")
        
        self._log_info(context, f"Applying feature selection algorithm: {algorithm_name}")
        await self._update_progress(context, f"Starting feature selection with {algorithm_name}...", 85)

        if target_column_name not in context.dataframe.columns:
            raise ValueError(f"Target column '{target_column_name}' not found in DataFrame after cleaning.")
        
        try:
            factory = FeatureSelectionStrategyFactory()
            strategy = factory.get_strategy(algorithm_name)
            
            features_df = context.dataframe.drop(columns=[target_column_name])
            target_series = context.dataframe[target_column_name]

            # Run the potentially CPU-bound logic in a separate thread
            selected_features = await asyncio.to_thread(
                strategy.select_features, features_df, target_series, params
            )
            
            if not selected_features:
                self._log_warning(context, f"Algorithm '{algorithm_name}' returned no features. The dataset will be empty except for the target column.")
            else:
                self._log_info(context, f"Selected {len(selected_features)} features.")
            
            # Reconstruct the DataFrame with only selected features and the target
            final_columns = selected_features + [target_column_name]
            context.dataframe = context.dataframe[final_columns]
            
            await self._update_progress(context, "Feature selection complete.", 90)

        except Exception as e:
            self._log_error(context, f"Feature selection failed: {e}", exc_info=True)
            raise RuntimeError("Feature selection step failed.") from e

        return context