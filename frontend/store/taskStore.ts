// frontend/store/taskStore.ts
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware'; // Optional: for Redux DevTools and persistence

// Ensure API_BASE_URL is correctly defined. It should NOT include /api/v1 if that's already part of the endpoint path.
// The EventSource URL should be the full path to the SSE endpoint.
const SSE_ENDPOINT_URL = `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/v1/tasks/stream-updates`;


export interface TaskStatusUpdatePayload {
  task_id: string;
  task_name?: string;
  status: string; // e.g., "PENDING", "RUNNING", "SUCCESS", "FAILURE", "REVOKED" (from JobStatusEnum or TaskStatusEnum)
  progress?: number | null; // Allow null for progress
  status_message?: string | null;
  job_type?: string | null;   // e.g., "repository_ingestion", "dataset_generation"
  entity_id?: number | string | null;  // ID of the repo, dataset, etc.
  entity_type?: string | null; // "Repository", "Dataset"
  user_id?: string | null; // If backend starts sending it
  timestamp?: string;
  error_details?: string | null;
  result_summary?: any | null; 
}

interface TaskStoreState {
  taskStatuses: Record<string, TaskStatusUpdatePayload>; // Map task_id to its latest status
  sseIsConnected: boolean; // To track SSE connection status
  sseEventSourceInstance: EventSource | null;
  setTaskStatus: (payload: TaskStatusUpdatePayload) => void;
  removeTaskStatus: (taskId: string) => void; // To clean up finished/old tasks
  connectSSE: () => void;
  disconnectSSE: () => void;
  getTaskStatusById: (taskId: string) => TaskStatusUpdatePayload | undefined;
  getTasksByEntity: (entityType: string, entityId: number | string) => TaskStatusUpdatePayload[];
  getLatestTaskForEntity: (entityType: string, entityId: number | string, jobType?: string) => TaskStatusUpdatePayload | undefined;
}

// Helper to sort tasks by timestamp (descending, newest first)
const sortTasksByTimestamp = (a: TaskStatusUpdatePayload, b: TaskStatusUpdatePayload) => {
 const dateA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
 const dateB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
 return dateB - dateA;
};

