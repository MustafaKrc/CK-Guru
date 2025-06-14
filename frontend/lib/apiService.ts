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
  TaskStatusResponse,
  FeatureSelectionDefinition,
  BotPatternRead,
  BotPatternCreatePayload,
  BotPatternUpdatePayload,
  PaginatedBotPatternRead,
  JobStatusEnum,
  PaginatedInferenceJobRead,
  InferenceJobRead,
  XAIResultRead,
  XAITriggerResponse,
} from "@/types/api";

const API_BASE_URL = `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/v1`;

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

export interface GetModelsParams {
  skip?: number;
  limit?: number;
  nameFilter?: string; // Changed from model_name to match backend alias
  model_type?: string;
  dataset_id?: number;
  repository_id?: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}

export interface GetTrainingJobsParams {
  skip?: number;
  limit?: number;
  dataset_id?: number;
  repository_id?: number;
  status?: JobStatusEnum | string;
  nameFilter?: string;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}

export interface GetHpSearchJobsParams extends GetTrainingJobsParams {}

export interface GetInferenceJobsParams {
  skip?: number;
  limit?: number;
  model_id?: number;
  repository_id?: number;
  status?: JobStatusEnum | string;
  nameFilter?: string;
  sortBy?: string;
  sortDir?: "asc" | "desc";
}

