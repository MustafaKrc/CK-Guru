# shared/schemas/enums.py
import enum

class JobStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    REVOKED = "revoked"

class DatasetStatusEnum(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"

class ObjectiveMetricEnum(str, enum.Enum):
    F1_WEIGHTED = "f1_weighted"
    AUC = "auc"
    PRECISION_WEIGHTED = "precision_weighted"
    RECALL_WEIGHTED = "recall_weighted"
    ACCURACY = "accuracy"

class SamplerTypeEnum(str, enum.Enum):
    TPE = "tpe"
    RANDOM = "random"
    CMAES = "cmaes"

class PrunerTypeEnum(str, enum.Enum):
    MEDIAN = "median"
    HYPERBAND = "hyperband"
    NOP = "nop"
    PERCENTILE = "percentile"
    SUCCESSIVEHALVING = "successivehalving"

class ModelTypeEnum(str, enum.Enum):
    """Enum defining the supported model types."""
    SKLEARN_RANDOMFOREST = "sklearn_randomforest"
    # Add other models here as they are supported
    # EXAMPLE: SKLEARN_LOGISTICREGRESSION = "sklearn_logisticregression"
    # EXAMPLE: PYTORCH_CNN = "pytorch_cnn"

class XAITypeEnum(str, enum.Enum):
    SHAP = "shap"
    LIME = "lime"
    FEATURE_IMPORTANCE = "feature_importance"
    DECISION_PATH = "decision_path"
    COUNTERFACTUALS = "counterfactuals"

class XAIStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"