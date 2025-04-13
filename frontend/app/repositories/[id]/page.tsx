"use client"

import { useState } from "react"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ArrowLeft, GitBranch, RefreshCw, Database, BarChart3 } from "lucide-react"
import Link from "next/link"

// Mock data for repository details
const mockRepository = {
  id: "1",
  name: "frontend-app",
  gitUrl: "https://github.com/org/frontend-app.git",
  dateAdded: "2023-04-10T10:30:00Z",
  status: "Ingested",
  lastIngested: "2023-04-12T14:20:00Z",
  commits: 1245,
  branches: 8,
  contributors: 12,
}

const mockDatasets = [
  {
    id: "1",
    name: "frontend-app-dataset-1",
    status: "Ready",
    dateCreated: "2023-04-15T09:20:00Z",
    description: "Dataset with CK metrics and commit history",
  },
  {
    id: "2",
    name: "frontend-app-dataset-2",
    status: "Generating",
    dateCreated: "2023-04-18T11:30:00Z",
    description: "Dataset with extended features and bot filtering",
  },
  {
    id: "3",
    name: "frontend-app-dataset-3",
    status: "Failed",
    dateCreated: "2023-04-20T14:45:00Z",
    description: "Experimental dataset with custom cleaning rules",
  },
]

const mockModels = [
  {
    id: "1",
    name: "RandomForest-frontend-1",
    version: "1.0.0",
    type: "RandomForest",
    dataset: "frontend-app-dataset-1",
    dateCreated: "2023-04-16T10:20:00Z",
    metrics: {
      f1: 0.85,
      accuracy: 0.88,
    },
  },
  {
    id: "2",
    name: "XGBoost-frontend-1",
    version: "1.0.0",
    type: "XGBoost",
    dataset: "frontend-app-dataset-1",
    dateCreated: "2023-04-17T09:15:00Z",
    metrics: {
      f1: 0.82,
      accuracy: 0.86,
    },
  },
]

const mockJobs = [
  {
    id: "1",
    name: "Train RandomForest",
    type: "Training",
    status: "Completed",
    dateCreated: "2023-04-16T08:30:00Z",
    dateCompleted: "2023-04-16T10:20:00Z",
  },
  {
    id: "2",
    name: "Train XGBoost",
    type: "Training",
    status: "Completed",
    dateCreated: "2023-04-17T07:45:00Z",
    dateCompleted: "2023-04-17T09:15:00Z",
  },
  {
    id: "3",
    name: "HP Search for RandomForest",
    type: "HP Search",
    status: "Running",
    dateCreated: "2023-04-20T13:10:00Z",
    dateCompleted: null,
  },
  {
    id: "4",
    name: "Inference on PR #123",
    type: "Inference",
    status: "Failed",
    dateCreated: "2023-04-19T15:30:00Z",
    dateCompleted: "2023-04-19T15:45:00Z",
  },
]

