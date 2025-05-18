// frontend/types/api/inference-job.ts
import { JobStatusEnum } from "./enums";
// Assuming FilePredictionDetail is also typed if needed for detailed view
// For now, prediction_result is Record<string, any> as per schema, but we can refine
// based on InferenceResultPackage from shared/schemas/inference_job.py

export interface FilePredictionDetail {
    file?: string | null;
    class_name?: string | null; // Matches 'class' alias
    prediction: number;
    probability: number;
}

export interface InferenceResultPackage {
    commit_prediction: number;
    max_bug_probability: number;
    num_files_analyzed: number;
    details?: FilePredictionDetail[] | null;
    error?: string | null;
}

export interface InferenceJobRead {
  id: number;
  ml_model_id: number;
  input_reference: Record<string, any>; // e.g., { commit_hash, repo_id, trigger_source }
  celery_task_id?: string | null;
  status: JobStatusEnum;
  status_message?: string | null;
  prediction_result?: InferenceResultPackage | null; // Use the defined package
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

// For triggering manual inference (matches ManualInferenceRequest)
export interface ManualInferenceRequestPayload {
    repo_id: number;
    target_commit_hash: string;
    ml_model_id: number;
}

// For the API response when triggering inference (matches InferenceTriggerResponse)
export interface InferenceTriggerResponse {
    inference_job_id: number;
    initial_task_id: string; // This is the feature extraction task ID
}

export interface PaginatedInferenceJobRead {
  items: InferenceJobRead[];
  total: number;
}
