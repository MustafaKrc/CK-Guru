"use client"

import { useState } from "react"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { MoreHorizontal, Eye, Play, BarChart3, Plus } from "lucide-react"
import Link from "next/link"
import { useToast } from "@/hooks/use-toast"

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
    metrics: {
      f1: 0.85,
      accuracy: 0.88,
      precision: 0.82,
      recall: 0.89,
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
    metrics: {
      f1: 0.82,
      accuracy: 0.86,
      precision: 0.8,
      recall: 0.84,
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
    metrics: {
      f1: 0.79,
      accuracy: 0.83,
      precision: 0.77,
      recall: 0.81,
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
    metrics: {
      f1: 0.76,
      accuracy: 0.8,
      precision: 0.75,
      recall: 0.78,
    },
  },
]

// Mock repositories for filtering
const mockRepositories = [
  { id: "1", name: "frontend-app" },
  { id: "2", name: "backend-api" },
  { id: "3", name: "mobile-client" },
  { id: "4", name: "shared-lib" },
]

// Mock model types for filtering
const modelTypes = ["RandomForest", "XGBoost", "LogisticRegression", "SVM", "NeuralNetwork"]

export default function ModelsPage() {
  const [models, setModels] = useState(mockModels)
  const [repositoryFilter, setRepositoryFilter] = useState("")
  const [typeFilter, setTypeFilter] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const { toast } = useToast()

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  const handleRunInference = (modelId: string) => {
    // In a real app, this would navigate to the inference page with the model pre-selected
    toast({
      title: "Navigating to inference",
      description: "Preparing to run inference with the selected model",
    })
  }

  const handleToggleModelSelection = (modelId: string) => {
    setSelectedModels((prev) => {
      if (prev.includes(modelId)) {
        return prev.filter((id) => id !== modelId)
      } else {
        return [...prev, modelId]
      }
    })
  }

  const handleCompareModels = () => {
    if (selectedModels.length < 2) {
      toast({
        title: "Selection required",
        description: "Please select at least two models to compare",
        variant: "destructive",
      })
      return
    }

    // In a real app, this would navigate to the comparison page with the selected models
    toast({
      title: "Navigating to comparison",
      description: `Comparing ${selectedModels.length} selected models`,
    })
  }

  const filteredModels = models.filter((model) => {
    const matchesRepository = repositoryFilter ? model.repositoryId === repositoryFilter : true
    const matchesType = typeFilter ? model.type === typeFilter : true
    const matchesSearch = searchQuery
      ? model.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        model.dataset.toLowerCase().includes(searchQuery.toLowerCase())
      : true

    return matchesRepository && matchesType && matchesSearch
  })

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">ML Models</h1>
          <div className="flex space-x-2">
            <Button variant="outline" onClick={handleCompareModels} disabled={selectedModels.length < 2}>
              <BarChart3 className="mr-2 h-4 w-4" />
              Compare Selected ({selectedModels.length})
            </Button>
            <Button asChild>
              <Link href="/jobs/train">
                <Plus className="mr-2 h-4 w-4" />
                Train New Model
              </Link>
            </Button>
          </div>
        </div>

        <div className="flex flex-col md:flex-row gap-4">
          <div className="w-full md:w-1/3">
            <Label htmlFor="search">Search</Label>
            <Input
              id="search"
              placeholder="Search models..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="w-full md:w-1/3">
            <Label htmlFor="repository">Repository</Label>
            <select
              id="repository"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              value={repositoryFilter}
              onChange={(e) => setRepositoryFilter(e.target.value)}
            >
              <option value="">All Repositories</option>
              {mockRepositories.map((repo) => (
                <option key={repo.id} value={repo.id}>
                  {repo.name}
                </option>
              ))}
            </select>
          </div>
          <div className="w-full md:w-1/3">
            <Label htmlFor="type">Model Type</Label>
            <select
              id="type"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            >
              <option value="">All Types</option>
              {modelTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">
                  <span className="sr-only">Select</span>
                </TableHead>
                <TableHead>Model Name</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Dataset</TableHead>
                <TableHead>Repository</TableHead>
                <TableHead>Date Created</TableHead>
                <TableHead>Metrics</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredModels.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center py-4 text-muted-foreground">
                    No models found matching the current filters
                  </TableCell>
                </TableRow>
              ) : (
                filteredModels.map((model) => (
                  <TableRow key={model.id}>
                    <TableCell>
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        checked={selectedModels.includes(model.id)}
                        onChange={() => handleToggleModelSelection(model.id)}
                      />
                    </TableCell>
                    <TableCell className="font-medium">{model.name}</TableCell>
                    <TableCell>{model.version}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{model.type}</Badge>
                    </TableCell>
                    <TableCell>
                      <Link href={`/datasets/${model.datasetId}`} className="hover:underline">
                        {model.dataset}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Link href={`/repositories/${model.repositoryId}`} className="hover:underline">
                        {model.repository}
                      </Link>
                    </TableCell>
                    <TableCell>{formatDate(model.dateCreated)}</TableCell>
                    <TableCell>
                      <div className="flex space-x-2">
                        <Badge variant="secondary" className="bg-primary/10 text-primary hover:bg-primary/20">
                          F1: {model.metrics.f1.toFixed(2)}
                        </Badge>
                        <Badge variant="secondary" className="bg-accent/10 text-accent hover:bg-accent/20">
                          Acc: {model.metrics.accuracy.toFixed(2)}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Open menu</span>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuLabel>Actions</DropdownMenuLabel>
                          <DropdownMenuItem asChild>
                            <Link href={`/models/${model.id}`}>
                              <Eye className="mr-2 h-4 w-4" />
                              View Details
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleRunInference(model.id)}>
                            <Play className="mr-2 h-4 w-4" />
                            Run Inference
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => handleToggleModelSelection(model.id)}>
                            <BarChart3 className="mr-2 h-4 w-4" />
                            {selectedModels.includes(model.id) ? "Remove from Comparison" : "Add to Comparison"}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </MainLayout>
  )
}
