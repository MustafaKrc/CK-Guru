"use client"

import { useState, useEffect } from "react"
import { MainLayout } from "@/components/main-layout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
import { Plus, MoreHorizontal, RefreshCw, Eye, Edit, Trash2, AlertCircle, Loader2 } from "lucide-react"
import Link from "next/link"
import { useToast } from "@/hooks/use-toast"
import { Skeleton } from "@/components/ui/skeleton"

import { apiService, handleApiError, ApiError } from "@/lib/apiService"
import { Repository, RepositoryCreatePayload, TaskResponse } from "@/types/api/repository"

import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";

export default function RepositoriesPage() {
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const [newRepoUrl, setNewRepoUrl] = useState("")
  const [isAddingRepository, setIsAddingRepository] = useState(false)
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [addRepoError, setAddRepoError] = useState<string | null>(null)

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedRepoForDelete, setSelectedRepoForDelete] = useState<Repository | null>(null)
  const [isDeletingRepository, setIsDeletingRepository] = useState(false)

  const [isIngesting, setIsIngesting] = useState<Record<number, boolean>>({}); // Track ingestion status per repo

  // Zustand store integration
  const taskStatuses = useTaskStore((state) => state.taskStatuses);
  // No need to call connectSSE here if GlobalAppEffects is handling it.

  // Local state for immediate button click feedback for ingest
  const [localIngestButtonLoading, setLocalIngestButtonLoading] = useState<Record<number, boolean>>({});

  const { toast } = useToast()

  const fetchRepositories = async (showLoading: boolean = true) => {
    if (showLoading) setIsLoading(true);
    setFetchError(null)
    try {
      const data = await apiService.get<Repository[]>('/repositories')
      setRepositories(data)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch repositories."
      setFetchError(errorMessage)
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }

  useEffect(() => {
    fetchRepositories()
  }, [])

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A"
    try {
      return new Date(dateString).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
    } catch (e) {
      return "Invalid Date"
    }
  }

  const handleAddRepository = async () => {
    if (!newRepoUrl.trim()) {
      setAddRepoError("Git URL cannot be empty.");
      return;
    }
    try {
      new URL(newRepoUrl);
      // No need to check for .git specifically, backend will handle actual git clone errors.
    } catch (_) {
      setAddRepoError("Please enter a valid Git URL (e.g., https://github.com/user/repo.git).");
      return;
    }

    setIsAddingRepository(true);
    setAddRepoError(null);

    try {
      const payload: RepositoryCreatePayload = { git_url: newRepoUrl };
      const newRepository = await apiService.post<Repository, RepositoryCreatePayload>('/repositories', payload);
      
      // Prepend to list for immediate UI update
      setRepositories(prevRepos => [newRepository, ...prevRepos]); 
      
      toast({
        title: "Repository Added",
        description: `Successfully added ${newRepository.name}. You can now ingest it.`,
      });
      setNewRepoUrl("");
      setAddDialogOpen(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setAddRepoError(err.message);
      } else {
        setAddRepoError("An unexpected error occurred while adding the repository.");
        handleApiError(err, "Add Repository Failed"); // Show toast for non-ApiError
      }
    } finally {
      setIsAddingRepository(false);
    }
  };

  const handleDeleteConfirmation = (repo: Repository) => {
    setSelectedRepoForDelete(repo);
    setDeleteDialogOpen(true);
  };

  const handleDeleteRepository = async () => {
    if (!selectedRepoForDelete) return;

    setIsDeletingRepository(true);
    try {
      await apiService.delete<Repository>(`/repositories/${selectedRepoForDelete.id}`);
      setRepositories(prevRepos => prevRepos.filter(repo => repo.id !== selectedRepoForDelete.id));
      toast({
        title: "Repository Deleted",
        description: `Repository "${selectedRepoForDelete.name}" has been successfully deleted.`,
      });
      setDeleteDialogOpen(false);
      setSelectedRepoForDelete(null);
    } catch (err) {
      handleApiError(err, "Delete Repository Failed");
    } finally {
      setIsDeletingRepository(false);
    }
  };

  const handleIngestRepository = async (repoId: number, repoName: string) => {
    setLocalIngestButtonLoading(prev => ({ ...prev, [repoId]: true }));
    try {
      const response = await apiService.post<TaskResponse>(`/repositories/${repoId}/ingest`);
      toast({
        title: "Ingestion Initiated",
        description: `${repoName}: Task ${response.task_id} submitted. Status will update via SSE.`,
        action: (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/tasks?taskId=${response.task_id}`}>View Task</Link>
          </Button>
        ),
      });
      // SSE will handle further status updates reflected through useTaskStore
    } catch (err) {
      handleApiError(err, `Ingest Repository ${repoName} Failed`);
    } finally {
      // Keep local loading true for a short moment to allow SSE to potentially catch up,
      // or remove if SSE is fast enough. For now, let's clear it.
      // A better approach: button shows API call loading, then switches to "Processing (SSE)"
      setLocalIngestButtonLoading(prev => ({ ...prev, [repoId]: false }));
    }
  };


  const renderContent = () => {
    if (isLoading && repositories.length === 0) { // Show skeletons only on initial load or if explicitly fetching
      return (
        Array.from({ length: 3 }).map((_, index) => (
          <TableRow key={`skeleton-${index}`}>
            <TableCell><Skeleton className="h-5 w-32" /></TableCell>
            <TableCell><Skeleton className="h-5 w-48" /></TableCell>
            <TableCell><Skeleton className="h-5 w-24" /></TableCell>
            <TableCell><Skeleton className="h-5 w-40" /></TableCell>
            <TableCell className="text-right"><Skeleton className="h-8 w-8 rounded-full" /></TableCell>
          </TableRow>
        ))
      )
    }

    if (fetchError) {
      return (
        <TableRow>
          <TableCell colSpan={5} className="text-center text-destructive py-4">
            <div className="flex items-center justify-center">
              <AlertCircle className="mr-2 h-5 w-5" />
              <span>Error: {fetchError}</span>
            </div>
            <Button onClick={() => fetchRepositories()} variant="outline" size="sm" className="mt-2">
              Try Again
            </Button>
          </TableCell>
        </TableRow>
      )
    }

    if (!isLoading && repositories.length === 0) {
      return (
        <TableRow>
          <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
            <p>No repositories added yet.</p>
            <Button size="sm" className="mt-2" onClick={() => { setAddRepoError(null); setNewRepoUrl(""); setAddDialogOpen(true);}}>
                <Plus className="mr-2 h-4 w-4" />
                Add Your First Repository
            </Button>
          </TableCell>
        </TableRow>
      )
    }

    return repositories.map((repo) => {
      // TODO: Fix this old working
      const ingestionTaskStatus = getLatestTaskForEntity(
        taskStatuses, 
        "Repository", // entityType
        repo.id,        // entityId
        "repository_ingestion" // jobType
      );
      // Determine if the repo is actively being processed (RUNNING or PENDING from SSE)
      const isRepoCurrentlyProcessingViaSSE = ingestionTaskStatus && 
                               (ingestionTaskStatus.status.toUpperCase() === "RUNNING" || ingestionTaskStatus.status.toUpperCase() === "PENDING");
      
      // For the main dropdown trigger, also consider the local button loading state for immediate feedback
      const isActionTriggerDisabled = localIngestButtonLoading[repo.id] || 
                                    isRepoCurrentlyProcessingViaSSE || 
                                    (isDeletingRepository && selectedRepoForDelete?.id === repo.id);
      
      const showSpinnerOnTrigger = localIngestButtonLoading[repo.id] || isRepoCurrentlyProcessingViaSSE;

      return (
        <TableRow key={repo.id} className={isRepoCurrentlyProcessingViaSSE ? "opacity-60" : ""}>
          <TableCell className="font-medium">{repo.name}</TableCell>
          <TableCell className="font-mono text-sm max-w-[200px] md:max-w-xs truncate" title={repo.git_url}>{repo.git_url}</TableCell>
          <TableCell>{formatDate(repo.created_at)}</TableCell>
          <TableCell>
            <div className="flex flex-col text-xs text-muted-foreground">
              <span>{repo.datasets_count} datasets</span>
              <span>{repo.bot_patterns_count} bot patterns</span>
              <span>{repo.github_issues_count} GitHub issues</span>
              {isRepoCurrentlyProcessingViaSSE && ingestionTaskStatus && (
                <span className="text-blue-600 dark:text-blue-400 mt-1 font-medium">
                  {ingestionTaskStatus.status_message || ingestionTaskStatus.status.toUpperCase()} 
                  {ingestionTaskStatus.progress != null ? ` (${ingestionTaskStatus.progress}%)` : ''}
                </span>
              )}
            </div>
          </TableCell>
          <TableCell className="text-right">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  disabled={isActionTriggerDisabled}
                >
                  {showSpinnerOnTrigger ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <MoreHorizontal className="h-4 w-4" />
                  )}
                  <span className="sr-only">Open menu for {repo.name}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Actions for {repo.name}</DropdownMenuLabel>
                <DropdownMenuItem asChild disabled={isActionTriggerDisabled}>
                  <Link href={`/repositories/${repo.id}`}>
                    <Eye className="mr-2 h-4 w-4" />
                    View Details
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => handleIngestRepository(repo.id, repo.name)}
                  disabled={isActionTriggerDisabled} // Disables if any processing related to this repo
                >
                  {showSpinnerOnTrigger ? ( // Use the same spinner logic as the trigger
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {ingestionTaskStatus?.status_message ? ingestionTaskStatus.status_message.substring(0,15)+'...' : (localIngestButtonLoading[repo.id] ? "Initiating..." : "Processing...")}
                    </>
                  ) : (
                    <>
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Ingest / Re-Ingest
                    </>
                  )}
                </DropdownMenuItem>
                <DropdownMenuItem disabled> 
                  <Edit className="mr-2 h-4 w-4" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => handleDeleteConfirmation(repo)}
                  disabled={isDeletingRepository || showSpinnerOnTrigger} // Disable delete if ingesting or another delete is in progress
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
      );
    });
  };

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">Repositories</h1>
          <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
            <DialogTrigger asChild>
              <Button onClick={() => { setAddRepoError(null); setNewRepoUrl(""); }}>
                <Plus className="mr-2 h-4 w-4" />
                Add Repository
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add New Repository</DialogTitle>
                <DialogDescription>Enter the Git URL of the repository you want to analyze.</DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="git-url">Git URL</Label>
                  <Input
                    id="git-url"
                    placeholder="https://github.com/org/repo.git"
                    value={newRepoUrl}
                    onChange={(e) => { setNewRepoUrl(e.target.value); setAddRepoError(null);}}
                    className={addRepoError ? "border-destructive" : ""}
                  />
                  {addRepoError && <p className="text-sm text-destructive mt-1">{addRepoError}</p>}
                  <p className="text-xs text-muted-foreground">
                    Provide the full clone URL (e.g., HTTPS or SSH).
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddRepository} disabled={isAddingRepository}>
                  {isAddingRepository ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Adding...
                    </>
                  ) : "Add Repository"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Git URL</TableHead>
                <TableHead>Date Added</TableHead>
                <TableHead>Summary & Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {renderContent()}
            </TableBody>
          </Table>
        </div>

        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete Repository: {selectedRepoForDelete?.name}</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this repository? This will also remove associated datasets, models, and jobs. This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteDialogOpen(false)} disabled={isDeletingRepository}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={handleDeleteRepository} disabled={isDeletingRepository}>
                {isDeletingRepository ? (
                    <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Deleting...
                    </>
                ) : "Delete"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </MainLayout>
  )
}