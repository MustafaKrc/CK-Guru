"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { RefreshCw, StopCircle, AlertTriangle, Clock, CheckCircle, XCircle } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface Task {
  id: string
  type: string
  status: "RUNNING" | "SUCCESS" | "FAILED" | "PENDING"
  progress: number
  statusMessage: string
  createdAt: string
  completedAt?: string
  error?: string
  result?: any
}

export default function TaskMonitorPage() {
  const [taskId, setTaskId] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [taskData, setTaskData] = useState<Task | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [runningTasks, setRunningTasks] = useState<Task[]>([])
  const [recentTasks, setRecentTasks] = useState<Task[]>([])
  const [isLoadingTasks, setIsLoadingTasks] = useState(true)
  const { toast } = useToast()

  // Fetch running and recent tasks on mount
  useEffect(() => {
    fetchTasks()
  }, [])

  const fetchTasks = () => {
    setIsLoadingTasks(true)

    // In a real app, this would be an API call to fetch tasks
    setTimeout(() => {
      // Mock data for running tasks
      const mockRunningTasks: Task[] = [
        {
          id: "task-789012",
          type: "MODEL_TRAINING",
          status: "RUNNING",
          progress: 65,
          statusMessage: "Training model (step 3/5)",
          createdAt: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
        },
        {
          id: "task-789013",
          type: "DATASET_CREATION",
          status: "RUNNING",
          progress: 30,
          statusMessage: "Processing data files",
          createdAt: new Date(Date.now() - 1800000).toISOString(), // 30 minutes ago
        },
        {
          id: "task-789014",
          type: "REPOSITORY_INGESTION",
          status: "PENDING",
          progress: 0,
          statusMessage: "Waiting to start",
          createdAt: new Date(Date.now() - 300000).toISOString(), // 5 minutes ago
        },
      ]

      // Mock data for recent tasks
      const mockRecentTasks: Task[] = [
        {
          id: "task-123456",
          type: "MODEL_TRAINING",
          status: "SUCCESS",
          progress: 100,
          statusMessage: "Task completed successfully",
          createdAt: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
          completedAt: new Date(Date.now() - 82800000).toISOString(), // 23 hours ago
          result: {
            modelId: "model-123",
            metrics: {
              f1: 0.85,
              accuracy: 0.88,
            },
          },
        },
        {
          id: "task-345678",
          type: "DATASET_CREATION",
          status: "FAILED",
          progress: 30,
          statusMessage: "Task failed due to an error",
          createdAt: new Date(Date.now() - 43200000).toISOString(), // 12 hours ago
          completedAt: new Date(Date.now() - 41400000).toISOString(), // 11.5 hours ago
          error: "Out of memory error during data processing",
        },
        {
          id: "task-567890",
          type: "INFERENCE",
          status: "SUCCESS",
          progress: 100,
          statusMessage: "Inference completed successfully",
          createdAt: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
          completedAt: new Date(Date.now() - 5400000).toISOString(), // 1.5 hours ago
          result: {
            predictionsCount: 1250,
            averageConfidence: 0.92,
          },
        },
      ]

      setRunningTasks(mockRunningTasks)
      setRecentTasks(mockRecentTasks)
      setIsLoadingTasks(false)
    }, 1000)
  }

  const handleTaskIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setTaskId(e.target.value)
  }

  const handleCheckStatus = () => {
    if (!taskId.trim()) {
      setError("Please enter a task ID")
      return
    }

    setIsLoading(true)
    setError(null)

    // In a real app, this would be an API call to check the task status
    setTimeout(() => {
      // Mock response based on the task ID
      if (taskId === "123456") {
        setTaskData({
          id: "123456",
          type: "MODEL_TRAINING",
          status: "SUCCESS",
          progress: 100,
          statusMessage: "Task completed successfully",
          createdAt: new Date(Date.now() - 86400000).toISOString(),
          completedAt: new Date(Date.now() - 82800000).toISOString(),
          result: {
            modelId: "model-123",
            metrics: {
              f1: 0.85,
              accuracy: 0.88,
            },
          },
        })
      } else if (taskId === "789012") {
        setTaskData({
          id: "789012",
          type: "MODEL_TRAINING",
          status: "RUNNING",
          progress: 65,
          statusMessage: "Training model (step 3/5)",
          createdAt: new Date(Date.now() - 3600000).toISOString(),
        })
      } else if (taskId === "345678") {
        setTaskData({
          id: "345678",
          type: "DATASET_CREATION",
          status: "FAILED",
          progress: 30,
          statusMessage: "Task failed due to an error",
          createdAt: new Date(Date.now() - 43200000).toISOString(),
          completedAt: new Date(Date.now() - 41400000).toISOString(),
          error: "Out of memory error during data processing",
        })
      } else {
        setError("Task not found")
        setTaskData(null)
      }

      setIsLoading(false)
    }, 1000)
  }

  const handleRevokeTask = (taskId: string) => {
    // In a real app, this would be an API call to revoke the task
    toast({
      title: "Task revocation requested",
      description: `Revocation request sent for task ${taskId}`,
    })
  }

  const handleRefreshTasks = () => {
    fetchTasks()
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SUCCESS":
        return (
          <Badge
            variant="outline"
            className="bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-400 dark:border-green-800"
          >
            <CheckCircle className="h-3 w-3 mr-1" />
            Success
          </Badge>
        )
      case "RUNNING":
        return (
          <Badge
            variant="outline"
            className="flex items-center gap-1 bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-400 dark:border-blue-800"
          >
            <RefreshCw className="h-3 w-3 animate-spin" />
            Running
          </Badge>
        )
      case "PENDING":
        return (
          <Badge
            variant="outline"
            className="flex items-center gap-1 bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-400 dark:border-yellow-800"
          >
            <Clock className="h-3 w-3" />
            Pending
          </Badge>
        )
      case "FAILED":
        return (
          <Badge
            variant="outline"
            className="bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-400 dark:border-red-800"
          >
            <XCircle className="h-3 w-3 mr-1" />
            Failed
          </Badge>
        )
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString()
  }

  const formatTaskType = (type: string) => {
    return type
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase())
  }

  const renderTaskCard = (task: Task) => {
    return (
      <Card key={task.id} className="mb-4">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">{formatTaskType(task.type)}</CardTitle>
                {getStatusBadge(task.status)}
              </div>
              <CardDescription className="mt-1">ID: {task.id}</CardDescription>
            </div>
            {task.status === "RUNNING" && (
              <Button variant="outline" size="sm" onClick={() => handleRevokeTask(task.id)}>
                <StopCircle className="mr-2 h-4 w-4" />
                Revoke
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pb-2">
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Progress</span>
              <span>{task.progress}%</span>
            </div>
            <Progress value={task.progress} className="bg-muted h-2" />
          </div>

          <div className="space-y-1">
            <h3 className="text-sm font-medium">Status</h3>
            <p className="text-sm">{task.statusMessage}</p>
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-muted-foreground">Created:</span> {formatDate(task.createdAt)}
            </div>
            {task.completedAt && (
              <div>
                <span className="text-muted-foreground">Completed:</span> {formatDate(task.completedAt)}
              </div>
            )}
          </div>

          {task.error && (
            <div className="space-y-1">
              <h3 className="text-sm font-medium text-destructive">Error</h3>
              <div className="p-3 text-sm border rounded-md border-destructive bg-destructive/10 text-destructive">
                {task.error}
              </div>
            </div>
          )}

          {task.result && (
            <div className="space-y-1">
              <h3 className="text-sm font-medium">Result</h3>
              <div className="p-3 text-sm border rounded-md bg-muted">
                <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(task.result, null, 2)}</pre>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    )
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-bold tracking-tight">Task Monitor</h1>
          <Button variant="outline" size="sm" onClick={handleRefreshTasks} disabled={isLoadingTasks}>
            {isLoadingTasks ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Refreshing...
              </>
            ) : (
              <>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </>
            )}
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Check Task Status</CardTitle>
            <CardDescription>Enter a task ID to check its current status and progress</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input placeholder="Enter task ID" value={taskId} onChange={handleTaskIdChange} />
              <Button onClick={handleCheckStatus} disabled={isLoading}>
                {isLoading ? (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                    Checking...
                  </>
                ) : (
                  "Check Status"
                )}
              </Button>
            </div>

            {error && (
              <div className="flex items-center p-4 text-sm border rounded-md border-destructive bg-destructive/10 text-destructive">
                <AlertTriangle className="h-4 w-4 mr-2" />
                {error}
              </div>
            )}
          </CardContent>
        </Card>

        {taskData && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Task {taskData.id}</CardTitle>
                  <CardDescription>Status: {getStatusBadge(taskData.status)}</CardDescription>
                </div>
                {taskData.status === "RUNNING" && (
                  <Button variant="outline" size="sm" onClick={() => handleRevokeTask(taskData.id)}>
                    <StopCircle className="mr-2 h-4 w-4" />
                    Revoke Task
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Progress</span>
                  <span>{taskData.progress}%</span>
                </div>
                <Progress value={taskData.progress} className="bg-muted h-2" />
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">Status Message</h3>
                <p className="text-sm">{taskData.statusMessage}</p>
              </div>

              {taskData.error && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-destructive">Error</h3>
                  <div className="p-4 text-sm border rounded-md border-destructive bg-destructive/10 text-destructive">
                    {taskData.error}
                  </div>
                </div>
              )}

              {taskData.result && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium">Result</h3>
                  <div className="p-4 text-sm border rounded-md bg-muted">
                    <pre className="whitespace-pre-wrap">{JSON.stringify(taskData.result, null, 2)}</pre>
                  </div>
                </div>
              )}
            </CardContent>
            <CardFooter>
              <p className="text-xs text-muted-foreground">
                Task information is updated in real-time. Refresh to get the latest status.
              </p>
            </CardFooter>
          </Card>
        )}

        <Tabs defaultValue="running" className="mt-6">
          <TabsList>
            <TabsTrigger value="running">Running Tasks ({runningTasks.length})</TabsTrigger>
            <TabsTrigger value="recent">Recent Tasks ({recentTasks.length})</TabsTrigger>
          </TabsList>
          <TabsContent value="running" className="mt-4">
            {isLoadingTasks ? (
              <div className="flex justify-center py-8">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : runningTasks.length > 0 ? (
              <div>{runningTasks.map(renderTaskCard)}</div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">No running tasks at the moment</div>
            )}
          </TabsContent>
          <TabsContent value="recent" className="mt-4">
            {isLoadingTasks ? (
              <div className="flex justify-center py-8">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : recentTasks.length > 0 ? (
              <div>{recentTasks.map(renderTaskCard)}</div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">No recent tasks to display</div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </MainLayout>
  )
}
