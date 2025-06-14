// frontend/lib/taskUtils.ts
import { TaskStatusUpdatePayload } from "@/store/taskStore"; // Adjust path as needed

/**
 * Finds the latest relevant task status for a given entity.
 * @param taskStatuses - The global map of task statuses from useTaskStore.
 * @param entityType - The type of the entity (e.g., "Repository", "Dataset", "MLModel").
 * @param entityId - The ID of the entity.
 * @param jobType - (Optional) The specific job type for the entity (e.g., "repository_ingestion", "dataset_generation").
 * @returns The latest TaskStatusUpdatePayload for the entity, or undefined.
 */
export const getLatestTaskForEntity = (
  taskStatuses: Record<string, TaskStatusUpdatePayload>,
  entityType: string,
  entityId: number | string,
  jobType?: string
): TaskStatusUpdatePayload | undefined => {
  // Explicitly check for null or undefined entityId.
  // Allows 0 or "" to be processed if they are valid IDs.
  if (entityId === null || entityId === undefined) {
    return undefined;
  }

  const relevantTasks = Object.values(taskStatuses).filter((task) => {
    // Entity type check:
    // 1. task.entity_type must exist (not null/undefined).
    // 2. If it exists, it must match the provided entityType (case-insensitive).
    const entityTypeMatch =
      task.entity_type && // Ensures task.entity_type is not null or undefined
      task.entity_type.toLowerCase() === entityType.toLowerCase();

    // Entity ID check:
    // Convert both to string for consistent comparison.
    // This handles cases where task.entity_id might be a number and entityId a string, or vice-versa.
    // String(null) becomes "null", String(undefined) becomes "undefined".
    const entityIdMatch = String(task.entity_id) === String(entityId);

    // Job type check:
    // If jobType is provided, task.job_type must match.
    // If jobType is not provided, this part of the condition is true.
    const jobTypeMatch = jobType ? task.job_type === jobType : true;

    return entityTypeMatch && entityIdMatch && jobTypeMatch;
  });

  if (relevantTasks.length === 0) return undefined;

  // Sort by timestamp (descending - newest first).
  // Fallback sort for identical timestamps uses task_id parts.
  return relevantTasks.sort((a, b) => {
    const dateA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
    const dateB = b.timestamp ? new Date(b.timestamp).getTime() : 0;

    // If timestamps are different, sort by them
    if (dateB !== dateA) return dateB - dateA;

    // Timestamps are identical (or both invalid/missing), fallback to task_id parsing.
    // Ensure radix is specified for parseInt and handle potential NaN results.
    const idPartBStr = b.task_id.split("-").pop() || "0";
    const idPartAStr = a.task_id.split("-").pop() || "0";

    const idPartB = parseInt(idPartBStr, 10);
    const idPartA = parseInt(idPartAStr, 10);

    // Treat NaN as 0 for comparison purposes to ensure stable sort,
    // though this might not be ideal for all task_id formats.
    // A more sophisticated fallback might be needed if task_ids are not numeric.
    const valB = isNaN(idPartB) ? 0 : idPartB;
    const valA = isNaN(idPartA) ? 0 : idPartA;

    return valB - valA;
  })[0];
};
