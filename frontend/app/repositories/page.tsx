"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Plus, MoreHorizontal, RefreshCw, Eye, Edit, Trash2, AlertCircle, Loader2, CheckCircle, ArrowUpDown } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { useDebounce } from "@/hooks/useDebounce"; // <-- Import the new hook
import { apiService, handleApiError, ApiError } from "@/lib/apiService";
import { Repository, RepositoryCreatePayload, PaginatedRepositoryRead, TaskResponse } from "@/types/api";
import { useTaskStore } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/components/ui/pagination";
import { generatePagination } from "@/lib/paginationUtils";

type SortableKeys = 'name' | 'created_at' | 'summary';
type SortConfig = {
  key: SortableKeys;
  direction: 'asc' | 'desc';
};

const RepositoryStatus: React.FC<{ repo: Repository }> = ({ repo }) => {
  const { taskStatuses } = useTaskStore();
  const ingestionTask = getLatestTaskForEntity(taskStatuses, "Repository", repo.id, "repository_ingestion");

  if (ingestionTask && (ingestionTask.status === 'RUNNING' || ingestionTask.status === 'PENDING')) {
    return (
      <div className="flex flex-col gap-1.5 w-full max-w-[160px]">
        <Badge variant="outline" className="text-blue-600 border-blue-600 dark:text-blue-400 dark:border-blue-500">
          <RefreshCw className="h-3 w-3 mr-1.5 animate-spin" />
          Ingesting... ({ingestionTask.progress ?? 0}%)
        </Badge>
        <Progress value={ingestionTask.progress ?? 0} className="h-1.5" indicatorClassName="bg-blue-500"/>
        <span className="text-xs text-muted-foreground truncate" title={ingestionTask.status_message ?? ''}>
          {ingestionTask.status_message || 'Starting...'}
        </span>
      </div>
    );
  }

  if (repo.datasets_count > 0 || repo.github_issues_count > 0 || repo.bot_patterns_count > 0) {
    return <Badge variant="default" className="bg-green-100 text-green-800 dark:bg-green-800/20 dark:text-green-300"><CheckCircle className="h-3 w-3 mr-1"/>Ingested</Badge>;
  }
  
  return <Badge variant="secondary">Not Ingested</Badge>;
};


