"use client"

import { useState } from "react"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { MoreHorizontal, RefreshCw, Eye, StopCircle, Play } from "lucide-react"
import Link from "next/link"
import { useToast } from "@/hooks/use-toast"

// Mock data for jobs
const mockJobs = {
  training: [
    {
      id: "train-1",
      name: "Train RandomForest on frontend-app",
      type: "Training",
      status: "Completed",
      repository: "frontend-app",
      repositoryId: "1",
      dataset: "frontend-app-dataset-1",
      datasetId: "1",
      modelType: "RandomForest",
      dateCreated: "2023-04-16T08:30:00Z",
      dateCompleted: "2023-04-16T10:20:00Z",
      resultModelId: "1",
    },
    {
      id: "train-2",
      name: "Train XGBoost on frontend-app",
      type: "Training",
      status: "Completed",
      repository: "frontend-app",
      repositoryId: "1",
      dataset: "frontend-app-dataset-1",
      datasetId: "1",
      modelType: "XGBoost",
      dateCreated: "2023-04-17T07:45:00Z",
      dateCompleted: "2023-04-17T09:15:00Z",
      resultModelId: "2",
    },
    {
      id: "train-3",
      name: "Train LogisticRegression on frontend-app",
      type: "Training",
      status: "Running",
      repository: "frontend-app",
      repositoryId: "1",
      dataset: "frontend-app-dataset-2",
      datasetId: "2",
      modelType: "LogisticRegression",
      dateCreated: "2023-04-20T13:10:00Z",
      dateCompleted: null,
      resultModelId: null,
    },
    {
      id: "train-4",
      name: "Train SVM on backend-api",
      type: "Training",
      status: "Failed",
      repository: "backend-api",
      repositoryId: "2",
      dataset: "backend-api-dataset-1",
      datasetId: "3",
      modelType: "SVM",
      dateCreated: "2023-04-18T09:30:00Z",
      dateCompleted: "2023-04-18T09:45:00Z",
      resultModelId: null,
      error: "Out of memory error during training",
    },
  ],
  hpSearch: [
    {
      id: "hp-1",
      name: "HP Search for RandomForest on frontend-app",
      type: "HP Search",
      status: "Completed",
      repository: "frontend-app",
      repositoryId: "1",
      dataset: "frontend-app-dataset-1",
      datasetId: "1",
      modelType: "RandomForest",
      dateCreated: "2023-04-15T10:30:00Z",
      dateCompleted: "2023-04-15T14:20:00Z",
      resultModelId: null,
      trials: 20,
      bestParams: {
        n_estimators: 100,
        max_depth: 10,
        min_samples_split: 2,
        min_samples_leaf: 1,
        bootstrap: true,
      },
    },
    {
      id: "hp-2",
      name: "HP Search for XGBoost on frontend-app",
      type: "HP Search",
      status: "Running",
      repository: "frontend-app",
      repositoryId: "1",
      dataset: "frontend-app-dataset-1",
      datasetId: "1",
      modelType: "XGBoost",
      dateCreated: "2023-04-19T11:45:00Z",
      dateCompleted: null,
      resultModelId: null,
      trials: 15,
      completedTrials: 8,
    },
  ],
  inference: [
    {
      id: "infer-1",
      name: "Inference on PR #123",
      type: "Inference",
      status: "Completed",
      repository: "frontend-app",
      repositoryId: "1",
      model: "RandomForest-frontend-1",
      modelId: "1",
      commitHash: "abc123def456",
      dateCreated: "2023-04-18T14:30:00Z",
      dateCompleted: "2023-04-18T14:35:00Z",
      result: {
        prediction: "buggy",
        probability: 0.87,
        features_importance: {
          CBO: 0.32,
          RFC: 0.28,
          lines_added: 0.25,
        },
      },
    },
    {
      id: "infer-2",
      name: "Inference on PR #145",
      type: "Inference",
      status: "Failed",
      repository: "frontend-app",
      repositoryId: "1",
      model: "XGBoost-frontend-1",
      modelId: "2",
      commitHash: "def789ghi012",
      dateCreated: "2023-04-19T15:30:00Z",
      dateCompleted: "2023-04-19T15:45:00Z",
      error: "Could not extract features from commit",
    },
    {
      id: "infer-3",
      name: "Inference on PR #156",
      type: "Inference",
      status: "Running",
      repository: "backend-api",
      repositoryId: "2",
      model: "RandomForest-backend-1",
      modelId: "3",
      commitHash: "jkl345mno678",
      dateCreated: "2023-04-20T09:15:00Z",
      dateCompleted: null,
    },
  ],
}

