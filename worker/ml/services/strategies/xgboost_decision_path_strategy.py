# worker/ml/services/strategies/xgboost_decision_path_strategy.py
import json
import logging
import re  # For parsing conditions
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import xgboost as xgb  # type: ignore

from shared.schemas.xai import (
    DecisionPathEdge,
    DecisionPathNode,
    DecisionPathResultData,
    InstanceDecisionPath,
)

from .base_decision_path_strategy import BaseDecisionPathStrategy

logger = logging.getLogger(__name__)


class XGBoostDecisionPathStrategy(BaseDecisionPathStrategy):
    def __init__(self, model: Any, background_data: Optional[pd.DataFrame] = None):
        super().__init__(model, background_data)
        if not isinstance(self.model, xgb.XGBClassifier) and not isinstance(
            self.model, xgb.XGBModel
        ):
            logger.warning(
                f"XGBoostDecisionPathStrategy initialized with non-XGBoost model: {type(self.model).__name__}"
            )

    # _parse_xgboost_condition remains the same
    def _parse_xgboost_condition(
        self, condition_str: str, feature_names: List[str]
    ) -> str:
        match = re.match(r"\[f(\d+)([<>=!]+)(.+)\]", condition_str)
        if match:
            feature_idx = int(match.group(1))
            operator = match.group(2)
            value_str = match.group(3)
            feature_name = (
                feature_names[feature_idx]
                if 0 <= feature_idx < len(feature_names)
                else f"feature_{feature_idx}"
            )
            try:
                threshold = round(float(value_str), 4)
                return f"{feature_name} {operator} {threshold}"
            except ValueError:
                return f"{feature_name} {operator} {value_str}"
        return condition_str

    def _trace_instance_path_for_tree(
        self,
        instance_series: pd.Series,
        tree_dump_json: Dict[str, Any],
        feature_names: List[str],
        tree_id_prefix: str = "",
    ) -> Tuple[List[DecisionPathNode], List[DecisionPathEdge]]:

        path_nodes_struct: List[DecisionPathNode] = []
        path_edges_struct: List[DecisionPathEdge] = []

        current_node_json = tree_dump_json
        parent_node_id_str_for_edge = None
        edge_label_to_current = None

        while True:
            node_id = int(current_node_json["nodeid"])
            node_id_str = f"{tree_id_prefix}N{node_id}"

            samples: Optional[int] = None
            if "cover" in current_node_json:
                samples = int(round(current_node_json["cover"]))

            if "leaf" in current_node_json:
                leaf_value = round(float(current_node_json["leaf"]), 4)
                path_nodes_struct.append(
                    DecisionPathNode(
                        id=node_id_str,
                        condition="Leaf",
                        samples=samples,
                        value=[leaf_value],
                    )
                )
                if parent_node_id_str_for_edge and edge_label_to_current:
                    path_edges_struct.append(
                        DecisionPathEdge(
                            source=parent_node_id_str_for_edge,
                            target=node_id_str,
                            label=edge_label_to_current,
                        )
                    )
                break
            else:
                split_feature_code = current_node_json["split"]
                split_condition_value_raw = current_node_json["split_condition"]

                feature_idx_match = re.match(r"f(\d+)", split_feature_code)
                feature_idx = -1
                if feature_idx_match:
                    feature_idx = int(feature_idx_match.group(1))

                feature_name = (
                    feature_names[feature_idx]
                    if 0 <= feature_idx < len(feature_names)
                    else split_feature_code
                )

                condition_str = (
                    f"{feature_name} < {round(float(split_condition_value_raw), 4)}"
                )

                path_nodes_struct.append(
                    DecisionPathNode(
                        id=node_id_str,
                        condition=condition_str,
                        samples=samples,
                        value=None,
                    )
                )

                if parent_node_id_str_for_edge and edge_label_to_current:
                    path_edges_struct.append(
                        DecisionPathEdge(
                            source=parent_node_id_str_for_edge,
                            target=node_id_str,
                            label=edge_label_to_current,
                        )
                    )

                instance_value = instance_series.get(feature_name)

                next_node_id_int: Optional[int] = None
                edge_label_for_next_edge: Optional[str] = None

                if pd.isna(instance_value):
                    next_node_id_int = int(current_node_json["missing"])
                    edge_label_for_next_edge = "Missing"
                    logger.debug(
                        f"Instance feature '{feature_name}' is NaN, taking 'missing' branch to node {next_node_id_int}"
                    )
                elif instance_value < float(split_condition_value_raw):
                    next_node_id_int = int(current_node_json["yes"])
                    edge_label_for_next_edge = "True (<)"
                else:
                    next_node_id_int = int(current_node_json["no"])
                    edge_label_for_next_edge = "False (>=)"

                parent_node_id_str_for_edge = node_id_str
                edge_label_to_current = edge_label_for_next_edge

                found_next = False
                if "children" in current_node_json:
                    for child_node_json in current_node_json.get("children", []):
                        if child_node_json["nodeid"] == next_node_id_int:
                            current_node_json = child_node_json
                            found_next = True
                            break
                if not found_next:
                    logger.error(
                        f"Could not find child node with ID {next_node_id_int} in tree dump. Path tracing incomplete."
                    )
                    break

        return path_nodes_struct, path_edges_struct

    def explain(
        self, X_inference: pd.DataFrame, identifiers_df: pd.DataFrame
    ) -> Optional[DecisionPathResultData]:
        if not isinstance(self.model, (xgb.XGBClassifier, xgb.XGBModel)):
            logger.error(
                f"XGBoostDecisionPathStrategy requires an XGBoost model. Got: {type(self.model).__name__}"
            )
            return None
        if X_inference.empty:
            logger.warning("XGBoostDecisionPathStrategy: Input DataFrame is empty.")
            return None

        logger.info(
            f"Generating XGBoost Decision Path explanations for {len(X_inference)} instances..."
        )

        try:
            booster = self.model.get_booster()
            if booster is None:
                logger.error("XGBoost model's booster object is None.")
                return None

            if hasattr(booster, "feature_names") and booster.feature_names:
                feature_names = booster.feature_names
            else:
                feature_names = X_inference.columns.tolist()
                logger.warning(
                    "XGBoost booster has no feature_names. Using X_inference columns. Ensure order matches training."
                )

            # Get all tree dumps at once if tree_ids is not supported for get_dump
            # Some versions of get_dump() without tree_ids will dump all trees.
            all_tree_dumps_str_list: List[str] = []
            try:
                all_tree_dumps_str_list = booster.get_dump(dump_format="json")
                if not isinstance(all_tree_dumps_str_list, list) or not all(
                    isinstance(item, str) for item in all_tree_dumps_str_list
                ):
                    logger.error(
                        f"booster.get_dump() did not return a list of strings as expected. Type: {type(all_tree_dumps_str_list)}"
                    )
                    # Fallback to trying dump_model with fout=None, which also failed previously but good to have a sequence of attempts
                    try:
                        logger.info(
                            "Trying booster.dump_model(fout=None, dump_format='json') as an alternative."
                        )
                        all_tree_dumps_str_list = booster.dump_model(
                            fout=None, dump_format="json"
                        )
                        if not isinstance(all_tree_dumps_str_list, list) or not all(
                            isinstance(item, str) for item in all_tree_dumps_str_list
                        ):
                            logger.error(
                                "booster.dump_model(fout=None) also did not return a list of strings."
                            )
                            return None  # Both main methods failed
                    except Exception as dump_model_err:
                        logger.error(
                            f"booster.dump_model(fout=None) also failed: {dump_model_err}"
                        )
                        return None  # Both main methods failed
            except (
                TypeError
            ) as te:  # Catch if get_dump() itself has unexpected arguments
                logger.error(
                    f"TypeError calling booster.get_dump(dump_format='json'): {te}. XGBoost API might differ."
                )
                return None  # Cannot proceed if tree dump fails

            if not all_tree_dumps_str_list:
                logger.warning("No trees found in XGBoost model dump (get_dump).")
                return DecisionPathResultData(instance_decision_paths=[])

            instance_paths_result: List[InstanceDecisionPath] = []

            num_trees_available = len(all_tree_dumps_str_list)
            num_trees_to_explain = min(1, num_trees_available)  # Explain first tree

            logger.info(
                f"XGBoost model has {num_trees_available} trees available from dump. Explaining paths for the first {num_trees_to_explain} tree(s)."
            )

            for i in range(len(X_inference)):
                instance_series = X_inference.iloc[i]
                instance_id_row = identifiers_df.iloc[i]

                for tree_idx in range(num_trees_to_explain):
                    if tree_idx >= len(all_tree_dumps_str_list):
                        logger.warning(
                            f"Requested tree_idx {tree_idx} is out of bounds for available tree dumps ({len(all_tree_dumps_str_list)})."
                        )
                        break
                    try:
                        single_tree_json_str = all_tree_dumps_str_list[tree_idx]
                        single_tree_parsed_json = json.loads(single_tree_json_str)
                        tree_id_prefix = f"T{tree_idx}_"

                        nodes, edges = self._trace_instance_path_for_tree(
                            instance_series,
                            single_tree_parsed_json,
                            feature_names,
                            tree_id_prefix,
                        )

                        if nodes:
                            instance_paths_result.append(
                                InstanceDecisionPath(
                                    file=instance_id_row.get("file"),
                                    class_name=instance_id_row.get("class_name"),
                                    nodes=nodes,
                                    edges=edges,
                                )
                            )
                    except json.JSONDecodeError as jde:
                        logger.error(
                            f"Failed to parse JSON for tree {tree_idx} dump: '{single_tree_json_str[:100]}...'. Error: {jde}"
                        )
                        continue
                    except Exception as tree_trace_err:
                        logger.error(
                            f"Error tracing path for instance {i}, tree {tree_idx}: {tree_trace_err}",
                            exc_info=True,
                        )
                        continue

            if not instance_paths_result:
                logger.warning(
                    "XGBoostDecisionPathStrategy generated no valid instance paths."
                )
                return DecisionPathResultData(instance_decision_paths=[])

            return DecisionPathResultData(instance_decision_paths=instance_paths_result)

        except Exception as e:
            logger.error(
                f"Error generating XGBoost Decision Path explanation: {e}",
                exc_info=True,
            )
            return None