export default function RepositoriesPage() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [pagination, setPagination] = useState({ currentPage: 1, totalItems: 0, itemsPerPage: 10, isLoading: true });
  const [fetchError, setFetchError] = useState<string | null>(null);

  // States for server-side operations
  const [nameFilter, setNameFilter] = useState("");
  const debouncedNameFilter = useDebounce(nameFilter, 500);
  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: 'name', direction: 'asc' });

  // UI state
  const [isAddingRepo, setIsAddingRepo] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [newRepoUrl, setNewRepoUrl] = useState("");
  const [addRepoError, setAddRepoError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedRepoForDelete, setSelectedRepoForDelete] = useState<Repository | null>(null);
  const [isDeletingRepo, setIsDeletingRepo] = useState(false);
  const [ingestLoading, setIngestLoading] = useState<Record<number, boolean>>({});

  const { toast } = useToast();
  const { taskStatuses } = useTaskStore();

  const fetchRepositories = useCallback(async (page: number, limit: number, sort: SortConfig, filter: string) => {
    setPagination(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await apiService.getRepositories({
        skip: (page - 1) * limit,
        limit: limit,
        sortBy: sort.key,
        sortDir: sort.direction,
        nameFilter: filter,
      });
      setRepositories(response.items || []);
      setPagination(prev => ({ ...prev, totalItems: response.total || 0, isLoading: false, currentPage: page, itemsPerPage: limit }));
    } catch (err) {
      handleApiError(err, "Failed to fetch repositories");
      setFetchError(err instanceof Error ? err.message : "Could not load data.");
      setPagination(prev => ({ ...prev, isLoading: false }));
    }
  }, []);
  
  // This single useEffect now controls all data fetching based on state changes.
  useEffect(() => {
      // We always fetch from page 1 when filters or sorting change
      fetchRepositories(1, pagination.itemsPerPage, sortConfig, debouncedNameFilter);
  }, [debouncedNameFilter, sortConfig]); // Note: pagination.itemsPerPage is not here, handled separately
  
  // This useEffect handles pagination changes specifically.
  useEffect(() => {
      fetchRepositories(pagination.currentPage, pagination.itemsPerPage, sortConfig, debouncedNameFilter);
  }, [pagination.currentPage, pagination.itemsPerPage]);


  const handleSort = (key: SortableKeys) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };
  
  // Other handlers (handleAddRepository, handleDelete, etc.) remain unchanged...
  const handleAddRepository = async () => {
    if (!newRepoUrl.trim()) { setAddRepoError("Git URL cannot be empty."); return; }
    if (!newRepoUrl.startsWith('http') && !newRepoUrl.startsWith('git@')) { setAddRepoError("Please enter a valid HTTP(S) or SSH Git URL."); return; }
    setIsAddingRepo(true); setAddRepoError(null);
    try {
      await apiService.post<Repository, RepositoryCreatePayload>('/repositories', { git_url: newRepoUrl });
      toast({ title: "Repository Added", description: "Successfully added repository." });
      setNewRepoUrl(""); setAddDialogOpen(false);
      fetchRepositories(1, pagination.itemsPerPage, sortConfig, debouncedNameFilter); // Refresh data
    } catch (err) {
      handleApiError(err, "Add Repository Failed");
      if (err instanceof ApiError) setAddRepoError(err.message);
    } finally { setIsAddingRepo(false); }
  };
  
  const handleDeleteConfirmation = (repo: Repository) => { setSelectedRepoForDelete(repo); setDeleteDialogOpen(true); };
  const handleDeleteRepository = async () => {
    if (!selectedRepoForDelete) return;
    setIsDeletingRepo(true);
    try {
      await apiService.delete<Repository>(`/repositories/${selectedRepoForDelete.id}`);
      toast({ title: "Repository Deleted", description: `Repository "${selectedRepoForDelete.name}" deleted.` });
      setDeleteDialogOpen(false);
      fetchRepositories(pagination.currentPage, pagination.itemsPerPage, sortConfig, debouncedNameFilter); // Refresh data
    } catch (err) { handleApiError(err, "Delete Repository Failed"); } finally { setIsDeletingRepo(false); }
  };
  
  const handleIngest = async (repo: Repository) => {
    setIngestLoading(prev => ({ ...prev, [repo.id]: true }));
    try {
      const response = await apiService.post<TaskResponse>(`/repositories/${repo.id}/ingest`);
      toast({ title: "Ingestion Started", description: `Task ${response.task_id} submitted for ${repo.name}.` });
    } catch (err) { handleApiError(err, `Failed to start ingestion for ${repo.name}`); } finally { setIngestLoading(prev => ({ ...prev, [repo.id]: false })); }
  };

  const handleItemsPerPageChange = (value: string) => {
    const newItemsPerPage = parseInt(value, 10);
    setPagination(prev => ({ ...prev, itemsPerPage: newItemsPerPage, currentPage: 1 }));
  };


  const renderPagination = () => {
    const totalPages = Math.ceil(pagination.totalItems / pagination.itemsPerPage);
    if (totalPages <= 1) return null;
    const pageNumbers = generatePagination(pagination.currentPage, totalPages);
    return (
      <Pagination>
        <PaginationContent>
          <PaginationItem><PaginationPrevious onClick={() => setPagination(p => ({...p, currentPage: p.currentPage - 1}))} aria-disabled={pagination.currentPage <= 1} /></PaginationItem>
          {pageNumbers.map((page, index) =>
            typeof page === 'number' ? (
              <PaginationItem key={page}><PaginationLink onClick={() => setPagination(p => ({...p, currentPage: page}))} isActive={pagination.currentPage === page}>{page}</PaginationLink></PaginationItem>
            ) : (
              <PaginationItem key={`ellipsis-${index}`}><PaginationEllipsis /></PaginationItem>
            )
          )}
          <PaginationItem><PaginationNext onClick={() => setPagination(p => ({...p, currentPage: p.currentPage + 1}))} aria-disabled={pagination.currentPage >= totalPages} /></PaginationItem>
        </PaginationContent>
      </Pagination>
    );
  };
  
  const renderTableContent = () => {
    if (pagination.isLoading) {
      return Array.from({ length: pagination.itemsPerPage }).map((_, i) => (
        <TableRow key={`skel-${i}`}><TableCell colSpan={5}><Skeleton className="h-10 w-full" /></TableCell></TableRow>
      ));
    }
    if (fetchError) {
      return <TableRow><TableCell colSpan={5} className="text-center text-destructive py-6">{fetchError}</TableCell></TableRow>;
    }
    if (repositories.length === 0) {
      return <TableRow><TableCell colSpan={5} className="text-center py-8 text-muted-foreground">No repositories found.</TableCell></TableRow>;
    }

    // `repositories` is now already sorted and filtered by the server. No `processedRepositories` needed.
    return repositories.map(repo => {
      const task = getLatestTaskForEntity(taskStatuses, "Repository", repo.id, "repository_ingestion");
      const isIngesting = ingestLoading[repo.id] || (task && (task.status === 'RUNNING' || task.status === 'PENDING'));
      return (
        <TableRow key={repo.id} data-state={isIngesting ? "active" : ""}>
          <TableCell className="font-medium">
            <Link href={`/repositories/${repo.id}`} className="hover:underline text-primary">{repo.name}</Link>
          </TableCell>
          <TableCell className="text-xs text-muted-foreground">
            <div>{repo.datasets_count} Datasets</div>
            <div>{repo.bot_patterns_count} Bot Patterns</div>
            <div>{repo.github_issues_count} GitHub Issues</div>
          </TableCell>
          <TableCell><RepositoryStatus repo={repo} /></TableCell>
          <TableCell>{new Date(repo.created_at).toLocaleDateString()}</TableCell>
          <TableCell className="text-right">
            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" disabled={isIngesting}><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>{repo.name}</DropdownMenuLabel>
                <DropdownMenuItem asChild><Link href={`/repositories/${repo.id}`}><Eye className="mr-2 h-4 w-4" />View Details</Link></DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleIngest(repo)} disabled={isIngesting}><RefreshCw className="mr-2 h-4 w-4" /> Ingest / Re-Ingest</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => handleDeleteConfirmation(repo)}><Trash2 className="mr-2 h-4 w-4" />Delete</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
      );
    });
  };

  const SortableHeader: React.FC<{ sortKey: SortableKeys; children: React.ReactNode }> = ({ sortKey, children }) => (
    <Button variant="ghost" onClick={() => handleSort(sortKey)}>
      {children}
      {sortConfig.key === sortKey && <ArrowUpDown className="ml-2 h-4 w-4 inline-block" />}
    </Button>
  );

  return (
    <MainLayout>
      <div className="container mx-auto py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">Repositories ({pagination.totalItems})</h1>
          <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
            <DialogTrigger asChild><Button onClick={() => setNewRepoUrl("")}><Plus className="mr-2 h-4 w-4"/>Add Repository</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Add New Repository</DialogTitle><DialogDescription>Enter the Git URL of the repository you want to analyze.</DialogDescription></DialogHeader>
              <div className="grid gap-4 py-4"><Label htmlFor="git-url">Git URL</Label><Input id="git-url" placeholder="https://github.com/org/repo.git" value={newRepoUrl} onChange={(e) => { setNewRepoUrl(e.target.value); setAddRepoError(null); }} className={addRepoError ? "border-destructive" : ""} />{addRepoError && <p className="text-sm text-destructive mt-1">{addRepoError}</p>}</div>
              <DialogFooter><Button variant="outline" onClick={() => setAddDialogOpen(false)}>Cancel</Button><Button onClick={handleAddRepository} disabled={isAddingRepo}>{isAddingRepo && <Loader2 className="mr-2 h-4 w-4 animate-spin"/>} Add Repository</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <div className="flex flex-col md:flex-row gap-4">
          <Input placeholder="Filter by name..." value={nameFilter} onChange={(e) => setNameFilter(e.target.value)} className="max-w-sm"/>
          <div className="flex items-center gap-2">
            <Label htmlFor="items-per-page" className="text-sm">Show:</Label>
            <Select value={String(pagination.itemsPerPage)} onValueChange={handleItemsPerPageChange}>
              <SelectTrigger id="items-per-page" className="w-[80px]"><SelectValue /></SelectTrigger>
              <SelectContent>{[10, 25, 50].map(size => <SelectItem key={size} value={String(size)}>{size}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[250px]"><SortableHeader sortKey="name">Name</SortableHeader></TableHead>
                <TableHead><SortableHeader sortKey="summary">Summary</SortableHeader></TableHead>
                <TableHead>Status</TableHead>
                <TableHead><SortableHeader sortKey="created_at">Date Added</SortableHeader></TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>{renderTableContent()}</TableBody>
          </Table>
        </div>

        {renderPagination()}

        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <DialogContent>
            <DialogHeader><DialogTitle>Delete {selectedRepoForDelete?.name}?</DialogTitle><DialogDescription>This action is irreversible and will delete all associated data (datasets, models, jobs).</DialogDescription></DialogHeader>
            <DialogFooter><Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button><Button variant="destructive" onClick={handleDeleteRepository} disabled={isDeletingRepo}>{isDeletingRepo && <Loader2 className="mr-2 h-4 w-4 animate-spin"/>} Delete</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </MainLayout>
  );
}