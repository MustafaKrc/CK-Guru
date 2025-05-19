// frontend/app/datasets/[id]/page.tsx
"use client";

import React, { useState, useEffect, useMemo } from "react"; // Removed useCallback as it's not used directly now
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, Download, RefreshCw, Trash2, AlertCircle, Loader2, Database, BarChart3, Settings, FileJson, Play, CheckCircle, Puzzle, ListFilter, TargetIcon, Plus } from "lucide-react"; // Added ListFilter, TargetIcon
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
import { DatasetRead, DatasetConfig } from "@/types/api/dataset";
import { MLModelRead, PaginatedMLModelRead } from "@/types/api/ml-model"; // Corrected import

import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { DatasetStatusEnum, JobStatusEnum } from "@/types/api/enums";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Label } from "@/components/ui/label";

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

function formatDate(dateString: string | Date | undefined): string {
  if (!dateString) return "-";
  const date = typeof dateString === "string" ? new Date(dateString) : dateString;
  return date.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export default function DatasetDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const { toast } = useToast();
  const datasetId = params.id;

  const [dataset, setDataset] = useState<DatasetRead | null>(null);
  const [isLoadingDataset, setIsLoadingDataset] = useState(true);
  const [datasetError, setDatasetError] = useState<string | null>(null);

  const [dataPreview, setDataPreview] = useState<Record<string, any>[]>([]);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  // totalPreviewRows is replaced by totalDatasetRows for pagination source of truth
  const [totalDatasetRows, setTotalDatasetRows] = useState(0); 
  
  const [modelsTrained, setModelsTrained] = useState<MLModelRead[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  
  const { taskStatuses } = useTaskStore();

  const liveDatasetStatus = useMemo(() => {
    if (!datasetId) return undefined;
    return getLatestTaskForEntity(taskStatuses, "Dataset", datasetId, "dataset_generation");
  }, [taskStatuses, datasetId]);

  const fetchDatasetDetails = React.useCallback(async () => {
    if (!datasetId) return;
    setIsLoadingDataset(true);
    setDatasetError(null);
    try {
      const fetchedDataset = await apiService.get<DatasetRead>(`/datasets/${datasetId}`);
      setDataset(fetchedDataset);
      if (fetchedDataset?.num_rows !== undefined && fetchedDataset.num_rows !== null) {
        setTotalDatasetRows(fetchedDataset.num_rows);
      }
      if (fetchedDataset?.status === "ready") {
        fetchDataPreview(1); // Fetch first page of preview
      }
    } catch (err) {
      handleApiError(err, "Failed to fetch dataset details");
      setDatasetError(err instanceof Error ? err.message : "Dataset not found or error loading.");
    } finally {
      setIsLoadingDataset(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [datasetId]); // fetchDataPreview is stable due to its own useCallback or definition outside effects

  // Fetch main dataset details on initial load or when datasetId changes
  useEffect(() => {
    fetchDatasetDetails();
  }, [fetchDatasetDetails]);

  // Fetch data preview
  const fetchDataPreview = async (page: number) => {
    if (!datasetId || dataset?.status !== "ready") return;
    setIsLoadingPreview(true);
    setPreviewError(null);
    setCurrentPage(page);
    const skip = (page - 1) * ROWS_PER_PAGE;
    try {
      const previewData = await apiService.get<Record<string, any>[]>(
        `/datasets/${datasetId}/view?skip=${skip}&limit=${ROWS_PER_PAGE}`
      );
      setDataPreview(previewData || []); // Ensure it's an array
    } catch (err) {
      handleApiError(err, "Failed to fetch data preview");
      setPreviewError(err instanceof Error ? err.message : "Could not load preview.");
      setDataPreview([]);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  // Fetch models trained on this dataset
  useEffect(() => {
    const fetchModels = async () => {
      if (!datasetId) return;
      setIsLoadingModels(true);
      setModelsTrained([]);
      try {
        const response = await apiService.get<PaginatedMLModelRead>(`/ml/models?dataset_id=${datasetId}&limit=100`);
        if (response && Array.isArray(response.items)) {
          setModelsTrained(response.items);
        } else {
          setModelsTrained([]);
        }
      } catch (err) {
        handleApiError(err, "Failed to fetch trained models");
        setModelsTrained([]);
      } finally {
        setIsLoadingModels(false);
      }
    };
    if(dataset) { // Only fetch models if dataset details are loaded
        fetchModels();
    }
  }, [datasetId, dataset]); // Re-fetch if dataset itself changes (e.g. after re-generation)

  const totalPagesForPreview = useMemo(() => {
    if (!totalDatasetRows) return 0;
    return Math.ceil(totalDatasetRows / ROWS_PER_PAGE);
  }, [totalDatasetRows]);

  const handlePreviewPageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPagesForPreview) {
      fetchDataPreview(newPage);
    }
  };

   useEffect(() => {
    if (liveDatasetStatus?.status === JobStatusEnum.SUCCESS && dataset?.status !== "ready") {
      toast({title: "Dataset Ready!", description: `Dataset ${dataset?.name || datasetId} is now ready.`});
      // Re-fetch all dataset details, which will in turn trigger preview if ready
      const fetchDetails = async () => {
        if (!datasetId) return;
        setIsLoadingDataset(true); setDatasetError(null);
        try {
          const fetchedDataset = await apiService.get<DatasetRead>(`/datasets/${datasetId}`);
          setDataset(fetchedDataset);
          if (fetchedDataset?.num_rows !== undefined && fetchedDataset.num_rows !== null) {
            setTotalDatasetRows(fetchedDataset.num_rows);
          }
          if (fetchedDataset?.status === "ready") {
            fetchDataPreview(1); 
          }
        } catch (err) { handleApiError(err, "Failed to fetch dataset details"); setDatasetError(err instanceof Error ? err.message : "Dataset not found or error loading.");
        } finally { setIsLoadingDataset(false); }
      };
      fetchDetails();
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
        toast({ title: "Regeneration Requested", description: `Regeneration for dataset ${dataset.name} requested. (Placeholder - Backend not implemented)`, variant: "default" });
        // To make it seem like it's working, we can simulate status change
        // setDataset(prev => prev ? ({...prev, status: "pending", status_message: "Regeneration requested..."}) : null);
        // And then refetch after a delay, or rely on SSE to update if backend were real
         const fetchDetails = async () => { /* ... */ }; // as in useEffect
         fetchDetails();
    } catch (err) { handleApiError(err, "Failed to request dataset regeneration"); }
  };

  const getDisplayDatasetStatusInfo = () => {
    if (isLoadingDataset && !dataset) return { text: "Loading Info...", badgeVariant: "outline" as const, icon: <Loader2 className="h-4 w-4 animate-spin" /> };
    if (datasetError) return { text: "Error Loading", badgeVariant: "destructive" as const, icon: <AlertCircle className="h-4 w-4" /> };
    if (!dataset) return { text: "Not Found", badgeVariant: "destructive" as const };

    const currentStatus = liveDatasetStatus || { status: dataset.status, progress: null, status_message: dataset.status_message };
    const statusString = String(currentStatus.status).toUpperCase();

    if (statusString === "GENERATING" || statusString === "PENDING" || statusString === "RUNNING" ) {
      return { 
        text: `${currentStatus.status_message || statusString} (${currentStatus.progress ?? 0}%)`,
        badgeVariant: "outline" as const,
        icon: <RefreshCw className="h-4 w-4 animate-spin" />
      };
    }
    if (statusString === "READY" || statusString === "SUCCESS") return { text: "Ready", badgeVariant: "default" as const, icon: <CheckCircle className="h-4 w-4 text-green-600"/> };
    if (statusString === "FAILED") return { text: `Failed: ${currentStatus.status_message || "Unknown error"}`, badgeVariant: "destructive" as const, icon: <AlertCircle className="h-4 w-4" /> };
    
    return { text: statusString, badgeVariant: "secondary" as const };
  };

  const displayDatasetStatus = getDisplayDatasetStatusInfo();
  const previewColumns = useMemo(() => dataPreview.length > 0 ? Object.keys(dataPreview[0]) : [], [dataPreview]);

  if (isLoadingDataset && !dataset && !datasetError) { /* ... loading UI ... */ 
    return (
        <MainLayout>
          <PageContainer title="Loading Dataset..." description="Fetching dataset details...">
            <Skeleton className="h-12 w-1/2 mb-4" />
            <div className="space-y-4"> <Skeleton className="h-32 w-full" /> <Skeleton className="h-64 w-full" /> <Skeleton className="h-40 w-full" /></div>
          </PageContainer>
        </MainLayout>
      );
  }
  if (datasetError || !dataset) { /* ... error UI ... */ 
    return (
        <MainLayout>
          <PageContainer title="Dataset Not Found" description={datasetError || "The requested dataset could not be found."}
            actions={<Button onClick={() => router.back()} variant="outline"><ArrowLeft className="mr-2 h-4 w-4"/> Back</Button>} >
             <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>Please check the dataset ID.</AlertDescription></Alert>
          </PageContainer>
        </MainLayout>
      );
  }

  const pageActions = ( 
    <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => { fetchDatasetDetails(); if (dataset.status === 'ready') fetchDataPreview(1);}} disabled={isLoadingDataset || (displayDatasetStatus.icon?.type === RefreshCw && displayDatasetStatus.icon.props.className.includes('animate-spin'))}>
            <RefreshCw className={`mr-2 h-4 w-4 ${(isLoadingDataset || (displayDatasetStatus.icon?.type === RefreshCw && displayDatasetStatus.icon.props.className.includes('animate-spin'))) ? 'animate-spin' : ''}`} />
            Refresh
        </Button>
        <AlertDialog>
            <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm" disabled={(displayDatasetStatus.icon?.type === RefreshCw && displayDatasetStatus.icon.props.className.includes('animate-spin'))}><Trash2 className="mr-2 h-4 w-4" /> Delete</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
                <AlertDialogHeader><AlertDialogTitle>Are you sure?</AlertDialogTitle><AlertDialogDescription>This will permanently delete the dataset definition and queue data deletion from storage.</AlertDialogDescription></AlertDialogHeader>
                <AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction onClick={handleDeleteDataset}>Delete</AlertDialogAction></AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    </div>
  );

  return (
    <MainLayout>
      <PageContainer 
        title={dataset.name}
        description={ <div className="flex items-center gap-2"> <Link href={`/repositories/${dataset.repository_id}`} className="text-sm text-primary hover:underline">Repo ID: {dataset.repository_id}</Link> <Badge variant={displayDatasetStatus.badgeVariant} className="text-xs px-2 py-0.5">{displayDatasetStatus.icon && <span className="mr-1.5">{displayDatasetStatus.icon}</span>}{displayDatasetStatus.text}</Badge> </div> }
        actions={pageActions}
        className="px-4 md:px-6 lg:px-8"
      >
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-6">
            {/* CONFIGURATION CARD */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center"><Settings className="mr-2 h-5 w-5 text-primary"/>Configuration</CardTitle>
                <CardDescription>Details of how this dataset was generated.</CardDescription>
              </CardHeader>
              <CardContent className="text-sm space-y-4">
                <div>
                  <Label className="text-muted-foreground flex items-center"><TargetIcon className="h-3.5 w-3.5 mr-1.5"/>Target Column</Label> 
                  <Badge variant="secondary" className="mt-1">{dataset.config.target_column}</Badge>
                </div>
                <div>
                  <Label className="text-muted-foreground flex items-center"><ListFilter className="h-3.5 w-3.5 mr-1.5"/>Feature Columns ({dataset.config.feature_columns.length})</Label>
                  <ScrollArea className="h-24 mt-1 rounded-md border p-2 text-xs bg-muted/10">
                    <ul className="list-disc list-inside pl-2 space-y-0.5">
                      {dataset.config.feature_columns.map(fc => <li key={fc} className="truncate" title={fc}>{fc}</li>)}
                    </ul>
                  </ScrollArea>
                </div>
                <div>
                  <Label className="text-muted-foreground flex items-center"><FileJson className="h-3.5 w-3.5 mr-1.5"/>Cleaning Rules Applied ({dataset.config.cleaning_rules.filter(r => r.enabled).length})</Label>
                  {dataset.config.cleaning_rules.filter(r => r.enabled).length > 0 ? (
                    <ScrollArea className="h-32 mt-1 rounded-md border p-2 text-xs bg-muted/10">
                      <ul className="space-y-1.5">
                      {dataset.config.cleaning_rules.filter(r => r.enabled).map(rule => (
                        <li key={rule.name} className="border-b border-dashed pb-1 last:border-b-0">
                          <span className="font-medium">{rule.name}</span>
                          {rule.params && Object.keys(rule.params).length > 0 && (
                            <dl className="mt-0.5 pl-3 text-xs">
                              {Object.entries(rule.params).map(([paramKey, paramValue]) => (
                                <div key={paramKey} className="flex">
                                  <dt className="text-muted-foreground w-20 truncate">{paramKey}:</dt>
                                  <dd className="font-mono">{String(paramValue)}</dd>
                                </div>
                              ))}
                            </dl>
                          )}
                        </li>
                      ))}
                      </ul>
                    </ScrollArea>
                  ) : <p className="text-xs text-muted-foreground italic mt-1">No cleaning rules were enabled.</p>}
                </div>
                {dataset.description && (
                    <div><Label className="text-muted-foreground">Description</Label> <p className="text-xs italic bg-muted/10 p-2 rounded-md">{dataset.description}</p></div>
                )}
                <div className="flex justify-between pt-2 border-t text-xs text-muted-foreground">
                    <span>Created: {formatDate(dataset.created_at)}</span>
                    <span>Updated: {formatDate(dataset.updated_at)}</span>
                </div>
                 {dataset.status_message && 
                  displayDatasetStatus.text !== DatasetStatusEnum.READY && 
                  displayDatasetStatus.text !== JobStatusEnum.SUCCESS && // Also check against JobStatusEnum.SUCCESS if liveStatus could use it
                  !(displayDatasetStatus.icon?.type === RefreshCw && displayDatasetStatus.icon.props.className.includes('animate-spin')) && // Don't show if actively processing
                  (
                    <Alert 
                        variant={displayDatasetStatus.text === DatasetStatusEnum.FAILED || displayDatasetStatus.text === JobStatusEnum.FAILED ? "destructive" : "default"} 
                        className="mt-2 text-xs"
                    >
                        <AlertCircle className="h-3 w-3"/>
                        <AlertDescription>{dataset.status_message}</AlertDescription>
                    </Alert>
                  )
                 }
              </CardContent>
              <CardFooter className="flex-col items-start gap-2">
                <Button variant="outline" size="sm" className="w-full" onClick={handleRegenerateDataset} disabled={(displayDatasetStatus.icon?.type === RefreshCw && displayDatasetStatus.icon.props.className.includes('animate-spin'))}>
                    <RefreshCw className="mr-2 h-4 w-4" /> Re-generate Dataset
                </Button>
              </CardFooter>
            </Card>

            {/* Models Trained Card */}
            <Card>
                <CardHeader className="pb-3"><CardTitle className="flex items-center"><Puzzle className="mr-2 h-5 w-5 text-primary"/>Models Trained</CardTitle><CardDescription>ML models trained using this dataset.</CardDescription></CardHeader>
                <CardContent>
                    {isLoadingModels ? <Skeleton className="h-20 w-full" /> : 
                     modelsTrained.length === 0 ? <p className="text-sm text-muted-foreground py-3 text-center">No models trained with this dataset.</p> :
                     <ul className="space-y-2">
                        {modelsTrained.map(model => (
                            <li key={model.id} className="text-sm flex justify-between items-center py-1.5 border-b last:border-b-0">
                                <Link href={`/models/${model.id}`} className="font-medium hover:underline truncate pr-2" title={model.name}>{model.name} (v{model.version})</Link>
                                <Badge variant="outline">{model.model_type}</Badge>
                            </li>
                        ))}
                     </ul>
                    }
                     {modelsTrained.length === 0 && !isLoadingModels && dataset.status === DatasetStatusEnum.READY && (
                        <Button size="sm" className="w-full mt-3" asChild>
                            <Link href={`/jobs/train?datasetId=${datasetId}`}><Plus className="mr-2 h-4 w-4" /> Train New Model</Link>
                        </Button>
                    )}
                </CardContent>
            </Card>
          </div>

          {/* Data Preview Card (no change from previous) */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                    <div><CardTitle>Data Preview</CardTitle><CardDescription>A sample of rows from the dataset ({totalDatasetRows > 0 ? `${totalDatasetRows} total rows` : "N/A total rows"}).</CardDescription></div>
                    <Button onClick={handleDownloadDataset} disabled={dataset.status !== "ready" || isLoadingPreview} size="sm"><Download className="mr-2 h-4 w-4" /> Download Full Dataset (CSV)</Button>
                </div>
              </CardHeader>
              <CardContent>
                {isLoadingPreview && (<div className="flex justify-center items-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>)}
                {previewError && !isLoadingPreview && (<Alert variant="destructive"><AlertCircle className="h-4 w-4"/><AlertDescription>{previewError}</AlertDescription></Alert>)}
                {!isLoadingPreview && !previewError && dataset.status !== "ready" && (<div className="text-center py-10 text-muted-foreground">Dataset not ready for preview. Status: {displayDatasetStatus.text}</div>)}
                {!isLoadingPreview && !previewError && dataset.status === "ready" && dataPreview.length === 0 && (<div className="text-center py-10 text-muted-foreground">No data to preview (dataset might be empty or preview failed to load).</div>)}
                {!isLoadingPreview && !previewError && dataset.status === "ready" && dataPreview.length > 0 && (
                  <>
                    <ScrollArea className="w-full whitespace-nowrap rounded-md border mb-4"><Table className="min-w-full"><TableHeader><TableRow>{previewColumns.map(col => <TableHead key={col} className="text-xs px-2 py-1 whitespace-nowrap">{col}</TableHead>)}</TableRow></TableHeader>
                        <TableBody>{dataPreview.map((row, rowIndex) => (<TableRow key={`row-${rowIndex}`}>{previewColumns.map(col => (<TableCell key={`${col}-${rowIndex}`} className="text-xs px-2 py-1 whitespace-nowrap truncate max-w-[150px]" title={String(row[col])}>{String(row[col])}</TableCell>))}</TableRow>))}</TableBody></Table><ScrollBar orientation="horizontal" />
                    </ScrollArea>
                    {totalPagesForPreview > 1 && (
                      <Pagination> <PaginationContent> <PaginationItem><PaginationPrevious onClick={() => handlePreviewPageChange(currentPage - 1)} aria-disabled={currentPage <= 1} className={currentPage <= 1 ? "pointer-events-none opacity-50" : ""} /></PaginationItem>
                          {Array.from({ length: totalPagesForPreview }, (_, i) => i + 1).filter(pn => totalPagesForPreview <= 7 || pn === 1 || pn === totalPagesForPreview || (pn >= currentPage - 1 && pn <= currentPage + 1)).map((pn, idx, arr) => (<React.Fragment key={`page-${pn}`}>{idx > 0 && arr[idx-1] + 1 < pn && <PaginationEllipsis />}<PaginationItem><PaginationLink onClick={() => handlePreviewPageChange(pn)} isActive={currentPage === pn}>{pn}</PaginationLink></PaginationItem></React.Fragment>))}
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