async function downloadFile(endpoint: string, options: RequestInit = {}): Promise<Blob> {
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const config: RequestInit = {
    ...options,
    headers: {
      Accept: "application/octet-stream, text/csv, */*", // Accept binary or csv data
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let errorData: ApiErrorResponse = { message: `HTTP error! status: ${response.status}` };
      try {
        const parsedError = await response.json();
        errorData = parsedError;
      } catch (e) {
        // Response might not be JSON, use status text
        errorData.message = response.statusText || errorData.message;
      }
      const userMessage =
        typeof errorData.detail === "string" ? errorData.detail : "File not found or server error.";
      throw new ApiError(userMessage, response.status, errorData);
    }

    // Return the response body as a Blob
    return response.blob();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    console.error("Network or unexpected error in file download:", { url, error });
    throw new ApiError(
      "A network error occurred during download. Please check your connection.",
      0,
      { message: (error as Error).message }
    );
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const config: RequestInit = {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
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
      if (typeof errorData.detail === "string") {
        userMessage = errorData.detail;
      } else if (Array.isArray(errorData.detail) && errorData.detail.length > 0) {
        const firstError = errorData.detail[0];
        if (
          typeof firstError === "object" &&
          firstError !== null &&
          "msg" in firstError &&
          "loc" in firstError &&
          Array.isArray(firstError.loc) // Ensure 'loc' is an array
        ) {
          userMessage = `Validation Error: ${firstError.loc.join(" -> ")} - ${firstError.msg}`;
        } else if (typeof firstError === "string") {
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
    throw new ApiError("A network error occurred. Please check your connection and try again.", 0, {
      message: (error as Error).message,
    });
  }
}

export const apiService = {
  get: async <T>(endpoint: string, options?: RequestInit): Promise<T> => {
    return request<T>(endpoint, { ...options, method: "GET" });
  },
  post: async <TResponse, TRequestData = any>(
    endpoint: string,
    data?: TRequestData,
    options?: RequestInit
  ): Promise<TResponse> => {
    return request<TResponse>(endpoint, {
      ...options,
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    });
  },
  put: async <TResponse, TRequestData = any>(
    endpoint: string,
    data: TRequestData,
    options?: RequestInit
  ): Promise<TResponse> => {
    return request<TResponse>(endpoint, { ...options, method: "PUT", body: JSON.stringify(data) });
  },
  delete: async <TResponse>(endpoint: string, options?: RequestInit): Promise<TResponse> => {
    return request<TResponse>(endpoint, { ...options, method: "DELETE" });
  },

  downloadFile: downloadFile,

  // --- Task Management ---
  getTaskStatus: async (taskId: string): Promise<TaskStatusResponse> => {
    return apiService.get<TaskStatusResponse>(`/tasks/${taskId}`);
  },

  revokeTask: async (
    taskId: string,
    terminate: boolean = true,
    signal: string = "TERM"
  ): Promise<{ message: string }> => {
    const queryParams = new URLSearchParams({ terminate: String(terminate), signal }).toString();
    return apiService.post<{ message: string }>(`/tasks/${taskId}/revoke?${queryParams}`);
  },

  // --- Bot Patterns ---
  getGlobalBotPatterns: async (params?: {
    skip?: number;
    limit?: number;
  }): Promise<PaginatedBotPatternRead> => {
    const queryParams = new URLSearchParams(params as any).toString();
    return apiService.get<PaginatedBotPatternRead>(`/bot-patterns?${queryParams}`);
  },

  getRepoBotPatterns: async (
    repoId: number,
    params?: { skip?: number; limit?: number; include_global?: boolean }
  ): Promise<PaginatedBotPatternRead> => {
    const queryParams = new URLSearchParams(params as any).toString();
    return apiService.get<PaginatedBotPatternRead>(
      `/repositories/${repoId}/bot-patterns?${queryParams}`
    );
  },

  createBotPattern: async (payload: BotPatternCreatePayload): Promise<BotPatternRead> => {
    if (payload.repository_id) {
      // Repository-specific
      return apiService.post<BotPatternRead, BotPatternCreatePayload>(
        `/repositories/${payload.repository_id}/bot-patterns`,
        payload
      );
    } else {
      // Global
      return apiService.post<BotPatternRead, BotPatternCreatePayload>("/bot-patterns", payload);
    }
  },

  updateBotPattern: async (
    patternId: number,
    payload: BotPatternUpdatePayload
  ): Promise<BotPatternRead> => {
    return apiService.put<BotPatternRead, BotPatternUpdatePayload>(
      `/bot-patterns/${patternId}`,
      payload
    );
  },

  deleteBotPattern: async (patternId: number): Promise<void> => {
    return apiService.delete<void>(`/bot-patterns/${patternId}`);
  },

  // --- Dashboard ---
  getDashboardSummaryStats: async (): Promise<DashboardSummaryStats> => {
    return apiService.get<DashboardSummaryStats>("/dashboard/stats");
  },

  // --- Repositories ---
  getRepositories: async (params?: {
    skip?: number;
    limit?: number;
    sortBy?: string;
    sortDir?: "asc" | "desc";
    nameFilter?: string;
  }): Promise<PaginatedRepositoryRead> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append("skip", String(params.skip));
    if (params?.limit !== undefined) queryParams.append("limit", String(params.limit));
    if (params?.nameFilter) queryParams.append("q", params.nameFilter);
    if (params?.sortBy) queryParams.append("sort_by", params.sortBy);
    if (params?.sortDir) queryParams.append("sort_order", params.sortDir);
    return apiService.get<PaginatedRepositoryRead>(`/repositories?${queryParams.toString()}`);
  },

  // --- Datasets ---
  getAvailableCleaningRules: async (): Promise<RuleDefinition[]> => {
    return apiService.get<RuleDefinition[]>("/datasets/available-cleaning-rules");
  },
  getAvailableFeatureSelectionAlgorithms: async (): Promise<FeatureSelectionDefinition[]> => {
    return apiService.get<FeatureSelectionDefinition[]>(
      "/datasets/available-feature-selection-algorithms"
    );
  },
  createDataset: async (
    repoId: string | number,
    payload: DatasetCreatePayload
  ): Promise<DatasetTaskResponse> => {
    return apiService.post<DatasetTaskResponse, DatasetCreatePayload>(
      `/repositories/${repoId}/datasets`,
      payload
    );
  },
  getDatasets: async (params?: {
    skip?: number;
    limit?: number;
    status?: string;
    repository_id?: string | number;
    nameFilter?: string;
    sortBy?: string;
    sortDir?: "asc" | "desc";
  }): Promise<PaginatedDatasetRead> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append("skip", String(params.skip));
    if (params?.limit !== undefined) queryParams.append("limit", String(params.limit));
    if (params?.status) queryParams.append("status", params.status);
    if (params?.repository_id !== undefined)
      queryParams.append("repository_id", String(params.repository_id));
    if (params?.nameFilter) queryParams.append("name_filter", params.nameFilter);
    if (params?.sortBy) queryParams.append("sort_by", params.sortBy);
    if (params?.sortDir) queryParams.append("sort_order", params.sortDir);
    return apiService.get<PaginatedDatasetRead>(`/datasets?${queryParams.toString()}`);
  },
  // --- ML Models ---

  getAvailableModelTypes: async (): Promise<AvailableModelType[]> => {
    return request<AvailableModelType[]>("/ml/model-types");
  },
  getModels: async (params?: GetModelsParams): Promise<PaginatedMLModelRead> => {
    const queryParams = new URLSearchParams(params as any);
    return apiService.get<PaginatedMLModelRead>(`/ml/models?${queryParams.toString()}`);
  },

  getModelDetails: async (modelId: number): Promise<MLModelRead> => {
    // This endpoint MUST return hyperparameter_schema for dynamic form generation
    return apiService.get<MLModelRead>(`/ml/models/${modelId}`);
  },

  // --- Training Jobs ---
  submitTrainingJob: async (
    payload: TrainingJobCreatePayload
  ): Promise<TrainingJobSubmitResponse> => {
    return apiService.post<TrainingJobSubmitResponse, TrainingJobCreatePayload>(
      "/ml/train",
      payload
    );
  },

  getTrainingJobDetails: async (jobId: string | number): Promise<TrainingJobRead> => {
    return apiService.get<TrainingJobRead>(`/ml/train/${jobId}`);
  },

  getTrainingJobs: async (params?: GetTrainingJobsParams): Promise<PaginatedTrainingJobRead> => {
    const queryParams = new URLSearchParams(params as any);
    return apiService.get<PaginatedTrainingJobRead>(`/ml/train?${queryParams.toString()}`);
  },

  getHpSearchJobs: async (params?: GetHpSearchJobsParams): Promise<PaginatedHPSearchJobRead> => {
    const queryParams = new URLSearchParams(params as any);
    return apiService.get<PaginatedHPSearchJobRead>(`/ml/search?${queryParams.toString()}`);
  },

  getInferenceJobs: async (params?: GetInferenceJobsParams): Promise<PaginatedInferenceJobRead> => {
    const queryParams = new URLSearchParams(params as any);
    return apiService.get<PaginatedInferenceJobRead>(`/ml/infer?${queryParams.toString()}`);
  },

  getCommits: async (
    repoId: number | string,
    params?: { skip?: number; limit?: number }
  ): Promise<PaginatedCommitList> => {
    const queryParams = new URLSearchParams();
    if (params?.skip !== undefined) queryParams.append("skip", String(params.skip));
    if (params?.limit !== undefined) queryParams.append("limit", String(params.limit));
    return apiService.get<PaginatedCommitList>(
      `/repositories/${repoId}/commits?${queryParams.toString()}`
    );
  },

  getCommitDetails: async (
    repoId: number | string,
    commitHash: string
  ): Promise<CommitPageResponse> => {
    return apiService.get<CommitPageResponse>(`/repositories/${repoId}/commits/${commitHash}`);
  },

  triggerCommitIngestion: async (
    repoId: number | string,
    commitHash: string
  ): Promise<TaskResponse> => {
    return apiService.post<TaskResponse>(`/repositories/${repoId}/commits/${commitHash}/ingest`);
  },
};

// Utility to show toast notifications for API errors
export const handleApiError = (error: any, customTitle: string = "Operation Failed") => {
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

export const getInferenceJobDetails = async (jobId: string | number): Promise<InferenceJobRead> => {
  return apiService.get<InferenceJobRead>(`/ml/infer/${jobId}`);
};

export const getXAIResultsForJob = async (
  inferenceJobId: string | number
): Promise<XAIResultRead[]> => {
  return apiService.get<XAIResultRead[]>(`/xai/inference-jobs/${inferenceJobId}/xai-results`);
};

export const triggerXAIProcessing = async (
  inferenceJobId: string | number
): Promise<XAITriggerResponse> => {
  return apiService.post<XAITriggerResponse>(
    `/xai/inference-jobs/${inferenceJobId}/xai-results/trigger`,
    {}
  );
};
