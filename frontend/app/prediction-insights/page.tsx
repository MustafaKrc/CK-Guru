// frontend/app/prediction-insights/page.tsx
"use client";

import React, { useEffect, useState, useMemo, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { MoreHorizontal, Eye, Search, Filter, AlertCircle, Loader2, CheckCircle, RefreshCw, Wand2 } from "lucide-react";

import { apiService, getInferenceJobs, handleApiError } from "@/lib/apiService";
import { InferenceJobRead, PaginatedInferenceJobRead, MLModelRead, PaginatedMLModelRead, Repository, PaginatedRepositoryRead } from "@/types/api";
import { JobStatusEnum } from "@/types/api/enums";
import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/components/ui/pagination";
import { useToast } from "@/hooks/use-toast";

const ITEMS_PER_PAGE = 10;
const ALL_FILTER_VALUE = "_all_";

const PredictionInsightsPage = () => {
  const router = useRouter();
  const { toast } = useToast();

  const [inferenceJobs, setInferenceJobs] = useState<InferenceJobRead[]>([]);
  const [pagination, setPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<JobStatusEnum | typeof ALL_FILTER_VALUE>(ALL_FILTER_VALUE);
  const [modelFilter, setModelFilter] = useState<string>(ALL_FILTER_VALUE);
  const [repositoryFilter, setRepositoryFilter] = useState<string>(ALL_FILTER_VALUE); // New

  const [models, setModels] = useState<MLModelRead[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [repositories, setRepositories] = useState<Repository[]>([]); // New
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(false); // New
  
  const { taskStatuses } = useTaskStore();
  const availableJobStatuses = Object.values(JobStatusEnum);

  const fetchFilterData = useCallback(async () => {
    setIsLoadingModels(true);
    setIsLoadingRepositories(true);
    try {
      const [modelsResponse, reposResponse] = await Promise.all([
        apiService.get<PaginatedMLModelRead>(`/ml/models?limit=200`),
        apiService.get<PaginatedRepositoryRead>(`/repositories?limit=200`)
      ]);
      setModels(modelsResponse.items || []);
      setRepositories(reposResponse.items || []);
    } catch (err) {
      handleApiError(err, "Failed to load filter options");
    } finally {
      setIsLoadingModels(false);
      setIsLoadingRepositories(false);
    }
  }, []);

  const fetchPaginatedInferenceJobs = useCallback(async (page: number = 1) => {
    setPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    setFetchError(null);
    const skip = (page - 1) * ITEMS_PER_PAGE;

    const params: Record<string, string | number> = { skip, limit: ITEMS_PER_PAGE };
    if (statusFilter !== ALL_FILTER_VALUE) params.status = statusFilter;
    if (modelFilter !== ALL_FILTER_VALUE) params.model_id = parseInt(modelFilter);
    
    // Backend doesn't directly support repository_id filter on /ml/infer
    // If repositoryFilter is set, we might need to fetch models for that repo
    // and then filter inference jobs by those model_ids, or do it client-side for now.
    // For simplicity, if repo filter is active, we'll fetch all matching model/status and then client-filter.
    // This is not ideal for large datasets.
    
    // If a repository is selected, and we want to filter strictly by it:
    // We'd first need to get models for that repository, then use those model IDs to filter inference jobs.
    // This can be complex. For now, let's assume if repo filter is on, it's more for client-side guidance.
    // Or backend could be enhanced. Let's just pass model_id and status for now.

    try {
      const response = await getInferenceJobs(params as any); // Casting as `any` for now as GetInferenceJobsParams might be stricter
      setInferenceJobs(response.items || []);
      setPagination(prev => ({ ...prev, totalItems: response.total || 0, isLoading: false }));
    } catch (err) {
      handleApiError(err, "Failed to fetch inference jobs");
      setFetchError(err instanceof Error ? err.message : "Error fetching jobs.");
      setInferenceJobs([]);
      setPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, [statusFilter, modelFilter]); // repositoryFilter will be handled client-side for now

  useEffect(() => {
    fetchFilterData();
  }, [fetchFilterData]);

  useEffect(() => {
    fetchPaginatedInferenceJobs(1); // Fetch page 1 when filters change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, modelFilter]); // Exclude repositoryFilter for now from API refetch dependencies


  const handlePageChange = (newPage: number) => {
    if (newPage !== pagination.currentPage) {
      fetchPaginatedInferenceJobs(newPage);
    }
  };

  const getStatusBadge = (taskStatus?: TaskStatusUpdatePayload, staticStatus?: JobStatusEnum) => {
    const currentStatusInfo = taskStatus || (staticStatus ? { status: staticStatus } as TaskStatusUpdatePayload : undefined);
    if (!currentStatusInfo || !currentStatusInfo.status) return <Badge variant="secondary">Unknown</Badge>;

    const { status, status_message, progress } = currentStatusInfo;
    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let text = status_message || status || "Unknown";

    switch (String(status).toUpperCase()) {
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

  const filteredAndSearchedJobs = useMemo(() => {
    return inferenceJobs.filter((job) => {
      const query = searchQuery.toLowerCase();
      const matchesSearch =
        !query ||
        job.id.toString().includes(query) ||
        job.ml_model_id.toString().includes(query) ||
        (job.input_reference.commit_hash &&
          typeof job.input_reference.commit_hash === "string" &&
          job.input_reference.commit_hash.toLowerCase().includes(query)) ||
        (job.status && job.status.toLowerCase().includes(query));
      
      // Client-side repository filter (temporary until backend supports it well for inference jobs)
      const matchesRepo = repositoryFilter === ALL_FILTER_VALUE || 
                          (job.input_reference.repo_id && job.input_reference.repo_id.toString() === repositoryFilter);

      return matchesSearch && matchesRepo;
    });
  }, [searchQuery, inferenceJobs, repositoryFilter]);


  const renderPaginationControls = () => {
    // Pagination should be based on API results unless client-side filtering is very aggressive
    const totalItemsForPagination = pagination.totalItems;
    const totalPages = Math.ceil(totalItemsForPagination / ITEMS_PER_PAGE);

    if (totalPages <= 1) return null;

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

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return "N/A";
    try { return new Date(dateString).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'});
    } catch (e) { return "Invalid Date"; }
  };

  const renderContent = () => {
    if (pagination.isLoading && filteredAndSearchedJobs.length === 0) {
      return Array.from({ length: 5 }).map((_, index) => (
        <TableRow key={`skel-job-${index}`}>
          <TableCell><Skeleton className="h-5 w-16" /></TableCell>
          <TableCell><Skeleton className="h-5 w-32" /></TableCell>
          <TableCell><Skeleton className="h-5 w-24" /></TableCell>
          <TableCell><Skeleton className="h-5 w-20" /></TableCell>
          <TableCell><Skeleton className="h-5 w-20" /></TableCell>
          <TableCell><Skeleton className="h-5 w-28" /></TableCell>
          <TableCell className="text-right"><Skeleton className="h-8 w-8 rounded-full" /></TableCell>
        </TableRow>
      ));
    }
    if (fetchError) {
      return <TableRow><TableCell colSpan={7} className="text-center text-destructive py-4"><Alert variant="destructive" className="justify-center"><AlertCircle className="mr-2 h-5 w-5" /><AlertDescription>{fetchError}</AlertDescription></Alert><Button onClick={() => fetchPaginatedInferenceJobs(1)} variant="outline" size="sm" className="mt-2">Try Again</Button></TableCell></TableRow>;
    }
    if (!pagination.isLoading && filteredAndSearchedJobs.length === 0) {
      return <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground"><p>No inference jobs found matching your criteria.</p><Button size="sm" className="mt-2" asChild><Link href="/jobs/inference"><Wand2 className="mr-2 h-4 w-4" />Run New Inference</Link></Button></TableCell></TableRow>;
    }

    return filteredAndSearchedJobs.map((job) => {
      const liveTaskStatus = getLatestTaskForEntity(taskStatuses, "InferenceJob", job.id);
      const commitHashShort = typeof job.input_reference.commit_hash === 'string' ? job.input_reference.commit_hash.substring(0, 7) : "N/A";
      const modelUsed = models.find(m => m.id === job.ml_model_id);
      const repoUsed = repositories.find(r => r.id === job.input_reference.repo_id);

      return (
        <TableRow key={job.id}>
          <TableCell className="font-mono text-xs">{job.id}</TableCell>
          <TableCell className="text-xs">
            {repoUsed ? (
              <Link href={`/repositories/${repoUsed.id}`} className="hover:underline text-primary">
                {repoUsed.name}
              </Link>
            ) : `Repo ID: ${job.input_reference.repo_id || 'N/A'}`}
             <span className="block text-muted-foreground text-[10px] font-mono" title={String(job.input_reference.commit_hash)}>Commit: {commitHashShort}</span>
          </TableCell>
          <TableCell className="text-xs">
            {modelUsed ? (
              <Link href={`/models/${modelUsed.id}`} className="hover:underline text-primary">
                {modelUsed.name} (v{modelUsed.version})
              </Link>
            ) : `Model ID: ${job.ml_model_id}`}
          </TableCell>
          <TableCell>{getStatusBadge(liveTaskStatus, job.status)}</TableCell>
          <TableCell className="text-xs">{formatDate(job.created_at)}</TableCell>
          <TableCell className="text-xs">
            {job.prediction_result?.commit_prediction !== undefined ? 
              (job.prediction_result.commit_prediction === 1 ? <Badge variant="destructive">Defect</Badge> : <Badge className="bg-green-600 hover:bg-green-700">Clean</Badge>)
              : "N/A"}
             {job.prediction_result?.max_bug_probability !== undefined && <span className="block text-muted-foreground text-[10px]">Prob: {job.prediction_result.max_bug_probability.toFixed(3)}</span>}
          </TableCell>
          <TableCell className="text-right">
            <DropdownMenu>
              <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="h-7 w-7"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Actions</DropdownMenuLabel>
                <DropdownMenuItem asChild disabled={job.status !== JobStatusEnum.SUCCESS}>
                    <Link href={`/prediction-insights/${job.id}`}><Eye className="mr-2 h-4 w-4" />View Details</Link>
                </DropdownMenuItem>
                {/* Add other relevant actions if any */}
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
        title={`Prediction Insights (${pagination.isLoading && pagination.totalItems === 0 ? "..." : pagination.totalItems})`}
        description="Review predictions and explanations from completed inference jobs."
        actions={
          <Button asChild>
            <Link href="/jobs/inference"><Wand2 className="mr-2 h-4 w-4" />Run New Inference</Link>
          </Button>
        }
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="sm:col-span-2 md:col-span-1">
            <Label htmlFor="search" className="text-xs">Search (ID, Commit, Model ID)</Label>
            <Input id="search" placeholder="Enter search query..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="statusFilter" className="text-xs">Filter by Status</Label>
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as JobStatusEnum | typeof ALL_FILTER_VALUE)}>
              <SelectTrigger id="statusFilter"><SelectValue placeholder="All Statuses" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER_VALUE}>All Statuses</SelectItem>
                {availableJobStatuses.map(s => <SelectItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
           <div>
            <Label htmlFor="repositoryFilter" className="text-xs">Filter by Repository</Label>
            <Select value={repositoryFilter} onValueChange={setRepositoryFilter} disabled={isLoadingRepositories || repositories.length === 0}>
              <SelectTrigger id="repositoryFilter"><SelectValue placeholder={isLoadingRepositories ? "Loading..." : "All Repositories"} /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER_VALUE}>All Repositories</SelectItem>
                {repositories.map(repo => <SelectItem key={repo.id} value={repo.id.toString()}>{repo.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="modelFilter" className="text-xs">Filter by Model</Label>
            <Select value={modelFilter} onValueChange={setModelFilter} disabled={isLoadingModels || models.length === 0}>
              <SelectTrigger id="modelFilter"><SelectValue placeholder={isLoadingModels ? "Loading..." : "All Models"} /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER_VALUE}>All Models</SelectItem>
                {models.map(model => <SelectItem key={model.id} value={model.id.toString()}>{model.name} (v{model.version})</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Job ID</TableHead>
                <TableHead>Repository & Commit</TableHead>
                <TableHead>Model Used</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Triggered At</TableHead>
                <TableHead>Prediction</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>{renderContent()}</TableBody>
          </Table>
        </div>
        {renderPaginationControls()}
      </PageContainer>
    </MainLayout>
  );
};

export default PredictionInsightsPage;