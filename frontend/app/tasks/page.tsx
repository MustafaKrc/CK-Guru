// app/tasks/page.tsx
"use client"

import React, { useState, useEffect, useMemo } from "react"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { RefreshCw, StopCircle, AlertTriangle, CheckCircle, XCircle, Clock, Search, Rss } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PageContainer } from "@/components/ui/page-container"
import { Skeleton } from "@/components/ui/skeleton"
import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore"
import { TaskStatusResponse } from "@/types/api/task"
import { apiService, handleApiError } from "@/lib/apiService"
import Link from "next/link"

const ACTIVE_STATUSES = ["PENDING", "RUNNING", "STARTED", "RECEIVED", "RETRY"];

// Helper function to format dates
function formatDate(dateString?: string | null): string {
  if (!dateString) return "N/A";
  try {
    return new Date(dateString).toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  } catch (e) {
    return "Invalid Date";
  }
};

// Helper function to format task type/name
function formatTaskType(task: TaskStatusUpdatePayload): string {
    const type = task.job_type || task.task_name || 'Unknown Task';
    return type
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
};

const TaskCard: React.FC<{ task: TaskStatusUpdatePayload; onRevoke: (task: TaskStatusUpdatePayload) => void; }> = ({ task, onRevoke }) => {
  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case "SUCCESS":
        return <Badge variant="default" className="bg-green-600 hover:bg-green-700 text-xs"><CheckCircle className="h-3 w-3 mr-1" />Success</Badge>;
      case "RUNNING":
      case "STARTED":
      case "RECEIVED":
        return <Badge variant="outline" className="text-blue-600 border-blue-600 text-xs"><RefreshCw className="h-3 w-3 animate-spin mr-1"/>Running</Badge>;
      case "PENDING":
        return <Badge variant="outline" className="text-yellow-600 border-yellow-600 text-xs"><Clock className="h-3 w-3 mr-1"/>Pending</Badge>;
      case "FAILED":
        return <Badge variant="destructive" className="text-xs"><XCircle className="h-3 w-3 mr-1" />Failed</Badge>;
      case "REVOKED":
        return <Badge variant="destructive" className="bg-gray-500 hover:bg-gray-600 text-xs"><StopCircle className="h-3 w-3 mr-1" />Revoked</Badge>;
      default:
        return <Badge variant="secondary" className="text-xs">{status}</Badge>;
    }
  };
  
  const isTaskActive = ACTIVE_STATUSES.includes(task.status.toUpperCase());
  
  return (
    <Card className="mb-4">
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between">
          <div className="flex-grow">
            <CardTitle className="text-base flex items-center justify-between">
              <span className="truncate" title={formatTaskType(task)}>{formatTaskType(task)}</span>
              {getStatusBadge(task.status)}
            </CardTitle>
            <CardDescription className="text-xs font-mono break-all mt-1">ID: {task.task_id}</CardDescription>
             {task.entity_type && task.entity_id && (
                <CardDescription className="text-xs mt-1">
                    Entity: {task.entity_type} / ID: {task.entity_id}
                </CardDescription>
             )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm pb-4">
        {isTaskActive && task.progress != null && (
          <div>
             <Progress value={task.progress} className="h-2" />
             <p className="text-xs text-muted-foreground text-center mt-1">{task.progress}% complete</p>
          </div>
        )}
        {task.status_message && (
          <p className="text-muted-foreground italic text-xs p-2 bg-muted/50 rounded-md">{task.status_message}</p>
        )}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div><span className="text-muted-foreground">Created:</span> {formatDate(task.timestamp)}</div>
        </div>
        {task.error_details && (
            <div className="space-y-1">
              <h4 className="font-medium text-destructive">Error</h4>
              <pre className="p-2 text-xs border rounded-md border-destructive bg-destructive/10 text-destructive whitespace-pre-wrap max-h-40 overflow-auto">{task.error_details}</pre>
            </div>
        )}
        {task.result_summary && (
            <div className="space-y-1">
              <h4 className="font-medium text-primary">Result Summary</h4>
              <pre className="p-2 text-xs border rounded-md bg-muted whitespace-pre-wrap max-h-40 overflow-auto">{JSON.stringify(task.result_summary, null, 2)}</pre>
            </div>
        )}
      </CardContent>
      {isTaskActive && (
        <CardFooter className="flex justify-end pt-0 pb-4">
            <Button variant="destructive" size="sm" onClick={() => onRevoke(task)}><StopCircle className="mr-2 h-4 w-4" />Revoke</Button>
        </CardFooter>
      )}
    </Card>
  );
};


