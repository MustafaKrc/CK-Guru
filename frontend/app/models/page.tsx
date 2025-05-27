// frontend/app/models/page.tsx
"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation"; // Added useRouter
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
import { MoreHorizontal, Eye, Play, BarChart3, Plus, Loader2, AlertCircle, Layers, Database } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";
import { PageContainer } from "@/components/ui/page-container";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
    Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious, PaginationEllipsis 
} from "@/components/ui/pagination";

import { apiService, handleApiError } from "@/lib/apiService";
import { MLModelRead, PaginatedMLModelRead } from "@/types/api/ml-model";
import { ModelTypeEnum } from "@/types/api/enums";
import { DatasetRead, PaginatedDatasetRead } from "@/types/api/dataset";

const ITEMS_PER_PAGE_MODELS = 10;
const ALL_FILTER_VALUE = "_all_";

export default function ModelsPage() {
  const [models, setModels] = useState<MLModelRead[]>([]);
  const [pagination, setPagination] = useState({ currentPage: 1, totalItems: 0, isLoading: true });
  const [fetchError, setFetchError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<ModelTypeEnum | typeof ALL_FILTER_VALUE>(ALL_FILTER_VALUE);
  const [datasetFilter, setDatasetFilter] = useState<string>(ALL_FILTER_VALUE);

  const [datasets, setDatasets] = useState<DatasetRead[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true); // Changed default to true
  
  const [selectedModelsForComparison, setSelectedModelsForComparison] = useState<string[]>([]);

  const { toast } = useToast();
  const router = useRouter();

  const availableModelTypes = Object.values(ModelTypeEnum);

  const fetchDatasetsForFilter = useCallback(async () => {
    setIsLoadingDatasets(true);
    try {
      const response = await apiService.get<PaginatedDatasetRead>(`/datasets?limit=200&status=ready`);
      setDatasets(response.items || []);
    } catch (err) {
      handleApiError(err, "Failed to fetch datasets for filter");
      setDatasets([]);
    } finally {
      setIsLoadingDatasets(false);
    }
  }, []);

  const fetchModels = useCallback(async (page: number = 1) => {
    setPagination(prev => ({ ...prev, isLoading: true, currentPage: page }));
    setFetchError(null);
    const skip = (page - 1) * ITEMS_PER_PAGE_MODELS;
    
    const params = new URLSearchParams({
      skip: skip.toString(),
      limit: ITEMS_PER_PAGE_MODELS.toString(),
    });
    if (searchQuery) params.append("model_name", searchQuery);
    if (typeFilter && typeFilter !== ALL_FILTER_VALUE) params.append("model_type", typeFilter);
    if (datasetFilter && datasetFilter !== ALL_FILTER_VALUE) params.append("dataset_id", datasetFilter);

    try {
      const response = await apiService.get<PaginatedMLModelRead>(`/ml/models?${params.toString()}`);
      if (response && Array.isArray(response.items) && typeof response.total === 'number') {
        setModels(response.items);
        setPagination(prev => ({ ...prev, totalItems: response.total, isLoading: false }));
      } else {
        console.error("Unexpected response structure for models:", response);
        setFetchError("Received invalid data structure for models.");
        setModels([]);
        setPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
      }
    } catch (err) {
      handleApiError(err, "Failed to fetch models");
      setFetchError(err instanceof Error ? err.message : "Error fetching models.");
      setModels([]);
      setPagination(prev => ({ ...prev, totalItems: 0, isLoading: false }));
    }
  }, [searchQuery, typeFilter, datasetFilter]); // Dependencies for re-fetching when filters change

  useEffect(() => {
    fetchDatasetsForFilter();
  }, [fetchDatasetsForFilter]);
  
  // Fetch models when filters change (always fetch page 1)
  useEffect(() => {
    fetchModels(1);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery, typeFilter, datasetFilter]); // fetchModels is memoized, so this is fine

  // The handlePageChange directly calls fetchModels, so a separate useEffect for pagination.currentPage is not strictly needed
  // if handlePageChange is the ONLY way currentPage is updated for fetching.
  // However, if currentPage could be set by other means (e.g. URL param on load), an effect might be useful.
  // For now, relying on direct call from handlePageChange.

  const handlePageChange = (newPage: number) => {
    if (newPage !== pagination.currentPage) {
      fetchModels(newPage);
    }
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  };

  const handleToggleModelSelection = (modelId: string) => {
    setSelectedModelsForComparison((prev) =>
      prev.includes(modelId) ? prev.filter((id) => id !== modelId) : [...prev, modelId]
    );
  };

  const handleCompareModels = () => {
    if (selectedModelsForComparison.length < 2) {
      toast({ title: "Selection Required", description: "Please select at least two models to compare.", variant: "destructive" });
      return;
    }
    router.push(`/model-comparison?models=${selectedModelsForComparison.join(",")}`);
  };

  const renderPaginationControls = () => {
    const totalPages = Math.ceil(pagination.totalItems / ITEMS_PER_PAGE_MODELS);
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


  const renderContent = () => {
    if (pagination.isLoading && models.length === 0) {
      return Array.from({ length: 5 }).map((_, index) => (
        <TableRow key={`skel-model-${index}`}>
          <TableCell><Skeleton className="h-4 w-4" /></TableCell>
          <TableCell><Skeleton className="h-5 w-40" /></TableCell>
          <TableCell><Skeleton className="h-5 w-16" /></TableCell>
          <TableCell><Skeleton className="h-5 w-24" /></TableCell>
          <TableCell><Skeleton className="h-5 w-32" /></TableCell>
          <TableCell><Skeleton className="h-5 w-20" /></TableCell>
          <TableCell><Skeleton className="h-5 w-20" /></TableCell>
          <TableCell className="text-right"><Skeleton className="h-8 w-8 rounded-full" /></TableCell>
        </TableRow>
      ));
    }
    if (fetchError) {
      return (
        <TableRow>
          <TableCell colSpan={8} className="text-center text-destructive py-4">
            <Alert variant="destructive" className="justify-center">
              <AlertCircle className="mr-2 h-5 w-5" /><AlertDescription>{fetchError}</AlertDescription>
            </Alert>
            <Button onClick={() => fetchModels(1)} variant="outline" size="sm" className="mt-2">Try Again</Button>
          </TableCell>
        </TableRow>
      );
    }
    if (!pagination.isLoading && models.length === 0) {
      return (
        <TableRow>
          <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
            <p>No models found matching your criteria.</p>
            <Button size="sm" className="mt-2" asChild><Link href="/jobs/train"><Plus className="mr-2 h-4 w-4" />Train Your First Model</Link></Button>
          </TableCell>
        </TableRow>
      );
    }

    return models.map((model) => (
      <TableRow key={model.id}>
        <TableCell>
          <Checkbox
            checked={selectedModelsForComparison.includes(model.id.toString())}
            onCheckedChange={() => handleToggleModelSelection(model.id.toString())}
            aria-label={`Select model ${model.name} for comparison`}
          />
        </TableCell>
        <TableCell className="font-medium break-all max-w-[200px]">{model.name}</TableCell>
        <TableCell>{model.version}</TableCell>
        <TableCell><Badge variant="outline" className="text-xs">{model.model_type}</Badge></TableCell>
        <TableCell>
          {model.dataset_id ? (
            <Link href={`/datasets/${model.dataset_id}`} className="hover:underline text-primary text-xs">
              ID: {model.dataset_id} {/* Display dataset name if available from model.dataset.name */}
              {model.dataset?.name ? ` (${model.dataset.name.substring(0,20)}${model.dataset.name.length > 20 ? '...' : ''})` : ''}
            </Link>
          ) : "N/A"}
        </TableCell>
        <TableCell>{formatDate(model.created_at)}</TableCell>
        <TableCell className="text-xs">
            {model.performance_metrics?.f1_weighted !== undefined && <Badge variant="secondary" className="mr-1 mb-1 text-xs">F1: {Number(model.performance_metrics.f1_weighted).toFixed(3)}</Badge>}
            {model.performance_metrics?.accuracy !== undefined && <Badge variant="secondary" className="text-xs">Acc: {Number(model.performance_metrics.accuracy).toFixed(3)}</Badge>}
            {(!model.performance_metrics || Object.keys(model.performance_metrics).length === 0) && <span className="text-muted-foreground">N/A</span>}
        </TableCell>
        <TableCell className="text-right">
          <DropdownMenu>
            <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="h-7 w-7"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Actions</DropdownMenuLabel>
              <DropdownMenuItem asChild><Link href={`/models/${model.id}`}><Eye className="mr-2 h-4 w-4" />View Details</Link></DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href={`/jobs/inference?modelId=${model.id}${model.dataset?.repository_id ? `&repositoryId=${model.dataset.repository_id}`: ''}`}>
                    <Play className="mr-2 h-4 w-4" />Run Inference
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => handleToggleModelSelection(model.id.toString())}>
                <BarChart3 className="mr-2 h-4 w-4" />
                {selectedModelsForComparison.includes(model.id.toString()) ? "Remove from Comparison" : "Add to Comparison"}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>
      </TableRow>
    ));
  };

  return (
    <MainLayout>
      <PageContainer
        title={`ML Models (${pagination.isLoading && pagination.totalItems === 0 ? "..." : pagination.totalItems})`}
        description="Browse, compare, and manage your trained machine learning models."
        actions={
          <div className="flex space-x-2">
            <Button variant="outline" onClick={handleCompareModels} disabled={selectedModelsForComparison.length < 2}>
              <BarChart3 className="mr-2 h-4 w-4" />Compare Selected ({selectedModelsForComparison.length})
            </Button>
            <Button asChild><Link href="/jobs/train"><Plus className="mr-2 h-4 w-4" />Train New Model</Link></Button>
          </div>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="md:col-span-1">
            <Label htmlFor="search">Search by Model Name</Label>
            <Input id="search" placeholder="Enter model name..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="typeFilter">Filter by Model Type</Label>
            <Select 
                value={typeFilter} 
                onValueChange={(value) => setTypeFilter(value as ModelTypeEnum | typeof ALL_FILTER_VALUE)}
            >
              <SelectTrigger id="typeFilter"><SelectValue placeholder="All Model Types" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER_VALUE}>All Model Types</SelectItem>
                {availableModelTypes.map(type => <SelectItem key={type} value={type}>{type}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="datasetFilter">Filter by Dataset</Label>
            <Select 
                value={datasetFilter} 
                onValueChange={setDatasetFilter} 
                disabled={isLoadingDatasets || datasets.length === 0}
            >
              <SelectTrigger id="datasetFilter"><SelectValue placeholder={isLoadingDatasets ? "Loading datasets..." : (datasets.length === 0 ? "No datasets available" : "All Datasets")} /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER_VALUE}>All Datasets</SelectItem>
                {datasets.map(ds => <SelectItem key={ds.id} value={ds.id.toString()}>{ds.name} (ID: {ds.id})</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12"><span className="sr-only">Select</span></TableHead>
                <TableHead>Model Name</TableHead><TableHead>Version</TableHead><TableHead>Type</TableHead>
                <TableHead>Dataset</TableHead><TableHead>Created</TableHead><TableHead>Key Metrics</TableHead>
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
}