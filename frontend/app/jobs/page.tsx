// frontend/app/jobs/page.tsx
"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis } from "@/components/ui/pagination";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { MoreHorizontal, RefreshCw, Eye, StopCircle, Play, Plus, Loader2, AlertCircle, CheckCircle, Layers, Puzzle, Wand2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

import { apiService, handleApiError } from "@/lib/apiService";
import { TrainingJobRead, PaginatedTrainingJobRead } from "@/types/api/training-job";
import { HPSearchJobRead, PaginatedHPSearchJobRead } from "@/types/api/hp-search-job";
import { InferenceJobRead, PaginatedInferenceJobRead } from "@/types/api/inference-job";
import { Repository } from "@/types/api/repository"; // For repository filter, if implemented
import { JobStatusEnum } from "@/types/api/enums";
import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const ITEMS_PER_PAGE_JOBS = 10;
const ALL_STATUSES_SELECT_VALUE = "__ALL_STATUSES__"; // Define a non-empty constant

type JobTypes = "training" | "hpSearch" | "inference";

export default function JobsPage() {
  const router = useRouter();
  const searchParamsHook = useSearchParams();
  const { toast } = useToast();

  const initialTab = (searchParamsHook.get('tab') as JobTypes) || "training";
  const [activeTab, setActiveTab] = useState<JobTypes>(initialTab);

  const [trainingJobs, setTrainingJobs] = useState<TrainingJobRead[]>([]);
  const [trainingJobsPagination, setTrainingJobsPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [trainingJobsError, setTrainingJobsError] = useState<string | null>(null);

  const [hpSearchJobs, setHpSearchJobs] = useState<HPSearchJobRead[]>([]);
  const [hpSearchJobsPagination, setHpSearchJobsPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [hpSearchJobsError, setHpSearchJobsError] = useState<string | null>(null);

  const [inferenceJobs, setInferenceJobs] = useState<InferenceJobRead[]>([]);
  const [inferenceJobsPagination, setInferenceJobsPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [inferenceJobsError, setInferenceJobsError] = useState<string | null>(null);
  
  // Filters
  const [statusFilter, setStatusFilter] = useState<JobStatusEnum | "">("");
  const [searchQuery, setSearchQuery] = useState("");
  // Repository filter state (optional, not fully implemented with backend calls yet)
  // const [repositoryFilter, setRepositoryFilter] = useState<string>("");
  // const [repositories, setRepositories] = useState<Repository[]>([]);
  // const [isLoadingRepositories, setIsLoadingRepositories] = useState(false);


  const { taskStatuses } = useTaskStore();

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return "N/A";
    try {
      return new Date(dateString).toLocaleDateString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
      });
    } catch (e) { return "Invalid Date"; }
  };

  const fetchTrainingJobs = useCallback(async (page: number, status?: JobStatusEnum | "", query?: string) => {
    setTrainingJobsPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    setTrainingJobsError(null);
    const params = new URLSearchParams({
      skip: ((page - 1) * ITEMS_PER_PAGE_JOBS).toString(),
      limit: ITEMS_PER_PAGE_JOBS.toString(),
    });
    if (status) params.append("status", status);
    if (query) params.append("q", query); // Assuming backend supports 'q' for search

    try {
      const response = await apiService.get<PaginatedTrainingJobRead>(`/ml/train?${params.toString()}`);
      setTrainingJobs(response.items || []);
      setTrainingJobsPagination(prev => ({ ...prev, totalItems: response.total || 0, isLoading: false }));
    } catch (err) {
      handleApiError(err, "Failed to fetch training jobs");
      setTrainingJobsError(err instanceof Error ? err.message : "Error fetching training jobs.");
      setTrainingJobsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, []);

  const fetchHpSearchJobs = useCallback(async (page: number, status?: JobStatusEnum | "", query?: string) => {
    setHpSearchJobsPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    setHpSearchJobsError(null);
    const params = new URLSearchParams({
      skip: ((page - 1) * ITEMS_PER_PAGE_JOBS).toString(),
      limit: ITEMS_PER_PAGE_JOBS.toString(),
    });
    if (status) params.append("status", status);
    if (query) params.append("study_name", query); // HP search might filter by study_name

    try {
      const response = await apiService.get<PaginatedHPSearchJobRead>(`/ml/search?${params.toString()}`);
      setHpSearchJobs(response.items || []);
      setHpSearchJobsPagination(prev => ({ ...prev, totalItems: response.total || 0, isLoading: false }));
    } catch (err) {
      handleApiError(err, "Failed to fetch HP search jobs");
      setHpSearchJobsError(err instanceof Error ? err.message : "Error fetching HP search jobs.");
      setHpSearchJobsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, []);
  
  const fetchInferenceJobs = useCallback(async (page: number, status?: JobStatusEnum | "", query?: string) => {
    setInferenceJobsPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    setInferenceJobsError(null);
    const params = new URLSearchParams({
      skip: ((page - 1) * ITEMS_PER_PAGE_JOBS).toString(),
      limit: ITEMS_PER_PAGE_JOBS.toString(),
    });
    if (status) params.append("status", status);
    // Inference jobs don't have a simple 'name' to search by 'q'.
    // Filtering for inference jobs might need specific criteria (e.g., by model_id, commit_hash partial).
    // For now, 'query' might not be directly applicable or would require backend changes.

    try {
      const response = await apiService.get<PaginatedInferenceJobRead>(`/ml/infer?${params.toString()}`);
      setInferenceJobs(response.items || []);
      setInferenceJobsPagination(prev => ({ ...prev, totalItems: response.total || 0, isLoading: false }));
    } catch (err) {
      handleApiError(err, "Failed to fetch inference jobs");
      setInferenceJobsError(err instanceof Error ? err.message : "Error fetching inference jobs.");
      setInferenceJobsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, []);

  // Effect to load data for the active tab or when filters change
  useEffect(() => {
    if (activeTab === "training") {
      fetchTrainingJobs(1, statusFilter, searchQuery);
    } else if (activeTab === "hpSearch") {
      fetchHpSearchJobs(1, statusFilter, searchQuery);
    } else if (activeTab === "inference") {
      fetchInferenceJobs(1, statusFilter, searchQuery);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, statusFilter, searchQuery]); // Intentionally not including fetch functions to avoid re-runs from their changes

  // Effects for pagination changes
  useEffect(() => {
    if (activeTab === "training") fetchTrainingJobs(trainingJobsPagination.currentPage, statusFilter, searchQuery);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trainingJobsPagination.currentPage, activeTab, statusFilter, searchQuery]);

  useEffect(() => {
    if (activeTab === "hpSearch") fetchHpSearchJobs(hpSearchJobsPagination.currentPage, statusFilter, searchQuery);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hpSearchJobsPagination.currentPage, activeTab, statusFilter, searchQuery]);

  useEffect(() => {
    if (activeTab === "inference") fetchInferenceJobs(inferenceJobsPagination.currentPage, statusFilter, searchQuery);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inferenceJobsPagination.currentPage, activeTab, statusFilter, searchQuery]);


  const handleTabChange = (newTab: JobTypes) => {
    setActiveTab(newTab);
    // Reset filters or keep them? For now, keep them. Reset pagination for the new tab.
    // if (newTab === "training") setTrainingJobsPagination(prev => ({...prev, currentPage: 1}));
    // else if (newTab === "hpSearch") setHpSearchJobsPagination(prev => ({...prev, currentPage: 1}));
    // else if (newTab === "inference") setInferenceJobsPagination(prev => ({...prev, currentPage: 1}));
    // The useEffect above handles refetching on activeTab change, which now calls with page 1.
  };
  
  const handleCancelJob = async (jobId: string | number, celeryTaskId?: string | null) => {
    if (!celeryTaskId) {
        toast({ title: "Cannot Cancel", description: "Job does not have a Celery Task ID to revoke.", variant: "destructive" });
        return;
    }
    toast({ title: "Attempting to Cancel Job", description: `Sending revocation request for task ${celeryTaskId}.` });
    try {
        await apiService.post(`/tasks/${celeryTaskId}/revoke`);
        toast({ title: "Revocation Sent", description: `Revocation request for task ${celeryTaskId} sent. Status will update.` });
        // Optionally, refetch the list for the current tab after a small delay
        setTimeout(() => {
            if (activeTab === "training") fetchTrainingJobs(trainingJobsPagination.currentPage, statusFilter, searchQuery);
            else if (activeTab === "hpSearch") fetchHpSearchJobs(hpSearchJobsPagination.currentPage, statusFilter, searchQuery);
            // Inference jobs might not be cancellable in the same way or might be too quick
        }, 2000);
    } catch (err) {
        handleApiError(err, "Failed to send revoke command");
    }
  };
  
  const renderStatusBadge = (jobId: number, jobTypeString: string, staticStatus?: string) => {
    const entityType = jobTypeString === 'training' ? 'TrainingJob' : jobTypeString === 'hpSearch' ? 'HPSearchJob' : 'InferenceJob';
    const taskJobType = jobTypeString === 'training' ? 'model_training' : jobTypeString === 'hpSearch' ? 'hp_search' : undefined; // Inference jobs might not have a specific 'job_type' for task updates

    const liveStatus = getLatestTaskForEntity(taskStatuses, entityType, jobId, taskJobType);
    
    const currentStatusToDisplay = liveStatus || (staticStatus ? { status: staticStatus } as TaskStatusUpdatePayload : undefined);
    if (!currentStatusToDisplay || !currentStatusToDisplay.status) return <Badge variant="secondary">Unknown</Badge>;

    const { status, status_message, progress } = currentStatusToDisplay;
    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let text = status_message || status || "Unknown";

    switch (String(status).toUpperCase()) {
      case JobStatusEnum.SUCCESS.toUpperCase():
      case "READY": // For dataset-like statuses if ever mixed
        badgeVariant = "default"; icon = <CheckCircle className="h-3 w-3 mr-1" />; text = `Success`; break;
      case JobStatusEnum.RUNNING.toUpperCase(): case JobStatusEnum.STARTED.toUpperCase(): case "GENERATING":
        badgeVariant = "outline"; icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />; text = `${status_message || status} (${progress ?? 0}%)`; break;
      case JobStatusEnum.PENDING.toUpperCase():
        badgeVariant = "outline"; icon = <Loader2 className="h-3 w-3 mr-1 animate-spin" />; text = "Pending"; break;
      case JobStatusEnum.FAILED.toUpperCase():
        badgeVariant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1" />; text = `Failed`; break; // Message shown separately
      case JobStatusEnum.REVOKED.toUpperCase():
        badgeVariant = "destructive"; icon = <StopCircle className="h-3 w-3 mr-1" />; text = "Revoked"; break;
      default: text = String(status).toUpperCase();
    }
    return <Badge variant={badgeVariant} className="whitespace-nowrap text-xs px-1.5 py-0.5" title={status_message || status || ''}>{icon}{text}</Badge>;
  };

  const renderPagination = (paginationState: {currentPage: number, totalItems: number, isLoading: boolean}, onPageChange: (page:number) => void) => {
    const totalPages = Math.ceil(paginationState.totalItems / ITEMS_PER_PAGE_JOBS);
    if (totalPages <= 1) return null;

    let pageNumbers: (number | string)[] = [];
    // Ensure at least 3 page numbers are shown if totalPages is small, otherwise apply ellipsis logic
    const MAX_VISIBLE_PAGES = 7; // Max items in pagination list (e.g., 1, ..., 4, 5, 6, ..., 10)
    const SIDE_PAGES = 1; // Number of pages to show on each side of current page
    const CURRENT_PAGE_WINDOW = SIDE_PAGES * 2 + 1; // Current page + side pages

    if (totalPages <= MAX_VISIBLE_PAGES) {
        pageNumbers = Array.from({ length: totalPages }, (_, i) => i + 1);
    } else {
        pageNumbers.push(1); // Always show first page

        const leftEllipsisNeeded = paginationState.currentPage > SIDE_PAGES + 2;
        const rightEllipsisNeeded = paginationState.currentPage < totalPages - (SIDE_PAGES + 1);

        if (leftEllipsisNeeded) {
            pageNumbers.push('...');
        }

        let startPage = Math.max(2, paginationState.currentPage - SIDE_PAGES);
        let endPage = Math.min(totalPages - 1, paginationState.currentPage + SIDE_PAGES);
        
        // Adjust window if current page is near the beginning
        if (paginationState.currentPage <= SIDE_PAGES + 1) {
            endPage = Math.min(totalPages -1, CURRENT_PAGE_WINDOW -1); // -1 because first page is already added
        }
        // Adjust window if current page is near the end
        if (paginationState.currentPage >= totalPages - SIDE_PAGES) {
            startPage = Math.max(2, totalPages - CURRENT_PAGE_WINDOW + 2); // +2 because last page is separate
        }


        for (let i = startPage; i <= endPage; i++) {
            pageNumbers.push(i);
        }

        if (rightEllipsisNeeded) {
             // Avoid duplicate ellipsis if endPage already leads to it
            if (endPage < totalPages - 1) {
                 pageNumbers.push('...');
            }
        }
        pageNumbers.push(totalPages); // Always show last page
        pageNumbers = [...new Set(pageNumbers)]; // Remove duplicates, though logic should prevent it
    }
    return (
        <Pagination className="mt-4">
          <PaginationContent>
            <PaginationItem><PaginationPrevious onClick={() => onPageChange(paginationState.currentPage - 1)} aria-disabled={paginationState.currentPage <= 1 || paginationState.isLoading} className={(paginationState.currentPage <= 1 || paginationState.isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
            {pageNumbers.map((page, index) => (
              <PaginationItem key={typeof page === 'number' ? `page-${page}` : `ellipsis-${index}`}>
                {typeof page === 'number' ? 
                  <PaginationLink onClick={() => onPageChange(page)} isActive={paginationState.currentPage === page} aria-disabled={paginationState.isLoading} className={paginationState.isLoading ? "pointer-events-none opacity-50" : ""}>{page}</PaginationLink> : 
                  <PaginationEllipsis />}
              </PaginationItem>
            ))}
            <PaginationItem><PaginationNext onClick={() => onPageChange(paginationState.currentPage + 1)} aria-disabled={paginationState.currentPage >= totalPages || paginationState.isLoading} className={(paginationState.currentPage >= totalPages || paginationState.isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
          </PaginationContent>
        </Pagination>
      );
  }

  const jobTableColumns = {
    training: [
        { header: "Job Name", accessor: (job: TrainingJobRead) => job.config.model_name, className: "font-medium break-all max-w-xs" },
        { header: "Dataset", accessor: (job: TrainingJobRead) => <Link href={`/datasets/${job.dataset_id}`} className="hover:underline text-primary text-xs">ID: {job.dataset_id}</Link>, className: undefined },
        { header: "Model Type", accessor: (job: TrainingJobRead) => <Badge variant="outline" className="text-xs">{job.config.model_type}</Badge>, className: undefined },
        { header: "Status", accessor: (job: TrainingJobRead) => renderStatusBadge(job.id, "training", job.status), className: undefined },
        { header: "Started", accessor: (job: TrainingJobRead) => formatDate(job.started_at), className: undefined },
        { header: "Completed", accessor: (job: TrainingJobRead) => formatDate(job.completed_at), className: undefined },
    ],
    hpSearch: [
        { header: "Study Name", accessor: (job: HPSearchJobRead) => job.optuna_study_name, className: "font-medium break-all max-w-xs" },
        { header: "Dataset", accessor: (job: HPSearchJobRead) => <Link href={`/datasets/${job.dataset_id}`} className="hover:underline text-primary text-xs">ID: {job.dataset_id}</Link>, className: undefined },
        { header: "Model Type", accessor: (job: HPSearchJobRead) => <Badge variant="outline" className="text-xs">{job.config.model_type}</Badge>, className: undefined },
        { header: "Status", accessor: (job: HPSearchJobRead) => renderStatusBadge(job.id, "hpSearch", job.status), className: undefined },
        { header: "Started", accessor: (job: HPSearchJobRead) => formatDate(job.started_at), className: undefined },
        { header: "Trials", accessor: (job: HPSearchJobRead) => job.best_trial_id !== null ? `${job.best_trial_id} / ${job.config.optuna_config.n_trials}` : `0 / ${job.config.optuna_config.n_trials}`, className: undefined },
    ],
    inference: [
        { header: "Commit Hash", accessor: (job: InferenceJobRead) => <span className="font-mono text-xs" title={job.input_reference?.commit_hash}>{String(job.input_reference?.commit_hash).substring(0,12) || "N/A"}...</span>, className: undefined },
        { header: "Model Used", accessor: (job: InferenceJobRead) => <Link href={`/models/${job.ml_model_id}`} className="hover:underline text-primary text-xs">ID: {job.ml_model_id}</Link>, className: undefined },
        { header: "Status", accessor: (job: InferenceJobRead) => renderStatusBadge(job.id, "inference", job.status), className: undefined },
        { header: "Triggered At", accessor: (job: InferenceJobRead) => formatDate(job.created_at), className: undefined },
        { header: "Result", accessor: (job: InferenceJobRead) => job.prediction_result?.commit_prediction !== undefined ? (job.prediction_result.commit_prediction === 1 ? <Badge variant="destructive">Defect</Badge> : <Badge className="bg-green-600 hover:bg-green-700">Clean</Badge>) : "N/A", className: undefined },
    ],
  };


  const renderJobsTable = (
    jobs: TrainingJobRead[] | HPSearchJobRead[] | InferenceJobRead[],
    jobTypeKey: JobTypes,
    isLoading: boolean,
    error: string | null,
    paginationState: {currentPage: number, totalItems: number, isLoading: boolean},
    handlePageChange: (page: number) => void
  ) => {
    const columns = jobTableColumns[jobTypeKey];
    const jobTypeSingular = jobTypeKey === "hpSearch" ? "hp_search" : jobTypeKey;

    if (isLoading && jobs.length === 0) {
      return Array.from({ length: 3 }).map((_, i) => (
        <TableRow key={`skel-${jobTypeKey}-${i}`}>
          {columns.map((col, j) => <TableCell key={j}><Skeleton className="h-5 w-full" /></TableCell>)}
          <TableCell className="text-right"><Skeleton className="h-8 w-8 rounded-full" /></TableCell>
        </TableRow>
      ));
    }
    if (error) {
      return <TableRow><TableCell colSpan={columns.length + 1} className="text-center text-destructive py-4">{error}</TableCell></TableRow>;
    }
    if (!isLoading && jobs.length === 0) {
      return <TableRow><TableCell colSpan={columns.length + 1} className="text-center py-8 text-muted-foreground">No {jobTypeKey.replace(/([A-Z])/g, ' $1').toLowerCase()} jobs found.</TableCell></TableRow>;
    }

    return (
      <>
        {jobs.map((job: any) => (
          <TableRow key={job.id}>
            {columns.map(col => <TableCell key={col.header} className={col.className || "text-xs"}>{col.accessor(job)}</TableCell>)}
            <TableCell className="text-right">
              <DropdownMenu>
                <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="h-7 w-7"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>Actions</DropdownMenuLabel>
                  {jobTypeKey !== 'inference' ? (
                    <DropdownMenuItem asChild>
                      <Link href={`/jobs/${job.id}?type=${jobTypeSingular}`}>
                        <Eye className="mr-2 h-4 w-4" /> View Details
                      </Link>
                    </DropdownMenuItem>
                  ) : (
                     <DropdownMenuItem asChild disabled={job.status !== JobStatusEnum.SUCCESS}>
                      <Link href={`/prediction-insights/${job.id}`}>
                        <Eye className="mr-2 h-4 w-4" /> View Insights
                      </Link>
                    </DropdownMenuItem>
                  )}
                  {(job.status === JobStatusEnum.RUNNING || job.status === JobStatusEnum.PENDING) && job.celery_task_id && (
                    <DropdownMenuItem onClick={() => handleCancelJob(job.id, job.celery_task_id)}><StopCircle className="mr-2 h-4 w-4" />Cancel Job</DropdownMenuItem>
                  )}
                  {jobTypeKey === 'training' && job.ml_model_id && job.status === JobStatusEnum.SUCCESS && (
                    <DropdownMenuItem asChild><Link href={`/models/${job.ml_model_id}`}><Puzzle className="mr-2 h-4 w-4" />View Model</Link></DropdownMenuItem>
                  )}
                   {jobTypeKey === 'hpSearch' && job.best_ml_model_id && job.status === JobStatusEnum.SUCCESS && (
                    <DropdownMenuItem asChild><Link href={`/models/${job.best_ml_model_id}`}><Puzzle className="mr-2 h-4 w-4" />View Best Model</Link></DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
        ))}
      </>
    );
  };


  return (
    <MainLayout>
      <PageContainer
        title="ML Jobs Dashboard"
        description="Monitor and manage your model training, hyperparameter searches, and inference tasks."
        actions={
          <div className="flex space-x-2">
            <Button variant="outline" asChild><Link href="/jobs/train"><Plus className="mr-2 h-4 w-4"/>New Training</Link></Button>
            <Button variant="outline" asChild><Link href="/jobs/hp-search"><Plus className="mr-2 h-4 w-4"/>New HP Search</Link></Button>
            <Button asChild><Link href="/jobs/inference"><Play className="mr-2 h-4 w-4" />Run Inference</Link></Button>
          </div>
        }
      >
        <div className="flex flex-col md:flex-row gap-4 mb-6">
          <div className="w-full md:flex-grow">
            <Label htmlFor="search">Search Jobs (by name/study name)</Label>
            <Input id="search" placeholder="Enter search query..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
          </div>
          <div className="w-full md:w-auto">
            <Label htmlFor="status">Filter by Status</Label>
            <Select
              value={statusFilter === "" ? ALL_STATUSES_SELECT_VALUE : statusFilter}
              onValueChange={(value) => setStatusFilter(value === ALL_STATUSES_SELECT_VALUE ? "" : value as JobStatusEnum)}
            >
              <SelectTrigger id="status"><SelectValue placeholder="All Statuses" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_STATUSES_SELECT_VALUE}>All Statuses</SelectItem>
                {Object.values(JobStatusEnum).map(s => <SelectItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={(value) => handleTabChange(value as JobTypes)} className="space-y-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="training">Training Jobs ({trainingJobsPagination.isLoading ? <Loader2 className="h-3 w-3 animate-spin"/> : trainingJobsPagination.totalItems})</TabsTrigger>
            <TabsTrigger value="hpSearch">HP Search ({hpSearchJobsPagination.isLoading ? <Loader2 className="h-3 w-3 animate-spin"/> : hpSearchJobsPagination.totalItems})</TabsTrigger>
            <TabsTrigger value="inference">Inference ({inferenceJobsPagination.isLoading ? <Loader2 className="h-3 w-3 animate-spin"/> : inferenceJobsPagination.totalItems})</TabsTrigger>
          </TabsList>

          <TabsContent value="training">
            <Card>
              <CardHeader><CardTitle>Training Jobs</CardTitle></CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader><TableRow>{jobTableColumns.training.map(col => <TableHead key={col.header}>{col.header}</TableHead>)}<TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                    <TableBody>{renderJobsTable(trainingJobs, "training", trainingJobsPagination.isLoading, trainingJobsError, trainingJobsPagination, (page) => setTrainingJobsPagination(p => ({...p, currentPage: page})))}</TableBody>
                  </Table>
                </div>
                {renderPagination(trainingJobsPagination, (page) => setTrainingJobsPagination(p => ({...p, currentPage: page})))}
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="hpSearch">
             <Card>
              <CardHeader><CardTitle>Hyperparameter Search Jobs</CardTitle></CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader><TableRow>{jobTableColumns.hpSearch.map(col => <TableHead key={col.header}>{col.header}</TableHead>)}<TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                    <TableBody>{renderJobsTable(hpSearchJobs, "hpSearch", hpSearchJobsPagination.isLoading, hpSearchJobsError, hpSearchJobsPagination, (page) => setHpSearchJobsPagination(p => ({...p, currentPage: page})))}</TableBody>
                  </Table>
                </div>
                {renderPagination(hpSearchJobsPagination, (page) => setHpSearchJobsPagination(p => ({...p, currentPage: page})))}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="inference">
             <Card>
              <CardHeader><CardTitle>Inference Jobs</CardTitle></CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader><TableRow>{jobTableColumns.inference.map(col => <TableHead key={col.header}>{col.header}</TableHead>)}<TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                    <TableBody>{renderJobsTable(inferenceJobs, "inference", inferenceJobsPagination.isLoading, inferenceJobsError, inferenceJobsPagination, (page) => setInferenceJobsPagination(p => ({...p, currentPage: page})))}</TableBody>
                  </Table>
                </div>
                {renderPagination(inferenceJobsPagination, (page) => setInferenceJobsPagination(p => ({...p, currentPage: page})))}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </PageContainer>
    </MainLayout>
  );
}