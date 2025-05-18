// frontend/types/api/dataset.ts
import { DatasetStatusEnum } from "./enums"; // Import from the local enums file

// This interface should mirror shared/schemas/dataset.py -> DatasetConfig
export interface DatasetConfig {
  feature_columns: string[];
  target_column: string;
  cleaning_rules: { // Mirrors CleaningRuleConfig
    name: string;
    enabled: boolean;
    params?: Record<string, any>; // Parameters specific to this rule
  }[];
}

// This interface should mirror shared/schemas/dataset.py -> DatasetRead
export interface DatasetRead {
  id: number;
  repository_id: number;
  name: string;
  description?: string | null;
  config: DatasetConfig;
  status: DatasetStatusEnum | string; // Allow string for robustness if enum values might not match perfectly initially
  status_message?: string | null;
  storage_path?: string | null;
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
  background_data_path?: string | null;
  num_rows?: number | null; // Number of rows in the dataset
}

// Payload for creating a dataset, mirrors shared/schemas/dataset.py -> DatasetCreate
export interface DatasetCreatePayload {
    name: string;
    description?: string | null;
    // repository_id is part of the URL path, not payload body for POST /repositories/{repo_id}/datasets
    config: DatasetConfig;
}

// Response when a dataset creation task is submitted, mirrors shared/schemas/dataset.py -> DatasetTaskResponse
export interface DatasetTaskResponse {
    dataset_id: number; // Corrected from 'int' to 'number'
    task_id: string;
}

export interface PaginatedDatasetRead {
  items: DatasetRead[];
  total: number;
}