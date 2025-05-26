// frontend/app/models/[id]/page.tsx
"use client";

import React, { useState, useEffect, useMemo, useCallback, Suspense } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  ArrowLeft, RefreshCw, BarChart3, Database, Layers, Settings, Play, Eye, AlertCircle, Loader2,
  Puzzle, Plus, CheckCircle, Download, Trash2, Cog, FileJson, Brain, Wand2, FileText, CalendarDays,
  Copy
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import {
  Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis
} from "@/components/ui/pagination";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";

import { apiService, handleApiError } from "@/lib/apiService";
import { MLModelRead, PaginatedMLModelRead } from "@/types/api/ml-model";
import { InferenceJobRead, PaginatedInferenceJobRead } from "@/types/api/inference-job";
import { TaskResponse } from "@/types/api/task";
import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { JobStatusEnum } from "@/types/api/enums";


const ITEMS_PER_PAGE = 5;

// Helper function to format dates
function formatDate(dateString?: string | Date | null): string {
  if (!dateString) return "N/A";
  const date = typeof dateString === "string" ? new Date(dateString) : dateString;
  return date.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

// Helper function to render key-value pairs (e.g., for hyperparameters, metrics)
const KeyValueDisplay: React.FC<{ data: Record<string, any> | null | undefined, title: string, icon?: React.ReactNode }> = ({ data, title, icon }) => {
  if (!data || Object.keys(data).length === 0) {
    return (
      <Card className="h-full"> {/* Ensure card takes full height for grid alignment */}
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center">{icon && <span className="mr-2">{icon}</span>}{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No {title.toLowerCase()} available for this model.</p>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
         <CardTitle className="text-base flex items-center">{icon && <span className="mr-2">{icon}</span>}{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[200px] pr-3"> {/* Added pr-3 for scrollbar spacing */}
          <dl className="space-y-1.5 text-sm">
            {Object.entries(data).map(([key, value]) => (
              <div key={key} className="flex justify-between items-start border-b border-dashed pb-1 last:border-b-0">
                <dt className="text-muted-foreground break-words mr-2" title={key}>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:</dt>
                <dd className="font-mono text-right break-all" title={String(value)}>{String(value)}</dd>
              </div>
            ))}
          </dl>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};


function ModelDetailPageContent() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const searchParamsHook = useSearchParams(); // Renamed to avoid conflict
  const { toast } = useToast();
  const modelId = params.id;
  
  const preSelectedTab = searchParamsHook.get("tab") || "details";
  const [activeTab, setActiveTab] = useState(preSelectedTab);

  const [model, setModel] = useState<MLModelRead | null>(null);
  const [isLoadingModel, setIsLoadingModel] = useState(true);
  const [modelError, setModelError] = useState<string | null>(null);
  const [isDeletingModel, setIsDeletingModel] = useState(false);

  const [inferenceJobs, setInferenceJobs] = useState<InferenceJobRead[]>([]);
  const [inferenceJobsPagination, setInferenceJobsPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });

  const { taskStatuses } = useTaskStore();

  const fetchModelDetails = useCallback(async () => {
    if (!modelId) return;
    setIsLoadingModel(true);
    setModelError(null);
    try {
      const fetchedModel = await apiService.get<MLModelRead>(`/ml/models/${modelId}`);
      setModel(fetchedModel);
    } catch (err) {
      handleApiError(err, "Failed to fetch model details");
      setModelError(err instanceof Error ? err.message : "Model not found or error loading.");
    } finally {
      setIsLoadingModel(false);
    }
  }, [modelId]);

  const fetchPaginatedInferenceJobs = useCallback(async (page: number) => {
    if (!modelId) return;
    setInferenceJobsPagination(prev => ({ 
        ...prev, 
        isLoading: true, 
        currentPage: page, 
        totalItems: (page === 1 || prev.totalItems === 0) ? 0 : prev.totalItems 
    }));
    const skip = (page - 1) * ITEMS_PER_PAGE;
    try {
      // This endpoint GET /ml/infer?model_id=... should now return PaginatedInferenceJobRead
      const response = await apiService.get<PaginatedInferenceJobRead>(`/ml/infer?model_id=${modelId}&skip=${skip}&limit=${ITEMS_PER_PAGE}`);
      
      // Check if response has items and total
      if (response && Array.isArray(response.items) && typeof response.total === 'number') {
        setInferenceJobs(response.items);
        setInferenceJobsPagination(prev => ({ ...prev, totalItems: response.total, isLoading: false }));
      } else {
        // This case should be less likely now if backend is fixed
        console.error("ModelDetail/InferenceJobs: Unexpected response structure", response);
        handleApiError({ message: "Received invalid data for inference jobs." }, "Fetch Error");
        setInferenceJobs([]);
        setInferenceJobsPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
      }
    } catch (err) {
      handleApiError(err, "Failed to fetch inference jobs");
      // Keep current page, set loading false, don't reset totalItems on error unless it's the first load.
      setInferenceJobsPagination(prev => ({ ...prev, isLoading: false, totalItems: (page === 1 ? 0 : prev.totalItems) }));
       if (page === 1) setInferenceJobs([]); // Clear items only if first page fetch fails
    }
  }, [modelId]);
  
  useEffect(() => {
    fetchModelDetails();
  }, [fetchModelDetails]);

  useEffect(() => {
    if (model && activeTab === 'inference-jobs') { // Fetch jobs only when model is loaded and tab is active
        fetchPaginatedInferenceJobs(inferenceJobsPagination.currentPage); // Use current page from state
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model, activeTab, inferenceJobsPagination.currentPage, fetchPaginatedInferenceJobs]);


  const handleRefreshData = () => {
    toast({ title: "Refreshing model data..." });
    fetchModelDetails();
    if (activeTab === 'inference-jobs') {
      fetchPaginatedInferenceJobs(1); // Reset to page 1 on manual refresh of jobs tab
    }
  };

  const handleDeleteModel = async () => {
    if (!model) return;
    setIsDeletingModel(true);
    try {
      await apiService.delete(`/ml/models/${model.id}`);
      toast({ title: "Model Deleted", description: `Model ${model.name} (v${model.version}) has been deleted.` });
      router.push('/models');
    } catch (err) {
      handleApiError(err, "Failed to delete model");
    } finally {
      setIsDeletingModel(false);
    }
  };

    const handleRunInference = () => {
    if (!model) {
        toast({ title: "Error", description: "Model data not loaded.", variant: "destructive"});
        return;
    }
    const repositoryId = model.dataset?.repository_id; // model.dataset might be null or undefined
    const queryParams = new URLSearchParams();
    queryParams.append("modelId", model.id.toString());
    if (repositoryId) {
        queryParams.append("repositoryId", repositoryId.toString());
    }
    router.push(`/jobs/inference?${queryParams.toString()}`);
    };

  const handleCopyArtifactPath = () => {
    if (model?.s3_artifact_path) {
      navigator.clipboard.writeText(model.s3_artifact_path)
        .then(() => toast({ title: "Copied!", description: "Artifact path copied to clipboard." }))
        .catch(() => toast({ title: "Copy Failed", description: "Could not copy path.", variant: "destructive" }));
    }
  };

  const renderPaginationControls = (
    currentPage: number, totalItems: number, limit: number, 
    onPageChange: (page: number) => void, isLoading: boolean
  ) => {
    const totalPages = Math.ceil(totalItems / limit);
    if (totalPages <= 1) return null;
    
    let pageNumbers: (number | string)[] = [];
    if (totalPages <= 7) {
        pageNumbers = Array.from({ length: totalPages }, (_, i) => i + 1);
    } else {
        pageNumbers.push(1);
        if (currentPage > 3) pageNumbers.push('...');
        if (currentPage > 2) pageNumbers.push(currentPage - 1);
        if (currentPage > 1 && currentPage < totalPages) pageNumbers.push(currentPage);
        if (currentPage < totalPages -1) pageNumbers.push(currentPage + 1);
        if (currentPage < totalPages - 2) pageNumbers.push('...');
        pageNumbers.push(totalPages);
        pageNumbers = [...new Set(pageNumbers)];
    }

    return (
      <Pagination className="mt-4">
        <PaginationContent>
          <PaginationItem><PaginationPrevious onClick={() => onPageChange(currentPage - 1)} aria-disabled={currentPage <= 1 || isLoading} className={(currentPage <= 1 || isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
          {pageNumbers.map((page, index) => (
            <PaginationItem key={typeof page === 'number' ? `page-${page}` : `ellipsis-${index}`}>
              {typeof page === 'number' ? 
                <PaginationLink onClick={() => onPageChange(page)} isActive={currentPage === page} aria-disabled={isLoading} className={isLoading ? "pointer-events-none opacity-50" : ""}>{page}</PaginationLink> : 
                <PaginationEllipsis />}
            </PaginationItem>
          ))}
          <PaginationItem><PaginationNext onClick={() => onPageChange(currentPage + 1)} aria-disabled={currentPage >= totalPages || isLoading} className={(currentPage >= totalPages || isLoading) ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
        </PaginationContent>
      </Pagination>
    );
  };

  const renderTaskAwareStatusBadge = (taskAwareEntityStatus?: TaskStatusUpdatePayload, fallbackStaticStatus?: string) => {
    const currentStatusToDisplay = taskAwareEntityStatus || (fallbackStaticStatus ? { status: fallbackStaticStatus } as TaskStatusUpdatePayload : undefined);
    if (!currentStatusToDisplay) return <Badge variant="secondary">Unknown</Badge>;

    const { status, status_message, progress } = currentStatusToDisplay;
    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";
    let icon = null;
    let text = status_message || status || "Unknown";

    switch (status?.toUpperCase()) {
      case "SUCCESS": case "READY":
        badgeVariant = "default"; icon = <CheckCircle className="h-3 w-3 mr-1" />; text = `${status_message || "Completed"}`; break;
      case "RUNNING": case "PENDING": case "GENERATING":
        badgeVariant = "outline"; icon = <RefreshCw className="h-3 w-3 mr-1 animate-spin" />; text = `${status_message || status} (${progress ?? 0}%)`; break;
      case "FAILED":
        badgeVariant = "destructive"; icon = <AlertCircle className="h-3 w-3 mr-1" />; text = `Failed: ${status_message || "Error"}`; break;
      default: text = String(status).toUpperCase();
    }
    return <Badge variant={badgeVariant} className="whitespace-nowrap">{icon}{text}</Badge>;
  };


  if (isLoadingModel && !model && !modelError) {
    return (
      <MainLayout>
        <PageContainer title="Loading Model..." description="Fetching model details...">
          <Skeleton className="h-12 w-1/2 mb-4" />
          <div className="space-y-4"> <Skeleton className="h-32 w-full" /> <Skeleton className="h-64 w-full" /> <Skeleton className="h-40 w-full" /></div>
        </PageContainer>
      </MainLayout>
    );
  }

  if (modelError || !model) {
    return (
      <MainLayout>
        <PageContainer
          title="Model Not Found"
          description={modelError || "The requested model could not be found or an error occurred."}
          actions={<Button onClick={() => router.back()} variant="outline"><ArrowLeft className="mr-2 h-4 w-4" /> Back</Button>}
        >
          <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>Please check the model ID or try again later.</AlertDescription></Alert>
        </PageContainer>
      </MainLayout>
    );
  }

  const pageActions = (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={handleRefreshData} disabled={isLoadingModel}>
        <RefreshCw className={`mr-2 h-4 w-4 ${isLoadingModel ? 'animate-spin' : ''}`} /> Refresh
      </Button>
      <AlertDialog>
        <AlertDialogTrigger asChild><Button variant="destructive" size="sm" disabled={isDeletingModel}><Trash2 className="mr-2 h-4 w-4" /> Delete Model</Button></AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Are you sure?</AlertDialogTitle><AlertDialogDescription>This action cannot be undone. This will permanently delete the model and its artifact.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeletingModel}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteModel} disabled={isDeletingModel}>
              {isDeletingModel ? <><Loader2 className="mr-2 h-4 w-4 animate-spin"/> Deleting...</> : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );

  return (
    <MainLayout>
      <PageContainer
        title={`${model.name} (v${model.version})`}
        description={<Badge variant="outline">{model.model_type}</Badge>}
        actions={pageActions}
        className="px-4 md:px-6 lg:px-8"
      >
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="inference-jobs">Inference Jobs ({inferenceJobsPagination.isLoading && inferenceJobsPagination.totalItems === 0 ? <Loader2 className="h-3 w-3 animate-spin"/> : inferenceJobsPagination.totalItems})</TabsTrigger>
          </TabsList>

          <TabsContent value="details" className="space-y-6">
            <Card>
              <CardHeader>
                  <CardTitle className="flex items-center"><FileText className="mr-2 h-5 w-5 text-primary"/>Model Information</CardTitle>
                  <CardDescription>{model.description || "No description provided."}</CardDescription>
              </CardHeader>
              <CardContent className="grid md:grid-cols-2 gap-x-8 gap-y-4 text-sm">
                <div><Label className="text-muted-foreground">Model ID</Label><p className="font-mono">{model.id}</p></div>
                <div><Label className="text-muted-foreground">Created At</Label><p><CalendarDays className="inline h-3.5 w-3.5 mr-1 text-muted-foreground"/>{formatDate(model.created_at)}</p></div>
                <div><Label className="text-muted-foreground">Updated At</Label><p><CalendarDays className="inline h-3.5 w-3.5 mr-1 text-muted-foreground"/>{formatDate(model.updated_at)}</p></div>
                
                {model.s3_artifact_path && (
                    <div className="col-span-full">
                        <Label className="text-muted-foreground">Artifact Path</Label>
                        <div className="flex items-center gap-2">
                            <p className="font-mono text-xs truncate flex-grow" title={model.s3_artifact_path}>{model.s3_artifact_path}</p>
                            <Button variant="ghost" size="icon" onClick={handleCopyArtifactPath} className="h-6 w-6"><Copy className="h-3.5 w-3.5"/></Button>
                        </div>
                    </div>
                )}
                
                {model.dataset_id && (
                    <div>
                        <Label className="text-muted-foreground">Trained on Dataset</Label>
                        <p><Link href={`/datasets/${model.dataset_id}`} className="text-primary hover:underline flex items-center"><Database className="inline h-3.5 w-3.5 mr-1"/>Dataset ID: {model.dataset_id}</Link></p>
                        {model.dataset?.name && <p className="text-xs text-muted-foreground ml-5">{model.dataset.name}</p>}
                    </div>
                )}
                 {model.training_job_id && (
                    <div>
                        <Label className="text-muted-foreground">Source Training Job</Label>
                        <p><Link href={`/jobs/${model.training_job_id}?type=training`} className="text-primary hover:underline flex items-center"><Puzzle className="inline h-3.5 w-3.5 mr-1"/>Job ID: {model.training_job_id}</Link></p>
                        {model.training_job?.config?.model_name && <p className="text-xs text-muted-foreground ml-5">({model.training_job.config.model_name})</p>}
                    </div>
                )}
                {model.hp_search_job_id && (
                     <div>
                        <Label className="text-muted-foreground">Source HP Search Job</Label>
                        <p><Link href={`/jobs/${model.hp_search_job_id}?type=hp_search`} className="text-primary hover:underline flex items-center"><Layers className="inline h-3.5 w-3.5 mr-1"/>Job ID: {model.hp_search_job_id}</Link></p>
                         {model.hp_search_job?.optuna_study_name && <p className="text-xs text-muted-foreground ml-5">({model.hp_search_job.optuna_study_name})</p>}
                    </div>
                )}
              </CardContent>
              <CardFooter>
                  <Button onClick={handleRunInference}>
                      <Play className="mr-2 h-4 w-4"/> Run Inference with this Model
                  </Button>
              </CardFooter>
            </Card>

            <div className="grid md:grid-cols-2 gap-6">
                <KeyValueDisplay data={model.hyperparameters} title="Hyperparameters" icon={<Cog className="h-5 w-5 text-primary"/>} /*isLoading={isLoadingModel}*//>
                <KeyValueDisplay data={model.performance_metrics} title="Performance Metrics" icon={<Brain className="h-5 w-5 text-primary"/>} /*isLoading={isLoadingModel}*//>
            </div>
          </TabsContent>

          <TabsContent value="inference-jobs" className="space-y-4">
            <PageContainer
                title="Inference Jobs Using This Model"
                description={ inferenceJobsPagination.isLoading && inferenceJobsPagination.totalItems === 0 ? "Loading jobs..." : `Showing ${inferenceJobs.length} of ${inferenceJobsPagination.totalItems} jobs.`}
            >
              {inferenceJobsPagination.isLoading && inferenceJobs.length === 0 ? (
                <div className="rounded-md border p-4 space-y-2">
                  {[1,2,3].map(i => <Skeleton key={i} className="h-10 w-full"/>)}
                </div>
              ) : !inferenceJobsPagination.isLoading && inferenceJobs.length === 0 ? (
                <Card className="text-center py-10">
                  <CardContent className="flex flex-col items-center justify-center">
                    <Wand2 className="h-12 w-12 text-muted-foreground mb-4" />
                    <p className="text-muted-foreground mb-3">No inference jobs have used this model yet.</p>
                    <Button onClick={handleRunInference}><Play className="mr-2 h-4 w-4" /> Run First Inference</Button>
                  </CardContent>
                </Card>
              ) : (
                <>
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader><TableRow><TableHead>Job ID</TableHead><TableHead>Input (Commit)</TableHead><TableHead>Status</TableHead><TableHead>Created At</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {inferenceJobs.map(job => {
                          const jobTask = getLatestTaskForEntity(taskStatuses, "InferenceJob", job.id);
                          const commitHash = typeof job.input_reference === 'object' && job.input_reference.commit_hash 
                                              ? String(job.input_reference.commit_hash).substring(0, 8) + "..." 
                                              : (typeof job.input_reference === 'string' ? String(job.input_reference).substring(0,8) + "..." : "N/A");
                          const fullCommitHash = typeof job.input_reference === 'object' && job.input_reference.commit_hash ? String(job.input_reference.commit_hash) : "N/A";
                          return (
                            <TableRow key={job.id}>
                              <TableCell className="font-mono">{job.id}</TableCell>
                              <TableCell className="font-mono" title={fullCommitHash}>{commitHash}</TableCell>
                              <TableCell>{renderTaskAwareStatusBadge(jobTask, job.status)}</TableCell>
                              <TableCell>{formatDate(job.created_at)}</TableCell>
                              <TableCell className="text-right">
                                {job.status === JobStatusEnum.SUCCESS ? (
                                     <Button variant="outline" size="sm" asChild>
                                        <Link href={`/prediction-insights/${job.id}`}>View Insights</Link>
                                    </Button>
                                ) : (
                                    <Button variant="outline" size="sm" disabled>View Insights</Button>
                                )}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                  {renderPaginationControls(inferenceJobsPagination.currentPage, inferenceJobsPagination.totalItems, ITEMS_PER_PAGE, (page) => setInferenceJobsPagination(prev => ({...prev, currentPage: page})), inferenceJobsPagination.isLoading)}
                </>
              )}
            </PageContainer>
          </TabsContent>
        </Tabs>
      </PageContainer>
    </MainLayout>
  );
}

export default function ModelDetailPage() { // New wrapper component
  return (
    <Suspense fallback={<div>Loading page data...</div>}>
      <ModelDetailPageContent />
    </Suspense>
  );
}