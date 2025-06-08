// frontend/lib/apiService.ts
import { toast } from "@/hooks/use-toast";

// Centralized API Types
import {
  PaginatedRepositoryRead, // Assuming this is already defined
  DatasetCreatePayload,
  DatasetTaskResponse,
  RuleDefinition, // Assuming this is defined in a new file or dataset.ts
  PaginatedDatasetRead, // For getDatasets (used in other parts, good to have)
  MLModelRead, 
  PaginatedMLModelRead,
  TrainingJobCreatePayload, 
  TrainingJobSubmitResponse,
  TrainingJobRead,
  DatasetRead,
  Repository,
  AvailableModelType,
  DashboardSummaryStats,
  PaginatedTrainingJobRead,
  PaginatedHPSearchJobRead,
  PaginatedCommitList, 
  CommitPageResponse,
  TaskResponse,
  FeatureSelectionDefinition,
  BotPatternRead,
  BotPatternCreatePayload,
  BotPatternUpdatePayload,
  PaginatedBotPatternRead,
} from "@/types/api"; // Assuming types are in @/types/api/*

const API_BASE_URL =  `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/v1`;

export interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiErrorResponse {
  detail?: string | ValidationErrorDetail[] | string[];
  message?: string;
}

export class ApiError extends Error {
  status: number;
  errorData: ApiErrorResponse;

  constructor(message: string, status: number, errorData: ApiErrorResponse = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorData = errorData;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  
  const config: RequestInit = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let errorData: ApiErrorResponse = { message: `HTTP error! status: ${response.status}` };
      try {
        const parsedError = await response.json();
        if (parsedError && (parsedError.detail || parsedError.message)) {
          errorData = parsedError;
        }
      } catch (e) {
        errorData.message = response.statusText || errorData.message;
      }
      
      let userMessage = "An API error occurred.";
      if (typeof errorData.detail === 'string') {
        userMessage = errorData.detail;
      } else if (Array.isArray(errorData.detail) && errorData.detail.length > 0) {
        const firstError = errorData.detail[0];
        if (
          typeof firstError === 'object' &&
          firstError !== null &&
          'msg' in firstError &&
          'loc' in firstError &&
          Array.isArray(firstError.loc) // Ensure 'loc' is an array
        ) {
          userMessage = `Validation Error: ${firstError.loc.join(' -> ')} - ${firstError.msg}`;
        } else if (typeof firstError === 'string') {
          userMessage = firstError;
        }
      } else if (errorData.message) {
        userMessage = errorData.message;
      }

      console.error("API Error:", { url, status: response.status, data: errorData });
      throw new ApiError(userMessage, response.status, errorData);
    }

    if (response.status === 204) {
      return null as T;
    }

    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    console.error("Network or unexpected error in API request:", { url, error });
    throw new ApiError(
      "A network error occurred. Please check your connection and try again.", 
      0, 
      { message: (error as Error).message }
    );
  }
}

