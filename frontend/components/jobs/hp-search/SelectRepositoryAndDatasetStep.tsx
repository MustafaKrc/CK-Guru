// frontend/components/jobs/hp-search/SelectRepositoryAndDatasetStep.tsx
"use client";

import React, { useState, useEffect, useCallback } from "react";
import { HpSearchJobFormData } from "@/types/jobs";
import { SearchableSelect } from "@/components/ui/searchable-select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { GitBranch, Database, Check } from "lucide-react";
import { apiService, handleApiError } from "@/lib/apiService";
import { Repository, DatasetRead } from "@/types/api";
import { useToast } from "@/hooks/use-toast";

interface SelectRepositoryAndDatasetStepProps {
  formData: HpSearchJobFormData;
  updateFormData: (updates: Partial<HpSearchJobFormData>) => void;
}

export const SelectRepositoryAndDatasetStep: React.FC<SelectRepositoryAndDatasetStepProps> = ({
  formData,
  updateFormData,
}) => {
  const { toast } = useToast();
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isLoadingRepos, setIsLoadingRepos] = useState(true);
  const [datasets, setDatasets] = useState<DatasetRead[]>([]);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(false);

  useEffect(() => {
    const fetchRepos = async () => {
      setIsLoadingRepos(true);
      try {
        const response = await apiService.getRepositories({ limit: 200 });
        setRepositories(response.items || []);
      } catch (error) {
        handleApiError(error, "Failed to load repositories");
      } finally {
        setIsLoadingRepos(false);
      }
    };
    fetchRepos();
  }, []);

  const fetchDatasetsForRepo = useCallback(async (repoId: number) => {
    setIsLoadingDatasets(true);
    setDatasets([]);
    try {
      const response = await apiService.getDatasets({
        repository_id: repoId,
        status: "ready",
        limit: 200,
      });
      setDatasets(response.items || []);
    } catch (error) {
      handleApiError(error, "Failed to load datasets for repository");
    } finally {
      setIsLoadingDatasets(false);
    }
  }, []);

  useEffect(() => {
    if (formData.repositoryId) {
      fetchDatasetsForRepo(formData.repositoryId);
    }
  }, [formData.repositoryId, fetchDatasetsForRepo]);

  const handleRepositorySelect = (repoIdString: string) => {
    const repoId = parseInt(repoIdString, 10);
    const selectedRepo = repositories.find((r) => r.id === repoId);
    updateFormData({
      repositoryId: repoId,
      repositoryName: selectedRepo?.name,
      datasetId: null,
      datasetName: undefined,
      datasetFeatureSpace: [],
      datasetTargetColumn: null,
    });
  };

  const handleDatasetSelect = (datasetIdString: string) => {
    if (!datasetIdString) {
      updateFormData({
        datasetId: null,
        datasetName: undefined,
        datasetFeatureSpace: [],
        datasetTargetColumn: null,
      });
      return;
    }
    const datasetId = parseInt(datasetIdString, 10);
    const selectedDS = datasets.find((ds) => ds.id === datasetId);
    if (selectedDS) {
      updateFormData({
        datasetId: selectedDS.id,
        datasetName: selectedDS.name,
        datasetFeatureSpace: selectedDS.config.feature_columns || [],
        datasetTargetColumn: selectedDS.config.target_column || null,
      });
      toast({ title: "Dataset Selected", description: `${selectedDS.name} is ready for use.` });
    }
  };

  const repositoryOptions = repositories.map((repo) => ({
    value: repo.id.toString(),
    label: repo.name,
  }));

  const datasetOptions = datasets.map((ds) => ({
    value: ds.id.toString(),
    label: ds.name,
  }));

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <GitBranch className="mr-2 h-5 w-5 text-primary" />
            Select Repository
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Label htmlFor="repository-select">Repository *</Label>
          {isLoadingRepos ? (
            <Skeleton className="h-10 w-full mt-2" />
          ) : (
            <SearchableSelect
              options={repositoryOptions}
              value={formData.repositoryId?.toString() || ""}
              onValueChange={handleRepositorySelect}
              disabled={repositories.length === 0}
              placeholder="Select a repository..."
              searchPlaceholder="Search repositories..."
              emptyMessage="No repositories found."
              isLoading={isLoadingRepos}
            />
          )}
        </CardContent>
      </Card>

      {formData.repositoryId && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Database className="mr-2 h-5 w-5 text-primary" />
              Select Dataset
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Label htmlFor="dataset-select">Dataset *</Label>
            {isLoadingDatasets ? (
              <Skeleton className="h-10 w-full mt-2" />
            ) : (
              <SearchableSelect
                options={datasetOptions}
                value={formData.datasetId?.toString() || ""}
                onValueChange={handleDatasetSelect}
                disabled={datasets.length === 0}
                placeholder={
                    datasets.length === 0
                      ? "No 'Ready' datasets found"
                      : "Select a 'Ready' dataset..."
                  }
                  searchPlaceholder="Search datasets..."
                  emptyMessage="No 'Ready' datasets found."
                  isLoading={isLoadingDatasets}
                />
            )}
          </CardContent>
        </Card>
      )}

      {formData.datasetId && (
        <Alert variant="default" className="bg-primary/5 border-primary/20">
          <Check className="h-5 w-5 text-primary" />
          <div className="ml-2">
            <p className="font-semibold text-primary">Data Source Selected</p>
            <p className="text-xs text-muted-foreground">Repository: {formData.repositoryName}</p>
            <p className="text-xs text-muted-foreground">Dataset: {formData.datasetName}</p>
          </div>
        </Alert>
      )}
    </div>
  );
};