export default function RepositoryDetailPage({ params }: { params: { id: string } }) {
  const [activeTab, setActiveTab] = useState("overview")

  // In a real app, we would fetch the repository data based on the ID
  const repository = mockRepository
  const datasets = mockDatasets
  const models = mockModels
  const jobs = mockJobs

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A"
    return new Date(dateString).toLocaleDateString()
  }

  // Update the getStatusBadge function to use our new custom badge styles
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "Ready":
      case "Completed":
        return <Badge className="status-badge-ready">Ready</Badge>
      case "Generating":
      case "Running":
        return (
          <Badge variant="outline" className="status-badge-running flex items-center gap-1">
            <RefreshCw className="h-3 w-3 animate-spin" />
            {status}
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

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" asChild>
            <Link href="/repositories">
              <ArrowLeft className="h-4 w-4" />
              <span className="sr-only">Back</span>
            </Link>
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{repository.name}</h1>
            <p className="text-muted-foreground">{repository.gitUrl}</p>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="datasets">Datasets</TabsTrigger>
            <TabsTrigger value="models">Models</TabsTrigger>
            <TabsTrigger value="jobs">Jobs</TabsTrigger>
            <TabsTrigger value="bot-patterns">Bot Patterns</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Repository Status</CardTitle>
                  <GitBranch className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="flex items-center space-x-2">
                    <Badge>Ingested</Badge>
                    <span className="text-sm text-muted-foreground">
                      Last ingested: {formatDate(repository.lastIngested)}
                    </span>
                  </div>
                  <div className="mt-2 text-2xl font-bold">{repository.commits} commits</div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {repository.branches} branches • {repository.contributors} contributors
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">Datasets</CardTitle>
                  <Database className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{datasets.length}</div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {datasets.filter((d) => d.status === "Ready").length} ready,
                    {datasets.filter((d) => d.status === "Generating").length} generating,
                    {datasets.filter((d) => d.status === "Failed").length} failed
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium">ML Models</CardTitle>
                  <BarChart3 className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{models.length}</div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Average F1 score:{" "}
                    {(models.reduce((acc, model) => acc + model.metrics.f1, 0) / models.length).toFixed(2)}
                  </p>
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Recent Datasets</CardTitle>
                  <CardDescription>Datasets created for this repository</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {datasets.slice(0, 3).map((dataset) => (
                      <div key={dataset.id} className="flex items-center justify-between">
                        <div className="space-y-1">
                          <p className="text-sm font-medium leading-none">{dataset.name}</p>
                          <p className="text-sm text-muted-foreground">{formatDate(dataset.dateCreated)}</p>
                        </div>
                        {getStatusBadge(dataset.status)}
                      </div>
                    ))}
                    {datasets.length > 3 && (
                      <Button variant="link" size="sm" className="px-0" onClick={() => setActiveTab("datasets")}>
                        View all datasets
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Recent Jobs</CardTitle>
                  <CardDescription>ML jobs for this repository</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {jobs.slice(0, 3).map((job) => (
                      <div key={job.id} className="flex items-center justify-between">
                        <div className="space-y-1">
                          <p className="text-sm font-medium leading-none">{job.name}</p>
                          <p className="text-sm text-muted-foreground">
                            {job.type} • {formatDate(job.dateCreated)}
                          </p>
                        </div>
                        {getStatusBadge(job.status)}
                      </div>
                    ))}
                    {jobs.length > 3 && (
                      <Button variant="link" size="sm" className="px-0" onClick={() => setActiveTab("jobs")}>
                        View all jobs
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="datasets" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Datasets</h2>
              <Button asChild>
                <Link href={`/datasets/create?repository=${params.id}`}>Create Dataset</Link>
              </Button>
            </div>

            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Dataset Name</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Date Created</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {datasets.map((dataset) => (
                    <TableRow key={dataset.id}>
                      <TableCell className="font-medium">{dataset.name}</TableCell>
                      <TableCell>{getStatusBadge(dataset.status)}</TableCell>
                      <TableCell>{formatDate(dataset.dateCreated)}</TableCell>
                      <TableCell>{dataset.description}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="outline" size="sm" asChild>
                          <Link href={`/datasets/${dataset.id}`}>View Details</Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </TabsContent>

          <TabsContent value="models" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">ML Models</h2>
              <Button asChild>
                <Link href={`/jobs/train?repository=${params.id}`}>Train New Model</Link>
              </Button>
            </div>

            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model Name</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Dataset</TableHead>
                    <TableHead>Date Created</TableHead>
                    <TableHead>Metrics</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((model) => (
                    <TableRow key={model.id}>
                      <TableCell className="font-medium">{model.name}</TableCell>
                      <TableCell>{model.version}</TableCell>
                      <TableCell>{model.type}</TableCell>
                      <TableCell>{model.dataset}</TableCell>
                      <TableCell>{formatDate(model.dateCreated)}</TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="text-sm">F1: {model.metrics.f1.toFixed(2)}</div>
                          <div className="text-sm">Accuracy: {model.metrics.accuracy.toFixed(2)}</div>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="outline" size="sm" asChild>
                          <Link href={`/models/${model.id}`}>View Details</Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </TabsContent>

          <TabsContent value="jobs" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">ML Jobs</h2>
              <div className="flex space-x-2">
                <Button variant="outline" asChild>
                  <Link href={`/jobs/train?repository=${params.id}`}>Train Model</Link>
                </Button>
                <Button variant="outline" asChild>
                  <Link href={`/jobs/hp-search?repository=${params.id}`}>HP Search</Link>
                </Button>
                <Button asChild>
                  <Link href={`/jobs/inference?repository=${params.id}`}>Run Inference</Link>
                </Button>
              </div>
            </div>

            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Completed</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell className="font-medium">{job.name}</TableCell>
                      <TableCell>{job.type}</TableCell>
                      <TableCell>{getStatusBadge(job.status)}</TableCell>
                      <TableCell>{formatDate(job.dateCreated)}</TableCell>
                      <TableCell>{formatDate(job.dateCompleted)}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="outline" size="sm" asChild>
                          <Link href={`/jobs/${job.id}`}>View Details</Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </TabsContent>

          <TabsContent value="bot-patterns" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold">Repository-Specific Bot Patterns</h2>
              <Button asChild>
                <Link href={`/bot-patterns?repository=${params.id}`}>Add Bot Pattern</Link>
              </Button>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Bot Patterns</CardTitle>
                <CardDescription>Patterns used to identify bot commits in this repository</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">
                  No repository-specific bot patterns defined yet. Repository will use global bot patterns.
                </p>
                <Button variant="outline" className="mt-4" asChild>
                  <Link href="/bot-patterns">View Global Bot Patterns</Link>
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </MainLayout>
  )
}
