// frontend/types/api/enums.ts

export enum DatasetStatusEnum {
  PENDING = "pending",
  GENERATING = "generating",
  READY = "ready",
  FAILED = "failed",
}

export enum CommitIngestionStatusEnum {
    NOT_INGESTED = "NOT_INGESTED",
    PENDING = "PENDING",
    RUNNING = "RUNNING",
    COMPLETE = "COMPLETE",
    FAILED = "FAILED",
}

export enum FileChangeTypeEnum {
    A = "A", // Added
    M = "M", // Modified
    D = "D", // Deleted
    R = "R", // Renamed
    C = "C", // Copied
    T = "T", // Type change
    U = "U", // Unmerged
    X = "X", // Unknown
    B = "B", // Broken
}


export enum JobStatusEnum {
  STARTED = "started",
  PENDING = "pending",
  RUNNING = "running",
  SUCCESS = "success",
  SKIPPED = "skipped",
  FAILED = "failed",
  REVOKED = "revoked",
}

// Add other enums from shared/schemas/enums.py as needed, for example:
export enum ModelTypeEnum {
  SKLEARN_RANDOMFOREST = "sklearn_randomforest",
  SKLEARN_LOGISTICREGRESSION = "sklearn_logisticregression",
  SKLEARN_SVC = "sklearn_svc",
  SKLEARN_GRADIENTBOOSTINGCLASSIFIER = "sklearn_gradientboostingclassifier",
  SKLEARN_ADABOOSTCLASSIFIER = "sklearn_adaboostclassifier",
  SKLEARN_DECISIONTREECLASSIFIER = "sklearn_decisiontreeclassifier",
  SKLEARN_KNNCLASSIFIER = "sklearn_knnclassifier",

  XGBOOST_CLASSIFIER = "xgboost_classifier",
  LIGHTGBM_CLASSIFIER = "lightgbm_classifier",
}

export enum XAITypeEnum {
    SHAP = "shap",
    LIME = "lime",
    FEATURE_IMPORTANCE = "feature_importance",
    DECISION_PATH = "decision_path",
    COUNTERFACTUALS = "counterfactuals",
}

export enum XAIStatusEnum {
    PENDING = "pending",
    RUNNING = "running",
    SUCCESS = "success",
    FAILED = "failed",
    REVOKED = "revoked",
}

export enum ObjectiveMetricEnum {
    F1_WEIGHTED = "f1_weighted",
    AUC = "auc",
    PRECISION_WEIGHTED = "precision_weighted",
    RECALL_WEIGHTED = "recall_weighted",
    ACCURACY = "accuracy",
}

export enum SamplerTypeEnum {
    TPE = "tpe",
    RANDOM = "random",
    CMAES = "cmaes",
}

export enum PrunerTypeEnum {
    MEDIAN = "median",
    HYPERBAND = "hyperband",
    NOP = "nop",
    PERCENTILE = "percentile",
    SUCCESSIVEHALVING = "successivehalving",
}

export enum PatternTypeEnum { // from shared/db/models/bot_pattern.py
    REGEX = "REGEX",
    WILDCARD = "WILDCARD",
    EXACT = "EXACT",
}