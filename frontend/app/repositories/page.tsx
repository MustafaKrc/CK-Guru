"use client"

import { useState } from "react"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Label } from "@/components/ui/label"
import { Plus, MoreHorizontal, RefreshCw, Eye, Edit, Trash2 } from "lucide-react"
import Link from "next/link"
import { useToast } from "@/hooks/use-toast"

// Mock data for repositories
const mockRepositories = [
  {
    id: "1",
    name: "frontend-app",
    gitUrl: "https://github.com/org/frontend-app.git",
    dateAdded: "2023-04-10T10:30:00Z",
    status: "Ingested",
    lastIngested: "2023-04-12T14:20:00Z",
    commits: 1245,
    datasets: 3,
    models: 2,
  },
  {
    id: "2",
    name: "backend-api",
    gitUrl: "https://github.com/org/backend-api.git",
    dateAdded: "2023-04-08T09:15:00Z",
    status: "Ingesting",
    lastIngested: null,
    commits: 892,
    datasets: 2,
    models: 1,
  },
  {
    id: "3",
    name: "mobile-client",
    gitUrl: "https://github.com/org/mobile-client.git",
    dateAdded: "2023-04-05T16:45:00Z",
    status: "Not Ingested",
    lastIngested: null,
    commits: 0,
    datasets: 0,
    models: 0,
  },
  {
    id: "4",
    name: "shared-lib",
    gitUrl: "https://github.com/org/shared-lib.git",
    dateAdded: "2023-04-01T11:20:00Z",
    status: "Failed",
    lastIngested: "2023-04-02T08:30:00Z",
    commits: 0,
    datasets: 0,
    models: 0,
  },
]

export default function RepositoriesPage() {
  const [repositories, setRepositories] = useState(mockRepositories)
  const [newRepoUrl, setNewRepoUrl] = useState("")
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null)
  const { toast } = useToast()

  const handleAddRepository = () => {
    // Validate URL
    if (!newRepoUrl || !newRepoUrl.trim()) {
      toast({
        title: "Error",
        description: "Please enter a valid Git URL",
        variant: "destructive",
      })
      return
    }

    // In a real app, this would be an API call
    const newRepo = {
      id: `${repositories.length + 1}`,
      name: newRepoUrl.split("/").pop()?.replace(".git", "") || "new-repo",
      gitUrl: newRepoUrl,
      dateAdded: new Date().toISOString(),
      status: "Not Ingested",
      lastIngested: null,
      commits: 0,
      datasets: 0,
      models: 0,
    }

    setRepositories([...repositories, newRepo])
    setNewRepoUrl("")
    setAddDialogOpen(false)

    toast({
      title: "Repository added",
      description: "The repository has been added successfully",
    })
  }

  const handleDeleteRepository = () => {
    if (!selectedRepo) return

    // In a real app, this would be an API call
    setRepositories(repositories.filter((repo) => repo.id !== selectedRepo))
    setDeleteDialogOpen(false)

    toast({
      title: "Repository deleted",
      description: "The repository has been deleted successfully",
    })
  }

  const handleIngestRepository = (repoId: string) => {
    // In a real app, this would be an API call
    setRepositories(repositories.map((repo) => (repo.id === repoId ? { ...repo, status: "Ingesting" } : repo)))

    toast({
      title: "Ingestion started",
      description: "Repository ingestion has been initiated",
    })
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "Ingested":
        return <Badge className="status-badge-ready">Ingested</Badge>
      case "Ingesting":
        return (
          <Badge variant="outline" className="status-badge-running flex items-center gap-1">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Ingesting
          </Badge>
        )
      case "Failed":
        return (
          <Badge variant="destructive" className="status-badge-failed">
            Failed
          </Badge>
        )
      default:
        return <Badge variant="secondary">Not Ingested</Badge>
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A"
    return new Date(dateString).toLocaleDateString()
  }

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">Repositories</h1>
          <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Add Repository
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Repository</DialogTitle>
                <DialogDescription>Enter the Git URL of the repository you want to add.</DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="git-url">Git URL</Label>
                  <Input
                    id="git-url"
                    placeholder="https://github.com/org/repo.git"
                    value={newRepoUrl}
                    onChange={(e) => setNewRepoUrl(e.target.value)}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddRepository}>Add Repository</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Repository Name</TableHead>
                <TableHead>Git URL</TableHead>
                <TableHead>Date Added</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Summary</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {repositories.map((repo) => (
                <TableRow key={repo.id}>
                  <TableCell className="font-medium">{repo.name}</TableCell>
                  <TableCell className="font-mono text-sm">{repo.gitUrl}</TableCell>
                  <TableCell>{formatDate(repo.dateAdded)}</TableCell>
                  <TableCell>
                    {getStatusBadge(repo.status)}
                    {repo.lastIngested && (
                      <div className="text-xs text-muted-foreground mt-1">Last: {formatDate(repo.lastIngested)}</div>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex space-x-4 text-sm">
                      <span>{repo.commits} commits</span>
                      <span>{repo.datasets} datasets</span>
                      <span>{repo.models} models</span>
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
                          <Link href={`/repositories/${repo.id}`}>
                            <Eye className="mr-2 h-4 w-4" />
                            View Details
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => handleIngestRepository(repo.id)}
                          disabled={repo.status === "Ingesting"}
                        >
                          <RefreshCw className="mr-2 h-4 w-4" />
                          {repo.status === "Not Ingested" ? "Ingest" : "Re-Ingest"}
                        </DropdownMenuItem>
                        <DropdownMenuItem>
                          <Edit className="mr-2 h-4 w-4" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive"
                          onClick={() => {
                            setSelectedRepo(repo.id)
                            setDeleteDialogOpen(true)
                          }}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete Repository</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this repository? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={handleDeleteRepository}>
                Delete
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </MainLayout>
  )
}
