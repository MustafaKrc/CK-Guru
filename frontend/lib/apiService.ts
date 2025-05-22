// frontend/lib/apiService.ts
import { toast } from "@/hooks/use-toast"; // Assuming useToast is available for error notifications

const API_BASE_URL =  `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/v1`;

export interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiErrorResponse {
  detail?: string | ValidationErrorDetail[] | string[]; // FastAPI error format
  message?: string; // Generic message
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
      // Authorization: `Bearer ${getToken()}` // Example for future auth
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let errorData: ApiErrorResponse = { message: `HTTP error! status: ${response.status}` };
      try {
        // Try to parse error response from backend
        const parsedError = await response.json();
        if (parsedError && (parsedError.detail || parsedError.message)) {
          errorData = parsedError;
        }
      } catch (e) {
        // If parsing fails, use the status text or a generic message
        errorData.message = response.statusText || errorData.message;
      }
      
      // Construct a user-friendly error message
      let userMessage = "An API error occurred.";
      if (typeof errorData.detail === 'string') {
        userMessage = errorData.detail;
      } else if (Array.isArray(errorData.detail) && errorData.detail.length > 0) {
        // Handle FastAPI validation errors which now have a typed loc
        const firstError = errorData.detail[0];
        if (
          typeof firstError === 'object' &&
          firstError !== null &&
          'msg' in firstError &&
          'loc' in firstError
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

    if (response.status === 204) { // No Content
      return null as T; // Or undefined, depending on how you want to handle it
    }

    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error; // Re-throw ApiError instances
    }
    // Handle network errors or other fetch-related issues
    console.error("Network or unexpected error in API request:", { url, error });
    throw new ApiError(
      "A network error occurred. Please check your connection and try again.", 
      0, // 0 for network or unknown errors
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
};

// --- Dedicated API Service Functions ---
// Import types from the centralized location. Assuming `~/types/api` resolves correctly.
import {
  PaginatedInferenceJobRead,
  InferenceJobRead,
  XAIResultRead,
  XAITriggerResponse,
  JobStatusEnum, // For potential use in params
} from "~/types/api"; // This path should work if tsconfig paths are set up

export interface GetInferenceJobsParams {
  skip?: number;
  limit?: number;
  ml_model_id?: number;
  status?: JobStatusEnum | string; // Allow string for flexibility if enum isn't strictly used in query
  // Add other query parameters as needed, e.g., search_query, sort_by
}

export const getInferenceJobs = async (params?: GetInferenceJobsParams): Promise<PaginatedInferenceJobRead> => {
  const queryParams = new URLSearchParams();
  if (params) {
    if (params.skip !== undefined) queryParams.append('skip', String(params.skip));
    if (params.limit !== undefined) queryParams.append('limit', String(params.limit));
    if (params.ml_model_id !== undefined) queryParams.append('ml_model_id', String(params.ml_model_id));
    if (params.status !== undefined) queryParams.append('status', params.status);
  }
  const endpoint = `/ml-jobs/infer?${queryParams.toString()}`;
  return apiService.get<PaginatedInferenceJobRead>(endpoint);
};

export const getInferenceJobDetails = async (jobId: string | number): Promise<InferenceJobRead> => {
  return apiService.get<InferenceJobRead>(`/ml-jobs/infer/${jobId}`);
};

export const getXAIResultsForJob = async (inferenceJobId: string | number): Promise<XAIResultRead[]> => {
  return apiService.get<XAIResultRead[]>(`/xai/inference-jobs/${inferenceJobId}/xai-results`);
};

export const triggerXAIProcessing = async (inferenceJobId: string | number): Promise<XAITriggerResponse> => {
  return apiService.post<XAITriggerResponse>(`/xai/inference-jobs/${inferenceJobId}/xai-results/trigger`, {});
};


// Utility to show toast notifications for API errors
export const handleApiError = (
  error: any,
  customTitle: string = "Operation Failed"
) => {
  let description = "An unexpected error occurred. Please try again.";
  if (error instanceof ApiError) {
    description = error.message; // Use the user-friendly message from ApiError
  } else if (error instanceof Error) {
    description = error.message;
  }

  toast({
    title: customTitle,
    description: description,
    variant: "destructive",
  });
};