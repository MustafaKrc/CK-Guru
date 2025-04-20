# shared/schemas/hp_search_job.py
import enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from shared.db.models.training_job import JobStatusEnum
from shared.schemas.ml_model import MLModelRead


class ObjectiveMetricEnum(str, enum.Enum):
    F1_WEIGHTED = "f1_weighted"
    AUC = "auc"
    PRECISION_WEIGHTED = "precision_weighted"
    RECALL_WEIGHTED = "recall_weighted"
    ACCURACY = "accuracy"
    # Add more as needed

class SamplerTypeEnum(str, enum.Enum):
    TPE = "tpe"
    RANDOM = "random"
    CMAES = "cmaes"
    # Add more

class PrunerTypeEnum(str, enum.Enum):
    MEDIAN = "median"
    HYPERBAND = "hyperband"
    NOP = "nop" # No pruning
    PERCENTILE = "percentile"
    SUCCESSIVEHALVING = "successivehalving"
    # Add more

class OptunaConfig(BaseModel):
    n_trials: int = Field(..., gt=0, description="Number of trials to run.")
    objective_metric: ObjectiveMetricEnum = Field(
        default=ObjectiveMetricEnum.F1_WEIGHTED,
        description="Metric to optimize ('minimize' or 'maximize' inferred from metric)."
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
        description="Attempt to continue study if name exists (requires matching dataset/model)."
    )
    hp_search_cv_folds: Optional[int] = Field(
        3, ge=2, description="Number of cross-validation folds within the objective function."
    )
    # Direction is now inferred from objective_metric


# --- Hyperparameter Space Definition ---
class HPSuggestion(BaseModel):
    param_name: str
    suggest_type: str = Field(..., description="e.g., 'float', 'int', 'categorical'")
    low: Optional[float | int] = None
    high: Optional[float | int] = None
    step: Optional[float | int] = None
    log: bool = Field(default=False, description="Use logarithmic scale (for float/int).")
    choices: Optional[List[Any]] = None


# --- HP Search Job Config ---
class HPSearchConfig(BaseModel):
    model_name: str = Field(..., description="Logical name prefix for models created during search.")
    model_type: str = Field(..., description="Type/architecture of the model.")
    hp_space: List[HPSuggestion] = Field(..., description="List defining the hyperparameter search space.")
    optuna_config: OptunaConfig = Field(..., description="Optuna configuration for the search.")
    save_best_model: bool = Field(True, description="Whether to train and save the model with best parameters.")
    feature_columns: List[str] = Field(..., description="List of features to use for evaluating trials.")
    target_column: str = Field(..., description="Name of the target column for evaluating trials.")
    random_seed: Optional[int] = Field(42)


# --- Base ---
class HPSearchJobBase(BaseModel):
    dataset_id: int = Field(..., description="ID of the dataset to use for the search.")
    optuna_study_name: str = Field(..., description="Unique name for the Optuna study.")
    config: HPSearchConfig = Field(..., description="Hyperparameter search configuration.")


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

    model_config = ConfigDict(extra='ignore') # Allow extra fields if needed


class HPSearchJobRead(HPSearchJobBase):
    id: int
    celery_task_id: Optional[str] = None
    status: JobStatusEnum
    status_message: Optional[str] = None
    best_trial_id: Optional[int] = None
    best_params: Optional[Dict[str, Any]] = None
    best_value: Optional[float] = None
    best_ml_model_id: Optional[int] = None
    best_ml_model: Optional[MLModelRead] = Field(None, description="Details of the best model created (if any).")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True # Serialize Enum member to its value
    )


# --- API Response for Job Submission ---
class HPSearchJobSubmitResponse(BaseModel):
    job_id: int
    celery_task_id: str
    message: str = "Hyperparameter search job submitted successfully."
