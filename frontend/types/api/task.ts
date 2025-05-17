// frontend/types/api/task.ts

/**
 * Mirrored from shared.schemas.task.TaskStatusEnum
 */
export enum TaskStatusEnum {
  PENDING = "PENDING",
  RECEIVED = "RECEIVED",
  STARTED = "STARTED",
  SUCCESS = "SUCCESS",
  FAILURE = "FAILURE",
  RETRY = "RETRY",
  REVOKED = "REVOKED",
}

/**
 * Mirrored from shared.schemas.task.TaskResponse
 */
export interface TaskResponse {
  task_id: string;
  message: string;
}

/**
 * Mirrored from shared.schemas.task.TaskStatusResponse
 */
export interface TaskStatus {
  task_id: string;
  status: TaskStatusEnum;
  progress?: number | null;
  status_message?: string | null;
  result?: any | null;
  error?: string | null;
}