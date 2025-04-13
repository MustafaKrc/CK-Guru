# shared/schemas/hp_search_job.py
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from pydantic import BaseModel, Field

from shared.db.models.training_job import JobStatusEnum # Reuse Enum
from .ml_model import MLModelRead

# --- Optuna Configuration within HP Search Config ---
class OptunaConfig(BaseModel):
    n_trials: int = Field(..., gt=0, description="Number of trials to run.")
    # Add other Optuna settings: direction, sampler, pruner config etc.
    direction: str = Field("maximize", description="Direction of optimization ('minimize' or 'maximize').")
    # Example sampler config (could be more complex)
    sampler_type: Optional[str] = Field(None, description="e.g., 'TPESampler', 'RandomSampler'")
    # Example pruner config
    pruner_type: Optional[str] = Field(None, description="e.g., 'MedianPruner', 'HyperbandPruner'")


# --- Hyperparameter Space Definition ---
# Use Optuna's suggestion types as hints
class HPSuggestion(BaseModel):
    param_name: str
    suggest_type: str = Field(..., description="e.g., 'float', 'int', 'categorical', 'loguniform'")
    # Define bounds/choices based on type
    low: Optional[float | int] = None # For float/int/loguniform
    high: Optional[float | int] = None # For float/int
    step: Optional[float | int] = None # For float/int
    choices: Optional[List[Any]] = None # For categorical

# --- HP Search Job Config ---
class HPSearchConfig(BaseModel):
    model_name: str = Field(..., description="Logical name prefix for models created during search.")
    model_type: str = Field(..., description="Type/architecture of the model.")
    hp_space: List[HPSuggestion] = Field(..., description="List defining the hyperparameter search space.")
    optuna_config: OptunaConfig = Field(...)
    save_best_model: bool = Field(True, description="Whether to train and save the model with best parameters.")

    feature_columns: List[str] = Field(..., description="List of features to use for evaluating trials.")
    target_column: str = Field(..., description="Name of the target column for evaluating trials.")
    # -------------------
    hp_space: List[HPSuggestion] = Field(..., description="Hyperparameter search space.")
    optuna_config: OptunaConfig = Field(...)
    save_best_model: bool = Field(True, description="Train and save the best model.")
    random_seed: Optional[int] = Field(42)
    hp_search_cv_folds: Optional[int] = Field(3, description="CV folds within objective function.")

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

# --- Read (API Response) ---
class HPSearchJobRead(HPSearchJobBase):
    id: int
    celery_task_id: Optional[str] = None
    status: JobStatusEnum
    status_message: Optional[str] = None
    best_trial_id: Optional[int] = None
    best_params: Optional[Dict[str, Any]] = None
    best_value: Optional[float] = None
    best_ml_model_id: Optional[int] = None
    best_ml_model: Optional[MLModelRead] = Field(None, description="Details of the best model created (if any).") # Nested model
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "use_enum_values": True # Serialize Enum member to its value
    }

# --- API Response for Job Submission ---
class HPSearchJobSubmitResponse(BaseModel):
    job_id: int
    celery_task_id: str
    message: str = "Hyperparameter search job submitted successfully."