export const useTaskStore = create<TaskStoreState>()(
  devtools( // Optional: Redux DevTools integration
    // persist( // Optional: Persist parts of the store to localStorage (be cautious with EventSource)
      (set, get) => ({
        taskStatuses: {},
        sseIsConnected: false,
        sseEventSourceInstance: null,
        
        setTaskStatus: (payload) => {
          console.log(`Zustand: Setting status for task ${payload.task_id}`, payload);
          set((state) => {
            const newState = {
              taskStatuses: {
                ...state.taskStatuses,
                [payload.task_id]: {
                   ...(state.taskStatuses[payload.task_id] || {}), // Merge with existing if any
                   ...payload, // Apply new updates
                }
              },
            };
            console.log('Zustand: New state after update:', newState);
            return newState;
          });
        },

        removeTaskStatus: (taskId) =>
          set((state) => {
            const newStatuses = { ...state.taskStatuses };
            delete newStatuses[taskId];
            return { taskStatuses: newStatuses };
          }),

        connectSSE: () => {
          const { sseEventSourceInstance, sseIsConnected } = get();
          // Prevent multiple connections
          if (sseEventSourceInstance && (sseEventSourceInstance.readyState === EventSource.OPEN || sseEventSourceInstance.readyState === EventSource.CONNECTING)) {
            console.info("SSE connection already active or attempting to connect.");
            return;
          }
          // If an old instance exists but is closed, ensure it's fully cleaned up before creating a new one.
          if (sseEventSourceInstance && sseEventSourceInstance.readyState === EventSource.CLOSED) {
             get().disconnectSSE(); // Clean up listeners on the old instance
          }


          console.log(`Attempting to connect to SSE: ${SSE_ENDPOINT_URL}`);
          // For local dev, ensure backend is running and accessible.
          // Add `withCredentials: true` if your SSE endpoint requires authentication via cookies.
          const es = new EventSource(SSE_ENDPOINT_URL, {withCredentials:true} /*, { withCredentials: true } */);
          
          set({ sseEventSourceInstance: es, sseIsConnected: false }); // Store instance, mark as connecting

          es.onopen = () => {
            console.log("SSE Connection Opened successfully.");
            set({ sseIsConnected: true });
          };

          es.addEventListener('task_update', (event: MessageEvent) => {
            try {
              if (typeof event.data === 'string') {
                const data: TaskStatusUpdatePayload = JSON.parse(event.data);
                console.log("SSE 'task_update' received:", data);
                get().setTaskStatus(data);
                console.log("Updated task statuses:", get().taskStatuses);
              } else {
                console.warn("Received non-string data for 'task_update' event:", event.data);
              }
            } catch (e) {
              console.error("Error parsing SSE 'task_update' data:", e, "Raw data:", event.data);
            }
          });

          es.addEventListener('heartbeat', (event: MessageEvent) => {
           //  const heartbeatData = JSON.parse(event.data);
           //  console.debug("SSE Heartbeat received:", heartbeatData.timestamp);
            // Can be used to confirm connection is live if UI needs it
          });

          es.onerror = (evt) => {
            // 1) If the browser is still trying to reconnect, leave it alone
            if (es.readyState === EventSource.CONNECTING) {
                console.debug("[SSE] transient error, browser will retry …");
                return;
            }

            // 2) Only act when the server told us it’s really over
            if (es.readyState === EventSource.CLOSED) {
                console.warn("[SSE] connection closed by server");
                set({ sseIsConnected: false, sseEventSourceInstance: null });

                // Optional manual back-off if you prefer to control reconnection yourself
                setTimeout(() => get().connectSSE(), 5000);
            }
            };
        },

        disconnectSSE: () => {
          const { sseEventSourceInstance } = get();
          if (sseEventSourceInstance) {
            sseEventSourceInstance.close();
            console.log("SSE Connection Closed by client.");
            set({ sseEventSourceInstance: null, sseIsConnected: false, /* taskStatuses: {} */ }); // Optionally clear statuses on disconnect
          }
        },

        // Selector to get status by task ID
        getTaskStatusById: (taskId: string) => {
          return get().taskStatuses[taskId];
        },

        // Selector to get all tasks related to a specific entity
        getTasksByEntity: (entityType: string, entityId: number | string) => {
          return Object.values(get().taskStatuses).filter(
            task => task.entity_type === entityType && String(task.entity_id) === String(entityId)
          ).sort(sortTasksByTimestamp);
        },
        
        // Selector to get the latest task for a specific entity and optional job type
        getLatestTaskForEntity: (entityType: string, entityId: number | string, jobType?: string) => {
          const tasks = Object.values(get().taskStatuses).filter(task => 
             task.entity_type === entityType && 
             String(task.entity_id) === String(entityId) &&
             (jobType ? task.job_type === jobType : true)
          );
          if (tasks.length === 0) return undefined;
          return tasks.sort(sortTasksByTimestamp)[0]; // Return the newest one
        },
      }),
      {
        name: "ck-guru-task-status-store", // Name for Redux DevTools
        // serialize: (state) => JSON.stringify({ ...state, sseEventSourceInstance: null }), // Don't persist EventSource
        // deserialize: (str) => { // Not needed if not persisting eventSourceInstance
        //   const state = JSON.parse(str);
        //   state.sseEventSourceInstance = null;
        //   return state;
        // },
        // partialize: (state) => ({ // Example if you were persisting
        //   taskStatuses: state.taskStatuses, 
        //   // Do not persist sseIsConnected or sseEventSourceInstance
        // }),
      }
    // ) // End of persist middleware
  )
);

// Optional: Auto-connect SSE when the store is first used/imported
// This is one way, another is via GlobalAppEffects component
// if (typeof window !== 'undefined') { // Ensure it runs only in browser
//   useTaskStore.getState().connectSSE();
// }