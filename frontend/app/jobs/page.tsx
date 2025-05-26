// frontend/app/jobs/page.tsx
"use client";

import React, { useState, useEffect, useCallback, useMemo, Suspense } from "react";  
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
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";

import { MoreHorizontal, RefreshCw, Eye, StopCircle, Play, Plus, Loader2, AlertCircle, CheckCircle, Puzzle, Layers, FileText, Wand2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

import { apiService, handleApiError } from "@/lib/apiService";
import { TrainingJobRead, PaginatedTrainingJobRead } from "@/types/api/training-job";
import { HPSearchJobRead, PaginatedHPSearchJobRead } from "@/types/api/hp-search-job";
import { InferenceJobRead, PaginatedInferenceJobRead } from "@/types/api/inference-job";
import { JobStatusEnum } from "@/types/api/enums";
import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const ITEMS_PER_PAGE = 10;
const ALL_FILTER_VALUE = "_all_"; // For status filter "All" option

type JobTypeKey = "training" | "hpSearch" | "inference";

interface JobPaginationState {
  currentPage: number;
  totalItems: number;
  isLoading: boolean;
}

function JobsPageContent() {  
  const router = useRouter();
  const searchParamsHook = useSearchParams();
  const { toast } = useToast();

  const initialTab = (searchParamsHook.get('tab') as JobTypeKey) || "training";
  const [activeTab, setActiveTab] = useState<JobTypeKey>(initialTab);

  const [trainingJobs, setTrainingJobs] = useState<TrainingJobRead[]>([]);
  const [trainingJobsPagination, setTrainingJobsPagination] = useState<JobPaginationState>({ currentPage: 1, totalItems: 0, isLoading: true });
  const [trainingJobsError, setTrainingJobsError] = useState<string | null>(null);

  const [hpSearchJobs, setHpSearchJobs] = useState<HPSearchJobRead[]>([]);
  const [hpSearchJobsPagination, setHpSearchJobsPagination] = useState<JobPaginationState>({ currentPage: 1, totalItems: 0, isLoading: true });
  const [hpSearchJobsError, setHpSearchJobsError] = useState<string | null>(null);

  const [inferenceJobs, setInferenceJobs] = useState<InferenceJobRead[]>([]);
  const [inferenceJobsPagination, setInferenceJobsPagination] = useState<JobPaginationState>({ currentPage: 1, totalItems: 0, isLoading: true });
  const [inferenceJobsError, setInferenceJobsError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<JobStatusEnum | typeof ALL_FILTER_VALUE>(ALL_FILTER_VALUE);
  const [searchQuery, setSearchQuery] = useState(""); // Backend needs to support 'q' for name/study search

  const { taskStatuses } = useTaskStore();
  const availableJobStatuses = Object.values(JobStatusEnum);
  
  const [jobToCancel, setJobToCancel] = useState<{id: string | number, celeryTaskId?: string | null, name: string} | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);


  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return "N/A";
    try { return new Date(dateString).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'});
    } catch (e) { return "Invalid Date"; }
  };

  const fetchTrainingJobs = useCallback(async (page: number) => {
    setTrainingJobsPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    setTrainingJobsError(null);
    const params = new URLSearchParams({ skip: ((page - 1) * ITEMS_PER_PAGE).toString(), limit: ITEMS_PER_PAGE.toString() });
    if (statusFilter && statusFilter !== ALL_FILTER_VALUE) params.append("status", statusFilter);
    if (searchQuery) params.append("q", searchQuery); // Assuming backend 'q' searches relevant name fields

    try {
      const response = await apiService.get<PaginatedTrainingJobRead>(`/ml/train?${params.toString()}`);
      setTrainingJobs(response.items || []);
      setTrainingJobsPagination(prev => ({ ...prev, totalItems: response.total || 0, isLoading: false }));
    } catch (err) {
      handleApiError(err, "Failed to fetch training jobs");
      setTrainingJobsError(err instanceof Error ? err.message : "Error.");
      setTrainingJobsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, [statusFilter, searchQuery]);

  const fetchHpSearchJobs = useCallback(async (page: number) => {
    setHpSearchJobsPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    setHpSearchJobsError(null);
    const params = new URLSearchParams({ skip: ((page - 1) * ITEMS_PER_PAGE).toString(), limit: ITEMS_PER_PAGE.toString() });
    if (statusFilter && statusFilter !== ALL_FILTER_VALUE) params.append("status", statusFilter);
    if (searchQuery) params.append("study_name", searchQuery); // HP search uses 'study_name' for search

    try {
      const response = await apiService.get<PaginatedHPSearchJobRead>(`/ml/search?${params.toString()}`);
      setHpSearchJobs(response.items || []);
      setHpSearchJobsPagination(prev => ({ ...prev, totalItems: response.total || 0, isLoading: false }));
    } catch (err) {
      handleApiError(err, "Failed to fetch HP search jobs");
      setHpSearchJobsError(err instanceof Error ? err.message : "Error.");
      setHpSearchJobsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, [statusFilter, searchQuery]);

  const fetchInferenceJobs = useCallback(async (page: number) => {
    setInferenceJobsPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    setInferenceJobsError(null);
    const params = new URLSearchParams({ skip: ((page - 1) * ITEMS_PER_PAGE).toString(), limit: ITEMS_PER_PAGE.toString() });
    if (statusFilter && statusFilter !== ALL_FILTER_VALUE) params.append("status", statusFilter);
    // Note: Search query for inference jobs is not directly supported by backend via 'q'. 
    // Client-side filtering would be needed if search is applied to this tab, or backend enhancement.

    try {
      const response = await apiService.get<PaginatedInferenceJobRead>(`/ml/infer?${params.toString()}`);
      setInferenceJobs(response.items || []);
      setInferenceJobsPagination(prev => ({ ...prev, totalItems: response.total || 0, isLoading: false }));
    } catch (err) {
      handleApiError(err, "Failed to fetch inference jobs");
      setInferenceJobsError(err instanceof Error ? err.message : "Error.");
      setInferenceJobsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, [statusFilter]);


  useEffect(() => {
    if (activeTab === "training") fetchTrainingJobs(1);
    else if (activeTab === "hpSearch") fetchHpSearchJobs(1);
    else if (activeTab === "inference") fetchInferenceJobs(1);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, statusFilter, searchQuery]); // Refetch on tab or filter change

  const handlePageChange = (jobType: JobTypeKey, newPage: number) => {
    if (jobType === "training" && newPage !== trainingJobsPagination.currentPage) fetchTrainingJobs(newPage);
    else if (jobType === "hpSearch" && newPage !== hpSearchJobsPagination.currentPage) fetchHpSearchJobs(newPage);
    else if (jobType === "inference" && newPage !== inferenceJobsPagination.currentPage) fetchInferenceJobs(newPage);
  };
  
  const confirmCancelJob = (job: {id: string | number, celeryTaskId?: string | null, name: string}) => {
    if (!job.celeryTaskId) {
        toast({ title: "Cannot Cancel", description: "This job does not have an active task ID to revoke.", variant: "destructive"});
        return;
    }
    setJobToCancel(job);
  };

  const executeCancelJob = async () => {
    if (!jobToCancel || !jobToCancel.celeryTaskId) return;
    setIsCancelling(true);
    try {
      await apiService.post(`/tasks/${jobToCancel.celeryTaskId}/revoke`);
      toast({ title: "Revocation Sent", description: `Attempting to revoke job: ${jobToCancel.name}.`});
      setJobToCancel(null);
      // Refresh list after a short delay for status to update
      setTimeout(() => {
        if (activeTab === "training") fetchTrainingJobs(trainingJobsPagination.currentPage);
        else if (activeTab === "hpSearch") fetchHpSearchJobs(hpSearchJobsPagination.currentPage);
        // Inference jobs typically aren't long-running in a way that needs cancellation via this UI.
      }, 2500);
    } catch (err) {
      handleApiError(err, "Failed to send revoke command");
    } finally {
      setIsCancelling(false);
    }
  };


  const renderStatusBadge = (jobId: number, jobTypeKey: JobTypeKey, staticStatusDb?: JobStatusEnum | string) => {
    const entityType = jobTypeKey === "training" ? "TrainingJob" : jobTypeKey === "hpSearch" ? "HPSearchJob" : "InferenceJob";
    const taskJobType = jobTypeKey === "training" ? "model_training" : jobTypeKey === "hpSearch" ? "hp_search" : undefined;
    const liveStatus = getLatestTaskForEntity(taskStatuses, entityType, jobId, taskJobType);
    
    const currentDisplayStatus = liveStatus || (staticStatusDb ? { status: staticStatusDb } as TaskStatusUpdatePayload : undefined);
    if (!currentDisplayStatus || !currentDisplayStatus.status) return <Badge variant="secondary" className="text-xs">Unknown</Badge>;

    const { status, status_message, progress } = currentDisplayStatus;
    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let text = status_message || String(status) || "Unknown";

    switch (String(status).toUpperCase()) {
      case JobStatusEnum.SUCCESS.toUpperCase(): badgeVariant = "default"; icon = <CheckCircle className="h-3 w-3 mr-1"/>; text = `Success`; break;
      case JobStatusEnum.RUNNING.toUpperCase(): case JobStatusEnum.STARTED.toUpperCase():
        badgeVariant = "outline"; icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin"/>; text = `${status_message || status} (${progress ?? 0}%)`; break;
      case JobStatusEnum.PENDING.toUpperCase():
        badgeVariant = "outline"; icon = <Loader2 className="h-3 w-3 mr-1 animate-spin"/>; text = "Pending"; break;
      case JobStatusEnum.FAILED.toUpperCase():
        badgeVariant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1"/>; text = `Failed`; break;
      case JobStatusEnum.REVOKED.toUpperCase():
        badgeVariant = "destructive"; icon = <StopCircle className="h-3 w-3 mr-1"/>; text = "Revoked"; break;
      default: text = String(status).toUpperCase();
    }
    return <Badge variant={badgeVariant} className="whitespace-nowrap text-xs px-1.5 py-0.5" title={status_message || String(status) || ''}>{icon}{text}</Badge>;
  };

  const renderPagination = (paginationState: JobPaginationState, jobType: JobTypeKey) => {
    const totalPages = Math.ceil(paginationState.totalItems / ITEMS_PER_PAGE);
    if (totalPages <= 1) return null;
    let pageNumbers: (number | string)[] = [];
    if (totalPages <= 7) { pageNumbers = Array.from({ length: totalPages }, (_, i) => i + 1); } 
    else { /* ... (ellipsis logic as before) ... */ 
        pageNumbers.push(1);
        if (paginationState.currentPage > 3) pageNumbers.push('...');
        if (paginationState.currentPage > 2) pageNumbers.push(paginationState.currentPage - 1);
        if (paginationState.currentPage > 1 && paginationState.currentPage < totalPages) pageNumbers.push(paginationState.currentPage);
        if (paginationState.currentPage < totalPages -1) pageNumbers.push(paginationState.currentPage + 1);
        if (paginationState.currentPage < totalPages - 2) pageNumbers.push('...');
        pageNumbers.push(totalPages);
        pageNumbers = [...new Set(pageNumbers)];
    }
    return (
        <Pagination className="mt-4">
          <PaginationContent>
            <PaginationItem><PaginationPrevious onClick={() => handlePageChange(jobType, paginationState.currentPage - 1)} aria-disabled={paginationState.currentPage <= 1 || paginationState.isLoading} className={(paginationState.currentPage <= 1 || paginationState.isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
            {pageNumbers.map((page, index) => ( <PaginationItem key={typeof page === 'number' ? `page-${page}` : `ellipsis-${index}`}> {typeof page === 'number' ? <PaginationLink onClick={() => handlePageChange(jobType, page)} isActive={paginationState.currentPage === page} aria-disabled={paginationState.isLoading} className={paginationState.isLoading ? "pointer-events-none opacity-50" : ""}>{page}</PaginationLink> : <PaginationEllipsis />} </PaginationItem> ))}
            <PaginationItem><PaginationNext onClick={() => handlePageChange(jobType, paginationState.currentPage + 1)} aria-disabled={paginationState.currentPage >= totalPages || paginationState.isLoading} className={(paginationState.currentPage >= totalPages || paginationState.isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
          </PaginationContent>
        </Pagination>
      );
  };

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
  
  // Generic Table Renderer
  const renderJobTableContent = (
    jobs: any[], 
    jobTypeKey: JobTypeKey, 
    isLoading: boolean, 
    error: string | null,
    columns: { header: string; accessor: (job: any) => React.ReactNode; className?: string }[]
  ) => {
    if (isLoading && jobs.length === 0) {
      return Array.from({ length: 3 }).map((_, i) => (
        <TableRow key={`skel-${jobTypeKey}-${i}`}>
          {columns.map((_, j) => <TableCell key={j}><Skeleton className="h-5 w-full" /></TableCell>)}
          <TableCell className="text-right"><Skeleton className="h-7 w-7 rounded-md" /></TableCell>
        </TableRow>
      ));
    }
    if (error) return <TableRow><TableCell colSpan={columns.length + 1} className="text-center text-destructive py-4"><Alert variant="destructive" className="justify-center"><AlertCircle className="mr-2 h-5 w-5" /><AlertDescription>{error}</AlertDescription></Alert></TableCell></TableRow>;
    if (!isLoading && jobs.length === 0) return <TableRow><TableCell colSpan={columns.length + 1} className="text-center py-8 text-muted-foreground">No {jobTypeKey.replace(/([A-Z])/g, ' $1').toLowerCase()} jobs found.</TableCell></TableRow>;

    return jobs.map((job: any) => (
      <TableRow key={`${jobTypeKey}-${job.id}`}>
        {columns.map(col => <TableCell key={col.header} className={`text-xs ${col.className || ""}`}>{col.accessor(job)}</TableCell>)}
        <TableCell className="text-right">
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="h-7 w-7"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Actions</DropdownMenuLabel>
              {jobTypeKey !== 'inference' ? (
                <DropdownMenuItem asChild><Link href={`/jobs/${job.id}?type=${jobTypeKey === "hpSearch" ? "hp_search" : jobTypeKey}`}><Eye className="mr-2 h-4 w-4" /> View Details</Link></DropdownMenuItem>
              ) : (
                <DropdownMenuItem asChild disabled={job.status !== JobStatusEnum.SUCCESS}><Link href={`/prediction-insights/${job.id}`}><Eye className="mr-2 h-4 w-4" /> View Insights</Link></DropdownMenuItem>
              )}
              {(job.status === JobStatusEnum.RUNNING || job.status === JobStatusEnum.PENDING) && job.celery_task_id && (
                <DropdownMenuItem onClick={() => confirmCancelJob({id: job.id, celeryTaskId: job.celery_task_id, name: job.config?.model_name || job.optuna_study_name || `Inference ${job.id}` })}>
                    <StopCircle className="mr-2 h-4 w-4 text-destructive" />Cancel Job
                </DropdownMenuItem>
              )}
              {jobTypeKey === 'training' && job.ml_model_id && job.status === JobStatusEnum.SUCCESS && (
                <DropdownMenuItem asChild><Link href={`/models/${job.ml_model_id}`}><Puzzle className="mr-2 h-4 w-4" />View Resulting Model</Link></DropdownMenuItem>
              )}
              {jobTypeKey === 'hpSearch' && job.best_ml_model_id && job.status === JobStatusEnum.SUCCESS && (
                <DropdownMenuItem asChild><Link href={`/models/${job.best_ml_model_id}`}><Puzzle className="mr-2 h-4 w-4" />View Best Model</Link></DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>
      </TableRow>
    ));
  };


  return (
    <MainLayout>
      <PageContainer
        title="ML Jobs Dashboard"
        description="Monitor and manage your model training, hyperparameter searches, and inference tasks."
        actions={ <div className="flex space-x-2"> <Button variant="outline" asChild><Link href="/jobs/train"><Plus className="mr-2 h-4 w-4"/>New Training</Link></Button> <Button variant="outline" asChild><Link href="/jobs/hp-search"><Plus className="mr-2 h-4 w-4"/>New HP Search</Link></Button> <Button asChild><Link href="/jobs/inference"><Play className="mr-2 h-4 w-4" />Run Inference</Link></Button> </div> }
      >
        <div className="flex flex-col md:flex-row gap-4 mb-6">
          <div className="w-full md:flex-grow">
            <Label htmlFor="search">Search (by Name / Study Name)</Label>
            <Input id="search" placeholder="Enter search query..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
          </div>
          <div className="w-full md:w-auto">
            <Label htmlFor="status">Filter by Status</Label>
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as JobStatusEnum | typeof ALL_FILTER_VALUE)}>
              <SelectTrigger id="status"><SelectValue placeholder="All Statuses" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER_VALUE}>All Statuses</SelectItem>
                {availableJobStatuses.map(s => <SelectItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as JobTypeKey)} className="space-y-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="training">Training ({trainingJobsPagination.isLoading ? <Loader2 className="h-3 w-3 animate-spin"/> : trainingJobsPagination.totalItems})</TabsTrigger>
            <TabsTrigger value="hpSearch">HP Search ({hpSearchJobsPagination.isLoading ? <Loader2 className="h-3 w-3 animate-spin"/> : hpSearchJobsPagination.totalItems})</TabsTrigger>
            <TabsTrigger value="inference">Inference ({inferenceJobsPagination.isLoading ? <Loader2 className="h-3 w-3 animate-spin"/> : inferenceJobsPagination.totalItems})</TabsTrigger>
          </TabsList>

          <TabsContent value="training">
            <Card><CardHeader><CardTitle>Training Jobs</CardTitle></CardHeader><CardContent>
                <div className="rounded-md border">
                    <Table><TableHeader><TableRow>{jobTableColumns.training.map(col => <TableHead key={col.header}>{col.header}</TableHead>)}<TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                    <TableBody>{renderJobTableContent(trainingJobs, "training", trainingJobsPagination.isLoading, trainingJobsError, jobTableColumns.training)}</TableBody></Table>
                </div>{renderPagination(trainingJobsPagination, "training")} </CardContent></Card>
          </TabsContent>
          
          <TabsContent value="hpSearch">
             <Card><CardHeader><CardTitle>Hyperparameter Search Jobs</CardTitle></CardHeader><CardContent>
                 <div className="rounded-md border">
                    <Table><TableHeader><TableRow>{jobTableColumns.hpSearch.map(col => <TableHead key={col.header}>{col.header}</TableHead>)}<TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                    <TableBody>{renderJobTableContent(hpSearchJobs, "hpSearch", hpSearchJobsPagination.isLoading, hpSearchJobsError, jobTableColumns.hpSearch)}</TableBody></Table>
                 </div>{renderPagination(hpSearchJobsPagination, "hpSearch")}</CardContent></Card>
          </TabsContent>

          <TabsContent value="inference">
             <Card><CardHeader><CardTitle>Inference Jobs</CardTitle></CardHeader><CardContent>
                 <div className="rounded-md border">
                     <Table><TableHeader><TableRow>{jobTableColumns.inference.map(col => <TableHead key={col.header}>{col.header}</TableHead>)}<TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                    <TableBody>{renderJobTableContent(inferenceJobs, "inference", inferenceJobsPagination.isLoading, inferenceJobsError, jobTableColumns.inference)}</TableBody></Table>
                 </div>{renderPagination(inferenceJobsPagination, "inference")}</CardContent></Card>
          </TabsContent>
        </Tabs>
        
        <AlertDialog open={!!jobToCancel} onOpenChange={(open) => !open && setJobToCancel(null)}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>Confirm Cancel Job</AlertDialogTitle>
                    <AlertDialogDescription>
                        Are you sure you want to attempt to cancel job: "{jobToCancel?.name}" (Task ID: {jobToCancel?.celeryTaskId})? 
                        This action may not be immediately effective if the task is already in a non-interruptible state.
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel onClick={() => setJobToCancel(null)} disabled={isCancelling}>Back</AlertDialogCancel>
                    <AlertDialogAction onClick={executeCancelJob} className="bg-destructive hover:bg-destructive/90" disabled={isCancelling}>
                        {isCancelling ? <><Loader2 className="mr-2 h-4 w-4 animate-spin"/>Cancelling...</> : "Yes, Cancel Job"}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>

      </PageContainer>
    </MainLayout>
  );
}

export default function JobsPage() { // New wrapper component
  return (
    <Suspense fallback={<div>Loading page data...</div>}>
      <JobsPageContent />
    </Suspense>
  );
}