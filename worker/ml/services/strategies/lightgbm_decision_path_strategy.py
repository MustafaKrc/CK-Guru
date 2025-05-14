# worker/ml/services/strategies/lightgbm_decision_path_strategy.py
import logging
from typing import Any, Dict, List, Optional, Tuple

import lightgbm as lgb  # type: ignore
import pandas as pd

from shared.schemas.xai import (
    DecisionPathEdge,
    DecisionPathNode,
    DecisionPathResultData,
    InstanceDecisionPath,
)

from .base_decision_path_strategy import BaseDecisionPathStrategy

logger = logging.getLogger(__name__)


class LightGBMDecisionPathStrategy(BaseDecisionPathStrategy):
    def __init__(self, model: Any, background_data: Optional[pd.DataFrame] = None):
        super().__init__(model, background_data)
        if not isinstance(self.model, lgb.LGBMClassifier):
            logger.warning(
                f"LightGBMDecisionPathStrategy initialized with non-LGBMClassifier model: {type(self.model).__name__}"
            )
            # This strategy will likely fail if it's not an LGBMClassifier
            # Consider raising an error here if strict type checking is desired early on.
            # raise TypeError(f"Model type {type(self.model).__name__} not supported by LightGBMDecisionPathStrategy.")

    def _parse_tree_structure(
        self, tree_info: Dict[str, Any], feature_names: List[str]
    ) -> Tuple[Dict[int, DecisionPathNode], List[Tuple[int, int, str]]]:
        """
        Parses a single tree structure from LightGBM's dump_model output.
        Returns a dictionary of nodes and a list of edge tuples (source_id, target_id, label).
        Node IDs are their original split_index or leaf_index from the dump.
        """
        nodes: Dict[int, DecisionPathNode] = {}
        edges: List[Tuple[int, int, str]] = (
            []
        )  # (source_node_id, target_node_id, label)

        def traverse_node(
            node_dict: Dict[str, Any],
            parent_id: Optional[int] = None,
            branch_taken: Optional[str] = None,
        ):
            node_id: Optional[int] = None
            condition_str: Optional[str] = None
            samples: Optional[int] = None
            value_list: Optional[List[float]] = (
                None  # LightGBM leaf values are typically prediction scores
            )

            if "leaf_index" in node_dict:  # Leaf node
                node_id = int(
                    node_dict["leaf_index"]
                )  # Using leaf_index might create ID collisions if not unique across tree
                # Consider a global node counter or prefixing if IDs are not globally unique from dump.
                # For simplicity, assume leaf_index + a large offset or split_index are distinct enough for vis.
                # A safer way is to assign unique IDs during traversal.
                # For now, let's assume we can use them if they are distinct.
                # Let's use a strategy where leaf_index is made distinct from split_index
                node_id = -(
                    node_id + 1
                )  # Make leaf IDs negative and distinct from split_index (which are non-negative)

                condition_str = "Leaf"
                samples = int(node_dict.get("leaf_count", 0))
                leaf_value = node_dict.get(
                    "leaf_value"
                )  # This is the raw prediction value for the leaf
                if leaf_value is not None:
                    value_list = [
                        round(float(leaf_value), 4)
                    ]  # Store as a list for consistency with schema

            elif "split_index" in node_dict:  # Split node
                node_id = int(node_dict["split_index"])
                feature_idx = int(node_dict["split_feature"])
                feature_name = (
                    feature_names[feature_idx]
                    if 0 <= feature_idx < len(feature_names)
                    else f"feature_{feature_idx}"
                )
                threshold = round(float(node_dict["threshold"]), 4)
                decision_type = node_dict.get(
                    "decision_type", "<="
                )  # Default decision type

                # Note: LightGBM decision_type can be '==', '<=', etc.
                condition_str = f"{feature_name} {decision_type} {threshold}"
                samples = int(node_dict.get("internal_count", 0))

                # For split nodes, 'value' can represent impurity or some other metric, not direct class probabilities.
                # It's often better to leave it None for split nodes in the visualization unless it's meaningful.
                # internal_value = node_dict.get("internal_value")
                # if internal_value is not None: value_list = [round(float(internal_value), 4)]

            else:
                logger.warning(
                    f"Unknown node structure in LightGBM tree dump: {node_dict}"
                )
                return

            if node_id is None:  # Should not happen if parsing correctly
                return

            # Create and store the node
            nodes[node_id] = DecisionPathNode(
                id=str(node_id),  # Ensure ID is string for schema
                condition=condition_str,
                samples=samples,
                value=value_list,
            )

            if parent_id is not None and branch_taken is not None:
                edges.append((parent_id, node_id, branch_taken))

            # Recursively process children
            if "left_child" in node_dict:
                # LightGBM's "default_left" indicates if missing values go left
                # The branch label is usually based on the condition being true or false
                traverse_node(
                    node_dict["left_child"],
                    node_id,
                    "True (<=)" if decision_type == "<=" else "Left",
                )  # Adjust label based on decision type
            if "right_child" in node_dict:
                traverse_node(
                    node_dict["right_child"],
                    node_id,
                    "False (>)" if decision_type == "<=" else "Right",
                )

        traverse_node(tree_info.get("tree_structure", {}))
        return nodes, edges

    def _trace_instance_path(
        self,
        instance_series: pd.Series,
        tree_info: Dict[
            str, Any
        ],  # Parsed structure of a single tree from dump_model()
        feature_names: List[str],
        tree_id_prefix: str = "",  # To make node IDs unique across trees
    ) -> Tuple[List[DecisionPathNode], List[DecisionPathEdge]]:

        path_nodes_struct: List[DecisionPathNode] = []
        path_edges_struct: List[DecisionPathEdge] = []

        current_node_dict = tree_info.get("tree_structure")
        parent_node_id_str = None

        while current_node_dict:
            node_id_str: Optional[str] = None
            condition_str: Optional[str] = None
            samples: Optional[int] = None
            value_list: Optional[List[float]] = None
            next_node_dict = None
            edge_label_to_next = None

            if "leaf_index" in current_node_dict:  # Leaf node
                leaf_idx = int(current_node_dict["leaf_index"])
                node_id_str = f"{tree_id_prefix}L{leaf_idx}"  # Unique leaf ID
                condition_str = "Leaf"
                samples = int(current_node_dict.get("leaf_count", 0))
                leaf_value = current_node_dict.get("leaf_value")
                if leaf_value is not None:
                    value_list = [round(float(leaf_value), 4)]

                next_node_dict = None  # End of path

            elif "split_index" in current_node_dict:  # Split node
                split_idx = int(current_node_dict["split_index"])
                node_id_str = f"{tree_id_prefix}S{split_idx}"  # Unique split ID

                feature_idx = int(current_node_dict["split_feature"])
                feature_name = (
                    feature_names[feature_idx]
                    if 0 <= feature_idx < len(feature_names)
                    else f"feature_{feature_idx}"
                )

                threshold = current_node_dict[
                    "threshold"
                ]  # Keep as original type for comparison
                decision_type = current_node_dict.get("decision_type", "<=")

                condition_str = (
                    f"{feature_name} {decision_type} {round(float(threshold), 4)}"
                )
                samples = int(current_node_dict.get("internal_count", 0))

                instance_value = instance_series.get(feature_name)

                # Handle missing values: LightGBM has a 'missing_type' and 'default_left'
                goes_left = current_node_dict.get(
                    "default_left", True
                )  # Default behavior if missing
                if pd.isna(instance_value):
                    logger.debug(
                        f"Instance has missing value for feature {feature_name}. Defaulting left: {goes_left}"
                    )
                    # Decision depends on 'default_left'
                elif decision_type == "<=":
                    goes_left = instance_value <= threshold
                elif decision_type == "==":  # Exact match
                    goes_left = instance_value == threshold
                # Add other decision_types if LightGBM uses more (e.g., '>')
                else:
                    logger.warning(
                        f"Unsupported decision type '{decision_type}' in LightGBM tree. Path may be incorrect."
                    )
                    # Fallback or error
                    break

                if goes_left:
                    next_node_dict = current_node_dict.get("left_child")
                    edge_label_to_next = (
                        "True" if decision_type == "<=" else "=="
                    )  # Adjust based on condition
                else:
                    next_node_dict = current_node_dict.get("right_child")
                    edge_label_to_next = "False" if decision_type == "<=" else "!="

            else:  # Should not happen
                logger.error(f"Node with unknown structure: {current_node_dict}")
                break

            if node_id_str:
                path_nodes_struct.append(
                    DecisionPathNode(
                        id=node_id_str,
                        condition=condition_str,
                        samples=samples,
                        value=value_list,
                    )
                )
                if parent_node_id_str and edge_label_to_next:
                    path_edges_struct.append(
                        DecisionPathEdge(
                            source=parent_node_id_str,
                            target=node_id_str,
                            label=edge_label_to_next,
                        )
                    )
                parent_node_id_str = node_id_str

            current_node_dict = next_node_dict
            if not current_node_dict:  # Reached a leaf or end of traversal
                break

        return path_nodes_struct, path_edges_struct

    def explain(
        self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame
    ) -> Optional[DecisionPathResultData]:
        if not isinstance(self.model, lgb.LGBMClassifier):
            logger.error(
                f"LightGBMDecisionPathStrategy requires an LGBMClassifier model. Got: {type(self.model).__name__}"
            )
            return None
        if X_inference.empty:
            logger.warning("LightGBMDecisionPathStrategy: Input DataFrame is empty.")
            return None

        logger.info(
            f"Generating LightGBM Decision Path explanations for {len(X_inference)} instances..."
        )

        try:
            booster = self.model.booster_
            if booster is None:
                logger.error("LightGBM model's booster_ attribute is None.")
                return None

            model_dump = booster.dump_model()
            trees_info: List[Dict[str, Any]] = model_dump.get("tree_info", [])

            if not trees_info:
                logger.warning("No trees found in LightGBM model dump.")
                return DecisionPathResultData(instance_decision_paths=[])

            feature_names = (
                self.model.feature_name_
                if hasattr(self.model, "feature_name_") and self.model.feature_name_
                else X_inference.columns.tolist()
            )  # Fallback to X_inference columns

            instance_paths_result: List[InstanceDecisionPath] = []

            # Explain path for a limited number of trees (e.g., first one)
            num_trees_to_explain = min(
                1, len(trees_info)
            )  # Change this to explain more trees

            for i in range(len(X_inference)):
                instance_series = X_inference.iloc[i]
                instance_id_row = identifiers_df.iloc[i]

                for tree_idx in range(num_trees_to_explain):
                    single_tree_info = trees_info[tree_idx]
                    tree_id_prefix = f"T{tree_idx}_"  # Prefix to distinguish nodes from different trees

                    nodes, edges = self._trace_instance_path(
                        instance_series, single_tree_info, feature_names, tree_id_prefix
                    )

                    if nodes:  # Only add if a path was successfully traced
                        instance_paths_result.append(
                            InstanceDecisionPath(
                                file=instance_id_row.get("file"),
                                class_name=instance_id_row.get("class_name"),
                                nodes=nodes,
                                edges=edges,
                                # tree_index=tree_idx # Optional: if you want to distinguish paths
                            )
                        )

            if not instance_paths_result:
                logger.warning(
                    "LightGBMDecisionPathStrategy generated no valid instance paths."
                )
                return DecisionPathResultData(instance_decision_paths=[])

            return DecisionPathResultData(instance_decision_paths=instance_paths_result)

        except Exception as e:
            logger.error(
                f"Error generating LightGBM Decision Path explanation: {e}",
                exc_info=True,
            )
            return None
