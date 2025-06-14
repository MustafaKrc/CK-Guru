"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem } from "@/components/ui/dropdown-menu";
import { DropdownMenuTrigger } from "@radix-ui/react-dropdown-menu"; // Direct import for clarity
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  MoreHorizontal,
  Eye,
  Play,
  BarChart3,
  Plus,
  Loader2,
  AlertCircle,
  ArrowUpDown,
} from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
  PaginationEllipsis,
} from "@/components/ui/pagination";
import { SearchableSelect, SearchableSelectOption } from "@/components/ui/searchable-select";
import { useDebounce } from "@/hooks/useDebounce";
import { apiService, handleApiError } from "@/lib/apiService";
import { MLModelRead, PaginatedMLModelRead, DatasetRead, PaginatedDatasetRead } from "@/types/api";
import { ModelTypeEnum } from "@/types/api/enums";
import { generatePagination } from "@/lib/paginationUtils";

const ITEMS_PER_PAGE_MODELS = 10;
const ALL_FILTER_VALUE = "_all_";

type SortableKeys = "name" | "version" | "model_type" | "created_at" | "dataset";
type SortConfig = {
  key: SortableKeys;
  direction: "asc" | "desc";
};

const SortableHeader: React.FC<{
  sortKey: SortableKeys;
  sortConfig: SortConfig;
  onSort: (key: SortableKeys) => void;
  children: React.ReactNode;
}> = ({ sortKey, sortConfig, onSort, children }) => (
  <Button variant="ghost" onClick={() => onSort(sortKey)} className="pl-2 pr-1">
    {children}
    <ArrowUpDown
      className={`ml-2 h-4 w-4 transition-opacity ${sortConfig.key === sortKey ? "opacity-100" : "opacity-30"}`}
    />
  </Button>
);

