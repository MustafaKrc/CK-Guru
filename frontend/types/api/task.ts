// frontend/types/api/task.ts

/**
 * Mirrored from shared.schemas.task.TaskStatusEnum
 */
export enum TaskStatusEnum {
  PENDING = "PENDING",
  RECEIVED = "RECEIVED",  // Task received by a worker
  STARTED = "STARTED",  // Task started execution
  SUCCESS = "SUCCESS",  // Task completed successfully
  FAILURE = "FAILURE",  // Task failed
  RETRY = "RETRY",  // Task is being retried
  REVOKED = "REVOKED",  // Task was revoked.
}

/**
 * Mirrored from shared.schemas.task.TaskResponse
 */
export interface TaskResponse {
  task_id: string;
  message?: string; // Optional message
}

/**
 * Mirrored from shared.schemas.task.TaskStatusResponse.
 * This is the response from GET /tasks/{task_id}
 */
export interface TaskStatusResponse {
  task_id: string;
  status: TaskStatusEnum;
  progress?: number | null;
  status_message?: string | null;
  result?: any | null;
  error?: string | null;
}