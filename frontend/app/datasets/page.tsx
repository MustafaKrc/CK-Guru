// frontend/app/datasets/page.tsx
"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { MoreHorizontal, Plus, Eye, Trash2, AlertCircle, Loader2, CheckCircle, RefreshCw, ArrowUpDown } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/components/ui/pagination";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { PageContainer } from "@/components/ui/page-container";
import { SearchableSelect, SearchableSelectOption } from "@/components/ui/searchable-select"; // Added import
import { useDebounce } from "@/hooks/useDebounce";
import { apiService, handleApiError } from "@/lib/apiService";
import { DatasetRead, PaginatedDatasetRead, Repository, PaginatedRepositoryRead } from "@/types/api";
import { DatasetStatusEnum } from "@/types/api/enums";
import { useTaskStore } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { generatePagination } from "@/lib/paginationUtils";

const ALL_FILTER_VALUE = "_all_";

type SortableKeys = 'name' | 'repository_name' | 'status' | 'created_at';
type SortConfig = {
  key: SortableKeys;
  direction: 'asc' | 'desc';
};

/**
 * A reusable UI component for sortable table headers.
 */
const SortableHeader: React.FC<{
  sortKey: SortableKeys;
  sortConfig: SortConfig;
  onSort: (key: SortableKeys) => void;
  children: React.ReactNode;
  className?: string;
}> = ({ sortKey, sortConfig, onSort, children, className }) => (
    <Button variant="ghost" onClick={() => onSort(sortKey)} className={className}>
        {children}
        <ArrowUpDown className={`ml-2 h-4 w-4 transition-opacity ${sortConfig.key === sortKey ? 'opacity-100' : 'opacity-30'}`} />
    </Button>
);

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetRead[]>([]);
  const [pagination, setPagination] = useState({ currentPage: 1, totalItems: 0, itemsPerPage: 10, isLoading: true });
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Server-side operation states
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 500);
  const [statusFilter, setStatusFilter] = useState<DatasetStatusEnum | typeof ALL_FILTER_VALUE>(ALL_FILTER_VALUE);
  const [repositoryFilter, setRepositoryFilter] = useState<string>(ALL_FILTER_VALUE);
  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: 'created_at', direction: 'desc' });

  // State for filter dropdowns
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
      const response = await apiService.get<PaginatedRepositoryRead>(`/repositories?limit=200`); // Fetch enough for selection
      setRepositories(response.items || []);
    } catch (err) { handleApiError(err, "Failed to fetch repositories for filter"); }
    finally { setIsLoadingRepositories(false); }
  }, []);

  const fetchDatasets = useCallback(async (
    pageToFetch: number, 
    limitToFetch: number, 
    currentSearch: string, 
    currentStatus: string, 
    currentRepoId: string, 
    currentSort: SortConfig
  ) => {
    setPagination(prev => ({ ...prev, isLoading: true }));
    try {
      const response = await apiService.getDatasets({
        skip: (pageToFetch - 1) * limitToFetch,
        limit: limitToFetch,
        status: currentStatus === ALL_FILTER_VALUE ? undefined : currentStatus as DatasetStatusEnum,
        repository_id: currentRepoId === ALL_FILTER_VALUE ? undefined : currentRepoId,
        nameFilter: currentSearch,
        sortBy: currentSort.key,
        sortDir: currentSort.direction,
      });
      setDatasets(response.items || []);
      setPagination(prev => ({ 
        ...prev, 
        totalItems: response.total, 
        isLoading: false, 
        currentPage: pageToFetch, 
        itemsPerPage: limitToFetch 
      }));
    } catch (err) {
      handleApiError(err, "Failed to fetch datasets");
      setFetchError(err instanceof Error ? err.message : "Error fetching datasets.");
      setPagination(prev => ({ ...prev, isLoading: false }));
    }
  }, []);

  useEffect(() => {
    fetchRepositoriesForFilter();
  }, [fetchRepositoriesForFilter]);

  // Effect for filters or sort config changing: fetch page 1
  useEffect(() => {
    fetchDatasets(1, pagination.itemsPerPage, debouncedSearchQuery, statusFilter, repositoryFilter, sortConfig);
  }, [debouncedSearchQuery, statusFilter, repositoryFilter, sortConfig, fetchDatasets]); // Removed fetchDatasets from dependency array as it's stable

  // Effect for pagination changes (currentPage or itemsPerPage)
  useEffect(() => {
    fetchDatasets(pagination.currentPage, pagination.itemsPerPage, debouncedSearchQuery, statusFilter, repositoryFilter, sortConfig);
  }, [pagination.currentPage, pagination.itemsPerPage, debouncedSearchQuery, statusFilter, repositoryFilter, sortConfig, fetchDatasets]); // Added missing dependencies


  const handlePageChange = (newPage: number) => {
    const totalPages = Math.ceil(pagination.totalItems / pagination.itemsPerPage);
    if (newPage !== pagination.currentPage && newPage > 0 && newPage <= totalPages) {
        setPagination(prev => ({ ...prev, currentPage: newPage }));
    }
  };

  const handleItemsPerPageChange = (value: string) => {
    const newItemsPerPage = parseInt(value, 10);
    setPagination(prev => ({ ...prev, itemsPerPage: newItemsPerPage, currentPage: 1 }));
  };

  const handleSort = (key: SortableKeys) => {
    setSortConfig(prev => ({ key, direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc' }));
  };
  
  const handleDeleteDataset = async () => {
    if (!selectedDatasetForDelete) return;
    setIsDeletingDataset(true);
    try {
        await apiService.delete<void>(`/datasets/${selectedDatasetForDelete.id}`);
        toast({ title: "Dataset Deleted", description: `Dataset ${selectedDatasetForDelete.name} has been marked for deletion.`});
        setSelectedDatasetForDelete(null);
        fetchDatasets(
          pagination.currentPage,
          pagination.itemsPerPage,
          debouncedSearchQuery,
          statusFilter,
          repositoryFilter,
          sortConfig
        ); // Refresh current page
    } catch (err) {
        handleApiError(err, "Failed to delete dataset");
    } finally {
        setIsDeletingDataset(false);
    }
  };
  
  const repositoryOptions: SearchableSelectOption[] = [
    { value: ALL_FILTER_VALUE, label: "All Repositories" },
    ...repositories.map(repo => ({
      value: String(repo.id),
      label: `${repo.name} (ID: ${repo.id})`,
    }))
  ];

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
  
  const renderPaginationControls = () => {
    const totalPages = Math.ceil(pagination.totalItems / pagination.itemsPerPage);
    if (totalPages <= 1) return null;
    const pageNumbers = generatePagination(pagination.currentPage, totalPages);
    return (
      <Pagination className="mt-4">
        <PaginationContent>
          <PaginationItem><PaginationPrevious onClick={() => handlePageChange(pagination.currentPage - 1)} aria-disabled={pagination.currentPage <= 1 || pagination.isLoading} className={(pagination.currentPage <= 1 || pagination.isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
          {pageNumbers.map((page, index) =>
            typeof page === 'number' ? (
              <PaginationItem key={page}><PaginationLink onClick={() => handlePageChange(page)} isActive={pagination.currentPage === page} aria-disabled={pagination.isLoading}>{page}</PaginationLink></PaginationItem>
            ) : (
              <PaginationItem key={`ellipsis-${index}`}><PaginationEllipsis /></PaginationItem>
            )
          )}
          <PaginationItem><PaginationNext onClick={() => handlePageChange(pagination.currentPage + 1)} aria-disabled={pagination.currentPage >= totalPages || pagination.isLoading} className={(pagination.currentPage >= totalPages || pagination.isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
        </PaginationContent>
      </Pagination>
    );
  };

  const renderContent = () => {
    if (pagination.isLoading) {
      return Array.from({ length: 5 }).map((_, i) => <TableRow key={`skel-${i}`}><TableCell colSpan={6}><Skeleton className="h-8 w-full"/></TableCell></TableRow>);
    }
    if (fetchError) {
      return <TableRow><TableCell colSpan={6} className="text-center py-6 text-destructive">{fetchError}</TableCell></TableRow>;
    }
    if (datasets.length === 0) {
      return <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground">No datasets found matching your criteria.</TableCell></TableRow>;
    }
    return datasets.map((dataset) => (
      <TableRow key={dataset.id}>
        <TableCell className="font-medium max-w-[250px] truncate">
          <Link href={`/datasets/${dataset.id}`} className="hover:underline text-primary">{dataset.name}</Link>
        </TableCell>
        <TableCell className="text-xs">
          {dataset.repository ? (
              <Link href={`/repositories/${dataset.repository.id}`} className="hover:underline text-primary">{dataset.repository.name}</Link>
          ) : `Repo ID: ${dataset.repository_id}`}
        </TableCell>
        <TableCell>{renderStatusBadge(dataset)}</TableCell>
        <TableCell className="text-xs">{new Date(dataset.created_at).toLocaleDateString()}</TableCell>
        <TableCell className="text-xs max-w-[200px] truncate">{dataset.description || "N/A"}</TableCell>
        <TableCell className="text-right">
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button variant="ghost" size="sm"><MoreHorizontal /></Button></DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem asChild><Link href={`/datasets/${dataset.id}`}><Eye className="mr-2 h-4 w-4"/>View</Link></DropdownMenuItem>
              <DropdownMenuSeparator/>
              <DropdownMenuItem onClick={() => setSelectedDatasetForDelete(dataset)} className="text-destructive focus:text-destructive"><Trash2 className="mr-2 h-4 w-4"/>Delete</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>
      </TableRow>
    ));
  };
  
  return (
    <MainLayout>
      <PageContainer
        title={`Datasets (${pagination.totalItems})`}
        description="Browse and manage your datasets for model training."
        actions={<Button asChild><Link href="/datasets/create"><Plus className="mr-2 h-4 w-4" />Create Dataset</Link></Button>}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-6">
          <Input placeholder="Search by dataset name..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="md:col-span-1 lg:col-span-1"/>
          <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as any)}>
            <SelectTrigger><SelectValue placeholder="Filter by Status" /></SelectTrigger>
            <SelectContent><SelectItem value={ALL_FILTER_VALUE}>All Statuses</SelectItem>{availableDatasetStatuses.map(s => <SelectItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</SelectItem>)}</SelectContent>
          </Select>
          <SearchableSelect
            options={repositoryOptions}
            value={repositoryFilter}
            onValueChange={setRepositoryFilter}
            placeholder="Filter by Repository"
            searchPlaceholder="Search repositories..."
            emptyMessage="No repositories found."
            disabled={isLoadingRepositories}
            isLoading={isLoadingRepositories}
          />
          <div className="flex items-center gap-2 md:col-start-3 lg:col-start-4">
            <Label htmlFor="items-per-page-datasets" className="text-sm shrink-0">Show:</Label>
            <Select value={String(pagination.itemsPerPage)} onValueChange={handleItemsPerPageChange}>
              <SelectTrigger id="items-per-page-datasets" className="w-full md:w-[80px]"><SelectValue /></SelectTrigger>
              <SelectContent>{[10, 25, 50, 100].map(size => <SelectItem key={size} value={String(size)}>{size}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead><SortableHeader sortKey="name" sortConfig={sortConfig} onSort={handleSort}>Dataset Name</SortableHeader></TableHead>
                <TableHead><SortableHeader sortKey="repository_name" sortConfig={sortConfig} onSort={handleSort}>Repository</SortableHeader></TableHead>
                <TableHead><SortableHeader sortKey="status" sortConfig={sortConfig} onSort={handleSort}>Status</SortableHeader></TableHead>
                <TableHead><SortableHeader sortKey="created_at" sortConfig={sortConfig} onSort={handleSort}>Created</SortableHeader></TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>{renderContent()}</TableBody>
          </Table>
        </div>
        {renderPaginationControls()}

        <AlertDialog open={!!selectedDatasetForDelete} onOpenChange={(open) => !open && setSelectedDatasetForDelete(null)}>
            <AlertDialogContent>
              <AlertDialogHeader><AlertDialogTitle>Delete {selectedDatasetForDelete?.name}?</AlertDialogTitle><AlertDialogDescription>Are you sure? This action cannot be undone.</AlertDialogDescription></AlertDialogHeader>
              <AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction onClick={handleDeleteDataset} disabled={isDeletingDataset} className="bg-destructive hover:bg-destructive/90">{isDeletingDataset && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Delete</AlertDialogAction></AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>

      </PageContainer>
    </MainLayout>
  );
}