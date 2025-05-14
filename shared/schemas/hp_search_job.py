# shared/schemas/hp_search_job.py
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import field_validator  # For Pydantic v2 field_validator
from pydantic import model_validator  # For Pydantic v2 model_validator
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from shared.core.config import settings
from shared.schemas.enums import (
    JobStatusEnum,
    ModelTypeEnum,
    ObjectiveMetricEnum,
    PrunerTypeEnum,
    SamplerTypeEnum,
)
from shared.schemas.ml_model import MLModelRead

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL.upper())


class OptunaConfig(BaseModel):
    n_trials: int = Field(..., gt=0, description="Number of trials to run.")
    objective_metric: ObjectiveMetricEnum = Field(
        default=ObjectiveMetricEnum.F1_WEIGHTED,
        description="Metric to optimize ('minimize' or 'maximize' inferred from metric).",
    )
    sampler_type: SamplerTypeEnum = Field(
        default=SamplerTypeEnum.TPE, description="Optuna sampler algorithm."
    )
    sampler_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional arguments for the sampler."
    )
    pruner_type: PrunerTypeEnum = Field(
        default=PrunerTypeEnum.MEDIAN, description="Optuna pruner algorithm."
    )
    pruner_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional arguments for the pruner."
    )
    continue_if_exists: bool = Field(
        default=False,
        description="Attempt to continue study if name exists (requires matching dataset/model).",
    )
    hp_search_cv_folds: Optional[int] = Field(
        3,  # Changed from 5 to 3 as per your input
        ge=2,
        description="Number of cross-validation folds within the objective function.",
    )


# --- Hyperparameter Space Definition ---
class HPSuggestion(BaseModel):
    param_name: str
    suggest_type: str = Field(..., description="e.g., 'float', 'int', 'categorical'")
    low: Optional[float | int] = None  # Made generic for float or int
    high: Optional[float | int] = None  # Made generic for float or int
    step: Optional[float | int] = (
        None  # Made generic for float or int, will validate specific type below
    )
    log: bool = Field(
        default=False, description="Use logarithmic scale (for float/int)."
    )
    choices: Optional[List[Any]] = None

    @field_validator("suggest_type")
    @classmethod
    def suggest_type_must_be_valid(cls, value: str) -> str:
        valid_types = ["float", "int", "categorical"]
        if value.lower() not in valid_types:
            raise ValueError(
                f"suggest_type must be one of {valid_types}, got '{value}'"
            )
        return value.lower()  # Normalize

    @model_validator(mode="after")  # Pydantic V2 model_validator
    def check_fields_based_on_type(self) -> "HPSuggestion":
        st = self.suggest_type  # Already normalized by field_validator

        if st == "categorical":
            if (
                self.choices is None
                or not isinstance(self.choices, list)
                or not self.choices
            ):
                raise ValueError(
                    f"For suggest_type 'categorical', 'choices' must be a non-empty list (param_name: {self.param_name})."
                )
            if self.low is not None or self.high is not None or self.step is not None:
                logger.warning(
                    f"For suggest_type 'categorical', 'low', 'high', and 'step' are ignored (param_name: {self.param_name})."
                )
        elif st in ["int", "float"]:
            if self.low is None or self.high is None:
                raise ValueError(
                    f"For suggest_type '{st}', 'low' and 'high' are required (param_name: {self.param_name})."
                )
            if not isinstance(self.low, (int, float)) or not isinstance(
                self.high, (int, float)
            ):
                raise ValueError(
                    f"'low' and 'high' must be numbers for suggest_type '{st}' (param_name: {self.param_name})."
                )
            if self.low >= self.high:
                raise ValueError(
                    f"'low' must be less than 'high' for suggest_type '{st}' (param_name: {self.param_name})."
                )
            if self.choices is not None:
                logger.warning(
                    f"For suggest_type '{st}', 'choices' is ignored (param_name: {self.param_name})."
                )

            # Step validation
            if self.step is not None:
                if not isinstance(self.step, (int, float)):
                    raise ValueError(
                        f"'step' must be a number if provided for suggest_type '{st}' (param_name: {self.param_name})."
                    )
                if self.step <= 0:
                    raise ValueError(
                        f"'step' must be a positive non-zero value if provided for suggest_type '{st}' (param_name: {self.param_name})."
                    )
                if st == "int" and not isinstance(self.step, int):
                    raise ValueError(
                        f"For suggest_type 'int', 'step' must be an integer if provided (param_name: {self.param_name})."
                    )

            # Log validation
            if (
                self.log and self.low <= 0 and st == "float"
            ):  # log scale for float needs positive low
                raise ValueError(
                    f"For log scale with suggest_type 'float', 'low' must be positive (param_name: {self.param_name})."
                )
            if (
                self.log and self.low <= 0 and st == "int"
            ):  # log scale for int needs positive low
                raise ValueError(
                    f"For log scale with suggest_type 'int', 'low' must be positive (param_name: {self.param_name})."
                )

        return self

    model_config = ConfigDict(extra="ignore")


# --- HP Search Job Config ---
class HPSearchConfig(BaseModel):
    model_name: str = Field(
        ..., description="Logical name prefix for models created during search."
    )
    model_type: ModelTypeEnum = Field(
        ..., description="Type/architecture of the model."
    )
    hp_space: List[HPSuggestion] = Field(
        ..., description="List defining the hyperparameter search space."
    )
    optuna_config: OptunaConfig = Field(
        ..., description="Optuna configuration for the search."
    )
    save_best_model: bool = Field(
        True, description="Whether to train and save the model with best parameters."
    )
    feature_columns: List[str] = Field(
        ..., description="List of features to use for evaluating trials."
    )
    target_column: str = Field(
        ..., description="Name of the target column for evaluating trials."
    )
    random_seed: Optional[int] = Field(42)


# --- Base ---
class HPSearchJobBase(BaseModel):
    dataset_id: int = Field(..., description="ID of the dataset to use for the search.")
    optuna_study_name: str = Field(..., description="Unique name for the Optuna study.")
    config: HPSearchConfig = Field(
        ..., description="Hyperparameter search configuration."
    )


# --- Create (API Request Body) ---
class HPSearchJobCreate(HPSearchJobBase):
    pass


# --- Update (Used internally by worker) ---
class HPSearchJobUpdate(BaseModel):
    celery_task_id: Optional[str] = None
    status: Optional[JobStatusEnum] = None
    status_message: Optional[str] = None
    best_trial_id: Optional[int] = None
    best_params: Optional[Dict[str, Any]] = None
    best_value: Optional[float] = None
    best_ml_model_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")  # Forbid extra fields to catch typos


class HPSearchJobRead(HPSearchJobBase):
    id: int
    celery_task_id: Optional[str] = None
    status: JobStatusEnum
    status_message: Optional[str] = None
    best_trial_id: Optional[int] = None
    best_params: Optional[Dict[str, Any]] = None
    best_value: Optional[float] = None
    best_ml_model_id: Optional[int] = None
    best_ml_model: Optional[MLModelRead] = Field(
        None, description="Details of the best model created by this search (if any)."
    )
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# --- API Response for Job Submission ---
class HPSearchJobSubmitResponse(BaseModel):
    job_id: int
    celery_task_id: str
    message: str = "Hyperparameter search job submitted successfully."