export default function ModelsPage() {
  const [models, setModels] = useState<MLModelRead[]>([]);
  const [pagination, setPagination] = useState({
    currentPage: 1,
    totalItems: 0,
    itemsPerPage: 10,
    isLoading: true,
  });
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Server-side operation states
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 500);
  const [typeFilter, setTypeFilter] = useState<string>(ALL_FILTER_VALUE);
  const [datasetFilter, setDatasetFilter] = useState<string>(ALL_FILTER_VALUE);
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: "created_at",
    direction: "desc",
  });

  // State for filter dropdowns
  const [datasets, setDatasets] = useState<DatasetRead[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true);

  const availableModelTypes = Object.values(ModelTypeEnum);

  const fetchDependencies = useCallback(async () => {
    setIsLoadingDatasets(true);
    try {
      const dsResponse = await apiService.get<PaginatedDatasetRead>(
        `/datasets?limit=500&status=ready`
      ); // Fetch enough for selection
      setDatasets(dsResponse.items || []);
    } catch (err) {
      handleApiError(err, "Failed to load datasets for filter");
    } finally {
      setIsLoadingDatasets(false);
    }
  }, []);

  const fetchModels = useCallback(
    async (
      pageToFetch: number,
      limitToFetch: number,
      currentSearch: string,
      currentType: string,
      currentDatasetId: string,
      currentSort: SortConfig
    ) => {
      setPagination((prev) => ({ ...prev, isLoading: true }));
      try {
        const response = await apiService.getModels({
          skip: (pageToFetch - 1) * limitToFetch,
          limit: limitToFetch,
          ...(currentSearch && { nameFilter: currentSearch }),
          ...(currentType !== ALL_FILTER_VALUE && { model_type: currentType }),
          ...(currentDatasetId !== ALL_FILTER_VALUE && { dataset_id: parseInt(currentDatasetId) }),
          sortBy: currentSort.key,
          sortDir: currentSort.direction,
        });
        setModels(response.items || []);
        setPagination((prev) => ({
          ...prev,
          totalItems: response.total,
          isLoading: false,
          currentPage: pageToFetch,
          itemsPerPage: limitToFetch,
        }));
      } catch (err) {
        handleApiError(err, "Failed to fetch models");
        setFetchError(err instanceof Error ? err.message : "Error fetching models.");
        setPagination((prev) => ({ ...prev, isLoading: false }));
      }
    },
    []
  );

  useEffect(() => {
    fetchDependencies();
  }, [fetchDependencies]);

  // Effect for filters or sort config changing: fetch page 1
  useEffect(() => {
    fetchModels(
      1,
      pagination.itemsPerPage,
      debouncedSearchQuery,
      typeFilter,
      datasetFilter,
      sortConfig
    );
  }, [debouncedSearchQuery, typeFilter, datasetFilter, sortConfig, fetchModels]);

  // Effect for pagination changes (currentPage or itemsPerPage)
  useEffect(() => {
    fetchModels(
      pagination.currentPage,
      pagination.itemsPerPage,
      debouncedSearchQuery,
      typeFilter,
      datasetFilter,
      sortConfig
    );
  }, [pagination.currentPage, pagination.itemsPerPage, fetchModels]);

  const handleSort = (key: SortableKeys) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
    }));
  };

  const handleItemsPerPageChange = (value: string) => {
    const newItemsPerPage = parseInt(value, 10);
    setPagination((prev) => ({ ...prev, itemsPerPage: newItemsPerPage, currentPage: 1 }));
  };

  const datasetOptions: SearchableSelectOption[] = datasets.map((d) => ({
    value: String(d.id),
    label: `${d.name} (ID: ${d.id})`,
  }));

  const formatDate = (dateString?: string) =>
    dateString ? new Date(dateString).toLocaleDateString() : "N/A";

  const renderPaginationControls = () => {
    const totalPages = Math.ceil(pagination.totalItems / pagination.itemsPerPage);
    if (totalPages <= 1) return null;
    const pageNumbers = generatePagination(pagination.currentPage, totalPages);
    return (
      <Pagination className="mt-4">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              onClick={() =>
                setPagination((p) => ({ ...p, currentPage: Math.max(1, p.currentPage - 1) }))
              }
              aria-disabled={pagination.currentPage <= 1}
            />
          </PaginationItem>
          {pageNumbers.map((page, index) =>
            typeof page === "number" ? (
              <PaginationItem key={page}>
                <PaginationLink
                  onClick={() => setPagination((p) => ({ ...p, currentPage: page }))}
                  isActive={pagination.currentPage === page}
                >
                  {page}
                </PaginationLink>
              </PaginationItem>
            ) : (
              <PaginationItem key={`ellipsis-${index}`}>
                <PaginationEllipsis />
              </PaginationItem>
            )
          )}
          <PaginationItem>
            <PaginationNext
              onClick={() =>
                setPagination((p) => ({
                  ...p,
                  currentPage: Math.min(totalPages, p.currentPage + 1),
                }))
              }
              aria-disabled={pagination.currentPage >= totalPages}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    );
  };

  const renderContent = () => {
    if (pagination.isLoading) {
      return Array.from({ length: 5 }).map((_, i) => (
        <TableRow key={`skel-${i}`}>
          <TableCell colSpan={7}>
            <Skeleton className="h-8 w-full" />
          </TableCell>
        </TableRow>
      ));
    }
    if (fetchError) {
      return (
        <TableRow>
          <TableCell colSpan={7} className="text-center text-destructive py-6">
            {fetchError}
          </TableCell>
        </TableRow>
      );
    }
    if (models.length === 0) {
      return (
        <TableRow>
          <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
            No models found matching your criteria.
          </TableCell>
        </TableRow>
      );
    }

    return models.map((model) => (
      <TableRow key={model.id}>
        <TableCell className="font-medium max-w-[200px] truncate">
          <Link href={`/models/${model.id}`} className="hover:underline text-primary">
            {model.name}
          </Link>
        </TableCell>
        <TableCell>{model.version}</TableCell>
        <TableCell>
          <Badge variant="outline">{model.model_type}</Badge>
        </TableCell>
        <TableCell>
          <Link href={`/datasets/${model.dataset_id}`} className="hover:underline text-primary">
            {model.dataset?.name}
          </Link>
        </TableCell>
        <TableCell className="text-xs">{formatDate(model.created_at)}</TableCell>
        <TableCell>
          <Badge variant="secondary" className="text-xs">
            F1: {Number(model.performance_metrics?.f1_weighted ?? 0).toFixed(3)}
          </Badge>
        </TableCell>
        <TableCell className="text-right">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreHorizontal />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem asChild>
                <Link href={`/models/${model.id}`}>
                  <Eye className="mr-2 h-4 w-4" />
                  View Details
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href={`/jobs/inference?modelId=${model.id}`}>
                  <Play className="mr-2 h-4 w-4" />
                  Run Inference
                </Link>
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
        title={`ML Models (${pagination.totalItems})`}
        description="Browse, compare, and manage your trained machine learning models."
        actions={
          <Button asChild>
            <Link href="/jobs/train">
              <Plus className="mr-2 h-4 w-4" />
              Train New Model
            </Link>
          </Button>
        }
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <Input
            placeholder="Search by model name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="md:col-span-2 lg:col-span-1"
          />
          <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v as any)}>
            <SelectTrigger>
              <SelectValue placeholder="All Model Types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_FILTER_VALUE}>All Types</SelectItem>
              {availableModelTypes.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <SearchableSelect
            options={[{ value: ALL_FILTER_VALUE, label: "All Datasets" }, ...datasetOptions]}
            value={datasetFilter}
            onValueChange={setDatasetFilter}
            placeholder="Filter by Dataset"
            searchPlaceholder="Search datasets..."
            emptyMessage="No datasets found."
            disabled={isLoadingDatasets}
            isLoading={isLoadingDatasets}
          />
          <div className="flex items-center gap-2 md:col-start-2 lg:col-start-4">
            <Label htmlFor="items-per-page-models" className="text-sm shrink-0">
              Show:
            </Label>
            <Select
              value={String(pagination.itemsPerPage)}
              onValueChange={handleItemsPerPageChange}
            >
              <SelectTrigger id="items-per-page-models" className="w-full md:w-[80px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[10, 25, 50, 100].map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <SortableHeader sortKey="name" sortConfig={sortConfig} onSort={handleSort}>
                    Model Name
                  </SortableHeader>
                </TableHead>
                <TableHead>
                  <SortableHeader sortKey="version" sortConfig={sortConfig} onSort={handleSort}>
                    Version
                  </SortableHeader>
                </TableHead>
                <TableHead>
                  <SortableHeader sortKey="model_type" sortConfig={sortConfig} onSort={handleSort}>
                    Type
                  </SortableHeader>
                </TableHead>
                <TableHead>
                  <SortableHeader sortKey="dataset" sortConfig={sortConfig} onSort={handleSort}>
                    Dataset
                  </SortableHeader>
                </TableHead>
                <TableHead>
                  <SortableHeader sortKey="created_at" sortConfig={sortConfig} onSort={handleSort}>
                    Created
                  </SortableHeader>
                </TableHead>
                <TableHead>F1 Score</TableHead>
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
