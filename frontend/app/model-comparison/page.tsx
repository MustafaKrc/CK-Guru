"use client"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Download, Info, Search, X } from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Input } from "@/components/ui/input"
import { MainLayout } from "@/components/main-layout"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Checkbox } from "@/components/ui/checkbox"

interface ModelData {
  id: string
  name: string
  type: string
  accuracy: number
  precision: number
  recall: number
  f1Score: number
  auc: number
  trainingTime: number
  inferenceTime: number
  lastUpdated: string
  size: number
}

const models: ModelData[] = [
  {
    id: "model1",
    name: "CodeQuality-GPT",
    type: "Transformer",
    accuracy: 0.92,
    precision: 0.89,
    recall: 0.94,
    f1Score: 0.91,
    auc: 0.95,
    trainingTime: 4.5,
    inferenceTime: 0.12,
    lastUpdated: "2023-09-15",
    size: 1.2,
  },
  {
    id: "model2",
    name: "BugDetector-XGBoost",
    type: "Gradient Boosting",
    accuracy: 0.88,
    precision: 0.92,
    recall: 0.85,
    f1Score: 0.88,
    auc: 0.91,
    trainingTime: 2.1,
    inferenceTime: 0.05,
    lastUpdated: "2023-09-10",
    size: 0.4,
  },
  {
    id: "model3",
    name: "CodeReviewer-BERT",
    type: "Transformer",
    accuracy: 0.9,
    precision: 0.87,
    recall: 0.92,
    f1Score: 0.89,
    auc: 0.93,
    trainingTime: 5.2,
    inferenceTime: 0.15,
    lastUpdated: "2023-09-05",
    size: 1.5,
  },
  {
    id: "model4",
    name: "StyleChecker-RandomForest",
    type: "Ensemble",
    accuracy: 0.85,
    precision: 0.84,
    recall: 0.86,
    f1Score: 0.85,
    auc: 0.88,
    trainingTime: 1.8,
    inferenceTime: 0.04,
    lastUpdated: "2023-08-28",
    size: 0.3,
  },
  {
    id: "model5",
    name: "SecurityAnalyzer-CNN",
    type: "Neural Network",
    accuracy: 0.91,
    precision: 0.9,
    recall: 0.89,
    f1Score: 0.9,
    auc: 0.94,
    trainingTime: 6.2,
    inferenceTime: 0.18,
    lastUpdated: "2023-09-20",
    size: 2.1,
  },
  {
    id: "model6",
    name: "PerformancePredictor-LightGBM",
    type: "Gradient Boosting",
    accuracy: 0.87,
    precision: 0.86,
    recall: 0.88,
    f1Score: 0.87,
    auc: 0.9,
    trainingTime: 1.9,
    inferenceTime: 0.06,
    lastUpdated: "2023-09-12",
    size: 0.5,
  },
  {
    id: "model7",
    name: "DependencyAnalyzer-SVM",
    type: "SVM",
    accuracy: 0.83,
    precision: 0.82,
    recall: 0.84,
    f1Score: 0.83,
    auc: 0.86,
    trainingTime: 1.2,
    inferenceTime: 0.03,
    lastUpdated: "2023-08-25",
    size: 0.2,
  },
  {
    id: "model8",
    name: "CodeComplexity-RNN",
    type: "Neural Network",
    accuracy: 0.89,
    precision: 0.88,
    recall: 0.9,
    f1Score: 0.89,
    auc: 0.92,
    trainingTime: 5.8,
    inferenceTime: 0.14,
    lastUpdated: "2023-09-08",
    size: 1.8,
  },
]

// Model types for filtering
const modelTypes = ["Transformer", "Gradient Boosting", "Ensemble", "Neural Network", "SVM"]