export default function TaskMonitorPage() {
  const { taskStatuses, sseIsConnected, setTaskStatus } = useTaskStore();
  const { toast } = useToast();

  const [manualTaskId, setManualTaskId] = useState("");
  const [isCheckingManualTask, setIsCheckingManualTask] = useState(false);
  const [manualTaskResult, setManualTaskResult] = useState<TaskStatusUpdatePayload | null>(null);

  const [taskToRevoke, setTaskToRevoke] = useState<TaskStatusUpdatePayload | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);

  const sortedTasks = useMemo(() => {
    return Object.values(taskStatuses).sort((a, b) => {
      const dateA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
      const dateB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
      return dateB - dateA;
    });
  }, [taskStatuses]);

  const activeTasks = useMemo(() => sortedTasks.filter(task => ACTIVE_STATUSES.includes(task.status.toUpperCase())), [sortedTasks]);
  const completedTasks = useMemo(() => sortedTasks.filter(task => !ACTIVE_STATUSES.includes(task.status.toUpperCase())), [sortedTasks]);

  const handleManualCheck = async () => {
    if (!manualTaskId.trim()) {
      toast({ title: "Error", description: "Please enter a Task ID.", variant: "destructive" });
      return;
    }
    setIsCheckingManualTask(true);
    setManualTaskResult(null);
    try {
      const result: TaskStatusResponse = await apiService.getTaskStatus(manualTaskId);
      // Adapt TaskStatusResponse to TaskStatusUpdatePayload
      const payload: TaskStatusUpdatePayload = {
        task_id: result.task_id,
        status: result.status,
        progress: result.progress,
        status_message: result.status_message,
        error_details: result.error,
        result_summary: result.result,
        timestamp: new Date().toISOString(), // Use current time for the update timestamp
      };
      setManualTaskResult(payload);
      setTaskStatus(payload); // Update the global store
    } catch (error) {
      handleApiError(error, "Failed to fetch task status");
    } finally {
      setIsCheckingManualTask(false);
    }
  };
  
  const executeRevokeTask = async () => {
    if (!taskToRevoke?.task_id) return;
    setIsRevoking(true);
    try {
      await apiService.revokeTask(taskToRevoke.task_id);
      toast({ title: "Revocation Sent", description: `Revocation request sent for task ${taskToRevoke.task_id}.` });
      setTaskToRevoke(null);
    } catch (error) {
      handleApiError(error, "Failed to revoke task");
    } finally {
      setIsRevoking(false);
    }
  };
  
  return (
    <MainLayout>
      <PageContainer
        title="Task Monitor"
        description="View real-time and historical status of background jobs."
      >
        <Alert variant={sseIsConnected ? "default" : "destructive"} className="mb-6">
          <Rss className="h-4 w-4" />
          <AlertTitle>Live Feed Status</AlertTitle>
          <AlertDescription>
            {sseIsConnected ? "Connected to the live task feed. Updates will appear automatically." : "Not connected to the live task feed. Data shown may be stale."}
          </AlertDescription>
        </Alert>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Check Specific Task</CardTitle>
            <CardDescription>Enter a task ID to get its latest status from the server.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input placeholder="Enter task ID..." value={manualTaskId} onChange={(e) => setManualTaskId(e.target.value)} />
              <Button onClick={handleManualCheck} disabled={isCheckingManualTask}>
                {isCheckingManualTask ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
                Check
              </Button>
            </div>
          </CardContent>
        </Card>

        {manualTaskResult && (
            <div className="mb-6">
                <h3 className="text-lg font-semibold mb-2">Manual Check Result</h3>
                <TaskCard task={manualTaskResult} onRevoke={setTaskToRevoke} />
            </div>
        )}

        <Tabs defaultValue="active">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="active">Active ({activeTasks.length})</TabsTrigger>
            <TabsTrigger value="completed">Completed ({completedTasks.length})</TabsTrigger>
          </TabsList>
          <TabsContent value="active" className="mt-4">
            {activeTasks.length > 0 ? (
              activeTasks.map(task => <TaskCard key={task.task_id} task={task} onRevoke={setTaskToRevoke} />)
            ) : (
              <p className="text-center text-muted-foreground py-8">No active tasks at the moment.</p>
            )}
          </TabsContent>
          <TabsContent value="completed" className="mt-4">
            {completedTasks.length > 0 ? (
              completedTasks.map(task => <TaskCard key={task.task_id} task={task} onRevoke={setTaskToRevoke} />)
            ) : (
              <p className="text-center text-muted-foreground py-8">No completed tasks found.</p>
            )}
          </TabsContent>
        </Tabs>

        <AlertDialog open={!!taskToRevoke} onOpenChange={(open) => !open && setTaskToRevoke(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Confirm Task Revocation</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to attempt to stop task <strong>{taskToRevoke?.task_id}</strong>?
                This action may not be immediately effective if the task is in a non-interruptible state.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={isRevoking}>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={executeRevokeTask} disabled={isRevoking} className="bg-destructive hover:bg-destructive/90">
                {isRevoking ? <><RefreshCw className="mr-2 h-4 w-4 animate-spin"/>Revoking...</> : "Yes, Revoke Task"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        
      </PageContainer>
    </MainLayout>
  );
}