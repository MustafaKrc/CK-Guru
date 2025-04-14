"use client"

import { useState, useEffect, useRef } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowLeft, BarChart3, Download, Eye } from "lucide-react"
import Link from "next/link"

// Mock data for models
const mockModels = [
  {
    id: "1",
    name: "RandomForest-frontend-1",
    version: "1.0.0",
    type: "RandomForest",
    dataset: "frontend-app-dataset-1",
    datasetId: "1",
    repository: "frontend-app",
    repositoryId: "1",
    dateCreated: "2023-04-16T10:20:00Z",
    sourceJob: "train-job-1",
    hyperparameters: {
      n_estimators: 100,
      max_depth: 10,
      min_samples_split: 2,
      min_samples_leaf: 1,
      bootstrap: true,
    },
    metrics: {
      f1: 0.85,
      accuracy: 0.88,
      precision: 0.82,
      recall: 0.89,
      auc: 0.91,
    },
  },
  {
    id: "2",
    name: "XGBoost-frontend-1",
    version: "1.0.0",
    type: "XGBoost",
    dataset: "frontend-app-dataset-1",
    datasetId: "1",
    repository: "frontend-app",
    repositoryId: "1",
    dateCreated: "2023-04-17T09:15:00Z",
    sourceJob: "train-job-2",
    hyperparameters: {
      n_estimators: 200,
      max_depth: 8,
      learning_rate: 0.1,
      subsample: 0.8,
      colsample_bytree: 0.8,
    },
    metrics: {
      f1: 0.82,
      accuracy: 0.86,
      precision: 0.8,
      recall: 0.84,
      auc: 0.89,
    },
  },
  {
    id: "3",
    name: "RandomForest-backend-1",
    version: "1.0.0",
    type: "RandomForest",
    dataset: "backend-api-dataset-1",
    datasetId: "3",
    repository: "backend-api",
    repositoryId: "2",
    dateCreated: "2023-04-14T11:30:00Z",
    sourceJob: "train-job-3",
    hyperparameters: {
      n_estimators: 150,
      max_depth: 12,
      min_samples_split: 3,
      min_samples_leaf: 2,
      bootstrap: true,
    },
    metrics: {
      f1: 0.79,
      accuracy: 0.83,
      precision: 0.77,
      recall: 0.81,
      auc: 0.85,
    },
  },
  {
    id: "4",
    name: "LogisticRegression-frontend-1",
    version: "1.0.0",
    type: "LogisticRegression",
    dataset: "frontend-app-dataset-2",
    datasetId: "2",
    repository: "frontend-app",
    repositoryId: "1",
    dateCreated: "2023-04-19T14:45:00Z",
    sourceJob: "train-job-4",
    hyperparameters: {
      C: 1.0,
      penalty: "l2",
      solver: "lbfgs",
      max_iter: 100,
      multi_class: "auto",
    },
    metrics: {
      f1: 0.76,
      accuracy: 0.8,
      precision: 0.75,
      recall: 0.78,
      auc: 0.82,
    },
  },
]

