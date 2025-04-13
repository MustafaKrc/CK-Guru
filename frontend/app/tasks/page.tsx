"use client"

import type React from "react"

import { useState } from "react"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { RefreshCw, StopCircle, AlertTriangle } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

export default function TaskMonitorPage() {
  const [taskId, setTaskId] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [taskData, setTaskData] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const { toast } = useToast()

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
          status: "SUCCESS",
          progress: 100,
          statusMessage: "Task completed successfully",
          result: {
            type: "model_training",
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
          status: "RUNNING",
          progress: 65,
          statusMessage: "Training model (step 3/5)",
          result: null,
        })
      } else if (taskId === "345678") {
        setTaskData({
          id: "345678",
          status: "FAILED",
          progress: 30,
          statusMessage: "Task failed due to an error",
          error: "Out of memory error during model training",
          result: null,
        })
      } else {
        setError("Task not found")
        setTaskData(null)
      }

      setIsLoading(false)
    }, 1000)
  }

  const handleRevokeTask = () => {
    if (!taskData) return

    // In a real app, this would be an API call to revoke the task
    toast({
      title: "Task revocation requested",
      description: `Revocation request sent for task ${taskData.id}`,
    })
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SUCCESS":
        return <Badge>Success</Badge>
      case "RUNNING":
        return (
          <Badge variant="outline" className="flex items-center gap-1">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Running
          </Badge>
        )
      case "FAILED":
        return <Badge variant="destructive">Failed</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">Task Monitor</h1>

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
                  <Button variant="outline" size="sm" onClick={handleRevokeTask}>
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
                <Progress value={taskData.progress} className="bg-muted h-2" indicatorClassName="bg-primary" />
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
      </div>
    </MainLayout>
  )
}
