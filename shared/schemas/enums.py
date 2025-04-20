# shared/schemas/enums.py
# NEW FILE to hold shared enums
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

class ModelTypeEnum(str, enum.Enum):
    """Enum defining the supported model types."""
    SKLEARN_RANDOMFOREST = "sklearn_randomforest"
    # Add other models here as they are supported
    # EXAMPLE: SKLEARN_LOGISTICREGRESSION = "sklearn_logisticregression"
    # EXAMPLE: PYTORCH_CNN = "pytorch_cnn"