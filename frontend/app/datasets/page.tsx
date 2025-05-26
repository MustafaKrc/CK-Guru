// frontend/app/datasets/page.tsx
"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MoreHorizontal, Plus, RefreshCw, Eye, Trash2, AlertCircle, Loader2, Database, CheckCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
    Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis 
} from "@/components/ui/pagination";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";


import { apiService, handleApiError } from "@/lib/apiService";
import { DatasetRead, PaginatedDatasetRead } from "@/types/api/dataset";
import { PaginatedRepositoryRead, Repository } from "@/types/api/repository"; // For repository filter dropdown
import { DatasetStatusEnum } from "@/types/api/enums";
import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";

const ITEMS_PER_PAGE_DATASETS = 10;
const ALL_FILTER_VALUE = "_all_";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetRead[]>([]);
  const [pagination, setPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState(""); // Will filter client-side for now, or backend can add 'q'
  const [statusFilter, setStatusFilter] = useState<DatasetStatusEnum | typeof ALL_FILTER_VALUE>(ALL_FILTER_VALUE);
  const [repositoryFilter, setRepositoryFilter] = useState<string>(ALL_FILTER_VALUE);

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(true);
  
  const [selectedDatasetForDelete, setSelectedDatasetForDelete] = useState<DatasetRead | null>(null);
  const [isDeletingDataset, setIsDeletingDataset] = useState(false);


  const { toast } = useToast();
  const { taskStatuses } = useTaskStore();
  const availableDatasetStatuses = Object.values(DatasetStatusEnum);

  const fetchRepositoriesForFilter = useCallback(async () => {
    setIsLoadingRepositories(true);
    try {
      const response = await apiService.get<PaginatedRepositoryRead>(`/repositories?limit=200`); // Assuming paginated
      setRepositories(response.items || []);
    } catch (err) {
      handleApiError(err, "Failed to fetch repositories for filter");
    } finally {
      setIsLoadingRepositories(false);
    }
  }, []);
  
  const fetchDatasets = useCallback(async (page: number = 1) => {
    setPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    setFetchError(null);
    const skip = (page - 1) * ITEMS_PER_PAGE_DATASETS;
    
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: ITEMS_PER_PAGE_DATASETS.toString(),
    });
    if (statusFilter && statusFilter !== ALL_FILTER_VALUE) params.append("status", statusFilter);
    // Backend /datasets endpoint doesn't currently filter by repository_id.
    // If it did, we'd add: if (repositoryFilter && repositoryFilter !== ALL_FILTER_VALUE) params.append("repository_id", repositoryFilter);
    // For now, repository filtering will be client-side if repositoryFilter is set. Search query is also client-side.

    try {
      const response = await apiService.get<PaginatedDatasetRead>(`/datasets?${params.toString()}`);
      if (response && Array.isArray(response.items) && typeof response.total === 'number') {
        setDatasets(response.items);
        setPagination(prev => ({ ...prev, totalItems: response.total, isLoading: false }));
      } else {
        setFetchError("Received invalid data structure for datasets.");
        setPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
      }
    } catch (err) {
      handleApiError(err, "Failed to fetch datasets");
      setFetchError(err instanceof Error ? err.message : "Error fetching datasets.");
      setPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, [statusFilter]); // Add other API-based filters here if they become available

  useEffect(() => {
    fetchRepositoriesForFilter();
  }, [fetchRepositoriesForFilter]);

  useEffect(() => {
    fetchDatasets(1); // Fetch page 1 when filters change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]); // Only refetch from API if API-supported filters change

  const handlePageChange = (newPage: number) => {
    if (newPage !== pagination.currentPage) {
      fetchDatasets(newPage);
    }
  };

  const handleDeleteConfirmation = (dataset: DatasetRead) => {
    setSelectedDatasetForDelete(dataset);
  };

  const handleDeleteDataset = async () => {
    if (!selectedDatasetForDelete) return;
    setIsDeletingDataset(true);
    try {
        await apiService.delete<void>(`/datasets/${selectedDatasetForDelete.id}`);
        toast({ title: "Dataset Deleted", description: `Dataset ${selectedDatasetForDelete.name} has been marked for deletion.`});
        setSelectedDatasetForDelete(null); // Close dialog
        // Refresh current page or go to previous if current becomes empty
        const newTotalItems = pagination.totalItems - 1;
        const newTotalPages = Math.ceil(newTotalItems / ITEMS_PER_PAGE_DATASETS);
        const newCurrentPage = Math.min(pagination.currentPage, Math.max(1, newTotalPages));
        fetchDatasets(newCurrentPage);
    } catch (err) {
        handleApiError(err, "Failed to delete dataset");
    } finally {
        setIsDeletingDataset(false);
    }
  };


  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  };

  const renderStatusBadge = (dataset: DatasetRead) => {
    const liveStatus = getLatestTaskForEntity(taskStatuses, "Dataset", dataset.id, "dataset_generation");
    const currentStatusToDisplay = liveStatus || { status: dataset.status, status_message: dataset.status_message, progress: null };
    
    const { status, status_message, progress } = currentStatusToDisplay;
    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let text = String(status_message || status || "Unknown").toUpperCase();

    switch (String(status).toUpperCase()) {
      case DatasetStatusEnum.READY.toUpperCase(): 
      case "SUCCESS": // From task status
        badgeVariant = "default"; icon = <CheckCircle className="h-3 w-3 mr-1" />; text = "Ready"; break;
      case DatasetStatusEnum.GENERATING.toUpperCase():
      case "RUNNING": // From task status
        badgeVariant = "outline"; icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />; text = `Generating (${progress ?? 0}%)`; break;
      case DatasetStatusEnum.PENDING.toUpperCase():
        badgeVariant = "outline"; icon = <Loader2 className="h-3 w-3 mr-1 animate-spin" />; text = "Pending"; break;
      case DatasetStatusEnum.FAILED.toUpperCase():
        badgeVariant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1" />; text = `Failed`; break; // Full message shown in tooltip/details
    }
    return <Badge variant={badgeVariant} className="whitespace-nowrap text-xs px-1.5 py-0.5" title={status_message || status || ''}>{icon}{text}</Badge>;
  };
  
  const filteredAndSearchedDatasets = useMemo(() => {
    return datasets.filter(dataset => {
        const matchesRepo = repositoryFilter === ALL_FILTER_VALUE || dataset.repository_id.toString() === repositoryFilter;
        const matchesSearch = searchQuery 
            ? dataset.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
              (dataset.description && dataset.description.toLowerCase().includes(searchQuery.toLowerCase()))
            : true;
        return matchesRepo && matchesSearch;
    });
  }, [datasets, searchQuery, repositoryFilter]);


  const renderPaginationControls = () => {
    // Uses filteredAndSearchedDatasets.length for total if client-side filtering is primary
    // Or pagination.totalItems if server-side filtering is primary
    const totalItemsForPagination = (repositoryFilter !== ALL_FILTER_VALUE || searchQuery) 
                                     ? filteredAndSearchedDatasets.length 
                                     : pagination.totalItems;
    const totalPages = Math.ceil(totalItemsForPagination / ITEMS_PER_PAGE_DATASETS);

    if (totalPages <= 1 && !(repositoryFilter !== ALL_FILTER_VALUE || searchQuery)) return null; // Only hide if no client filtering applied for single server page
    if (totalPages <= 1 && (repositoryFilter !== ALL_FILTER_VALUE || searchQuery) && totalItemsForPagination <= ITEMS_PER_PAGE_DATASETS ) return null;


    let pageNumbers: (number | string)[] = [];
    if (totalPages <= 7) { pageNumbers = Array.from({ length: totalPages }, (_, i) => i + 1); } 
    else {
        pageNumbers.push(1);
        if (pagination.currentPage > 3) pageNumbers.push('...');
        if (pagination.currentPage > 2) pageNumbers.push(pagination.currentPage - 1);
        if (pagination.currentPage > 1 && pagination.currentPage < totalPages) pageNumbers.push(pagination.currentPage);
        if (pagination.currentPage < totalPages -1) pageNumbers.push(pagination.currentPage + 1);
        if (pagination.currentPage < totalPages - 2) pageNumbers.push('...');
        pageNumbers.push(totalPages);
        pageNumbers = [...new Set(pageNumbers)];
    }

    // If client-side filtering is active, pagination should adjust based on filtered results,
    // but the page number still refers to the *API's* current page.
    // This logic is complex if mixing server and client pagination.
    // For now, if client-side filters are active, pagination might be misleading or should be disabled/simplified.
    // A simpler approach: if client-side filtering, show all results without client-side pagination,
    // or ensure API handles all filtering.

    // For now, let's assume pagination always refers to the API's pages.
    // If client-side filtering reduces items significantly, pagination UI might look odd.
    if (pagination.totalItems <= ITEMS_PER_PAGE_DATASETS && !searchQuery && repositoryFilter === ALL_FILTER_VALUE) return null;


    return (
      <Pagination className="mt-4">
        <PaginationContent>
          <PaginationItem><PaginationPrevious onClick={() => handlePageChange(pagination.currentPage - 1)} aria-disabled={pagination.currentPage <= 1 || pagination.isLoading} className={(pagination.currentPage <= 1 || pagination.isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
          {pageNumbers.map((page, index) => (
            <PaginationItem key={typeof page === 'number' ? `page-${page}` : `ellipsis-${index}`}>
              {typeof page === 'number' ? 
                <PaginationLink onClick={() => handlePageChange(page)} isActive={pagination.currentPage === page} aria-disabled={pagination.isLoading} className={pagination.isLoading ? "pointer-events-none opacity-50" : ""}>{page}</PaginationLink> : 
                <PaginationEllipsis />}
            </PaginationItem>
          ))}
          <PaginationItem><PaginationNext onClick={() => handlePageChange(pagination.currentPage + 1)} aria-disabled={pagination.currentPage >= totalPages || pagination.isLoading} className={(pagination.currentPage >= totalPages || pagination.isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
        </PaginationContent>
      </Pagination>
    );
  };

  const renderContent = () => {
    if (pagination.isLoading && datasets.length === 0) {
      return Array.from({ length: 5 }).map((_, index) => (
        <TableRow key={`skel-dataset-${index}`}>
          <TableCell><Skeleton className="h-5 w-40" /></TableCell>
          <TableCell><Skeleton className="h-5 w-32" /></TableCell>
          <TableCell><Skeleton className="h-5 w-24" /></TableCell>
          <TableCell><Skeleton className="h-5 w-20" /></TableCell>
          <TableCell><Skeleton className="h-5 w-48" /></TableCell>
          <TableCell className="text-right"><Skeleton className="h-8 w-8 rounded-full" /></TableCell>
        </TableRow>
      ));
    }
    if (fetchError) {
      return <TableRow><TableCell colSpan={6} className="text-center text-destructive py-4"><Alert variant="destructive" className="justify-center"><AlertCircle className="mr-2 h-5 w-5" /><AlertDescription>{fetchError}</AlertDescription></Alert><Button onClick={() => fetchDatasets(1)} variant="outline" size="sm" className="mt-2">Try Again</Button></TableCell></TableRow>;
    }
    if (!pagination.isLoading && filteredAndSearchedDatasets.length === 0) {
      return <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground"><p>No datasets found matching your criteria.</p><Button size="sm" className="mt-2" asChild><Link href="/datasets/create"><Plus className="mr-2 h-4 w-4" />Create Your First Dataset</Link></Button></TableCell></TableRow>;
    }

    return filteredAndSearchedDatasets.map((dataset) => {
      const repo = repositories.find(r => r.id === dataset.repository_id);
      return (
        <TableRow key={dataset.id}>
          <TableCell className="font-medium break-all max-w-[250px]">{dataset.name}</TableCell>
          <TableCell className="text-xs">
            {repo ? <Link href={`/repositories/${repo.id}`} className="hover:underline text-primary">{repo.name}</Link> : `ID: ${dataset.repository_id}`}
          </TableCell>
          <TableCell>{renderStatusBadge(dataset)}</TableCell>
          <TableCell className="text-xs">{formatDate(dataset.created_at)}</TableCell>
          <TableCell className="text-xs truncate max-w-[200px]" title={dataset.description || ""}>{dataset.description || "N/A"}</TableCell>
          <TableCell className="text-right">
            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="h-7 w-7"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Actions</DropdownMenuLabel>
                <DropdownMenuItem asChild><Link href={`/datasets/${dataset.id}`}><Eye className="mr-2 h-4 w-4" />View Details</Link></DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => handleDeleteConfirmation(dataset)} disabled={isDeletingDataset && selectedDatasetForDelete?.id === dataset.id}>
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
      <PageContainer
        title={`Datasets (${pagination.isLoading && pagination.totalItems === 0 ? "..." : pagination.totalItems})`}
        description="Browse and manage your datasets for model training."
        actions={<Button asChild><Link href="/datasets/create"><Plus className="mr-2 h-4 w-4" />Create Dataset</Link></Button>}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="md:col-span-1">
            <Label htmlFor="search">Search by Name/Description</Label>
            <Input id="search" placeholder="Enter search query..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="statusFilter">Filter by Status</Label>
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as DatasetStatusEnum | typeof ALL_FILTER_VALUE)}>
              <SelectTrigger id="statusFilter"><SelectValue placeholder="All Statuses" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER_VALUE}>All Statuses</SelectItem>
                {availableDatasetStatuses.map(s => <SelectItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="repositoryFilter">Filter by Repository</Label>
            <Select value={repositoryFilter} onValueChange={setRepositoryFilter} disabled={isLoadingRepositories || repositories.length === 0}>
              <SelectTrigger id="repositoryFilter"><SelectValue placeholder={isLoadingRepositories ? "Loading..." : "All Repositories"} /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER_VALUE}>All Repositories</SelectItem>
                {repositories.map(repo => <SelectItem key={repo.id} value={repo.id.toString()}>{repo.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Dataset Name</TableHead><TableHead>Repository</TableHead><TableHead>Status</TableHead>
                <TableHead>Created</TableHead><TableHead>Description</TableHead><TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>{renderContent()}</TableBody>
          </Table>
        </div>
        {renderPaginationControls()}
        
        <AlertDialog open={!!selectedDatasetForDelete} onOpenChange={(open) => !open && setSelectedDatasetForDelete(null)}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Dataset: {selectedDatasetForDelete?.name}</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete this dataset definition and its associated data from storage? This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel onClick={() => setSelectedDatasetForDelete(null)} disabled={isDeletingDataset}>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleDeleteDataset} disabled={isDeletingDataset} className="bg-destructive hover:bg-destructive/90">
                  {isDeletingDataset ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Deleting...</> : "Delete"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>

      </PageContainer>
    </MainLayout>
  );
}