export default function ModelComparisonPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const modelIds = searchParams.get("models")?.split(",") || []
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [selectedModels, setSelectedModels] = useState<any[]>([])

  useEffect(() => {
    if (modelIds.length > 0) {
      // In a real app, this would be an API call to fetch the models
      const models = mockModels.filter((model) => modelIds.includes(model.id))
      setSelectedModels(models)
    }
  }, [modelIds])

  // Draw radar chart when selected models change
  useEffect(() => {
    if (selectedModels.length >= 2 && canvasRef.current) {
      drawRadarChart(canvasRef.current, selectedModels)
    }
  }, [selectedModels])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const handleRemoveModel = (modelId: string) => {
    const updatedModels = selectedModels.filter((model) => model.id !== modelId)
    setSelectedModels(updatedModels)

    // Update URL
    const newModelIds = updatedModels.map((model) => model.id).join(",")
    if (newModelIds) {
      router.push(`/model-comparison?models=${newModelIds}`)
    } else {
      router.push("/models")
    }
  }

  // Find the best metric value across all models
  const getBestMetricValue = (metricName: string) => {
    return Math.max(...selectedModels.map((model) => model.metrics[metricName as keyof typeof model.metrics] as number))
  }

  // Check if this model has the best value for a specific metric
  const isBestMetric = (model: any, metricName: string) => {
    const bestValue = getBestMetricValue(metricName)
    return model.metrics[metricName as keyof typeof model.metrics] === bestValue
  }

  // Function to draw radar chart
  const drawRadarChart = (canvas: HTMLCanvasElement, models: any[]) => {
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Set canvas dimensions
    const width = canvas.width
    const height = canvas.height
    const centerX = width / 2
    const centerY = height / 2
    const radius = Math.min(centerX, centerY) * 0.8

    // Define metrics to display
    const metrics = ["accuracy", "f1", "precision", "recall", "auc"]
    const metricLabels = ["Accuracy", "F1 Score", "Precision", "Recall", "AUC"]
    const numMetrics = metrics.length

    // Define colors for each model
    const colors = [
      { stroke: "rgba(59, 130, 246, 0.8)", fill: "rgba(59, 130, 246, 0.2)" }, // Blue
      { stroke: "rgba(139, 92, 246, 0.8)", fill: "rgba(139, 92, 246, 0.2)" }, // Purple
      { stroke: "rgba(16, 185, 129, 0.8)", fill: "rgba(16, 185, 129, 0.2)" }, // Green
      { stroke: "rgba(245, 158, 11, 0.8)", fill: "rgba(245, 158, 11, 0.2)" }, // Yellow
    ]

    // Draw axis lines and labels
    ctx.strokeStyle = "rgba(156, 163, 175, 0.5)"
    ctx.fillStyle = "rgba(107, 114, 128, 1)"
    ctx.font = "12px sans-serif"
    ctx.textAlign = "center"
    ctx.textBaseline = "middle"

    // Draw concentric circles
    const numCircles = 5
    for (let i = 1; i <= numCircles; i++) {
      const circleRadius = (radius * i) / numCircles
      ctx.beginPath()
      ctx.arc(centerX, centerY, circleRadius, 0, 2 * Math.PI)
      ctx.stroke()

      // Add value label for the first circle only
      if (i === 1) {
        ctx.fillText((i * 0.2).toFixed(1), centerX, centerY - circleRadius - 5)
      }
    }

    // Draw axis lines and labels
    for (let i = 0; i < numMetrics; i++) {
      const angle = (i * 2 * Math.PI) / numMetrics - Math.PI / 2
      const x = centerX + radius * Math.cos(angle)
      const y = centerY + radius * Math.sin(angle)

      // Draw axis line
      ctx.beginPath()
      ctx.moveTo(centerX, centerY)
      ctx.lineTo(x, y)
      ctx.stroke()

      // Draw axis label
      const labelX = centerX + (radius + 20) * Math.cos(angle)
      const labelY = centerY + (radius + 20) * Math.sin(angle)
      ctx.fillText(metricLabels[i], labelX, labelY)
    }

    // Draw data for each model
    models.forEach((model, modelIndex) => {
      const color = colors[modelIndex % colors.length]

      // Draw model data
      ctx.beginPath()
      metrics.forEach((metric, i) => {
        const value = model.metrics[metric as keyof typeof model.metrics] as number
        const angle = (i * 2 * Math.PI) / numMetrics - Math.PI / 2
        const x = centerX + radius * value * Math.cos(angle)
        const y = centerY + radius * value * Math.sin(angle)

        if (i === 0) {
          ctx.moveTo(x, y)
        } else {
          ctx.lineTo(x, y)
        }
      })

      // Close the path
      const firstMetric = metrics[0]
      const firstValue = model.metrics[firstMetric as keyof typeof model.metrics] as number
      const firstAngle = -Math.PI / 2
      const firstX = centerX + radius * firstValue * Math.cos(firstAngle)
      const firstY = centerY + radius * firstValue * Math.sin(firstAngle)
      ctx.lineTo(firstX, firstY)

      // Fill and stroke
      ctx.fillStyle = color.fill
      ctx.fill()
      ctx.strokeStyle = color.stroke
      ctx.lineWidth = 2
      ctx.stroke()

      // Add dots at each metric point
      metrics.forEach((metric, i) => {
        const value = model.metrics[metric as keyof typeof model.metrics] as number
        const angle = (i * 2 * Math.PI) / numMetrics - Math.PI / 2
        const x = centerX + radius * value * Math.cos(angle)
        const y = centerY + radius * value * Math.sin(angle)

        ctx.beginPath()
        ctx.arc(x, y, 4, 0, 2 * Math.PI)
        ctx.fillStyle = color.stroke
        ctx.fill()
      })
    })

    // Draw legend
    const legendX = 20
    let legendY = 20

    models.forEach((model, modelIndex) => {
      const color = colors[modelIndex % colors.length]

      // Draw legend item
      ctx.fillStyle = color.stroke
      ctx.fillRect(legendX, legendY, 15, 15)

      // Draw model name
      ctx.fillStyle = "rgba(0, 0, 0, 0.8)"
      ctx.font = "14px sans-serif"
      ctx.textAlign = "left"
      ctx.textBaseline = "middle"
      ctx.fillText(model.name, legendX + 25, legendY + 7.5)

      // Move to next legend item
      legendY += 25
    })
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" asChild>
            <Link href="/models">
              <ArrowLeft className="h-4 w-4" />
              <span className="sr-only">Back</span>
            </Link>
          </Button>
          <h1 className="text-3xl font-bold tracking-tight">Model Comparison</h1>
        </div>

        {selectedModels.length < 2 ? (
          <Card>
            <CardHeader>
              <CardTitle>Not Enough Models Selected</CardTitle>
              <CardDescription>Please select at least two models to compare</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild>
                <Link href="/models">Select Models</Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics Comparison</CardTitle>
                <CardDescription>Compare key performance metrics across selected models</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Model</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Dataset</TableHead>
                        <TableHead>F1 Score</TableHead>
                        <TableHead>Accuracy</TableHead>
                        <TableHead>Precision</TableHead>
                        <TableHead>Recall</TableHead>
                        <TableHead>AUC</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedModels.map((model) => (
                        <TableRow key={model.id}>
                          <TableCell className="font-medium">{model.name}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{model.type}</Badge>
                          </TableCell>
                          <TableCell>
                            <Link href={`/datasets/${model.datasetId}`} className="hover:underline">
                              {model.dataset}
                            </Link>
                          </TableCell>
                          <TableCell className={isBestMetric(model, "f1") ? "font-bold text-primary" : ""}>
                            {model.metrics.f1.toFixed(2)}
                          </TableCell>
                          <TableCell className={isBestMetric(model, "accuracy") ? "font-bold text-primary" : ""}>
                            {model.metrics.accuracy.toFixed(2)}
                          </TableCell>
                          <TableCell className={isBestMetric(model, "precision") ? "font-bold text-primary" : ""}>
                            {model.metrics.precision.toFixed(2)}
                          </TableCell>
                          <TableCell className={isBestMetric(model, "recall") ? "font-bold text-primary" : ""}>
                            {model.metrics.recall.toFixed(2)}
                          </TableCell>
                          <TableCell className={isBestMetric(model, "auc") ? "font-bold text-primary" : ""}>
                            {model.metrics.auc.toFixed(2)}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex justify-end space-x-2">
                              <Button variant="outline" size="sm" asChild>
                                <Link href={`/models/${model.id}`}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  Details
                                </Link>
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => handleRemoveModel(model.id)}>
                                Remove
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Radar Chart Comparison</CardTitle>
                <CardDescription>Visual comparison of model performance across key metrics</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex justify-center">
                  <canvas ref={canvasRef} width={600} height={500} className="max-w-full"></canvas>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Hyperparameters Comparison</CardTitle>
                <CardDescription>Compare hyperparameters across selected models</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Model</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Hyperparameters</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedModels.map((model) => (
                        <TableRow key={model.id}>
                          <TableCell className="font-medium">{model.name}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{model.type}</Badge>
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(model.hyperparameters).map(([key, value]) => (
                                <Badge key={key} variant="secondary" className="whitespace-nowrap">
                                  {key}: {value.toString()}
                                </Badge>
                              ))}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end space-x-2">
              <Button variant="outline">
                <Download className="mr-2 h-4 w-4" />
                Export Comparison
              </Button>
              <Button asChild>
                <Link href="/models">
                  <BarChart3 className="mr-2 h-4 w-4" />
                  Select Different Models
                </Link>
              </Button>
            </div>
          </>
        )}
      </div>
    </MainLayout>
  )
}
