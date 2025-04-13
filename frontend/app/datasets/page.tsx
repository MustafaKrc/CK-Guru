"use client"

import { useState } from "react"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Plus, MoreHorizontal, RefreshCw, Download, Eye, FileJson, Trash2 } from "lucide-react"
import Link from "next/link"
import { useToast } from "@/hooks/use-toast"

// Mock data for datasets
const mockDatasets = [
  {
    id: "1",
    name: "frontend-app-dataset-1",
    repository: "frontend-app",
    repositoryId: "1",
    status: "Ready",
    dateCreated: "2023-04-15T09:20:00Z",
    description: "Dataset with CK metrics and commit history",
  },
  {
    id: "2",
    name: "frontend-app-dataset-2",
    repository: "frontend-app",
    repositoryId: "1",
    status: "Generating",
    dateCreated: "2023-04-18T11:30:00Z",
    description: "Dataset with extended features and bot filtering",
  },
  {
    id: "3",
    name: "backend-api-dataset-1",
    repository: "backend-api",
    repositoryId: "2",
    status: "Ready",
    dateCreated: "2023-04-12T14:45:00Z",
    description: "Standard dataset with default cleaning rules",
  },
  {
    id: "4",
    name: "mobile-client-dataset-1",
    repository: "mobile-client",
    repositoryId: "3",
    status: "Failed",
    dateCreated: "2023-04-20T10:15:00Z",
    description: "Experimental dataset with custom cleaning rules",
  },
]

// Mock repositories for filtering
const mockRepositories = [
  { id: "1", name: "frontend-app" },
  { id: "2", name: "backend-api" },
  { id: "3", name: "mobile-client" },
  { id: "4", name: "shared-lib" },
]

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState(mockDatasets)
  const [repositoryFilter, setRepositoryFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [viewConfigDialogOpen, setViewConfigDialogOpen] = useState(false)
  const [selectedDataset, setSelectedDataset] = useState<any>(null)
  const { toast } = useToast()

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  // Update the getStatusBadge function to use our new custom badge styles
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "Ready":
        return <Badge className="status-badge-ready">Ready</Badge>
      case "Generating":
        return (
          <Badge variant="outline" className="status-badge-running flex items-center gap-1">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Generating
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

  const handleDownload = (datasetId: string) => {
    // In a real app, this would trigger an API call to download the dataset
    toast({
      title: "Download started",
      description: "Your dataset download has started",
    })
  }

  const handleViewConfig = (dataset: any) => {
    setSelectedDataset(dataset)
    setViewConfigDialogOpen(true)
  }

  const filteredDatasets = datasets.filter((dataset) => {
    const matchesRepository = repositoryFilter ? dataset.repositoryId === repositoryFilter : true
    const matchesStatus = statusFilter ? dataset.status === statusFilter : true
    const matchesSearch = searchQuery
      ? dataset.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        dataset.description.toLowerCase().includes(searchQuery.toLowerCase())
      : true

    return matchesRepository && matchesStatus && matchesSearch
  })

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">Datasets</h1>
          <Button asChild>
            <Link href="/datasets/create">
              <Plus className="mr-2 h-4 w-4" />
              Create Dataset
            </Link>
          </Button>
        </div>

        <div className="flex flex-col md:flex-row gap-4">
          <div className="w-full md:w-1/3">
            <Label htmlFor="search">Search</Label>
            <Input
              id="search"
              placeholder="Search datasets..."
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
              <option value="Ready">Ready</option>
              <option value="Generating">Generating</option>
              <option value="Failed">Failed</option>
            </select>
          </div>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Dataset Name</TableHead>
                <TableHead>Repository</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Date Created</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredDatasets.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-4 text-muted-foreground">
                    No datasets found matching the current filters
                  </TableCell>
                </TableRow>
              ) : (
                filteredDatasets.map((dataset) => (
                  <TableRow key={dataset.id}>
                    <TableCell className="font-medium">{dataset.name}</TableCell>
                    <TableCell>
                      <Link href={`/repositories/${dataset.repositoryId}`} className="hover:underline">
                        {dataset.repository}
                      </Link>
                    </TableCell>
                    <TableCell>{getStatusBadge(dataset.status)}</TableCell>
                    <TableCell>{formatDate(dataset.dateCreated)}</TableCell>
                    <TableCell className="max-w-xs truncate">{dataset.description}</TableCell>
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
                          <DropdownMenuItem onClick={() => handleViewConfig(dataset)}>
                            <FileJson className="mr-2 h-4 w-4" />
                            View Config
                          </DropdownMenuItem>
                          <DropdownMenuItem asChild>
                            <Link href={`/datasets/${dataset.id}`}>
                              <Eye className="mr-2 h-4 w-4" />
                              View Data
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => handleDownload(dataset.id)}
                            disabled={dataset.status !== "Ready"}
                          >
                            <Download className="mr-2 h-4 w-4" />
                            Download
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem className="text-destructive focus:text-destructive">
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
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

        <Dialog open={viewConfigDialogOpen} onOpenChange={setViewConfigDialogOpen}>
          <DialogContent className="max-w-3xl">
            <DialogHeader>
              <DialogTitle>Dataset Configuration</DialogTitle>
              <DialogDescription>Configuration details for {selectedDataset?.name}</DialogDescription>
            </DialogHeader>
            {selectedDataset && (
              <div className="grid gap-4 py-4">
                <div className="rounded-md bg-muted p-4">
                  <pre className="text-sm overflow-auto">
                    {JSON.stringify(
                      {
                        name: selectedDataset.name,
                        repository: selectedDataset.repository,
                        features: [
                          "CBO",
                          "RFC",
                          "WMC",
                          "LCOM",
                          "DIT",
                          "NOC",
                          "lines_added",
                          "lines_deleted",
                          "files_changed",
                          "commit_message_length",
                          "commit_hour",
                          "commit_day",
                        ],
                        target: "is_buggy",
                        cleaning_rules: [
                          {
                            name: "remove_outliers",
                            enabled: true,
                            parameters: {
                              method: "iqr",
                              threshold: 1.5,
                            },
                          },
                          {
                            name: "handle_missing_values",
                            enabled: true,
                            parameters: {
                              method: "mean",
                            },
                          },
                          {
                            name: "filter_bot_commits",
                            enabled: true,
                            parameters: {
                              use_global_patterns: true,
                              use_repo_patterns: true,
                            },
                          },
                        ],
                        created_at: selectedDataset.dateCreated,
                        status: selectedDataset.status,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </MainLayout>
  )
}
