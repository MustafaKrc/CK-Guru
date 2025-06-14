// frontend/app/prediction-insights/page.tsx

"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useDebounce } from "@/hooks/useDebounce";

import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from "@/components/ui/table";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { MoreHorizontal, Eye, AlertCircle, Loader2, CheckCircle, RefreshCw, Wand2, ArrowUpDown } from "lucide-react";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/components/ui/pagination";
import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { SearchableSelect, SearchableSelectOption } from "@/components/ui/searchable-select";

import { apiService, GetInferenceJobsParams, handleApiError } from "@/lib/apiService";
import { InferenceJobRead, PaginatedInferenceJobRead, MLModelRead, Repository, PaginatedMLModelRead, PaginatedRepositoryRead } from "@/types/api";
import { JobStatusEnum } from "@/types/api/enums";
import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { generatePagination } from "@/lib/paginationUtils";

const ALL_FILTER_VALUE = "_all_";

type SortableKeys = 'job_id' | 'repository_name' | 'commit' | 'model_name' | 'status' | 'triggered_at' | 'prediction';
type SortConfig = {
  key: SortableKeys;
  direction: 'asc' | 'desc';
};

const SortableHeader: React.FC<{
  sortKey: SortableKeys;
  sortConfig: SortConfig;
  onSort: (key: SortableKeys) => void;
  children: React.ReactNode;
}> = ({ sortKey, sortConfig, onSort, children }) => (
    <Button variant="ghost" onClick={() => onSort(sortKey)} className="pl-1 pr-1 h-8">
        {children}
        <ArrowUpDown className={`ml-2 h-4 w-4 transition-opacity ${sortConfig.key === sortKey ? 'opacity-100' : 'opacity-30'}`} />
    </Button>
);

