// frontend/types/api/xai.ts
import { XAITypeEnum, XAIStatusEnum } from "./enums";

// --- Schemas from shared/schemas/xai.py ---
// Note: Make sure field names match the Pydantic models, especially if using `alias` in Pydantic.
// For example, `class_name: Optional[str] = Field(None, alias="class", ...)` means frontend might receive "class".
// However, for consistency and to avoid issues with TypeScript property names, using `class_name` is often preferred
// and the backend should ideally serialize with `by_alias=False` or ensure frontend matches the alias.
// Assuming backend sends `class_name` or `populate_by_name=True` is used carefully in Pydantic.

export interface FilePredictionDetail { // This is also used by InferenceJob, so it needs to be consistent or imported.
  file_path: string; // Path to the file
  predicted_label: number; // The prediction for this specific file
  prediction_probability: number; // The probability for this prediction
  class_name?: string | null; // Optional class name if applicable
  // file?: string; // Alternative if schema uses 'file' instead of 'file_path'
}

export interface FeatureImportanceValue {
  feature: string;
  importance: number;
}

export interface FeatureImportanceResultData {
  feature_importances: FeatureImportanceValue[];
}

export interface FeatureSHAPValue {
  feature: string;
  value: number;
  feature_value?: any;
}

export interface InstanceSHAPResult {
  file?: string | null;
  class_name?: string | null; // Using class_name instead of 'class'
  shap_values: FeatureSHAPValue[];
  base_value?: number;
}

export interface SHAPResultData {
  instance_shap_values: InstanceSHAPResult[];
}

export interface InstanceLIMEResult {
  file?: string | null;
  class_name?: string | null; // Using class_name
  explanation: [string, number][]; // List of (feature, weight) tuples
}

export interface LIMEResultData {
  instance_lime_values: InstanceLIMEResult[];
}

export interface CounterfactualExample {
  features: Record<string, any>;
  outcome_probability: number;
}

export interface InstanceCounterfactualResult {
  file?: string | null;
  class_name?: string | null; // Using class_name
  counterfactuals: CounterfactualExample[];
}

export interface CounterfactualResultData {
  instance_counterfactuals: InstanceCounterfactualResult[];
}

export interface DecisionPathNode {
  id: string; // Node ID
  condition?: string | null; // Condition for splitting (non-leaf)
  samples?: number | null; // Number of samples at this node
  value?: number[] | number[][] | null; // Class distribution or value at leaf
}

export interface DecisionPathEdge {
  source: string; // Source node ID
  target: string; // Target node ID
  label?: string | null; // Label for the edge (e.g., "True", "False")
}

export interface InstanceDecisionPath {
  file?: string | null;
  class_name?: string | null; // Using class_name
  nodes: DecisionPathNode[];
  edges: DecisionPathEdge[];
}

export interface DecisionPathResultData {
  instance_decision_paths: InstanceDecisionPath[];
}

// --- Schemas from shared/schemas/xai_job.py ---
export interface XAIResultRead {
  id: number;
  inference_job_id: number;
  xai_type: XAITypeEnum;
  status: XAIStatusEnum;
  status_message?: string | null;
  result_data?: FeatureImportanceResultData | SHAPResultData | LIMEResultData | CounterfactualResultData | DecisionPathResultData | Record<string, any> | null;
  celery_task_id?: string | null;
  started_at?: string | null; // ISO date string
  completed_at?: string | null; // ISO date string
  created_at: string; // ISO date string
  updated_at: string; // ISO date string
}

export interface XAITriggerResponse {
  task_id?: string | null;
  message: string;
}