// Mock repositories for filtering
const mockRepositories = [
  { id: "1", name: "frontend-app" },
  { id: "2", name: "backend-api" },
  { id: "3", name: "mobile-client" },
  { id: "4", name: "shared-lib" },
]

export default function JobsPage() {
  const [activeTab, setActiveTab] = useState("training")
  const [repositoryFilter, setRepositoryFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const { toast } = useToast()

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A"
    return new Date(dateString).toLocaleDateString()
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "Completed":
        return <Badge className="status-badge-ready">Completed</Badge>
      case "Running":
        return (
          <Badge variant="outline" className="status-badge-running flex items-center gap-1">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Running
          </Badge>
        )
      case "Failed":
        return (
          <Badge variant="destructive" className="status-badge-failed">
            Failed
          </Badge>
        )
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const handleCancelJob = (jobId: string) => {
    // In a real app, this would be an API call to cancel the job
    toast({
      title: "Job cancellation requested",
      description: "The job cancellation request has been sent",
    })
  }

  const getFilteredJobs = () => {
    const jobs = mockJobs[activeTab as keyof typeof mockJobs]

    return jobs.filter((job: any) => {
      const matchesRepository = repositoryFilter ? job.repositoryId === repositoryFilter : true
      const matchesStatus = statusFilter ? job.status === statusFilter : true
      const matchesSearch = searchQuery ? job.name.toLowerCase().includes(searchQuery.toLowerCase()) : true

      return matchesRepository && matchesStatus && matchesSearch
    })
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">ML Jobs</h1>
          <div className="flex space-x-2">
            <Button variant="outline" asChild>
              <Link href="/jobs/train">Train Model</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/jobs/hp-search">HP Search</Link>
            </Button>
            <Button asChild>
              <Link href="/jobs/inference">
                <Play className="mr-2 h-4 w-4" />
                Run Inference
              </Link>
            </Button>
          </div>
        </div>

        <div className="flex flex-col md:flex-row gap-4">
          <div className="w-full md:w-1/3">
            <Label htmlFor="search">Search</Label>
            <Input
              id="search"
              placeholder="Search jobs..."
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
            <Label htmlFor="status">Status</Label>
            <select
              id="status"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="Completed">Completed</option>
              <option value="Running">Running</option>
              <option value="Failed">Failed</option>
            </select>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="training">Training Jobs</TabsTrigger>
            <TabsTrigger value="hpSearch">HP Search Jobs</TabsTrigger>
            <TabsTrigger value="inference">Inference Jobs</TabsTrigger>
          </TabsList>

          <TabsContent value="training" className="space-y-4">
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job Name</TableHead>
                    <TableHead>Repository</TableHead>
                    <TableHead>Dataset</TableHead>
                    <TableHead>Model Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Completed</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {getFilteredJobs().length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-4 text-muted-foreground">
                        No training jobs found matching the current filters
                      </TableCell>
                    </TableRow>
                  ) : (
                    getFilteredJobs().map((job: any) => (
                      <TableRow key={job.id}>
                        <TableCell className="font-medium">{job.name}</TableCell>
                        <TableCell>
                          <Link href={`/repositories/${job.repositoryId}`} className="hover:underline">
                            {job.repository}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Link href={`/datasets/${job.datasetId}`} className="hover:underline">
                            {job.dataset}
                          </Link>
                        </TableCell>
                        <TableCell>{job.modelType}</TableCell>
                        <TableCell>{getStatusBadge(job.status)}</TableCell>
                        <TableCell>{formatDate(job.dateCreated)}</TableCell>
                        <TableCell>{formatDate(job.dateCompleted)}</TableCell>
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
                                <Link href={`/jobs/${job.id}`}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Details
                                </Link>
                              </DropdownMenuItem>
                              {job.status === "Running" && (
                                <DropdownMenuItem onClick={() => handleCancelJob(job.id)}>
                                  <StopCircle className="mr-2 h-4 w-4" />
                                  Cancel Job
                                </DropdownMenuItem>
                              )}
                              {job.resultModelId && (
                                <DropdownMenuItem asChild>
                                  <Link href={`/models/${job.resultModelId}`}>
                                    <Play className="mr-2 h-4 w-4" />
                                    View Model
                                  </Link>
                                </DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </TabsContent>

          <TabsContent value="hpSearch" className="space-y-4">
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job Name</TableHead>
                    <TableHead>Repository</TableHead>
                    <TableHead>Dataset</TableHead>
                    <TableHead>Model Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Trials</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {getFilteredJobs().length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-4 text-muted-foreground">
                        No HP search jobs found matching the current filters
                      </TableCell>
                    </TableRow>
                  ) : (
                    getFilteredJobs().map((job: any) => (
                      <TableRow key={job.id}>
                        <TableCell className="font-medium">{job.name}</TableCell>
                        <TableCell>
                          <Link href={`/repositories/${job.repositoryId}`} className="hover:underline">
                            {job.repository}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Link href={`/datasets/${job.datasetId}`} className="hover:underline">
                            {job.dataset}
                          </Link>
                        </TableCell>
                        <TableCell>{job.modelType}</TableCell>
                        <TableCell>{getStatusBadge(job.status)}</TableCell>
                        <TableCell>{formatDate(job.dateCreated)}</TableCell>
                        <TableCell>
                          {job.status === "Running" ? `${job.completedTrials} / ${job.trials}` : job.trials}
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
                                <Link href={`/jobs/${job.id}`}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Details
                                </Link>
                              </DropdownMenuItem>
                              {job.status === "Running" && (
                                <DropdownMenuItem onClick={() => handleCancelJob(job.id)}>
                                  <StopCircle className="mr-2 h-4 w-4" />
                                  Cancel Job
                                </DropdownMenuItem>
                              )}
                              {job.status === "Completed" && (
                                <DropdownMenuItem asChild>
                                  <Link href={`/jobs/train?hpSearchId=${job.id}`}>
                                    <Play className="mr-2 h-4 w-4" />
                                    Train with Best Params
                                  </Link>
                                </DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </TabsContent>

          <TabsContent value="inference" className="space-y-4">
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job Name</TableHead>
                    <TableHead>Repository</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Commit Hash</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Completed</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {getFilteredJobs().length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-4 text-muted-foreground">
                        No inference jobs found matching the current filters
                      </TableCell>
                    </TableRow>
                  ) : (
                    getFilteredJobs().map((job: any) => (
                      <TableRow key={job.id}>
                        <TableCell className="font-medium">{job.name}</TableCell>
                        <TableCell>
                          <Link href={`/repositories/${job.repositoryId}`} className="hover:underline">
                            {job.repository}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Link href={`/models/${job.modelId}`} className="hover:underline">
                            {job.model}
                          </Link>
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {job.commitHash ? job.commitHash.substring(0, 8) : "N/A"}
                        </TableCell>
                        <TableCell>{getStatusBadge(job.status)}</TableCell>
                        <TableCell>{formatDate(job.dateCreated)}</TableCell>
                        <TableCell>{formatDate(job.dateCompleted)}</TableCell>
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
                                <Link href={`/jobs/${job.id}`}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Details
                                </Link>
                              </DropdownMenuItem>
                              {job.status === "Running" && (
                                <DropdownMenuItem onClick={() => handleCancelJob(job.id)}>
                                  <StopCircle className="mr-2 h-4 w-4" />
                                  Cancel Job
                                </DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </MainLayout>
  )
}