const PredictionInsightsPage = () => {
  const router = useRouter();
  const [jobs, setJobs] = useState<InferenceJobRead[]>([]);
  const [pagination, setPagination] = useState({ currentPage: 1, totalItems: 0, itemsPerPage: 10, isLoading: true });
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 500);
  const [statusFilter, setStatusFilter] = useState<string>(ALL_FILTER_VALUE);
  const [modelFilter, setModelFilter] = useState<string>(ALL_FILTER_VALUE);
  const [repositoryFilter, setRepositoryFilter] = useState<string>(ALL_FILTER_VALUE);
  const [sortConfig, setSortConfig] = useState<SortConfig>({ key: 'triggered_at', direction: 'desc' });

  const [models, setModels] = useState<SearchableSelectOption[]>([]);
  const [repositories, setRepositories] = useState<SearchableSelectOption[]>([]);
  const [isLoadingFilters, setIsLoadingFilters] = useState(true);

  const { taskStatuses } = useTaskStore();
  const availableJobStatuses = Object.values(JobStatusEnum);

  const fetchFilterOptions = useCallback(async () => {
    setIsLoadingFilters(true);
    try {
      const [modelsResponse, reposResponse] = await Promise.all([
        apiService.get<PaginatedMLModelRead>('/ml/models?limit=500'),
        apiService.get<PaginatedRepositoryRead>('/repositories?limit=500')
      ]);
      setModels(modelsResponse.items.map(m => ({ value: String(m.id), label: `${m.name} v${m.version}` })));
      setRepositories(reposResponse.items.map(r => ({ value: String(r.id), label: r.name })));
    } catch (err) {
      handleApiError(err, "Failed to load filter options");
    } finally {
      setIsLoadingFilters(false);
    }
  }, []);

  const fetchInferenceJobs = useCallback(async (page: number) => {
    setPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    try {
      const params: GetInferenceJobsParams = {
        skip: (page - 1) * pagination.itemsPerPage,
        limit: pagination.itemsPerPage,
        sortBy: sortConfig.key,
        sortDir: sortConfig.direction,
      };
      if (debouncedSearchQuery) params.nameFilter = debouncedSearchQuery;
      if (statusFilter !== ALL_FILTER_VALUE) params.status = statusFilter;
      if (repositoryFilter !== ALL_FILTER_VALUE) params.repository_id = parseInt(repositoryFilter);
      if (modelFilter !== ALL_FILTER_VALUE) params.model_id = parseInt(modelFilter);

      const response = await apiService.getInferenceJobs(params);
      setJobs(response.items);
      setPagination(prev => ({ ...prev, totalItems: response.total, isLoading: false }));
    } catch (err) {
      handleApiError(err, "Failed to fetch prediction insights");
      setFetchError(err instanceof Error ? err.message : "Could not load data.");
      setPagination(prev => ({ ...prev, isLoading: false }));
    }
  }, [pagination.itemsPerPage, sortConfig, debouncedSearchQuery, statusFilter, repositoryFilter, modelFilter]);

  useEffect(() => {
    fetchFilterOptions();
  }, [fetchFilterOptions]);

  useEffect(() => {
    fetchInferenceJobs(1);
  }, [debouncedSearchQuery, statusFilter, repositoryFilter, modelFilter, sortConfig, pagination.itemsPerPage]);

  useEffect(() => {
    fetchInferenceJobs(pagination.currentPage);
  }, [pagination.currentPage]);

  const handleSort = (key: SortableKeys) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const getStatusBadge = (taskStatus?: TaskStatusUpdatePayload, staticStatus?: JobStatusEnum) => {
    const currentStatusInfo = taskStatus || (staticStatus ? { status: staticStatus } as TaskStatusUpdatePayload : undefined);
    if (!currentStatusInfo || !currentStatusInfo.status) return <Badge variant="secondary">Unknown</Badge>;

    const { status, status_message, progress } = currentStatusInfo;
    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let text = status_message || status || "Unknown";

    switch (String(status).toUpperCase().replace("JOBSTATUSENUM", "").replace("TASKSTATUSENUM", "").replace(".", "")) {
      case JobStatusEnum.SUCCESS.toUpperCase(): badgeVariant = "default"; icon = <CheckCircle className="h-3 w-3 mr-1" />; text = "Success"; break;
      case JobStatusEnum.RUNNING.toUpperCase(): case JobStatusEnum.STARTED.toUpperCase():
        badgeVariant = "outline"; icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />; text = `${status_message || status} (${progress ?? 0}%)`; break;
      case JobStatusEnum.PENDING.toUpperCase():
        badgeVariant = "outline"; icon = <Loader2 className="h-3 w-3 mr-1 animate-spin" />; text = "Pending"; break;
      case JobStatusEnum.FAILED.toUpperCase():
        badgeVariant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1" />; text = `Failed`; break; // Full message shown in tooltip/details
      case JobStatusEnum.REVOKED.toUpperCase():
        badgeVariant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1" />; text = "Revoked"; break;
      default: text = String(status).toUpperCase();
    }
    return <Badge variant={badgeVariant} className="whitespace-nowrap text-xs px-1.5 py-0.5" title={status_message || String(status) || ''}>{icon}{text}</Badge>;
  };

  const renderPaginationControls = () => {
    const totalPages = Math.ceil(pagination.totalItems / pagination.itemsPerPage);
    if (totalPages <= 1) return null;
    const pageNumbers = generatePagination(pagination.currentPage, totalPages);
    return (
      <Pagination className="mt-4">
        <PaginationContent>
          <PaginationItem>
            {pagination.currentPage <= 1 || pagination.isLoading ? (
              <span className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:bg-accent hover:text-accent-foreground h-10 px-4 py-2 gap-1 pl-2.5 opacity-50 cursor-not-allowed">Previous</span>
            ) : (
              <PaginationPrevious onClick={() => setPagination(p => ({...p, currentPage: Math.max(1, p.currentPage - 1)}))} />
            )}
          </PaginationItem>
          {pageNumbers.map((page, index) =>
            typeof page === 'number' ?
              <PaginationItem key={page}><PaginationLink onClick={() => setPagination(p => ({...p, currentPage: page}))} isActive={pagination.currentPage === page}>{page}</PaginationLink></PaginationItem> :
              <PaginationItem key={`ellipsis-${index}`}><PaginationEllipsis /></PaginationItem>
          )}
          <PaginationItem>
            {pagination.currentPage >= totalPages || pagination.isLoading ? (
              <span className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:bg-accent hover:text-accent-foreground h-10 px-4 py-2 gap-1 pr-2.5 opacity-50 cursor-not-allowed">Next</span>
            ) : (
              <PaginationNext onClick={() => setPagination(p => ({...p, currentPage: Math.min(totalPages, p.currentPage + 1)}))} />
            )}
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    );
  };

  const formatDate = (dateString?: string) => dateString ? new Date(dateString).toLocaleString() : 'N/A';

  const renderTableContent = () => {
    if (pagination.isLoading && jobs.length === 0) {
      return Array.from({ length: 5 }).map((_, i) => (
        <TableRow key={`skel-${i}`}><TableCell colSpan={8}><Skeleton className="h-8 w-full" /></TableCell></TableRow>
      ));
    }
    if (fetchError) {
      return <TableRow><TableCell colSpan={8} className="text-center text-destructive py-6">{fetchError}</TableCell></TableRow>;
    }
    if (jobs.length === 0) {
      return <TableRow><TableCell colSpan={8} className="text-center py-8 text-muted-foreground">No predictions found matching your criteria.</TableCell></TableRow>;
    }
    return jobs.map(job => {
      const liveTask = getLatestTaskForEntity(taskStatuses, "InferenceJob", job.id);
      const prediction = job.prediction_result?.commit_prediction;
      const predictionProb = job.prediction_result?.max_bug_probability;

      return (
        <TableRow key={job.id}>
          <TableCell><Link href={`/prediction-insights/${job.id}`} className="font-mono text-xs text-primary hover:underline">{job.id}</Link></TableCell>
          <TableCell><Link href={`/repositories/${job.ml_model?.dataset?.repository?.id}`} className="font-mono text-xs text-primary hover:underline">{job.ml_model?.dataset?.repository?.name || 'N/A'}</Link></TableCell>
          <TableCell><Link href={`/repositories/${job.ml_model?.dataset?.repository?.id}/commits/${job.input_reference.commit_hash}`} className="font-mono text-xs text-primary hover:underline">{job.input_reference.commit_hash?.substring(0, 7) || 'N/A'}</Link></TableCell>
          <TableCell><Link href={`/models/${job.ml_model_id}`} className="font-mono text-xs text-primary hover:underline">{job.ml_model?.name || 'N/A'} (v{job.ml_model?.version || '?'})</Link></TableCell>
          <TableCell>{getStatusBadge(liveTask, job.status)}</TableCell>
          <TableCell className="text-xs">{formatDate(job.created_at)}</TableCell>
          <TableCell>
            {prediction === undefined ? <Badge variant="secondary">N/A</Badge> : (
              prediction === 1 ? <Badge variant="destructive">Defect</Badge> : <Badge className="bg-green-600">Clean</Badge>
            )}
            {predictionProb !== undefined && <p className="text-[10px] text-muted-foreground mt-1">Prob: {predictionProb.toFixed(3)}</p>}
          </TableCell>
        </TableRow>
      );
    });
  };

  return (
    <MainLayout>
      <PageContainer
        title="Prediction Insights"
        description="Review predictions and explanations from completed inference jobs."
        actions={<Button asChild><Link href="/jobs/inference"><Wand2 className="mr-2 h-4 w-4" />Run New Inference</Link></Button>}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
          <Input placeholder="Search commit hash..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="lg:col-span-2" />
          <SearchableSelect options={[{ value: ALL_FILTER_VALUE, label: "All Repositories" }, ...repositories]} value={repositoryFilter} onValueChange={setRepositoryFilter} placeholder="Filter by Repository..." isLoading={isLoadingFilters} />
          <SearchableSelect options={[{ value: ALL_FILTER_VALUE, label: "All Models" }, ...models]} value={modelFilter} onValueChange={setModelFilter} placeholder="Filter by Model..." isLoading={isLoadingFilters} />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_FILTER_VALUE}>All Statuses</SelectItem>
              {availableJobStatuses.map(s => <SelectItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</SelectItem>)}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-2 lg:col-start-5">
            <Label htmlFor="items-per-page" className="text-sm shrink-0">Show:</Label>
            <Select value={String(pagination.itemsPerPage)} onValueChange={(val) => setPagination(p => ({...p, itemsPerPage: parseInt(val), currentPage: 1}))}>
              <SelectTrigger id="items-per-page" className="w-full"><SelectValue /></SelectTrigger>
              <SelectContent>{[10, 25, 50].map(size => <SelectItem key={size} value={String(size)}>{size}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead><SortableHeader sortKey="job_id" sortConfig={sortConfig} onSort={handleSort}>Job ID</SortableHeader></TableHead>
                <TableHead><SortableHeader sortKey="repository_name" sortConfig={sortConfig} onSort={handleSort}>Repository</SortableHeader></TableHead>
                <TableHead><SortableHeader sortKey="commit" sortConfig={sortConfig} onSort={handleSort}>Commit</SortableHeader></TableHead>
                <TableHead><SortableHeader sortKey="model_name" sortConfig={sortConfig} onSort={handleSort}>Model Used</SortableHeader></TableHead>
                <TableHead><SortableHeader sortKey="status" sortConfig={sortConfig} onSort={handleSort}>Status</SortableHeader></TableHead>
                <TableHead><SortableHeader sortKey="triggered_at" sortConfig={sortConfig} onSort={handleSort}>Triggered At</SortableHeader></TableHead>
                <TableHead><SortableHeader sortKey="prediction" sortConfig={sortConfig} onSort={handleSort}>Prediction</SortableHeader></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>{renderTableContent()}</TableBody>
          </Table>
        </div>
        {renderPaginationControls()}
      </PageContainer>
    </MainLayout>
  );
};

export default PredictionInsightsPage;