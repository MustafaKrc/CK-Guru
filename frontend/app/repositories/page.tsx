// frontend/app/repositories/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { Plus, MoreHorizontal, RefreshCw, Eye, Edit, Trash2, AlertCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert"; // Corrected import for Alert

import { apiService, handleApiError, ApiError } from "@/lib/apiService";
import { Repository, RepositoryCreatePayload, PaginatedRepositoryRead } from "@/types/api/repository";
import { TaskResponse } from "@/types/api/task";

import { useTaskStore } from "@/store/taskStore"; // TaskStatusUpdatePayload is exported from here
import { getLatestTaskForEntity } from "@/lib/taskUtils";
// IMPORT PAGINATION COMPONENTS
import { 
    Pagination, 
    PaginationContent, 
    PaginationItem, 
    PaginationLink, 
    PaginationNext, 
    PaginationPrevious,
    PaginationEllipsis 
} from "@/components/ui/pagination";

const ITEMS_PER_PAGE_REPOS = 10;

export default function RepositoriesPage() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [pagination, setPagination] = useState({
    currentPage: 1,
    totalItems: 0,
    isLoading: true,
  });
  // const [isLoading, setIsLoading] = useState(true); // This is now part of pagination.isLoading
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [newRepoUrl, setNewRepoUrl] = useState("");
  const [isAddingRepository, setIsAddingRepository] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [addRepoError, setAddRepoError] = useState<string | null>(null);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedRepoForDelete, setSelectedRepoForDelete] = useState<Repository | null>(null);
  const [isDeletingRepository, setIsDeletingRepository] = useState(false);

  // const [isIngesting, setIsIngesting] = useState<Record<number, boolean>>({}); // Not directly used, relies on taskStatuses
  const { taskStatuses } = useTaskStore();
  const [localIngestButtonLoading, setLocalIngestButtonLoading] = useState<Record<number, boolean>>({});
  const { toast } = useToast();

  const fetchRepositories = useCallback(async (page: number = 1, showLoadingSpinner: boolean = true) => {
    if (showLoadingSpinner) {
        setPagination(prev => ({ ...prev, isLoading: true, currentPage: page })); // Ensure currentPage is updated here too
    } else {
        setPagination(prev => ({ ...prev, currentPage: page })); // Update currentPage for non-spinner fetches
    }
    setFetchError(null);
    const skip = (page - 1) * ITEMS_PER_PAGE_REPOS;
    try {
      const response = await apiService.get<PaginatedRepositoryRead>(`/repositories?skip=${skip}&limit=${ITEMS_PER_PAGE_REPOS}`);
      if (response && Array.isArray(response.items) && typeof response.total === 'number') {
        setRepositories(response.items);
        setPagination(prev => ({ 
            ...prev, // Keep potentially updated currentPage from above
            totalItems: response.total, 
            isLoading: false 
        }));
      } else {
        console.error("Unexpected response structure for repositories:", response);
        setFetchError("Received invalid data structure for repositories.");
        setRepositories([]);
        setPagination(prev => ({ ...prev, totalItems: 0, isLoading: false}));
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch repositories.";
      setFetchError(errorMessage);
      setRepositories([]);
      setPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, []);

  // Initial fetch on mount only
  useEffect(() => {
    fetchRepositories(1, true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty dependency array means this runs once on mount

  // Effect for page changes driven by pagination controls
  useEffect(() => {
    // Avoid fetching on initial mount again if fetchRepositories already did it
    // This check can be refined, e.g. by a flag, or by ensuring initial fetch does not set a different currentPage than 1.
    if (pagination.currentPage !== 1 || repositories.length === 0 && !pagination.isLoading && !fetchError) {
       // Fetch only if page changed from initial or if initial load resulted in no repos (and not error/loading)
    }
     // The fetch for page changes is now handled by handlePageChange directly calling fetchRepositories
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pagination.currentPage]);


  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A";
    try {
      return new Date(dateString).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
    } catch (e) {
      return "Invalid Date";
    }
  };

  const handleAddRepository = async () => {
    if (!newRepoUrl.trim()) {
      setAddRepoError("Git URL cannot be empty.");
      return;
    }
    try { new URL(newRepoUrl); } catch (_) {
      setAddRepoError("Please enter a valid Git URL."); return;
    }
    setIsAddingRepository(true); setAddRepoError(null);
    try {
      const payload: RepositoryCreatePayload = { git_url: newRepoUrl };
      await apiService.post<Repository, RepositoryCreatePayload>('/repositories', payload);
      toast({ title: "Repository Added", description: `Successfully added ${newRepoUrl}. You can now ingest it.` });
      setNewRepoUrl(""); setAddDialogOpen(false);
      fetchRepositories(1, false); // Refresh list, go to page 1, no main spinner
    } catch (err) {
      if (err instanceof ApiError) { setAddRepoError(err.message); } 
      else { setAddRepoError("An unexpected error."); handleApiError(err, "Add Repository Failed"); }
    } finally { setIsAddingRepository(false); }
  };

  const handleDeleteConfirmation = (repo: Repository) => {
    setSelectedRepoForDelete(repo); setDeleteDialogOpen(true);
  };

  const handleDeleteRepository = async () => {
    if (!selectedRepoForDelete) return;
    setIsDeletingRepository(true);
    try {
      await apiService.delete<Repository>(`/repositories/${selectedRepoForDelete.id}`);
      toast({ title: "Repository Deleted", description: `Repository "${selectedRepoForDelete.name}" deleted.`});
      setDeleteDialogOpen(false); setSelectedRepoForDelete(null);
      const newTotalItems = pagination.totalItems - 1;
      const newTotalPages = Math.ceil(newTotalItems / ITEMS_PER_PAGE_REPOS);
      const newCurrentPage = Math.min(pagination.currentPage, Math.max(1, newTotalPages));
      fetchRepositories(newCurrentPage, false);
    } catch (err) { handleApiError(err, "Delete Repository Failed");
    } finally { setIsDeletingRepository(false); }
  };

  const handleIngestRepository = async (repoId: number, repoName: string) => {
    setLocalIngestButtonLoading(prev => ({ ...prev, [repoId]: true }));
    try {
      const response = await apiService.post<TaskResponse>(`/repositories/${repoId}/ingest`);
      toast({
        title: "Ingestion Initiated",
        description: `${repoName}: Task ${response.task_id} submitted.`,
        action: (<Button variant="outline" size="sm" asChild><Link href={`/tasks?taskId=${response.task_id}`}>View Task</Link></Button>),
      });
    } catch (err) { handleApiError(err, `Ingest Repository ${repoName} Failed`);
    } finally { setLocalIngestButtonLoading(prev => ({ ...prev, [repoId]: false })); }
  };

  const handlePageChange = (newPage: number) => {
    if (newPage !== pagination.currentPage) {
        fetchRepositories(newPage, true); // Show loading spinner for page changes
    }
  };

  const renderPaginationControls = () => {
    const totalPages = Math.ceil(pagination.totalItems / ITEMS_PER_PAGE_REPOS);
    if (totalPages <= 1) return null;

    let pageNumbers: (number | string)[] = [];
    if (totalPages <= 7) {
        pageNumbers = Array.from({ length: totalPages }, (_, i) => i + 1);
    } else {
        pageNumbers.push(1);
        if (pagination.currentPage > 3) pageNumbers.push('...');
        if (pagination.currentPage > 2) pageNumbers.push(pagination.currentPage - 1);
        if (pagination.currentPage > 1 && pagination.currentPage < totalPages) pageNumbers.push(pagination.currentPage);
        if (pagination.currentPage < totalPages -1) pageNumbers.push(pagination.currentPage + 1);
        if (pagination.currentPage < totalPages - 2) pageNumbers.push('...');
        pageNumbers.push(totalPages);
        pageNumbers = [...new Set(pageNumbers)]; // Remove duplicates
    }


    return (
      <Pagination className="mt-4">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              onClick={() => handlePageChange(pagination.currentPage - 1)}
              aria-disabled={pagination.currentPage <= 1 || pagination.isLoading}
              className={(pagination.currentPage <= 1 || pagination.isLoading) ? "pointer-events-none opacity-50" : ""}
            />
          </PaginationItem>
          {pageNumbers.map((page, index) => (
            <PaginationItem key={typeof page === 'number' ? `page-${page}` : `ellipsis-${index}`}>
              {typeof page === 'number' ? (
                <PaginationLink
                  onClick={() => handlePageChange(page)}
                  isActive={pagination.currentPage === page}
                  aria-disabled={pagination.isLoading}
                  className={pagination.isLoading ? "pointer-events-none opacity-50" : ""}
                >
                  {page}
                </PaginationLink>
              ) : (
                <PaginationEllipsis />
              )}
            </PaginationItem>
          ))}
          <PaginationItem>
            <PaginationNext
              onClick={() => handlePageChange(pagination.currentPage + 1)}
              aria-disabled={pagination.currentPage >= totalPages || pagination.isLoading}
              className={(pagination.currentPage >= totalPages || pagination.isLoading) ? "pointer-events-none opacity-50" : ""}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    );
  };


  const renderContent = () => {
    if (pagination.isLoading && repositories.length === 0) {
      return Array.from({ length: Math.max(1, Math.floor(ITEMS_PER_PAGE_REPOS / 2)) }).map((_, index) => (
        <TableRow key={`skeleton-${index}`}>
          <TableCell><Skeleton className="h-5 w-32" /></TableCell>
          <TableCell><Skeleton className="h-5 w-48" /></TableCell>
          <TableCell><Skeleton className="h-5 w-24" /></TableCell>
          <TableCell><Skeleton className="h-5 w-40" /></TableCell>
          <TableCell className="text-right"><Skeleton className="h-8 w-8 rounded-full" /></TableCell>
        </TableRow>
      ));
    }

    if (fetchError) {
      return (
        <TableRow>
          <TableCell colSpan={5} className="text-center text-destructive py-4">
            <Alert variant="destructive" className="justify-center">
              <AlertCircle className="mr-2 h-5 w-5" />
              <AlertDescription>{fetchError}</AlertDescription>
            </Alert>
            <Button onClick={() => fetchRepositories(1, true)} variant="outline" size="sm" className="mt-2">
              Try Again
            </Button>
          </TableCell>
        </TableRow>
      );
    }

    if (!pagination.isLoading && repositories.length === 0) {
      return (
        <TableRow>
          <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
            <p>No repositories added yet.</p>
            <Button size="sm" className="mt-2" onClick={() => { setAddRepoError(null); setNewRepoUrl(""); setAddDialogOpen(true);}}>
                <Plus className="mr-2 h-4 w-4" /> Add Your First Repository
            </Button>
          </TableCell>
        </TableRow>
      );
    }

    return repositories.map((repo) => {
      const ingestionTaskStatus = getLatestTaskForEntity(taskStatuses, "Repository", repo.id, "repository_ingestion");
      const isRepoCurrentlyProcessingViaSSE = ingestionTaskStatus && 
                               (ingestionTaskStatus.status.toUpperCase() === "RUNNING" || ingestionTaskStatus.status.toUpperCase() === "PENDING");
      const isActionTriggerDisabled = localIngestButtonLoading[repo.id] || isRepoCurrentlyProcessingViaSSE || (isDeletingRepository && selectedRepoForDelete?.id === repo.id);
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
                <Button variant="ghost" size="icon" disabled={isActionTriggerDisabled}>
                  {showSpinnerOnTrigger ? <Loader2 className="h-4 w-4 animate-spin" /> : <MoreHorizontal className="h-4 w-4" />}
                  <span className="sr-only">Open menu for {repo.name}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Actions for {repo.name}</DropdownMenuLabel>
                <DropdownMenuItem asChild disabled={isActionTriggerDisabled}><Link href={`/repositories/${repo.id}`}><Eye className="mr-2 h-4 w-4" />View Details</Link></DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleIngestRepository(repo.id, repo.name)} disabled={isActionTriggerDisabled}>
                  {showSpinnerOnTrigger ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />{ingestionTaskStatus?.status_message ? ingestionTaskStatus.status_message.substring(0,15)+'...' : (localIngestButtonLoading[repo.id] ? "Initiating..." : "Processing...")}</>
                                       : <><RefreshCw className="mr-2 h-4 w-4" />Ingest / Re-Ingest</>}
                </DropdownMenuItem>
                <DropdownMenuItem disabled> <Edit className="mr-2 h-4 w-4" />Edit</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => handleDeleteConfirmation(repo)} disabled={isDeletingRepository || showSpinnerOnTrigger}>
                  <Trash2 className="mr-2 h-4 w-4" />Delete
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
          <h1 className="text-3xl font-bold tracking-tight">
            Repositories ({pagination.isLoading && pagination.totalItems === 0 ? <Loader2 className="inline h-6 w-6 animate-spin" /> : pagination.totalItems})
          </h1>
          <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
            <DialogTrigger asChild>
              <Button onClick={() => { setAddRepoError(null); setNewRepoUrl(""); }}>
                <Plus className="mr-2 h-4 w-4" />Add Repository
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
                  <Input id="git-url" placeholder="https://github.com/org/repo.git" value={newRepoUrl} onChange={(e) => { setNewRepoUrl(e.target.value); setAddRepoError(null);}} className={addRepoError ? "border-destructive" : ""} />
                  {addRepoError && <p className="text-sm text-destructive mt-1">{addRepoError}</p>}
                  <p className="text-xs text-muted-foreground">Provide the full clone URL (e.g., HTTPS or SSH).</p>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setAddDialogOpen(false)}>Cancel</Button>
                <Button onClick={handleAddRepository} disabled={isAddingRepository}>
                  {isAddingRepository ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Adding...</> : "Add Repository"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead><TableHead>Git URL</TableHead><TableHead>Date Added</TableHead>
                <TableHead>Summary & Status</TableHead><TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>{renderContent()}</TableBody>
          </Table>
        </div>
        
        {/* PAGINATION UI - RENDERED HERE */}
        {renderPaginationControls()}

        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete Repository: {selectedRepoForDelete?.name}</DialogTitle>
                <DialogDescription>
                  Are you sure you want to delete this repository? This will also remove associated datasets, models, and jobs. This action cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => setDeleteDialogOpen(false)} disabled={isDeletingRepository}>Cancel</Button>
                <Button variant="destructive" onClick={handleDeleteRepository} disabled={isDeletingRepository}>
                  {isDeletingRepository ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Deleting...</> : "Delete"}
                </Button>
              </DialogFooter>
            </DialogContent>
        </Dialog>
      </div>
    </MainLayout>
  );
}