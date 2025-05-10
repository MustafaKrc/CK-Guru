# worker/ml/services/strategies/decision_path_strategy.py
import logging
import pandas as pd
import numpy as np
from typing import Optional, List, Any

from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier, _tree


from .base_xai_strategy import BaseXAIStrategy
from shared.schemas.xai import (
    DecisionPathResultData, InstanceDecisionPath, DecisionPathNode, DecisionPathEdge
)

logger = logging.getLogger(__name__)

class DecisionPathStrategy(BaseXAIStrategy):
    """Generates Decision Path explanations for compatible tree-based models."""

    def explain(self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame) -> Optional[DecisionPathResultData]:
        if X_inference.empty:
            logger.warning("DecisionPathStrategy: Input DataFrame is empty.")
            return None

        # --- Check Model Compatibility ---
        if not isinstance(self.model, (RandomForestClassifier, DecisionTreeClassifier)):
            logger.error(f"Decision Path explanation is not supported for model type: {type(self.model).__name__}. Supported: RandomForestClassifier, DecisionTreeClassifier.")
            return None

        logger.info(f"Generating Decision Path explanations for {len(X_inference)} instances...")
        feature_names = X_inference.columns.tolist()
        instance_paths: List[InstanceDecisionPath] = []

        try:
            num_trees_to_explain = 3 # Limit explanation for RandomForest
            estimators = []
            if isinstance(self.model, RandomForestClassifier):
                estimators = self.model.estimators_[:num_trees_to_explain] if self.model.estimators_ else []
            elif isinstance(self.model, DecisionTreeClassifier):
                 estimators = [self.model]

            if not estimators:
                 logger.warning("No tree estimators found in the model.")
                 return None

            for i in range(len(X_inference)):
                instance_id_row = identifiers_df.iloc[i]
                instance_feature_vector = X_inference.iloc[[i]] # Keep as DataFrame row

                for tree_idx, estimator in enumerate(estimators):
                    if not hasattr(estimator, 'tree_') or estimator.tree_ is None:
                        logger.warning(f"Estimator {tree_idx} has no 'tree_' attribute. Skipping.")
                        continue

                    tree_ = estimator.tree_
                    if not isinstance(tree_, _tree.Tree):
                        logger.warning(f"Estimator {tree_idx}'s 'tree_' attribute is not a valid Tree object ({type(tree_)}). Skipping.")
                        continue

                    feature = tree_.feature
                    threshold = tree_.threshold

                    try:
                        # Get the path for the instance
                        node_indicator = estimator.decision_path(instance_feature_vector)
                        # node_index contains the indices of the nodes in the path
                        node_index = node_indicator.indices[node_indicator.indptr[0]:node_indicator.indptr[1]]
                    except Exception as path_err:
                         logger.error(f"Failed to get decision path for instance {i}, tree {tree_idx}: {path_err}", exc_info=True)
                         continue # Skip this tree/instance combination on error

                    path_nodes_struct: List[DecisionPathNode] = []
                    path_edges_struct: List[DecisionPathEdge] = []

                    for node_id_idx, node_id in enumerate(node_index):
                        is_leaf = tree_.children_left[node_id] == tree_.children_right[node_id]
                        condition = None
                        if not is_leaf:
                            feat_idx = feature[node_id]
                            thresh_val = round(threshold[node_id], 3)
                            # Ensure feature index is valid
                            if feat_idx >= 0 and feat_idx < len(feature_names):
                                feature_name = feature_names[feat_idx]
                                condition = f"{feature_name} <= {thresh_val}"
                            else:
                                condition = f"feature_{feat_idx} <= {thresh_val}" # Fallback if feature name mapping issue

                        # Safely get node values (class counts)
                        node_value_raw = tree_.value[node_id][0] if tree_.value is not None and node_id < len(tree_.value) else []
                        node_value = [int(v) for v in node_value_raw]

                        node_info = DecisionPathNode(
                            id=str(node_id),
                            condition=condition if not is_leaf else "Leaf",
                            samples=int(tree_.n_node_samples[node_id]),
                            value=node_value
                        )
                        path_nodes_struct.append(node_info)

                        # Add edge from previous node if not the first node
                        if node_id_idx > 0:
                            prev_node_id = node_index[node_id_idx - 1]
                            # Determine label based on which child was taken
                            label = "True" if node_id == tree_.children_left[prev_node_id] else "False"
                            path_edges_struct.append(DecisionPathEdge(
                                source=str(prev_node_id),
                                target=str(node_id),
                                label=label
                            ))

                    # Add the path for this instance/tree combination
                    instance_paths.append(InstanceDecisionPath(
                        file=instance_id_row.get('file'),
                        class_name=instance_id_row.get('class_name'),
                        # Add tree index for RandomForest clarity
                        tree_index=tree_idx if isinstance(self.model, RandomForestClassifier) else None,
                        nodes=path_nodes_struct,
                        edges=path_edges_struct
                    ))

            if not instance_paths:
                logger.warning("Decision Path explanation generated no valid instance paths.")
                return None

            return DecisionPathResultData(instance_decision_paths=instance_paths)

        except Exception as e:
            logger.error(f"Error generating Decision Path explanation: {e}", exc_info=True)
            return None