export const apiService = {
  get: async <T>(endpoint: string, options?: RequestInit): Promise<T> => {
    return request<T>(endpoint, { ...options, method: 'GET' });
  },
  post: async <TResponse, TRequestData = any>(endpoint: string, data?: TRequestData, options?: RequestInit): Promise<TResponse> => {
    return request<TResponse>(endpoint, { ...options, method: 'POST', body: data ? JSON.stringify(data) : undefined });
  },
  put: async <TResponse, TRequestData = any>(endpoint: string, data: TRequestData, options?: RequestInit): Promise<TResponse> => {
    return request<TResponse>(endpoint, { ...options, method: 'PUT', body: JSON.stringify(data) });
  },
  delete: async <TResponse>(endpoint: string, options?: RequestInit): Promise<TResponse> => {
    return request<TResponse>(endpoint, { ...options, method: 'DELETE' });
  },

  // --- Bot Patterns ---
  getGlobalBotPatterns: async (params?: { skip?: number; limit?: number }): Promise<PaginatedBotPatternRead> => {
    const queryParams = new URLSearchParams(params as any).toString();
    return apiService.get<PaginatedBotPatternRead>(`/bot-patterns?${queryParams}`);
  },

  getRepoBotPatterns: async (repoId: number, params?: { skip?: number; limit?: number, include_global?: boolean }): Promise<PaginatedBotPatternRead> => {
    const queryParams = new URLSearchParams(params as any).toString();
    return apiService.get<PaginatedBotPatternRead>(`/repositories/${repoId}/bot-patterns?${queryParams}`);
  },
  
  createBotPattern: async (payload: BotPatternCreatePayload): Promise<BotPatternRead> => {
    if (payload.repository_id) {
      // Repository-specific
      return apiService.post<BotPatternRead, BotPatternCreatePayload>(`/repositories/${payload.repository_id}/bot-patterns`, payload);
    } else {
      // Global
      return apiService.post<BotPatternRead, BotPatternCreatePayload>('/bot-patterns', payload);
    }
  },

  updateBotPattern: async (patternId: number, payload: BotPatternUpdatePayload): Promise<BotPatternRead> => {
    return apiService.put<BotPatternRead, BotPatternUpdatePayload>(`/bot-patterns/${patternId}`, payload);
  },

  deleteBotPattern: async (patternId: number): Promise<void> => {
    return apiService.delete<void>(`/bot-patterns/${patternId}`);
  },

  // --- Dashboard ---
  getDashboardSummaryStats: async (): Promise<DashboardSummaryStats> => {
    return apiService.get<DashboardSummaryStats>('/dashboard/stats');
  },

  // --- Repositories ---
  getRepositories: async (params?: { skip?: number; limit?: number }): Promise<PaginatedRepositoryRead> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', String(params.skip));
    if (params?.limit !== undefined) queryParams.append('limit', String(params.limit));
    return apiService.get<PaginatedRepositoryRead>(`/repositories?${queryParams.toString()}`);
  },
  
  // --- Datasets ---
  getAvailableCleaningRules: async (): Promise<RuleDefinition[]> => {
    return apiService.get<RuleDefinition[]>('/datasets/available-cleaning-rules');
  },
  getAvailableFeatureSelectionAlgorithms: async (): Promise<FeatureSelectionDefinition[]> => {
    return apiService.get<FeatureSelectionDefinition[]>('/datasets/available-feature-selection-algorithms');
  },
  createDataset: async (repoId: string | number, payload: DatasetCreatePayload): Promise<DatasetTaskResponse> => {
    return apiService.post<DatasetTaskResponse, DatasetCreatePayload>(`/repositories/${repoId}/datasets`, payload);
  },
  getDatasets: async (params?: { skip?: number; limit?: number; status?: string; repository_id?: string | number }): Promise<PaginatedDatasetRead> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', String(params.skip));
    if (params?.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params?.status) queryParams.append('status', params.status);
    if (params?.repository_id !== undefined) queryParams.append('repository_id', String(params.repository_id)); // Add repo_id if provided
    return apiService.get<PaginatedDatasetRead>(`/datasets?${queryParams.toString()}`);
  },
  // --- ML Models ---

  getAvailableModelTypes: async (): Promise<AvailableModelType[]> => {
    return request<AvailableModelType[]>('/ml/model-types');
  },
  getModels: async (params?: {
    skip?: number;
    limit?: number;
    model_name?: string;
    model_type?: string;
    dataset_id?: number;
    repository_id?: number; // Add if backend supports listing models by repo
  }): Promise<PaginatedMLModelRead> => {
    const queryParams = new URLSearchParams();
    if (params) {
        if (params.skip !== undefined) queryParams.append('skip', String(params.skip));
        if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
        if (params.model_name) queryParams.append('model_name', params.model_name);
        if (params.model_type) queryParams.append('model_type', params.model_type);
        if (params.dataset_id !== undefined) queryParams.append('dataset_id', String(params.dataset_id));
        if (params.repository_id !== undefined) queryParams.append('repository_id', String(params.repository_id));
    }
    return apiService.get<PaginatedMLModelRead>(`/ml/models?${queryParams.toString()}`);
  },

  getModelDetails: async (modelId: number): Promise<MLModelRead> => {
    // This endpoint MUST return hyperparameter_schema for dynamic form generation
    return apiService.get<MLModelRead>(`/ml/models/${modelId}`);
  },

  // --- Training Jobs ---
  submitTrainingJob: async (payload: TrainingJobCreatePayload): Promise<TrainingJobSubmitResponse> => {
    return apiService.post<TrainingJobSubmitResponse, TrainingJobCreatePayload>('/ml/train', payload);
  },

  getTrainingJobDetails: async (jobId: string | number): Promise<TrainingJobRead> => {
    return apiService.get<TrainingJobRead>(`/ml/train/${jobId}`);
  },

  getTrainingJobs: async (params?: { 
    skip?: number; limit?: number; dataset_id?: number; status?: JobStatusEnum, q?: string 
  }): Promise<PaginatedTrainingJobRead> => {
    const queryParams = new URLSearchParams();
    if (params) {
        if (params.skip !== undefined) queryParams.append('skip', String(params.skip));
        if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
        if (params.dataset_id !== undefined) queryParams.append('dataset_id', String(params.dataset_id));
        if (params.status) queryParams.append('status', params.status);
        if (params.q) queryParams.append('q', params.q);
    }
    return apiService.get<PaginatedTrainingJobRead>(`/ml/train?${queryParams.toString()}`);
  },

  getHpSearchJobs: async (params?: { 
    skip?: number; limit?: number; dataset_id?: number; status?: JobStatusEnum; study_name?: string 
  }): Promise<PaginatedHPSearchJobRead> => {
    const queryParams = new URLSearchParams();
    if (params) {
        if (params.skip !== undefined) queryParams.append('skip', String(params.skip));
        if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
        if (params.dataset_id !== undefined) queryParams.append('dataset_id', String(params.dataset_id));
        if (params.status) queryParams.append('status', params.status);
        if (params.study_name) queryParams.append('study_name', params.study_name);
    }
    return apiService.get<PaginatedHPSearchJobRead>(`/ml/search?${queryParams.toString()}`);
  },

  getInferenceJobs: async (params?: GetInferenceJobsParams): Promise<PaginatedInferenceJobRead> => {
    const queryParams = new URLSearchParams();
    if (params) {
      if (params.skip !== undefined) queryParams.append('skip', String(params.skip));
      if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
      if (params.ml_model_id !== undefined) queryParams.append('ml_model_id', String(params.ml_model_id));
      if (params.status !== undefined) queryParams.append('status', params.status);
    }
    const endpoint = `/ml/infer?${queryParams.toString()}`;
    return apiService.get<PaginatedInferenceJobRead>(endpoint);
  },

  getCommits: async (repoId: number | string, params?: { skip?: number; limit?: number }): Promise<PaginatedCommitList> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append('skip', String(params.skip));
    if (params?.limit !== undefined) queryParams.append('limit', String(params.limit));
    return apiService.get<PaginatedCommitList>(`/repositories/${repoId}/commits?${queryParams.toString()}`);
  },

  getCommitDetails: async (repoId: number | string, commitHash: string): Promise<CommitPageResponse> => {
    return apiService.get<CommitPageResponse>(`/repositories/${repoId}/commits/${commitHash}`);
  },

  triggerCommitIngestion: async (repoId: number | string, commitHash: string): Promise<TaskResponse> => {
    return apiService.post<TaskResponse>(`/repositories/${repoId}/commits/${commitHash}/ingest`);
  },
  
};