export default function ModelComparisonPage() {
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const [comparisonMetric, setComparisonMetric] = useState<string>("accuracy")
  const [searchQuery, setSearchQuery] = useState("")
  const [typeFilter, setTypeFilter] = useState("all")
  const [activeTab, setActiveTab] = useState("comparison")
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const radarCanvasRef = useRef<HTMLCanvasElement>(null)

  // Effect to redraw charts when tab changes or models are selected
  useEffect(() => {
    if (selectedModels.length > 0) {
      if (activeTab === "comparison") {
        drawComparisonChart()
        drawRadarChart()
      }
    }
  }, [selectedModels, comparisonMetric, activeTab])

  const toggleModelSelection = (modelId: string) => {
    setSelectedModels((prev) => {
      if (prev.includes(modelId)) {
        return prev.filter((id) => id !== modelId)
      } else {
        // Limit to max 4 models for better visualization
        if (prev.length >= 4) {
          return [...prev.slice(1), modelId]
        }
        return [...prev, modelId]
      }
    })
  }

  const clearModelSelection = () => {
    setSelectedModels([])
  }

  const filteredModels = models.filter((model) => {
    const matchesSearch = searchQuery ? model.name.toLowerCase().includes(searchQuery.toLowerCase()) : true
    const matchesType = typeFilter === "all" ? true : model.type === typeFilter
    return matchesSearch && matchesType
  })

  const drawComparisonChart = () => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const filteredModels = models.filter((model) => selectedModels.includes(model.id))
    const metricValues = filteredModels.map((model) => model[comparisonMetric as keyof ModelData] as number)
    const maxValue = Math.max(...metricValues) * 1.2
    const barWidth = canvas.width / (filteredModels.length * 2)
    const colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"]

    // Draw bars
    filteredModels.forEach((model, index) => {
      const value = model[comparisonMetric as keyof ModelData] as number
      const barHeight = (value / maxValue) * (canvas.height - 60)
      const x = index * (barWidth * 2) + barWidth / 2
      const y = canvas.height - barHeight - 30

      // Draw bar
      ctx.fillStyle = colors[index % colors.length]
      ctx.fillRect(x, y, barWidth, barHeight)

      // Draw model name
      ctx.fillStyle = "#888888"
      ctx.font = "12px Arial"
      ctx.textAlign = "center"
      ctx.fillText(model.name.split("-")[0], x + barWidth / 2, canvas.height - 10)

      // Draw value
      ctx.fillStyle = "#000000"
      ctx.font = "14px Arial"
      ctx.textAlign = "center"
      ctx.fillText(value.toFixed(2), x + barWidth / 2, y - 5)
    })

    // Draw y-axis
    ctx.strokeStyle = "#cccccc"
    ctx.beginPath()
    ctx.moveTo(20, 20)
    ctx.lineTo(20, canvas.height - 30)
    ctx.stroke()

    // Draw x-axis
    ctx.beginPath()
    ctx.moveTo(20, canvas.height - 30)
    ctx.lineTo(canvas.width - 20, canvas.height - 30)
    ctx.stroke()
  }

  const drawRadarChart = () => {
    const canvas = radarCanvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const filteredModels = models.filter((model) => selectedModels.includes(model.id))
    if (filteredModels.length === 0) return

    const metrics = ["accuracy", "precision", "recall", "f1Score", "auc"]
    const centerX = canvas.width / 2
    const centerY = canvas.height / 2
    const radius = Math.min(centerX, centerY) - 50
    const angleStep = (Math.PI * 2) / metrics.length
    const colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"]

    // Draw radar background
    ctx.strokeStyle = "#cccccc"
    ctx.fillStyle = "rgba(240, 240, 240, 0.5)"

    // Draw radar rings with value indicators
    for (let r = 0.2; r <= 1; r += 0.2) {
      ctx.beginPath()
      for (let i = 0; i < metrics.length; i++) {
        const angle = i * angleStep - Math.PI / 2
        const x = centerX + radius * r * Math.cos(angle)
        const y = centerY + radius * r * Math.sin(angle)
        if (i === 0) {
          ctx.moveTo(x, y)
        } else {
          ctx.lineTo(x, y)
        }
      }
      ctx.closePath()
      ctx.stroke()

      // Add value indicators for each ring
      ctx.fillStyle = "#888888"
      ctx.font = "10px Arial"
      ctx.textAlign = "right"
      ctx.fillText(r.toFixed(1), centerX - 5, centerY - radius * r + 3)
    }

    // Draw radar axes
    for (let i = 0; i < metrics.length; i++) {
      const angle = i * angleStep - Math.PI / 2
      const x = centerX + radius * Math.cos(angle)
      const y = centerY + radius * Math.sin(angle)

      ctx.beginPath()
      ctx.moveTo(centerX, centerY)
      ctx.lineTo(x, y)
      ctx.stroke()

      // Draw metric labels
      const labelX = centerX + (radius + 20) * Math.cos(angle)
      const labelY = centerY + (radius + 20) * Math.sin(angle)

      ctx.fillStyle = "#000000"
      ctx.font = "14px Arial"
      ctx.textAlign = "center"
      ctx.textBaseline = "middle"
      ctx.fillText(metrics[i], labelX, labelY)

      // Add value indicators along each axis
      for (let r = 0.2; r <= 1; r += 0.2) {
        const indicatorX = centerX + radius * r * Math.cos(angle)
        const indicatorY = centerY + radius * r * Math.sin(angle)

        // Draw small tick marks
        ctx.beginPath()
        ctx.moveTo(indicatorX, indicatorY)
        const tickLength = 5
        const perpAngle = angle + Math.PI / 2
        ctx.lineTo(indicatorX + tickLength * Math.cos(perpAngle), indicatorY + tickLength * Math.sin(perpAngle))
        ctx.stroke()

        // Add value text for the first axis only to avoid clutter
        if (i === 0) {
          ctx.fillStyle = "#666666"
          ctx.font = "10px Arial"
          ctx.textAlign = "center"
          ctx.fillText(r.toFixed(1), indicatorX, indicatorY - 10)
        }
      }
    }

    // Draw model data
    filteredModels.forEach((model, modelIndex) => {
      ctx.strokeStyle = colors[modelIndex % colors.length]
      ctx.fillStyle = colors[modelIndex % colors.length] + "40" // Add transparency

      ctx.beginPath()
      for (let i = 0; i < metrics.length; i++) {
        const metric = metrics[i] as keyof ModelData
        const value = model[metric] as number
        const angle = i * angleStep - Math.PI / 2
        const x = centerX + radius * value * Math.cos(angle)
        const y = centerY + radius * value * Math.sin(angle)

        if (i === 0) {
          ctx.moveTo(x, y)
        } else {
          ctx.lineTo(x, y)
        }
      }
      ctx.closePath()
      ctx.stroke()
      ctx.fill()

      // Draw data points with values
      for (let i = 0; i < metrics.length; i++) {
        const metric = metrics[i] as keyof ModelData
        const value = model[metric] as number
        const angle = i * angleStep - Math.PI / 2
        const x = centerX + radius * value * Math.cos(angle)
        const y = centerY + radius * value * Math.sin(angle)

        // Draw point
        ctx.beginPath()
        ctx.arc(x, y, 4, 0, Math.PI * 2)
        ctx.fillStyle = colors[modelIndex % colors.length]
        ctx.fill()

        // Draw value text
        ctx.fillStyle = "#000000"
        ctx.font = "10px Arial"
        ctx.textAlign = "center"
        ctx.fillText(value.toFixed(2), x, y - 10)
      }
    })

    // Draw legend
    const legendY = canvas.height - 30
    filteredModels.forEach((model, index) => {
      const x = 50 + index * 150

      ctx.fillStyle = colors[index % colors.length]
      ctx.fillRect(x, legendY, 15, 15)

      ctx.fillStyle = "#000000"
      ctx.font = "14px Arial"
      ctx.textAlign = "left"
      ctx.fillText(model.name, x + 25, legendY + 12)
    })
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Model Comparison</h1>
            <p className="text-muted-foreground">Compare performance metrics across different ML models</p>
          </div>
          <Button variant="outline">
            <Download className="mr-2 h-4 w-4" />
            Export Report
          </Button>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="comparison">Comparison</TabsTrigger>
            <TabsTrigger value="models">Models</TabsTrigger>
          </TabsList>

          <TabsContent value="comparison" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Model Selection</CardTitle>
                <CardDescription>
                  Select up to 4 models to compare (currently selected: {selectedModels.length})
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col space-y-4">
                  <div className="flex flex-wrap gap-2 mb-2">
                    {selectedModels.length > 0 ? (
                      <>
                        {models
                          .filter((model) => selectedModels.includes(model.id))
                          .map((model) => (
                            <Badge key={model.id} variant="secondary" className="px-3 py-1 flex items-center gap-1">
                              {model.name}
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-4 w-4 ml-1 p-0"
                                onClick={() => toggleModelSelection(model.id)}
                              >
                                <X className="h-3 w-3" />
                              </Button>
                            </Badge>
                          ))}
                        <Button variant="outline" size="sm" className="h-7" onClick={clearModelSelection}>
                          Clear All
                        </Button>
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No models selected. Select models from the list below.
                      </p>
                    )}
                  </div>

                  <div className="flex flex-col md:flex-row gap-4">
                    <div className="w-full md:w-1/2">
                      <div className="relative">
                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                          placeholder="Search models..."
                          className="pl-8"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                      </div>
                    </div>
                    <div className="w-full md:w-1/2">
                      <Select value={typeFilter} onValueChange={setTypeFilter}>
                        <SelectTrigger>
                          <SelectValue placeholder="Filter by model type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Types</SelectItem>
                          {modelTypes.map((type) => (
                            <SelectItem key={type} value={type}>
                              {type}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="border rounded-md">
                    <ScrollArea className="h-[200px]">
                      <div className="p-4 space-y-2">
                        {filteredModels.length === 0 ? (
                          <p className="text-center py-4 text-muted-foreground">
                            No models found matching your criteria
                          </p>
                        ) : (
                          filteredModels.map((model) => (
                            <div
                              key={model.id}
                              className={`flex items-center justify-between p-2 rounded-md hover:bg-accent cursor-pointer ${
                                selectedModels.includes(model.id) ? "bg-accent/50" : ""
                              }`}
                              onClick={() => toggleModelSelection(model.id)}
                            >
                              <div className="flex items-center gap-3">
                                <Checkbox
                                  checked={selectedModels.includes(model.id)}
                                  onCheckedChange={() => toggleModelSelection(model.id)}
                                  id={`model-${model.id}`}
                                />
                                <div>
                                  <p className="font-medium">{model.name}</p>
                                  <p className="text-xs text-muted-foreground">
                                    Type: {model.type} | Accuracy: {model.accuracy.toFixed(2)}
                                  </p>
                                </div>
                              </div>
                              <Badge variant="outline">{model.lastUpdated}</Badge>
                            </div>
                          ))
                        )}
                      </div>
                    </ScrollArea>
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Card className="col-span-2">
                <CardHeader>
                  <CardTitle>Performance Comparison</CardTitle>
                  <CardDescription>Compare selected models by specific metrics</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-4 mb-6">
                    <span className="text-sm font-medium">Compare by:</span>
                    <Select value={comparisonMetric} onValueChange={setComparisonMetric}>
                      <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="Select metric" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="accuracy">Accuracy</SelectItem>
                        <SelectItem value="precision">Precision</SelectItem>
                        <SelectItem value="recall">Recall</SelectItem>
                        <SelectItem value="f1Score">F1 Score</SelectItem>
                        <SelectItem value="auc">AUC</SelectItem>
                        <SelectItem value="trainingTime">Training Time</SelectItem>
                        <SelectItem value="inferenceTime">Inference Time</SelectItem>
                        <SelectItem value="size">Model Size</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {selectedModels.length > 0 ? (
                    <div className="h-[300px] w-full">
                      <canvas ref={canvasRef} width={800} height={300} className="w-full h-full"></canvas>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-[300px] border rounded-md border-dashed">
                      <p className="text-muted-foreground">Select models above to compare</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Model Stats</CardTitle>
                  <CardDescription>Key statistics for selected models</CardDescription>
                </CardHeader>
                <CardContent>
                  {selectedModels.length > 0 ? (
                    <div className="space-y-4">
                      {models
                        .filter((model) => selectedModels.includes(model.id))
                        .map((model) => (
                          <div key={model.id} className="space-y-2">
                            <h3 className="font-medium">{model.name}</h3>
                            <div className="grid grid-cols-2 gap-2 text-sm">
                              <div>Type:</div>
                              <div className="font-medium">{model.type}</div>
                              <div>Size:</div>
                              <div className="font-medium">{model.size} GB</div>
                              <div>Training Time:</div>
                              <div className="font-medium">{model.trainingTime} hours</div>
                              <div>Inference Time:</div>
                              <div className="font-medium">{model.inferenceTime} ms</div>
                              <div>Last Updated:</div>
                              <div className="font-medium">{model.lastUpdated}</div>
                            </div>
                          </div>
                        ))}
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-[200px]">
                      <p className="text-muted-foreground">No models selected</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="col-span-3">
                <CardHeader>
                  <CardTitle>Radar Comparison</CardTitle>
                  <CardDescription>Compare multiple metrics across selected models</CardDescription>
                </CardHeader>
                <CardContent>
                  {selectedModels.length > 0 ? (
                    <div className="h-[500px] w-full">
                      <canvas ref={radarCanvasRef} width={1000} height={500} className="w-full h-full"></canvas>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-[500px] border rounded-md border-dashed">
                      <p className="text-muted-foreground">Select models above to compare</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="models">
            <Card>
              <CardHeader>
                <CardTitle>Available Models</CardTitle>
                <CardDescription>All machine learning models available for comparison</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col md:flex-row gap-4 mb-4">
                  <div className="w-full md:w-1/2">
                    <div className="relative">
                      <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Search models..."
                        className="pl-8"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="w-full md:w-1/2">
                    <Select value={typeFilter} onValueChange={setTypeFilter}>
                      <SelectTrigger>
                        <SelectValue placeholder="Filter by model type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Types</SelectItem>
                        {modelTypes.map((type) => (
                          <SelectItem key={type} value={type}>
                            {type}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">
                        <span className="sr-only">Select</span>
                      </TableHead>
                      <TableHead>Model Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Accuracy</TableHead>
                      <TableHead>F1 Score</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead>Last Updated</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredModels.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={8} className="text-center py-4 text-muted-foreground">
                          No models found matching your criteria
                        </TableCell>
                      </TableRow>
                    ) : (
                      filteredModels.map((model) => (
                        <TableRow key={model.id}>
                          <TableCell>
                            <Checkbox
                              checked={selectedModels.includes(model.id)}
                              onCheckedChange={() => toggleModelSelection(model.id)}
                              id={`table-model-${model.id}`}
                            />
                          </TableCell>
                          <TableCell className="font-medium">{model.name}</TableCell>
                          <TableCell>{model.type}</TableCell>
                          <TableCell>{model.accuracy.toFixed(2)}</TableCell>
                          <TableCell>{model.f1Score.toFixed(2)}</TableCell>
                          <TableCell>{model.size} GB</TableCell>
                          <TableCell>{model.lastUpdated}</TableCell>
                          <TableCell>
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Button variant="ghost" size="icon">
                                    <Info className="h-4 w-4" />
                                    <span className="sr-only">Model details</span>
                                  </Button>
                                </TooltipTrigger>
                                <TooltipContent>
                                  <p>View detailed model information</p>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>

                {selectedModels.length > 0 && (
                  <div className="mt-6 flex justify-between items-center">
                    <div className="text-sm text-muted-foreground">
                      {selectedModels.length} model{selectedModels.length !== 1 ? "s" : ""} selected
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={clearModelSelection}>
                        Clear Selection
                      </Button>
                      <Button size="sm" onClick={() => setActiveTab("comparison")}>
                        View Comparison
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </MainLayout>
  )
}
