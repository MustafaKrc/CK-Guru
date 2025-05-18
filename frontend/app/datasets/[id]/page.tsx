"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, Download, RefreshCw, Trash2, AlertCircle, Loader2, Database, BarChart3, ChevronLeft, ChevronRight, Settings, FileJson, Play, CheckCircle, Puzzle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"; // For data preview table
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
import { DatasetRead, DatasetConfig } from "@/types/api/dataset"; // Make sure DatasetConfig is exported from your types
import { MLModelRead } from "@/types/api/ml-model";

import { useTaskStore, TaskStatusUpdatePayload } from "@/store/taskStore";
import { getLatestTaskForEntity } from "@/lib/taskUtils";
import { JobStatusEnum } from "@/types/api/enums"; // For status comparison
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
} from "@/components/ui/pagination"

const ROWS_PER_PAGE = 10;

// Simple date formatting helper
function formatDate(dateString: string | Date | undefined): string {
  if (!dateString) return "-";
  const date = typeof dateString === "string" ? new Date(dateString) : dateString;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
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
  const [totalPreviewRows, setTotalPreviewRows] = useState(0); // We won't know this accurately yet
  const [canFetchMore, setCanFetchMore] = useState(true);


  const [modelsTrained, setModelsTrained] = useState<MLModelRead[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);

  const [totalDatasetRows, setTotalDatasetRows] = useState(0); 
  
  const { taskStatuses } = useTaskStore();

  // Memoized live status for the current dataset
  const liveDatasetStatus = useMemo(() => {
    if (!datasetId) return undefined;
    return getLatestTaskForEntity(taskStatuses, "Dataset", datasetId, "dataset_generation");
  }, [taskStatuses, datasetId]);

  const effectiveDatasetStatus = useMemo(() => {
    return liveDatasetStatus || dataset?.status; // Prioritize live SSE status
  }, [liveDatasetStatus, dataset?.status]);


  const fetchDatasetDetails = async () => {
    if (!datasetId) return;
    setIsLoadingDataset(true);
    setDatasetError(null);
    try {
      const fetchedDataset = await apiService.get<DatasetRead>(`/datasets/${datasetId}`);
      setDataset(fetchedDataset);
      if (fetchedDataset?.num_rows !== undefined && fetchedDataset.num_rows !== null) { // Check if num_rows is available
        setTotalDatasetRows(fetchedDataset.num_rows);
      }
      if (fetchedDataset?.status === "ready") {
        fetchDataPreview(1, true); 
      }
    } catch (err) {
      handleApiError(err, "Failed to fetch dataset details");
      setDatasetError(err instanceof Error ? err.message : "Dataset not found or error loading.");
    } finally {
      setIsLoadingDataset(false);
    }
  };

  const fetchDataPreview = async (page: number, _isInitialLoad = false) => { // _isInitialLoad no longer needed for total count
    if (!datasetId || dataset?.status !== "ready") return;
    setIsLoadingPreview(true);
    setPreviewError(null);
    setCurrentPage(page); // Update current page state
    const skip = (page - 1) * ROWS_PER_PAGE;
    try {
      const previewData = await apiService.get<Record<string, any>[]>(
        `/datasets/${datasetId}/view?skip=${skip}&limit=${ROWS_PER_PAGE}`
      );
      setDataPreview(previewData);
      // canFetchMore is now determined by totalDatasetRows and currentPage
    } catch (err) {
      handleApiError(err, "Failed to fetch data preview");
      setPreviewError(err instanceof Error ? err.message : "Could not load preview.");
      setDataPreview([]); // Clear preview on error
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const fetchModelsTrained = async () => {
    if (!datasetId) return;
    setIsLoadingModels(true);
    try {
      const modelsData = await apiService.get<MLModelRead[]>(`/ml/models?dataset_id=${datasetId}`);
      setModelsTrained(modelsData);
    } catch (err) {
      handleApiError(err, "Failed to fetch trained models");
    } finally {
      setIsLoadingModels(false);
    }
  };

  const totalPages = useMemo(() => {
    if (!totalDatasetRows) return 0;
    return Math.ceil(totalDatasetRows / ROWS_PER_PAGE);
  }, [totalDatasetRows]);

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      fetchDataPreview(newPage);
    }
  };

  useEffect(() => {
    fetchDatasetDetails();
    fetchModelsTrained();
  }, [datasetId]);

  // Effect to refetch preview if dataset becomes ready via SSE
   useEffect(() => {
    if (liveDatasetStatus?.status === "SUCCESS" && dataset?.status !== "ready") {
      // If SSE says success, and local state isn't ready yet, refresh all dataset details
      toast({title: "Dataset Ready!", description: `Dataset ${dataset?.name || datasetId} is now ready.`});
      fetchDatasetDetails(); // This will re-fetch dataset details and then preview
    }
  }, [liveDatasetStatus, dataset?.status, datasetId, dataset?.name]);


  const handleDownloadDataset = () => {
    if (!datasetId) return;
    // Direct browser navigation handles the download
    window.location.href = `${process.env.NEXT_PUBLIC_API_URL || ''}/api/v1/datasets/${datasetId}/download`;
    toast({ title: "Download Initialized", description: "Your dataset download should start shortly." });
  };

  const handleDeleteDataset = async () => {
    if (!datasetId || !dataset) return;
    try {
        await apiService.delete<void>(`/datasets/${datasetId}`);
        toast({ title: "Dataset Deleted", description: `Dataset ${dataset.name} has been marked for deletion.`});
        router.push(`/repositories/${dataset.repository_id}`); // Navigate back to repo detail or datasets list
    } catch (err) {
        handleApiError(err, "Failed to delete dataset");
    }
  };
  
  const handleRegenerateDataset = async () => {
    if (!datasetId || !dataset) return;
    // This would ideally call a dedicated regenerate endpoint.
    // For now, simulating a re-trigger:
    try {
        // This is a simplified re-trigger. Backend might need specific logic.
        // If backend supports re-triggering the original task for dataset ID:
        // await apiService.post(`/datasets/${datasetId}/trigger-task`);
        toast({ title: "Regeneration Requested", description: `Regeneration for dataset ${dataset.name} requested. (Not fully implemented)`, variant: "default" });
        // Potentially set dataset status to PENDING and refresh details
        fetchDatasetDetails();
    } catch (err) {
        handleApiError(err, "Failed to request dataset regeneration");
    }
  };

  const getDisplayDatasetStatusInfo = () => {
    if (isLoadingDataset && !dataset) return { text: "Loading Info...", badgeVariant: "outline" as const, icon: <Loader2 className="h-4 w-4 animate-spin" /> };
    if (datasetError) return { text: "Error Loading", badgeVariant: "destructive" as const, icon: <AlertCircle className="h-4 w-4" /> };
    if (!dataset) return { text: "Not Found", badgeVariant: "destructive" as const };

    const currentStatus = liveDatasetStatus || { status: dataset.status, progress: null, status_message: dataset.status_message };

    if (currentStatus.status === "GENERATING" || currentStatus.status === "PENDING" || (typeof currentStatus.status === 'string' && (currentStatus.status.toUpperCase() === "RUNNING" || currentStatus.status.toUpperCase() === "PENDING"))) {
      return { 
        text: `${currentStatus.status_message || currentStatus.status} (${currentStatus.progress ?? 0}%)`,
        badgeVariant: "outline" as const,
        icon: <RefreshCw className="h-4 w-4 animate-spin" />
      };
    }
    if (currentStatus.status === "READY" || currentStatus.status === "SUCCESS") return { text: "Ready", badgeVariant: "default" as const, icon: <CheckCircle className="h-4 w-4 text-green-600"/> };
    if (currentStatus.status === "FAILED") return { text: `Failed: ${currentStatus.status_message || ""}`, badgeVariant: "destructive" as const, icon: <AlertCircle className="h-4 w-4" /> };
    
    return { text: String(currentStatus.status).toUpperCase(), badgeVariant: "secondary" as const };
  };

  const displayDatasetStatus = getDisplayDatasetStatusInfo();

  const previewColumns = useMemo(() => {
    if (dataPreview.length === 0) return [];
    return Object.keys(dataPreview[0]);
  }, [dataPreview]);

  if (isLoadingDataset && !dataset && !datasetError) {
    return (
      <MainLayout>
        <PageContainer title="Loading Dataset..." description="Fetching dataset details...">
          <Skeleton className="h-12 w-1/2 mb-4" />
          <div className="space-y-4">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        </PageContainer>
      </MainLayout>
    );
  }

  if (datasetError || !dataset) {
    return (
      <MainLayout>
        <PageContainer
          title="Dataset Not Found"
          description={datasetError || "The requested dataset could not be found or an error occurred."}
          actions={<Button onClick={() => router.back()} variant="outline"><ArrowLeft className="mr-2 h-4 w-4"/> Back</Button>}
        >
           <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                    Please check the dataset ID or try again later.
                </AlertDescription>
            </Alert>
        </PageContainer>
      </MainLayout>
    );
  }

  // Actions for PageContainer
  const pageActions = (
    <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={fetchDatasetDetails} disabled={isLoadingDataset || displayDatasetStatus.icon?.type === RefreshCw}>
            <RefreshCw className={`mr-2 h-4 w-4 ${(isLoadingDataset || displayDatasetStatus.icon?.type === RefreshCw) ? 'animate-spin' : ''}`} />
            Refresh
        </Button>
        <AlertDialog>
            <AlertDialogTrigger asChild>
                <Button variant="destructive" size="sm" disabled={displayDatasetStatus.icon?.type === RefreshCw}><Trash2 className="mr-2 h-4 w-4" /> Delete Dataset</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
                <AlertDialogHeader><AlertDialogTitle>Are you sure?</AlertDialogTitle><AlertDialogDescription>This action cannot be undone. This will permanently delete the dataset definition and queue the deletion of its data from storage.</AlertDialogDescription></AlertDialogHeader>
                <AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction onClick={handleDeleteDataset}>Delete</AlertDialogAction></AlertDialogFooter>
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
                <Link href={`/repositories/${dataset.repository_id}`} className="text-sm text-primary hover:underline">
                    Repo ID: {dataset.repository_id}
                </Link>
                <Badge variant={displayDatasetStatus.badgeVariant} className="text-xs px-2 py-0.5">
                    {displayDatasetStatus.icon && <span className="mr-1.5">{displayDatasetStatus.icon}</span>}
                    {displayDatasetStatus.text}
                </Badge>
            </div>
        }
        actions={pageActions}
        className="px-4 md:px-6 lg:px-8"
      >
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Column 1: Config & Models */}
          <div className="lg:col-span-1 space-y-6">
            <Card>
              <CardHeader><CardTitle>Configuration</CardTitle><CardDescription>Details of how this dataset was generated.</CardDescription></CardHeader>
              <CardContent className="text-sm space-y-3">
                <div><Label className="text-muted-foreground">Target Column:</Label> <Badge variant="secondary">{dataset.config.target_column}</Badge></div>
                <div>
                  <Label className="text-muted-foreground">Feature Columns ({dataset.config.feature_columns.length}):</Label>
                  <ScrollArea className="h-20 mt-1 rounded-md border p-2 text-xs">
                    <ul className="list-disc list-inside">
                      {dataset.config.feature_columns.map(fc => <li key={fc} className="truncate" title={fc}>{fc}</li>)}
                    </ul>
                  </ScrollArea>
                </div>
                <div>
                  <Label className="text-muted-foreground">Cleaning Rules Applied ({dataset.config.cleaning_rules.filter(r => r.enabled).length}):</Label>
                  {dataset.config.cleaning_rules.filter(r => r.enabled).length > 0 ? (
                    <ScrollArea className="h-24 mt-1 rounded-md border p-2 text-xs">
                      <ul className="space-y-1">
                      {dataset.config.cleaning_rules.filter(r => r.enabled).map(rule => (
                        <li key={rule.name} className="truncate" title={rule.name}>
                          {rule.name} 
                          {rule.params && Object.keys(rule.params).length > 0 && 
                           <span className="text-muted-foreground text-xs ml-1">({JSON.stringify(rule.params)})</span>}
                        </li>
                      ))}
                      </ul>
                    </ScrollArea>
                  ) : <p className="text-xs text-muted-foreground italic mt-1">No cleaning rules enabled.</p>}
                </div>
                {dataset.description && (
                    <div><Label className="text-muted-foreground">Description:</Label> <p className="text-xs italic">{dataset.description}</p></div>
                )}
                <div className="flex justify-between pt-2 border-t">
                    <span className="text-xs text-muted-foreground">Created: {formatDate(dataset.created_at)}</span>
                    <span className="text-xs text-muted-foreground">Updated: {formatDate(dataset.updated_at)}</span>
                </div>
                 {dataset.status_message && <Alert variant={dataset.status === "failed" ? "destructive" : "default"} className="mt-2 text-xs"><AlertCircle className="h-3 w-3"/><AlertDescription>{dataset.status_message}</AlertDescription></Alert>}
              </CardContent>
              <CardFooter className="flex-col items-start gap-2">
                <Button variant="outline" size="sm" className="w-full" onClick={handleRegenerateDataset} disabled={displayDatasetStatus.icon?.type === RefreshCw}>
                    <RefreshCw className="mr-2 h-4 w-4" /> Re-generate Dataset (if config changed)
                </Button>
              </CardFooter>
            </Card>

            <Card>
                <CardHeader className="pb-3"><CardTitle>Models Trained</CardTitle><CardDescription>ML models trained using this dataset.</CardDescription></CardHeader>
                <CardContent>
                    {isLoadingModels ? <Skeleton className="h-20 w-full" /> : 
                     modelsTrained.length === 0 ? <p className="text-sm text-muted-foreground py-3 text-center">No models have been trained with this dataset yet.</p> :
                     <ul className="space-y-2">
                        {modelsTrained.map(model => (
                            <li key={model.id} className="text-sm flex justify-between items-center py-1.5 border-b last:border-b-0">
                                <Link href={`/models/${model.id}`} className="font-medium hover:underline truncate pr-2" title={model.name}>{model.name} (v{model.version})</Link>
                                <Badge variant="outline">{model.model_type}</Badge>
                            </li>
                        ))}
                     </ul>
                    }
                     {modelsTrained.length === 0 && !isLoadingModels && (
                        <Button size="sm" className="w-full mt-3" asChild>
                            <Link href={`/jobs/train?datasetId=${datasetId}`}><Puzzle className="mr-2 h-4 w-4" /> Train New Model</Link>
                        </Button>
                    )}
                </CardContent>
            </Card>
          </div>

          {/* Column 2: Data Preview */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                    <div>
                        <CardTitle>Data Preview</CardTitle>
                        <CardDescription>A sample of rows from the dataset.</CardDescription>
                    </div>
                    <Button 
                        onClick={handleDownloadDataset} 
                        disabled={dataset.status !== "ready" || isLoadingPreview}
                        size="sm"
                    >
                        <Download className="mr-2 h-4 w-4" /> Download Full Dataset (CSV)
                    </Button>
                </div>
              </CardHeader>
              <CardContent>
                {isLoadingPreview && (<div className="flex justify-center items-center h-64"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>)}
                {previewError && !isLoadingPreview && (<Alert variant="destructive"><AlertCircle className="h-4 w-4"/><AlertDescription>{previewError}</AlertDescription></Alert>)}
                {!isLoadingPreview && !previewError && dataset.status !== "ready" && (
                    <div className="text-center py-10 text-muted-foreground">
                        Dataset is not ready for preview. Current status: {displayDatasetStatus.text}
                    </div>
                )}
                {!isLoadingPreview && !previewError && dataset.status === "ready" && dataPreview.length === 0 && (
                    <div className="text-center py-10 text-muted-foreground">No data to preview for this dataset (it might be empty).</div>
                )}
                {!isLoadingPreview && !previewError && dataset.status === "ready" && dataPreview.length > 0 && (
                  <>
                    <ScrollArea className="w-full whitespace-nowrap rounded-md border mb-4">
                      <Table className="min-w-full">
                        <TableHeader>
                          <TableRow>
                            {previewColumns.map(col => <TableHead key={col} className="text-xs px-2 py-1 whitespace-nowrap">{col}</TableHead>)}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {dataPreview.map((row, rowIndex) => (
                            <TableRow key={`row-${rowIndex}`}>
                              {previewColumns.map(col => (
                                <TableCell key={`${col}-${rowIndex}`} className="text-xs px-2 py-1 whitespace-nowrap truncate max-w-[150px]" title={String(row[col])}>
                                  {String(row[col])}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                      <ScrollBar orientation="horizontal" />
                    </ScrollArea>
                    {/* PAGINATION COMPONENT INTEGRATION */}
                    {totalPages > 1 && (
                      <Pagination>
                        <PaginationContent>
                          <PaginationItem>
                            <PaginationPrevious
                              onClick={() => handlePageChange(currentPage - 1)}
                              aria-disabled={currentPage <= 1}
                              className={currentPage <= 1 ? "pointer-events-none opacity-50" : undefined}
                            />
                          </PaginationItem>
                          
                          {/* Simplified pagination items - can be made more complex with page numbers & ellipsis later */}
                          {Array.from({ length: totalPages }, (_, i) => i + 1)
                            // Logic to display only a few page numbers around current page + ellipsis
                            .filter(pageNumber => {
                                if (totalPages <= 7) return true; // Show all if 7 or less
                                // Show first, last, current, and 2 around current
                                return pageNumber === 1 || pageNumber === totalPages || 
                                       (pageNumber >= currentPage - 1 && pageNumber <= currentPage + 1);
                            })
                            .map((pageNumber, index, arr) => {
                                const isEllipsisNeeded = arr[index+1] && arr[index+1] > pageNumber + 1;
                                return (
                                    <React.Fragment key={`page-${pageNumber}`}>
                                        <PaginationItem>
                                        <PaginationLink
                                            onClick={() => handlePageChange(pageNumber)}
                                            isActive={currentPage === pageNumber}
                                        >
                                            {pageNumber}
                                        </PaginationLink>
                                        </PaginationItem>
                                        {isEllipsisNeeded && (
                                            <PaginationItem>
                                                <PaginationEllipsis />
                                            </PaginationItem>
                                        )}
                                    </React.Fragment>
                                );
                            })
                          }
                          
                          <PaginationItem>
                            <PaginationNext
                              onClick={() => handlePageChange(currentPage + 1)}
                              aria-disabled={currentPage >= totalPages}
                              className={currentPage >= totalPages ? "pointer-events-none opacity-50" : undefined}
                            />
                          </PaginationItem>
                        </PaginationContent>
                      </Pagination>
                    )}
                    <div className="text-center text-sm text-muted-foreground mt-2">
                        {totalDatasetRows > 0 ? `Page ${currentPage} of ${totalPages} (${totalDatasetRows} total rows)` : "No rows to display"}
                    </div>
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