// Utility to show toast notifications for API errors
export const handleApiError = (
  error: any,
  customTitle: string = "Operation Failed"
) => {
  let description = "An unexpected error occurred. Please try again.";
  if (error instanceof ApiError) {
    description = error.message;
  } else if (error instanceof Error) {
    description = error.message;
  }

  toast({
    title: customTitle,
    description: description,
    variant: "destructive",
  });
};

// --- Dedicated API Service Functions ---
import {
  PaginatedInferenceJobRead,
  InferenceJobRead,
  XAIResultRead,
  XAITriggerResponse,
} from "@/types/api";

import { JobStatusEnum } from "@/types/api/enums";

export interface GetInferenceJobsParams {
  skip?: number;
  limit?: number;
  ml_model_id?: number;
  status?: JobStatusEnum | string;
}

export const getInferenceJobs = async (params?: GetInferenceJobsParams): Promise<PaginatedInferenceJobRead> => {
  const queryParams = new URLSearchParams();
  if (params) {
    if (params.skip !== undefined) queryParams.append('skip', String(params.skip));
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.ml_model_id !== undefined) queryParams.append('ml_model_id', String(params.ml_model_id));
    if (params.status !== undefined) queryParams.append('status', params.status);
  }
  const endpoint = `/ml/infer?${queryParams.toString()}`;
  return apiService.get<PaginatedInferenceJobRead>(endpoint);
};

export const getInferenceJobDetails = async (jobId: string | number): Promise<InferenceJobRead> => {
  return apiService.get<InferenceJobRead>(`/ml/infer/${jobId}`);
};

export const getXAIResultsForJob = async (inferenceJobId: string | number): Promise<XAIResultRead[]> => {
  return apiService.get<XAIResultRead[]>(`/xai/inference-jobs/${inferenceJobId}/xai-results`);
};

export const triggerXAIProcessing = async (inferenceJobId: string | number): Promise<XAITriggerResponse> => {
  return apiService.post<XAITriggerResponse>(`/xai/inference-jobs/${inferenceJobId}/xai-results/trigger`, {});
};