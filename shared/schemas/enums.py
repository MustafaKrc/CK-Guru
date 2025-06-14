# shared/schemas/enums.py
import enum


class JobStatusEnum(str, enum.Enum):
    STARTED = "started"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    REVOKED = "revoked"


class DatasetStatusEnum(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class CommitIngestionStatusEnum(str, enum.Enum):
    NOT_INGESTED = "NOT_INGESTED"  # A state for the API response, not stored in DB
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class FileChangeTypeEnum(str, enum.Enum):
    A = "A"  # Added
    M = "M"  # Modified
    D = "D"  # Deleted
    R = "R"  # Renamed
    C = "C"  # Copied
    T = "T"  # Type change (e.g., from file to directory)
    U = "U"  # Unmerged (conflict)
    X = "X"  # Unknown (e.g., file type not recognized)
    B = "B"  # Broken (e.g., file was deleted but still exists in the index)


class FeatureSelectionAlgorithmEnum(str, enum.Enum):
    """Enum defining the supported feature selection algorithm names."""

    CBFS = "cbfs"
    MRMR = "mrmr"
    MODEL_BASED = "model_based"


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
    SKLEARN_LOGISTICREGRESSION = "sklearn_logisticregression"
    SKLEARN_SVC = "sklearn_svc"
    SKLEARN_GRADIENTBOOSTINGCLASSIFIER = "sklearn_gradientboostingclassifier"
    SKLEARN_ADABOOSTCLASSIFIER = "sklearn_adaboostclassifier"
    SKLEARN_DECISIONTREECLASSIFIER = "sklearn_decisiontreeclassifier"
    SKLEARN_KNNCLASSIFIER = "sklearn_knnclassifier"  # k-Nearest Neighbors

    # gradient boosting libraries
    XGBOOST_CLASSIFIER = "xgboost_classifier"
    LIGHTGBM_CLASSIFIER = "lightgbm_classifier"
    # CATBOOST_CLASSIFIER = "catboost_classifier" # Example for later

    # Placeholder for future types (Deep Learning, etc.)
    # PYTORCH_LSTM = "pytorch_lstm"
    # TENSORFLOW_CNN = "tensorflow_cnn"


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
    REVOKED = "revoked"
