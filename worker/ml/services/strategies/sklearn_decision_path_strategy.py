# worker/ml/services/strategies/sklearn_decision_path_strategy.py
import logging
from typing import Any, List, Optional  # Added Any

import pandas as pd

# Ensure necessary sklearn imports are here
from sklearn.ensemble import (
    AdaBoostClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.tree import DecisionTreeClassifier, _tree  # For accessing tree structure

from shared.schemas.xai import (
    DecisionPathEdge,
    DecisionPathNode,
    DecisionPathResultData,
    InstanceDecisionPath,
)

# Import the new base class
from .base_decision_path_strategy import BaseDecisionPathStrategy

logger = logging.getLogger(__name__)


class SklearnDecisionPathStrategy(BaseDecisionPathStrategy):  # Inherit from new base
    """
    Generates Decision Path explanations for scikit-learn tree-based models.
    (Effectively the previous DecisionPathStrategy, now specialized).
    """

    def __init__(self, model: Any, background_data: Optional[pd.DataFrame] = None):
        super().__init__(model, background_data)
        # Check model compatibility upon initialization
        if not isinstance(
            self.model,
            (
                RandomForestClassifier,
                DecisionTreeClassifier,
                GradientBoostingClassifier,
                AdaBoostClassifier,
            ),
        ):
            logger.error(
                f"SklearnDecisionPathStrategy is not compatible with model type: {type(self.model).__name__}."
            )
            # Raise error or set a flag to indicate incompatibility
            # For now, let explain method handle it, but constructor check is good.
            # raise TypeError(f"Model type {type(self.model).__name__} not supported by SklearnDecisionPathStrategy.")

    def explain(
        self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame
    ) -> Optional[DecisionPathResultData]:
        if X_inference.empty:
            logger.warning(
                "SklearnDecisionPathStrategy: Input X_inference DataFrame is empty."
            )
            return None

        # Model compatibility check (can also be in __init__)
        if not isinstance(
            self.model,
            (
                RandomForestClassifier,
                DecisionTreeClassifier,
                GradientBoostingClassifier,
                AdaBoostClassifier,
            ),
        ):
            logger.error(
                f"SklearnDecisionPathStrategy cannot explain model type: {type(self.model).__name__}. "
                "Supported: RandomForestClassifier, DecisionTreeClassifier, GradientBoostingClassifier, AdaBoostClassifier."
            )
            return None

        logger.info(
            f"SklearnDecisionPathStrategy: Generating Decision Path explanations for {len(X_inference)} instances..."
        )
        feature_names = X_inference.columns.tolist()
        instance_paths_result: List[InstanceDecisionPath] = []  # Corrected type name

        try:
            estimators = []
            # For GradientBoostingClassifier, estimators_ is a 2D array of DecisionTreeRegressor
            # We are interested in explaining individual trees.
            if isinstance(self.model, GradientBoostingClassifier):
                # Explain first few trees for each class if multi-class, or first few trees for binary.
                # GBC for classification usually has n_estimators trees for each class if n_classes > 2.
                # For binary, it's typically n_estimators trees.
                # Let's take the first tree of the first estimator array.
                if self.model.estimators_.ndim == 2:  # array of arrays of trees
                    estimators.extend(
                        self.model.estimators_[:1, :1].flatten()
                    )  # First tree of first "class"
                elif self.model.estimators_.ndim == 1:  # array of trees
                    estimators.extend(self.model.estimators_[:1])
                if not estimators:
                    logger.warning("GBC: No base estimators found.")

            elif isinstance(self.model, RandomForestClassifier) or isinstance(
                self.model, AdaBoostClassifier
            ):
                num_trees_to_explain = min(
                    3,
                    (
                        len(self.model.estimators_)
                        if hasattr(self.model, "estimators_")
                        else 0
                    ),
                )
                estimators = (
                    self.model.estimators_[:num_trees_to_explain]
                    if self.model.estimators_
                    else []
                )
            elif isinstance(self.model, DecisionTreeClassifier):
                estimators = [self.model]

            if not estimators:
                logger.warning(
                    "No tree estimators found in the model to explain decision paths."
                )
                return DecisionPathResultData(
                    instance_decision_paths=[]
                )  # Return empty if no estimators

            for i in range(len(X_inference)):
                instance_id_row = identifiers_df.iloc[i]
                instance_feature_vector = X_inference.iloc[[i]]

                for tree_idx, estimator_tree in enumerate(estimators):
                    # Ensure the estimator is a Decision Tree compatible type
                    if not isinstance(estimator_tree, DecisionTreeClassifier) and not (
                        hasattr(estimator_tree, "tree_")
                        and isinstance(estimator_tree.tree_, _tree.Tree)
                    ):  # GBC trees are DecisionTreeRegressor
                        logger.warning(
                            f"Estimator {tree_idx} is not a DecisionTreeClassifier or compatible tree. Type: {type(estimator_tree)}. Skipping."
                        )
                        continue

                    tree_ = estimator_tree.tree_
                    if tree_ is None:  # Should not happen if above check passes
                        logger.warning(
                            f"Estimator {tree_idx} has no 'tree_' attribute. Skipping."
                        )
                        continue

                    feature_indices = (
                        tree_.feature
                    )  # Renamed from 'feature' to avoid conflict
                    threshold_values = tree_.threshold  # Renamed

                    try:
                        node_indicator = estimator_tree.decision_path(
                            instance_feature_vector
                        )
                        node_index_path = node_indicator.indices[
                            node_indicator.indptr[0] : node_indicator.indptr[1]
                        ]
                    except Exception as path_err:
                        logger.error(
                            f"Failed to get decision path for instance {i}, tree {tree_idx}: {path_err}",
                            exc_info=False,
                        )
                        continue

                    path_nodes_struct: List[DecisionPathNode] = []
                    path_edges_struct: List[DecisionPathEdge] = []

                    for node_id_idx, current_node_id in enumerate(node_index_path):
                        is_leaf = (
                            tree_.children_left[current_node_id]
                            == tree_.children_right[current_node_id]
                        )

                        condition_str = "Leaf"
                        if not is_leaf:
                            feature_idx_at_node = feature_indices[current_node_id]
                            threshold_at_node = round(
                                threshold_values[current_node_id], 4
                            )
                            feature_name_at_node = (
                                feature_names[feature_idx_at_node]
                                if feature_idx_at_node >= 0
                                and feature_idx_at_node < len(feature_names)
                                else f"feature_{feature_idx_at_node}"
                            )
                            condition_str = (
                                f"{feature_name_at_node} <= {threshold_at_node}"
                            )

                        node_value_raw = (
                            tree_.value[current_node_id][0]
                            if tree_.value is not None
                            and current_node_id < len(tree_.value)
                            else []
                        )
                        node_value_list = [
                            round(float(v), 4) for v in node_value_raw
                        ]  # Store as float for probabilities/counts

                        node_info = DecisionPathNode(
                            id=str(current_node_id),  # Node ID as string
                            condition=condition_str,
                            samples=int(tree_.n_node_samples[current_node_id]),
                            value=node_value_list,
                        )
                        path_nodes_struct.append(node_info)

                        if node_id_idx > 0:
                            prev_node_id = node_index_path[node_id_idx - 1]
                            edge_label = (
                                "True"
                                if current_node_id == tree_.children_left[prev_node_id]
                                else "False"
                            )
                            path_edges_struct.append(
                                DecisionPathEdge(
                                    source=str(prev_node_id),
                                    target=str(current_node_id),
                                    label=edge_label,
                                )
                            )

                    # Add path for this instance/tree combination
                    instance_paths_result.append(
                        InstanceDecisionPath(
                            file=instance_id_row.get("file"),  # type: ignore
                            class_name=instance_id_row.get("class_name"),  # type: ignore
                            nodes=path_nodes_struct,
                            edges=path_edges_struct,
                            # tree_index=tree_idx # Optional: if you want to distinguish paths from different trees in an ensemble
                        )
                    )

            if not instance_paths_result:
                logger.warning(
                    "SklearnDecisionPathStrategy generated no valid instance paths."
                )
                return DecisionPathResultData(instance_decision_paths=[])

            return DecisionPathResultData(instance_decision_paths=instance_paths_result)

        except Exception as e:
            logger.error(
                f"Error generating Sklearn Decision Path explanation: {e}",
                exc_info=True,
            )
            return None
