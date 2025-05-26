// frontend/app/datasets/[id]/page.tsx
"use client";

import React, { useState, useEffect, useMemo, useCallback, Suspense } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, Download, RefreshCw, Trash2, AlertCircle, Loader2, Database, BarChart3, Settings, FileJson, Play, CheckCircle, Puzzle, ListFilter, TargetIcon, Plus, Wand2, Edit, Info } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

import { apiService, handleApiError } from "@/lib/apiService";
import { DatasetRead } from "@/types/api/dataset"; // Keep only DatasetRead from here
import { MLModelRead, PaginatedMLModelRead } from "@/types/api/ml-model";
import { Repository } from "@/types/api/repository"; // For repository name

import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { DatasetStatusEnum, JobStatusEnum } from "@/types/api/enums";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";
import { PageLoader } from '@/components/ui/page-loader';

import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";

const ROWS_PER_PAGE = 10;

function formatDate(dateString: string | Date | undefined | null): string {
  if (!dateString) return "N/A";
  const date = typeof dateString === "string" ? new Date(dateString) : dateString;
  try {
    return date.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return "Invalid Date";
  }
}

function DatasetDetailPageContent() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const { toast } = useToast();
  const datasetId = params.id;

  const [dataset, setDataset] = useState<DatasetRead | null>(null);
  const [repository, setRepository] = useState<Repository | null>(null); // For displaying repo name
  const [isLoadingDataset, setIsLoadingDataset] = useState(true);
  const [datasetError, setDatasetError] = useState<string | null>(null);

  const [dataPreview, setDataPreview] = useState<Record<string, any>[]>([]);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalDatasetRows, setTotalDatasetRows] = useState(0); 
  
  const [modelsTrained, setModelsTrained] = useState<MLModelRead[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  
  const { taskStatuses } = useTaskStore();

  const liveDatasetStatus = useMemo(() => {
    if (!datasetId) return undefined;
    return getLatestTaskForEntity(taskStatuses, "Dataset", datasetId, "dataset_generation");
  }, [taskStatuses, datasetId]);

  const fetchDatasetDetails = useCallback(async (showToast = false) => {
    if (!datasetId) return;
    if (showToast) toast({ title: "Refreshing dataset details..." });
    setIsLoadingDataset(true);
    setDatasetError(null);
    try {
      const fetchedDataset = await apiService.get<DatasetRead>(`/datasets/${datasetId}`);
      setDataset(fetchedDataset);
      if (fetchedDataset?.num_rows !== undefined && fetchedDataset.num_rows !== null) {
        setTotalDatasetRows(fetchedDataset.num_rows);
      }
      if (fetchedDataset?.status.toUpperCase() === DatasetStatusEnum.READY.toUpperCase()) {
        fetchDataPreview(1, fetchedDataset.storage_path); 
      }
      if (fetchedDataset?.repository_id) {
        try {
            const repoData = await apiService.get<Repository>(`/repositories/${fetchedDataset.repository_id}`);
            setRepository(repoData);
        } catch (repoErr) {
            console.warn("Failed to fetch repository details for dataset:", repoErr);
            setRepository(null); // Set to null or a placeholder if fetch fails
        }
      }
      if (showToast) toast({ title: "Dataset details refreshed!", variant: "default" });
    } catch (err) {
      handleApiError(err, "Failed to fetch dataset details");
      setDatasetError(err instanceof Error ? err.message : "Dataset not found or error loading.");
      setDataset(null); // Clear dataset on error
      setRepository(null);
    } finally {
      setIsLoadingDataset(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]); // fetchDataPreview is stable

  useEffect(() => {
    fetchDatasetDetails();
  }, [fetchDatasetDetails]);

  const fetchDataPreview = async (page: number, storagePath?: string | null) => {
    const currentDatasetStatus = liveDatasetStatus?.status || dataset?.status;
    if (!datasetId || currentDatasetStatus?.toUpperCase() !== DatasetStatusEnum.READY.toUpperCase() || !storagePath) {
        setDataPreview([]); // Clear preview if not ready
        return;
    }
    setIsLoadingPreview(true);
    setPreviewError(null);
    setCurrentPage(page);
    const skip = (page - 1) * ROWS_PER_PAGE;
    try {
      const previewData = await apiService.get<Record<string, any>[]>(
        `/datasets/${datasetId}/view?skip=${skip}&limit=${ROWS_PER_PAGE}`
      );
      setDataPreview(previewData || []);
    } catch (err) {
      handleApiError(err, "Failed to fetch data preview");
      setPreviewError(err instanceof Error ? err.message : "Could not load preview.");
      setDataPreview([]);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const fetchModels = useCallback(async () => {
    if (!datasetId) return;
    setIsLoadingModels(true);
    setModelsTrained([]);
    try {
      const response = await apiService.get<PaginatedMLModelRead>(`/ml/models?dataset_id=${datasetId}&limit=100`);
      setModelsTrained(response.items || []);
    } catch (err) {
      handleApiError(err, "Failed to fetch trained models");
      setModelsTrained([]);
    } finally {
      setIsLoadingModels(false);
    }
  }, [datasetId]);

  useEffect(() => {
    if(dataset && dataset.status.toUpperCase() === DatasetStatusEnum.READY.toUpperCase()) {
        fetchModels();
    } else {
        setModelsTrained([]); // Clear models if dataset not ready
    }
  }, [dataset, fetchModels]); 

  const totalPagesForPreview = useMemo(() => {
    if (!totalDatasetRows) return 0;
    return Math.ceil(totalDatasetRows / ROWS_PER_PAGE);
  }, [totalDatasetRows]);

  const handlePreviewPageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPagesForPreview) {
      fetchDataPreview(newPage, dataset?.storage_path);
    }
  };

   useEffect(() => {
    const staticStatus = dataset?.status?.toUpperCase();
    const liveStatusUpper = liveDatasetStatus?.status?.toUpperCase();

    if (liveDatasetStatus && 
        (liveStatusUpper === JobStatusEnum.SUCCESS.toUpperCase() || liveStatusUpper === JobStatusEnum.FAILED.toUpperCase())) {
        // Only refetch if the static status isn't already reflecting the final state.
        const isStaticFinal = staticStatus === DatasetStatusEnum.READY.toUpperCase() || staticStatus === DatasetStatusEnum.FAILED.toUpperCase();
        
        if (!isStaticFinal || (liveStatusUpper === JobStatusEnum.SUCCESS.toUpperCase() && staticStatus !== DatasetStatusEnum.READY.toUpperCase()) || (liveStatusUpper === JobStatusEnum.FAILED.toUpperCase() && staticStatus !== DatasetStatusEnum.FAILED.toUpperCase())) {
            toast({
                title: `Dataset Generation ${liveStatusUpper === JobStatusEnum.SUCCESS.toUpperCase() ? "Complete" : "Failed"}`,
                description: `Dataset ${dataset?.name || datasetId} processing ${liveDatasetStatus.status_message || liveDatasetStatus.status.toLowerCase()}. Refreshing details...`
            });
            fetchDatasetDetails(false); // Fetch silently in background
        }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveDatasetStatus, dataset?.status, datasetId]);


  const handleDownloadDataset = () => {
    if (!datasetId) return;
    window.location.href = `${process.env.NEXT_PUBLIC_API_URL || ''}/api/v1/datasets/${datasetId}/download`;
    toast({ title: "Download Initialized", description: "Your dataset download should start shortly." });
  };

  const handleDeleteDataset = async () => {
    if (!datasetId || !dataset) return;
    try {
        await apiService.delete<void>(`/datasets/${datasetId}`);
        toast({ title: "Dataset Deleted", description: `Dataset ${dataset.name} has been marked for deletion.`});
        router.push(`/repositories/${dataset.repository_id}`); 
    } catch (err) { handleApiError(err, "Failed to delete dataset"); }
  };
  
  const handleRegenerateDataset = async () => {
    if (!datasetId || !dataset) return;
    try {
        // In a real app, this might be a specific endpoint: POST /datasets/{dataset_id}/regenerate
        // For now, we'll re-submit the creation task, which means the backend might
        // need to handle this gracefully (e.g., update existing PENDING or FAILED, or create new version)
        // This simplified re-trigger uses the original creation endpoint.
        // If the backend doesn't support "re-creating" this way, it might error or create a duplicate.
        // A proper "regenerate" would likely just re-queue the original Celery task for the existing dataset_id.
        
        const taskResponse = await apiService.createDataset(dataset.repository_id.toString(), {
            name: dataset.name, // Re-use existing name or allow modification
            description: dataset.description,
            config: dataset.config, // Re-use existing config
        });

        toast({ title: "Regeneration Requested", description: `Regeneration for dataset ${dataset.name} initiated. Task ID: ${taskResponse.task_id}`, variant: "default" });
        fetchDatasetDetails(true); // Refresh details to show PENDING status
    } catch (err) { handleApiError(err, "Failed to request dataset regeneration"); }
  };

  const getDisplayDatasetStatusInfo = () => {
    if (isLoadingDataset && !dataset && !datasetError) return { text: "Loading Info...", badgeVariant: "outline" as const, icon: <Loader2 className="h-4 w-4 animate-spin" /> };
    if (datasetError) return { text: "Error Loading Dataset", badgeVariant: "destructive" as const, icon: <AlertCircle className="h-4 w-4" /> };
    if (!dataset) return { text: "Dataset Not Found", badgeVariant: "destructive" as const, icon: <AlertCircle className="h-4 w-4" /> };

    const currentStatusInfo = liveDatasetStatus || { status: dataset.status, progress: null, status_message: dataset.status_message };
    
    let displayStatus = String(currentStatusInfo.status).toUpperCase();
    let displayMessage = currentStatusInfo.status_message || displayStatus; // Fallback to status itself
    let displayProgress = currentStatusInfo.progress;

    let icon: React.ReactNode = <Info className="h-4 w-4" />; // Default icon
    let badgeVariant: "default" | "secondary" | "destructive" | "outline" = "secondary";

    if (displayStatus === JobStatusEnum.SUCCESS.toUpperCase() || displayStatus === DatasetStatusEnum.READY.toUpperCase()) {
        displayMessage = "Ready";
        badgeVariant = "default"; // Green-ish
        icon = <CheckCircle className="h-4 w-4"/>;
    } else if (displayStatus === JobStatusEnum.PENDING.toUpperCase() || displayStatus === DatasetStatusEnum.PENDING.toUpperCase()) {
        displayStatus = "Pending";
        badgeVariant = "outline";
        icon = <Loader2 className="h-4 w-4 animate-spin" />;
    } else if (displayStatus === JobStatusEnum.RUNNING.toUpperCase() || displayStatus === JobStatusEnum.STARTED.toUpperCase() || displayStatus === DatasetStatusEnum.GENERATING.toUpperCase()) {
        displayStatus = "Generating";
        badgeVariant = "outline";
        icon = <RefreshCw className="h-4 w-4 animate-spin" />;
        displayMessage = `${currentStatusInfo.status_message || displayStatus}${displayProgress !== null ? ` (${displayProgress}%)` : ''}`;
    } else if (displayStatus === JobStatusEnum.FAILED.toUpperCase() || displayStatus === DatasetStatusEnum.FAILED.toUpperCase()) {
        displayStatus = "Failed";
        badgeVariant = "destructive";
        icon = <AlertCircle className="h-4 w-4" />;
        displayMessage = `Failed: ${currentStatusInfo.status_message || "Unknown error"}`;
    } else if (displayStatus === JobStatusEnum.REVOKED.toUpperCase()) {
        displayStatus = "Revoked";
        badgeVariant = "destructive";
        icon = <AlertCircle className="h-4 w-4" />;
        displayMessage = `Revoked: ${currentStatusInfo.status_message || "Task was revoked"}`;
    } else { // Any other status from task store or unknown dataset status
        displayMessage = currentStatusInfo.status_message || displayStatus;
        if (currentStatusInfo.progress !== null && currentStatusInfo.progress !== undefined) {
            displayMessage += ` (${currentStatusInfo.progress}%)`;
        }
         // Default to outline if it's an active task state, otherwise secondary
        badgeVariant = (liveDatasetStatus && (liveDatasetStatus.status.toUpperCase() === "RUNNING" || liveDatasetStatus.status.toUpperCase() === "PENDING" || liveDatasetStatus.status.toUpperCase() === "STARTED")) ? "outline" : "secondary";
        if (badgeVariant === "outline") icon = <RefreshCw className="h-4 w-4 animate-spin" />;
    }
    
    return { text: displayMessage, badgeVariant, icon };
  };

  const displayDatasetStatus = getDisplayDatasetStatusInfo();
  const previewColumns = useMemo(() => dataPreview.length > 0 ? Object.keys(dataPreview[0]) : [], [dataPreview]);
  
  const isDatasetReady = dataset?.status.toUpperCase() === DatasetStatusEnum.READY.toUpperCase() || liveDatasetStatus?.status.toUpperCase() === JobStatusEnum.SUCCESS.toUpperCase();
  const isDatasetProcessing = displayDatasetStatus.icon?.type === RefreshCw || displayDatasetStatus.icon?.type === Loader2;


  if (isLoadingDataset && !dataset && !datasetError) {
    return <PageLoader message="Loading dataset details..." />;
  }
  if (datasetError || !dataset) {
    return (
        <MainLayout>
          <PageContainer title="Dataset Not Found" description={datasetError || "The requested dataset could not be found."}
            actions={<Button onClick={() => router.back()} variant="outline"><ArrowLeft className="mr-2 h-4 w-4"/> Back</Button>} >
             <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>Please check the dataset ID or try again.</AlertDescription></Alert>
          </PageContainer>
        </MainLayout>
      );
  }

  const pageActions = ( 
    <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => fetchDatasetDetails(true)} disabled={isLoadingDataset || isDatasetProcessing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${(isLoadingDataset || isDatasetProcessing) ? 'animate-spin' : ''}`} />
            Refresh
        </Button>
        <AlertDialog>
            <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm" disabled={isDatasetProcessing}><Trash2 className="mr-2 h-4 w-4" /> Delete</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
                <AlertDialogHeader><AlertDialogTitle>Are you sure?</AlertDialogTitle><AlertDialogDescription>This will permanently delete the dataset definition and queue data deletion from storage. This action cannot be undone.</AlertDialogDescription></AlertDialogHeader>
                <AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction onClick={handleDeleteDataset} className="bg-destructive hover:bg-destructive/90">Delete</AlertDialogAction></AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    </div>
  );

  return (
    <MainLayout>
      <PageContainer 
        title={dataset.name}
        description={ 
            <div className="flex items-center gap-2"> 
                {repository ? (
                    <Link href={`/repositories/${dataset.repository_id}`} className="text-sm text-primary hover:underline">
                        Repo: {repository.name} (ID: {dataset.repository_id})
                    </Link>
                ) : (
                     <span className="text-sm text-muted-foreground">Repo ID: {dataset.repository_id}</span>
                )}
                <Badge variant={displayDatasetStatus.badgeVariant} className="text-xs px-2 py-0.5" title={displayDatasetStatus.text}>
                    {displayDatasetStatus.icon && <span className="mr-1.5">{displayDatasetStatus.icon}</span>}
                    {displayDatasetStatus.text.length > 50 ? displayDatasetStatus.text.substring(0, 47) + "..." : displayDatasetStatus.text}
                </Badge> 
            </div> 
        }
        actions={pageActions}
        className="px-4 md:px-6 lg:px-8"
      >
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Metadata & Actions */}
          <div className="lg:col-span-1 space-y-6">
            <Card>
              <CardHeader><CardTitle className="flex items-center"><Settings className="mr-2 h-5 w-5 text-primary"/>Configuration</CardTitle><CardDescription>Details of how this dataset was generated.</CardDescription></CardHeader>
              <CardContent className="text-sm space-y-3">
                <div><Label className="text-xs text-muted-foreground uppercase flex items-center tracking-wider"><TargetIcon className="h-3.5 w-3.5 mr-1.5"/>Target Column</Label> <Badge variant="secondary" className="mt-0.5">{dataset.config.target_column}</Badge></div>
                <div><Label className="text-xs text-muted-foreground uppercase flex items-center tracking-wider"><ListFilter className="h-3.5 w-3.5 mr-1.5"/>Feature Columns ({dataset.config.feature_columns.length})</Label>
                  <ScrollArea className="h-20 mt-1 rounded-md border p-2 text-xs bg-muted/10"><ul className="list-disc list-inside pl-2 space-y-0.5">{dataset.config.feature_columns.map(fc => <li key={fc} className="truncate" title={fc}>{fc}</li>)}</ul></ScrollArea>
                </div>
                <div><Label className="text-xs text-muted-foreground uppercase flex items-center tracking-wider"><FileJson className="h-3.5 w-3.5 mr-1.5"/>Cleaning Rules ({dataset.config.cleaning_rules.filter(r => r.enabled).length} enabled)</Label>
                  {dataset.config.cleaning_rules.filter(r => r.enabled).length > 0 ? (
                    <ScrollArea className="h-28 mt-1 rounded-md border p-2 text-xs bg-muted/10">
                      <ul className="space-y-1.5">
                      {dataset.config.cleaning_rules.filter(r => r.enabled).map(rule => (
                        <li key={rule.name} className="border-b border-dashed pb-1 last:border-b-0">
                          <span className="font-medium">{rule.name}</span>
                          {rule.params && Object.keys(rule.params).length > 0 && (
                            <dl className="mt-0.5 pl-3 text-xs">{Object.entries(rule.params).map(([paramKey, paramValue]) => (<div key={paramKey} className="flex"><dt className="text-muted-foreground w-20 truncate">{paramKey}:</dt><dd className="font-mono">{String(paramValue)}</dd></div>))}</dl>
                          )}</li>))}</ul></ScrollArea>
                  ) : <p className="text-xs text-muted-foreground italic mt-1">No cleaning rules were enabled.</p>}
                </div>
                {dataset.description && (<div><Label className="text-xs text-muted-foreground uppercase">Description</Label> <p className="text-xs italic bg-muted/10 p-2 rounded-md whitespace-pre-wrap">{dataset.description}</p></div>)}
                <div className="flex justify-between pt-2 border-t text-xs text-muted-foreground"><p>Created: {formatDate(dataset.created_at)}</p><p>Updated: {formatDate(dataset.updated_at)}</p></div>
              </CardContent>
              <CardFooter className="flex-col items-stretch gap-2">
                {/* TODO: Add Edit Config button if/when supported */}
                {/* <Button variant="outline" size="sm" disabled={isDatasetProcessing || !isDatasetReady}><Edit className="mr-2 h-4 w-4"/>Edit Configuration</Button> */}
                <Button variant="outline" size="sm" onClick={handleRegenerateDataset} disabled={isDatasetProcessing}>
                    <RefreshCw className={`mr-2 h-4 w-4 ${isDatasetProcessing && displayDatasetStatus.text.includes("Generating") ? "animate-spin":""}`} /> Re-generate Dataset
                </Button>
              </CardFooter>
            </Card>

            <Card>
                <CardHeader className="pb-3"><CardTitle className="flex items-center text-base"><Puzzle className="mr-2 h-4 w-4 text-primary"/>Models Trained</CardTitle><CardDescription className="text-xs">ML models trained using this dataset.</CardDescription></CardHeader>
                <CardContent>
                    {isLoadingModels ? <Skeleton className="h-20 w-full" /> : 
                     modelsTrained.length === 0 ? <p className="text-sm text-muted-foreground py-3 text-center">No models trained with this dataset.</p> :
                     <ScrollArea className="h-24"><ul className="space-y-1 pr-2">{modelsTrained.map(model => (<li key={model.id} className="text-sm flex justify-between items-center py-1 border-b last:border-b-0"><Link href={`/models/${model.id}`} className="font-medium hover:underline truncate pr-2" title={model.name}>{model.name} (v{model.version})</Link><Badge variant="secondary" className="text-xs">{model.model_type}</Badge></li>))}</ul></ScrollArea>}
                </CardContent>
                 {isDatasetReady && (
                    <CardFooter className="pt-2">
                        <Button size="sm" className="w-full" asChild><Link href={`/jobs/train?datasetId=${datasetId}`}><Plus className="mr-2 h-4 w-4" /> Train New Model</Link></Button>
                    </CardFooter>
                )}
            </Card>
             {isDatasetReady && (
                 <Card>
                    <CardHeader className="pb-3"><CardTitle className="text-base flex items-center"><Wand2 className="mr-2 h-4 w-4 text-primary"/>Hyperparameter Search</CardTitle></CardHeader>
                    <CardFooter>
                        <Button size="sm" className="w-full" asChild><Link href={`/jobs/hp-search?datasetId=${datasetId}`}><Plus className="mr-2 h-4 w-4"/>New HP Search Job</Link></Button>
                    </CardFooter>
                 </Card>
             )}
          </div>

          {/* Right Column: Data Preview */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center">
                    <div className="mb-2 sm:mb-0"><CardTitle>Data Preview</CardTitle><CardDescription>A sample of rows from the dataset ({totalDatasetRows > 0 ? `${totalDatasetRows} total rows` : "N/A total rows"}).</CardDescription></div>
                    <Button onClick={handleDownloadDataset} disabled={!isDatasetReady || isLoadingPreview} size="sm"><Download className="mr-2 h-4 w-4" /> Download (CSV)</Button>
                </div>
              </CardHeader>
              <CardContent>
                {isLoadingPreview && (<div className="flex justify-center items-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>)}
                {previewError && !isLoadingPreview && (<Alert variant="destructive"><AlertCircle className="h-4 w-4"/><AlertDescription>{previewError}</AlertDescription></Alert>)}
                {!isLoadingPreview && !previewError && !isDatasetReady && (<div className="text-center py-10 text-muted-foreground">Dataset not ready for preview. Current status: {displayDatasetStatus.text}</div>)}
                {!isLoadingPreview && !previewError && isDatasetReady && dataPreview.length === 0 && (<div className="text-center py-10 text-muted-foreground">No data to preview (dataset might be empty or preview could not load).</div>)}
                {!isLoadingPreview && !previewError && isDatasetReady && dataPreview.length > 0 && (
                  <>
                    <ScrollArea className="w-full whitespace-nowrap rounded-md border mb-4"><Table className="min-w-full"><TableHeader><TableRow>{previewColumns.map(col => <TableHead key={col} className="text-xs px-2 py-1 whitespace-nowrap font-semibold">{col}</TableHead>)}</TableRow></TableHeader>
                        <TableBody>{dataPreview.map((row, rowIndex) => (<TableRow key={`row-${rowIndex}`}>{previewColumns.map(col => (<TableCell key={`${col}-${rowIndex}`} className="text-xs px-2 py-1 whitespace-nowrap truncate max-w-[150px]" title={String(row[col])}>{String(row[col])}</TableCell>))}</TableRow>))}</TableBody></Table><ScrollBar orientation="horizontal" />
                    </ScrollArea>
                    {totalPagesForPreview > 1 && (
                      <Pagination> <PaginationContent> <PaginationItem><PaginationPrevious onClick={() => handlePreviewPageChange(currentPage - 1)} aria-disabled={currentPage <= 1} className={currentPage <= 1 ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
                          {Array.from({ length: totalPagesForPreview }, (_, i) => i + 1).filter(pn => totalPagesForPreview <= 7 || pn === 1 || pn === totalPagesForPreview || (pn >= currentPage - 2 && pn <= currentPage + 2)).map((pn, idx, arr) => {
                            const isEllipsis = idx > 0 && arr[idx-1] + 1 < pn && typeof arr[idx-1] === 'number';
                            return <React.Fragment key={`page-frag-${pn}`}>{isEllipsis && <PaginationEllipsis />}<PaginationItem><PaginationLink onClick={() => handlePreviewPageChange(pn)} isActive={currentPage === pn}>{pn}</PaginationLink></PaginationItem></React.Fragment>
                          })}
                          <PaginationItem><PaginationNext onClick={() => handlePreviewPageChange(currentPage + 1)} aria-disabled={currentPage >= totalPagesForPreview} className={currentPage >= totalPagesForPreview ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
                        </PaginationContent></Pagination>)}
                    <div className="text-center text-sm text-muted-foreground mt-2">{totalDatasetRows > 0 ? `Page ${currentPage} of ${totalPagesForPreview}` : "No rows to display"}</div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </PageContainer>
    </MainLayout>
  );
}

export default function DatasetDetailPage() {
  return (
    <Suspense fallback={<PageLoader message="Loading dataset details..." />}>
      <DatasetDetailPageContent />
    </Suspense>
  );
}