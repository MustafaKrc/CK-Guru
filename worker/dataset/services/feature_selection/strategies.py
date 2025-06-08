# worker/dataset/services/feature_selection/strategies.py
import logging
from typing import Any, Dict, List

import pandas as pd
from pydantic import ValidationError
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import SelectFromModel

# Assuming mrmr and cbfs might come from a library like 'skfeature-chappers' or a custom implementation
# As a placeholder, we will implement simplified logic.
from shared.feature_selection import (
    FeatureSelectionParamDefinition,
    FeatureSelectionStrategy,
)

logger = logging.getLogger(__name__)


class CbfsFeatureSelection(FeatureSelectionStrategy):
    """Correlation-Based Feature Selection (CBFS)."""
    algorithm_name = "cbfs"
    display_name = "Correlation-Based Feature Selection"
    description = "Selects features highly correlated with the target but uncorrelated with each other."
    parameters = [
        FeatureSelectionParamDefinition(name="threshold", type="float", description="Correlation threshold for feature removal.", default=0.7)
    ]

    def select_features(self, dataframe: pd.DataFrame, target_column: pd.Series, params: Dict[str, Any]) -> List[str]:
        threshold = params.get("threshold", 0.7)
        logger.info(f"Applying CBFS with threshold: {threshold}")
        
        df_with_target = pd.concat([dataframe, target_column], axis=1)
        corr_matrix = df_with_target.corr(numeric_only=True).abs()

        # Find features highly correlated with the target
        target_corr = corr_matrix[target_column.name]
        relevant_features = target_corr[target_corr > threshold].index.tolist()
        if target_column.name in relevant_features:
            relevant_features.remove(target_column.name)
            
        if not relevant_features:
            logger.warning("CBFS: No features found above the correlation threshold with the target. Returning all original features.")
            return dataframe.columns.tolist()

        # Remove highly correlated features among the relevant set
        selected_features = []
        for feature in relevant_features:
            is_redundant = False
            for selected in selected_features:
                if corr_matrix.loc[feature, selected] > threshold:
                    is_redundant = True
                    break
            if not is_redundant:
                selected_features.append(feature)
        
        logger.info(f"CBFS selected {len(selected_features)} out of {len(dataframe.columns)} features.")
        return selected_features


class MrmrFeatureSelection(FeatureSelectionStrategy):
    """Minimum Redundancy Maximum Relevance (mRMR)."""
    algorithm_name = "mrmr"
    display_name = "Min-Redundancy Max-Relevance"
    description = "Selects features with the highest relevance to the target and least redundancy among themselves."
    parameters = [
        FeatureSelectionParamDefinition(name="k", type="integer", description="Number of top features to select.", default=20)
    ]

    def select_features(self, dataframe: pd.DataFrame, target_column: pd.Series, params: Dict[str, Any]) -> List[str]:
        k = params.get("k", 20)
        logger.info(f"Applying mRMR to select top {k} features.")
        
        # Placeholder logic: Select top K features based on correlation with target
        df_with_target = pd.concat([dataframe, target_column], axis=1)
        target_corr = df_with_target.corr(numeric_only=True)[target_column.name].abs().sort_values(ascending=False)
        selected = target_corr[1:k+1].index.tolist() # Exclude target itself
        
        logger.info(f"mRMR (placeholder) selected {len(selected)} features.")
        return selected


class ModelBasedFeatureSelection(FeatureSelectionStrategy):
    """Feature selection using a supervised model's feature importances."""
    algorithm_name = "model_based"
    display_name = "Model-Based Feature Selection"
    description = "Uses a Random Forest to judge feature importance and select the top K features."
    parameters = [
        FeatureSelectionParamDefinition(name="k", type="integer", description="Number of top features to select.", default=20)
    ]

    def select_features(self, dataframe: pd.DataFrame, target_column: pd.Series, params: Dict[str, Any]) -> List[str]:
        k = params.get("k", 20)
        logger.info(f"Applying Model-based selection with RandomForest to select top {k} features.")

        # Ensure data is numeric and handle NaNs for the model
        numeric_df = dataframe.select_dtypes(include=['number']).fillna(0)
        if numeric_df.empty:
            logger.warning("No numeric features found for model-based selection. Returning empty list.")
            return []

        model = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
        selector = SelectFromModel(model, max_features=k, threshold=-1) # Use max_features
        selector.fit(numeric_df, target_column)

        selected_features = numeric_df.columns[selector.get_support()].tolist()
        logger.info(f"Model-based selection chose {len(selected_features)} features.")
        return selected_features