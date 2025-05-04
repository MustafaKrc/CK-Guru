# worker/dataset/services/cleaning_service.py
import logging
from typing import List, Dict, Any, Optional, Type

import pandas as pd
from pydantic import BaseModel, Field, ValidationError, create_model

from shared.core.config import settings
from .interfaces import ICleaningService
from .cleaning_rules.base import CleaningRuleBase, RuleParamDefinition

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())

class RuleBasedCleaningService(ICleaningService): # Inherit directly from interface
    """Implements cleaning by applying configured rules using an injected registry."""

    def __init__(
        self,
        cleaning_rules_config: List[Dict],
        dataset_config: Dict,
        rule_registry: Dict[str, Type[CleaningRuleBase]] # Accept injected registry
    ):
        # Implement __init__ directly
        self.cleaning_rules_config = cleaning_rules_config
        self.dataset_config = dataset_config
        self.rule_registry = rule_registry
        self.batch_rules_info: List[Dict] = []
        self.global_rules_info: List[Dict] = []
        logger.info(f"Initializing Cleaning Service: {self.__class__.__name__}")
        self._load_and_prepare_rules() # Load rules using the injected registry

    # _validate_and_prepare_params method remains the same
    def _validate_and_prepare_params(self, rule_name: str, rule_params_def: List[RuleParamDefinition], config_params: Dict) -> Optional[BaseModel]:
        """
        Creates a Pydantic model dynamically for rule parameters, validates
        config_params against it, and applies defaults.
        Returns a validated Pydantic model instance or None on failure.
        """
        param_fields = {}
        has_errors = False
        for param_def in rule_params_def:
            field_type: Type = Any # Default type
            if param_def.type == "integer": field_type = int
            elif param_def.type == "float": field_type = float
            elif param_def.type == "string": field_type = str
            elif param_def.type == "boolean": field_type = bool

            field_default = param_def.default
            if param_def.required and field_default is None:
                 field_info = Field(..., description=param_def.description)
            else:
                 field_info = Field(default=field_default, description=param_def.description)

            param_fields[param_def.name] = (Optional[field_type], field_info)

        if not param_fields:
            ParamsModel = create_model(f"{rule_name.capitalize()}Params", **{}) # Empty model
        else:
            ParamsModel = create_model(f"{rule_name.capitalize()}Params", **param_fields)

        try:
            validated_params_model = ParamsModel(**config_params)
            logger.debug(f"Rule '{rule_name}': Parameters validated successfully: {validated_params_model.model_dump()}")
            return validated_params_model
        except ValidationError as e:
            logger.error(f"Rule '{rule_name}': Parameter validation failed.")
            for error in e.errors(): logger.error(f"  - Param '{error['loc'][0]}': {error['msg']}")
            logger.error(f"  - Received Params: {config_params}")
            logger.error(f"  - Expected Schema: {ParamsModel.model_json_schema(indent=2)}")
            return None

    # _load_and_prepare_rules method remains the same
    def _load_and_prepare_rules(self):
        """Loads rule instances using the injected registry and prepares param models."""
        logger.info("Loading and preparing cleaning rule instances...")
        self.batch_rules_info = []
        self.global_rules_info = []

        for rule_cfg in self.cleaning_rules_config:
            rule_name = rule_cfg.get("name")
            is_enabled = rule_cfg.get("enabled", True)
            config_params = rule_cfg.get("params", {})

            if not rule_name or not is_enabled: continue

            rule_cls = self.rule_registry.get(rule_name)
            if rule_cls:
                try:
                    instance = rule_cls()
                    validated_params_model = self._validate_and_prepare_params(rule_name, instance.parameters, config_params)
                    if validated_params_model is None:
                         logger.error(f"Skipping rule '{rule_name}' due to parameter validation errors.")
                         continue
                    rule_info = {'instance': instance, 'params_model': validated_params_model}
                    if instance.is_batch_safe: self.batch_rules_info.append(rule_info)
                    else: self.global_rules_info.append(rule_info)
                    logger.debug(f"Loaded and prepared rule '{rule_name}' (Batch safe: {instance.is_batch_safe})")
                except Exception as e:
                    logger.error(f"Failed to instantiate or prepare rule '{rule_name}': {e}", exc_info=True)
            else:
                logger.warning(f"Rule '{rule_name}' enabled in config but not found in registry.")
        logger.info(f"Loaded and prepared {len(self.batch_rules_info)} batch-safe and {len(self.global_rules_info)} global rules.")

    # apply_batch_rules method remains the same
    def apply_batch_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies all configured batch-safe rules sequentially using prepared params."""
        if not self.batch_rules_info: return df
        logger.debug(f"Applying {len(self.batch_rules_info)} batch-safe cleaning rules...")
        current_df = df
        for rule_info in self.batch_rules_info:
            instance: CleaningRuleBase = rule_info['instance']
            validated_params: BaseModel = rule_info['params_model']
            rule_name = instance.rule_name
            try:
                start_shape = current_df.shape
                current_df = instance.apply(current_df, validated_params.model_dump(), self.dataset_config)
                end_shape = current_df.shape
                if start_shape != end_shape: logger.debug(f"Batch rule '{rule_name}' applied. Shape change: {start_shape} -> {end_shape}")
                if current_df.empty:
                    logger.warning(f"DataFrame became empty after applying batch rule '{rule_name}'.")
                    break
            except Exception as e:
                logger.error(f"Error applying batch rule '{rule_name}': {e}", exc_info=True)
        return current_df

    # apply_global_rules method remains the same
    def apply_global_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies all configured global rules sequentially using prepared params."""
        if not self.global_rules_info: return df
        logger.info(f"Applying {len(self.global_rules_info)} global cleaning rules...")
        current_df = df
        for rule_info in self.global_rules_info:
            instance: CleaningRuleBase = rule_info['instance']
            validated_params: BaseModel = rule_info['params_model']
            rule_name = instance.rule_name
            logger.info(f"Applying global rule: {rule_name}...")
            try:
                start_shape = current_df.shape
                current_df = instance.apply(current_df, validated_params.model_dump(), self.dataset_config)
                end_shape = current_df.shape
                logger.info(f"Global rule '{rule_name}' applied. Shape change: {start_shape} -> {end_shape}")
                if current_df.empty:
                    logger.warning(f"DataFrame became empty after applying global rule '{rule_name}'.")
                    break
            except Exception as e:
                logger.error(f"Error applying global rule '{rule_name}': {e}", exc_info=True)
        logger.info("Finished applying global rules.")
        return current_df