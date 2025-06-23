// frontend/components/jobs/train/SelectRepositoryAndDatasetStep.tsx
import React, { useState, useEffect, useCallback } from "react";
import { TrainingJobFormData } from "@/types/jobs";
import { Button } from "@/components/ui/button";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Plus, Check, Loader2, DatabaseZap, Link } from "lucide-react";
import { apiService, handleApiError } from "@/lib/apiService";
import {
  Repository,
  PaginatedRepositoryRead,
  DatasetRead,
  PaginatedDatasetRead,
  DatasetTaskResponse,
  DatasetCreatePayload,
} from "@/types/api";
import { SearchableSelect } from "@/components/ui/searchable-select";
import { DatasetStatusEnum } from "@/types/api/enums"; // Ensure this path is correct
import { useToast } from "@/hooks/use-toast";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
// We will NOT import CreateDatasetFormContent for this simplified version

interface SelectRepositoryAndDatasetStepProps {
  formData: TrainingJobFormData;
  updateFormData: (updates: Partial<TrainingJobFormData>) => void;
  onStepComplete: () => void;
}

export const SelectRepositoryAndDatasetStep: React.FC<SelectRepositoryAndDatasetStepProps> = ({
  formData,
  updateFormData,
}) => {
  const { toast } = useToast();

  const [availableRepositories, setAvailableRepositories] = useState<Repository[]>([]);
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(true);

  const [existingDatasets, setExistingDatasets] = useState<DatasetRead[]>([]);
  const [isLoadingExistingDatasets, setIsLoadingExistingDatasets] = useState(false);

  const [selectionMode, setSelectionMode] = useState<"select" | "create">("select");
  const [showCreateDatasetModal, setShowCreateDatasetModal] = useState(false);

  const [isCreatingDataset, setIsCreatingDataset] = useState(false);
  const [newDatasetName, setNewDatasetName] = useState("");
  const [newDatasetDescription, setNewDatasetDescription] = useState("");
  // No complex feature/rule state for this simplified modal

  useEffect(() => {
    const fetchRepos = async () => {
      setIsLoadingRepositories(true);
      try {
        const response = await apiService.getRepositories({ limit: 200 });
        setAvailableRepositories(response.items || []);
      } catch (error) {
        handleApiError(error, "Failed to load repositories");
      } finally {
        setIsLoadingRepositories(false);
      }
    };
    fetchRepos();
  }, []);

  const fetchDatasetsForRepo = useCallback(async (repoId: number) => {
    setIsLoadingExistingDatasets(true);
    setExistingDatasets([]);
    try {
      const response = await apiService.getDatasets({
        repository_id: repoId,
        status: "ready",
        limit: 200,
      });
      setExistingDatasets(response.items || []);
    } catch (error) {
      handleApiError(error, "Failed to load datasets for repository");
    } finally {
      setIsLoadingExistingDatasets(false);
    }
  }, []);

  useEffect(() => {
    if (formData.repositoryId) {
      fetchDatasetsForRepo(formData.repositoryId);
    } else {
      setExistingDatasets([]);
    }
  }, [formData.repositoryId, fetchDatasetsForRepo]);

  const handleRepositorySelect = (repoIdString: string) => {
    const repoId = parseInt(repoIdString);
    const selectedRepo = availableRepositories.find((r) => r.id === repoId);
    updateFormData({
      repositoryId: repoId,
      repositoryName: selectedRepo?.name,
      datasetId: null,
      datasetName: undefined,
      datasetFeatureSpace: [],
      datasetTargetColumn: null,
    });
    setSelectionMode("select"); // Default to select mode when repo changes
  };

  const handleExistingDatasetSelect = async (datasetIdString: string) => {
    if (!datasetIdString) {
      updateFormData({
        datasetId: null,
        datasetName: undefined,
        datasetFeatureSpace: [],
        datasetTargetColumn: null,
      });
      return;
    }
    const datasetId = parseInt(datasetIdString);
    const selectedDS = existingDatasets.find((ds) => ds.id === datasetId);
    if (selectedDS) {
      try {
        // Assuming the list already has necessary config, or fetch details if not
        // For this step, feature_columns and target_column from dataset.config are crucial.
        // If `existingDatasets` already contains `config`, we can use it directly.
        // Otherwise, an additional fetch might be needed for `GET /datasets/{datasetId}`.
        // Let's assume `existingDatasets` items are `DatasetRead` which include the config.
        updateFormData({
          datasetId: selectedDS.id,
          datasetName: selectedDS.name,
          datasetFeatureSpace: selectedDS.config.feature_columns || [],
          datasetTargetColumn: selectedDS.config.target_column || null,
        });
        toast({ title: "Dataset Selected", description: `${selectedDS.name} is ready.` });
      } catch (error) {
        handleApiError(error, "Error processing dataset selection");
      }
    }
  };

  const handleCreateNewDatasetSubmit = async () => {
    if (!formData.repositoryId || !newDatasetName.trim()) {
      toast({
        title: "Error",
        description: "Repository and new dataset name are required.",
        variant: "destructive",
      });
      return;
    }
    setIsCreatingDataset(true);

    // Simplified payload: backend needs to handle default features/rules
    const payload: DatasetCreatePayload = {
      name: newDatasetName,
      description: newDatasetDescription || undefined,
      config: {
        // Backend should ideally infer these from the repository's available metrics
        // or use a predefined default set of features and a standard target.
        feature_columns: ["la", "ld", "lt", "fix", "ns", "nd", "nf", "entropy"], // Example sensible defaults
        target_column: "is_buggy", // Standard target
        cleaning_rules: [
          // Example default cleaning rules
          { name: "drop_na_target", enabled: true },
          { name: "handle_bots_rf", enabled: true, params: { threshold_val: 0.8 } }, // Example param
        ],
      },
    };

    try {
      const taskResponse = await apiService.createDataset(formData.repositoryId, payload);
      toast({
        title: "Dataset Creation Started",
        description: `Task ID: ${taskResponse.task_id}. Polling for readiness...`,
      });
      setShowCreateDatasetModal(false); // Close modal

      let attempts = 0;
      const maxAttempts = 30; // Poll for ~3 minutes (30 * 6s)
      const pollInterval = setInterval(async () => {
        attempts++;
        try {
          const createdDataset = await apiService.get<DatasetRead>(
            `/datasets/${taskResponse.dataset_id}`
          );
          if (createdDataset.status.toUpperCase() === DatasetStatusEnum.READY.toUpperCase()) {
            clearInterval(pollInterval);
            setIsCreatingDataset(false);
            setNewDatasetName("");
            setNewDatasetDescription("");
            updateFormData({
              datasetId: createdDataset.id,
              datasetName: createdDataset.name,
              datasetFeatureSpace: createdDataset.config.feature_columns || [],
              datasetTargetColumn: createdDataset.config.target_column || null,
            });
            // Also refresh the list of existing datasets for this repo
            if (formData.repositoryId) fetchDatasetsForRepo(formData.repositoryId);
            setSelectionMode("select"); // Switch back to select mode
            toast({
              title: "Dataset Created & Selected",
              description: `${createdDataset.name} is ready.`,
            });
          } else if (
            createdDataset.status.toUpperCase() === DatasetStatusEnum.FAILED.toUpperCase()
          ) {
            clearInterval(pollInterval);
            setIsCreatingDataset(false);
            toast({
              title: "Dataset Creation Failed",
              description: createdDataset.status_message || "Unknown error.",
              variant: "destructive",
            });
          } else if (attempts >= maxAttempts) {
            clearInterval(pollInterval);
            setIsCreatingDataset(false);
            toast({
              title: "Dataset Timeout",
              description:
                "Dataset creation is taking longer than expected. Please check its status on the Datasets page.",
              variant: "default",
            });
          }
        } catch (pollError) {
          console.error("Polling error:", pollError);
          if (attempts >= maxAttempts) {
            clearInterval(pollInterval);
            setIsCreatingDataset(false);
            toast({
              title: "Dataset Polling Error",
              description: "Could not confirm dataset status.",
              variant: "destructive",
            });
          }
        }
      }, 6000);
    } catch (error) {
      handleApiError(error, "Failed to start dataset creation");
      setIsCreatingDataset(false);
    }
  };

  const repositoryOptions = availableRepositories.map((repo) => ({
    value: repo.id.toString(),
    label: `${repo.name} (ID: ${repo.id})`,
  }));

  const datasetOptions = existingDatasets.map((ds) => ({
    value: ds.id.toString(),
    label: `${ds.name} (ID: ${ds.id}, Rows: ${ds.num_rows ?? "N/A"})`,
  }));

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <DatabaseZap className="mr-2 h-5 w-5 text-primary" />
            Source Data Selection
          </CardTitle>
          <CardDescription>
            Choose the repository and the dataset you want to use for training.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="repository-select">Repository *</Label>
            {isLoadingRepositories ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <SearchableSelect
                value={formData.repositoryId?.toString() || ""}
                onValueChange={handleRepositorySelect}
                options={repositoryOptions}
                placeholder="Select a repository..."
                searchPlaceholder="Search repositories..."
                emptyMessage="No repositories found"
                disabled={isLoadingRepositories || availableRepositories.length === 0}
                isLoading={isLoadingRepositories}
              />
            )}
            {availableRepositories.length === 0 && !isLoadingRepositories && (
              <Alert variant="default" className="mt-2">
                <AlertDescription>
                  No repositories found. Please{" "}
                  <Link href="/repositories" className="font-medium text-primary hover:underline">
                    add a repository
                  </Link>{" "}
                  first.
                </AlertDescription>
              </Alert>
            )}
          </div>

          {formData.repositoryId && (
            <div className="space-y-4 pt-4 border-t">
              <Label>Dataset *</Label>
              <div className="flex space-x-2">
                <Button
                  variant={selectionMode === "select" ? "default" : "outline"}
                  onClick={() => setSelectionMode("select")}
                  size="sm"
                  disabled={isCreatingDataset}
                >
                  Select Existing Dataset
                </Button>
                <Dialog open={showCreateDatasetModal} onOpenChange={setShowCreateDatasetModal}>
                  <DialogTrigger asChild>
                    <Button
                      variant={selectionMode === "create" ? "default" : "outline"}
                      onClick={() => {
                        // setSelectionMode('create'); // This will be set if user clicks this button
                        // No need to set selectionMode here explicitly if this button itself denotes 'create' mode
                        // and we manage the modal's open state separately.
                      }}
                      size="sm"
                      disabled={isCreatingDataset}
                    >
                      <Plus className="mr-2 h-4 w-4" /> Create New Dataset
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="sm:max-w-[500px]">
                    <DialogHeader>
                      <DialogTitle>Create New Dataset</DialogTitle>
                      <DialogDescription>
                        For repository:{" "}
                        <strong>{formData.repositoryName || `ID ${formData.repositoryId}`}</strong>.
                        <br />
                        This quick add uses default feature and cleaning configurations. For full
                        control, use the dedicated "Create Dataset" page.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                      <div className="space-y-1.5">
                        <Label htmlFor="new-dataset-name">New Dataset Name *</Label>
                        <Input
                          id="new-dataset-name"
                          value={newDatasetName}
                          onChange={(e) => setNewDatasetName(e.target.value)}
                          placeholder="e.g., Main Bug Prediction Dataset"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="new-dataset-description">Description (Optional)</Label>
                        <Textarea
                          id="new-dataset-description"
                          value={newDatasetDescription}
                          onChange={(e) => setNewDatasetDescription(e.target.value)}
                          placeholder="A brief description..."
                          rows={2}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <DialogClose asChild>
                        <Button variant="outline" disabled={isCreatingDataset}>
                          Cancel
                        </Button>
                      </DialogClose>
                      <Button
                        onClick={handleCreateNewDatasetSubmit}
                        disabled={isCreatingDataset || !newDatasetName.trim()}
                      >
                        {isCreatingDataset ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Creating & Polling...
                          </>
                        ) : (
                          "Create & Select"
                        )}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>

              {selectionMode === "select" && (
                <div className="space-y-2">
                  {isLoadingExistingDatasets ? (
                    <Skeleton className="h-10 w-full" />
                  ) : (
                    <SearchableSelect
                      value={formData.datasetId?.toString() || ""}
                      onValueChange={handleExistingDatasetSelect}
                      options={datasetOptions}
                      placeholder={
                        isCreatingDataset
                          ? "Waiting for new dataset..."
                          : isLoadingExistingDatasets
                            ? "Loading datasets..."
                            : existingDatasets.length === 0
                              ? "No 'Ready' datasets found"
                              : "Select a 'Ready' dataset..."
                      }
                      searchPlaceholder="Search datasets..."
                      emptyMessage="No 'Ready' datasets found."
                      disabled={isCreatingDataset || isLoadingExistingDatasets || existingDatasets.length === 0}
                      isLoading={isLoadingExistingDatasets || isCreatingDataset}
                    />
                  )}
                  {existingDatasets.length === 0 &&
                    !isLoadingExistingDatasets &&
                    !isCreatingDataset && (
                      <Alert variant="default" className="mt-2 text-xs">
                        <AlertDescription>
                          No 'Ready' datasets found for this repository. You can use the button
                          above to create one.
                        </AlertDescription>
                      </Alert>
                    )}
                </div>
              )}
            </div>
          )}

          {formData.datasetId && formData.datasetName && (
            <Alert variant="default" className="mt-4 bg-primary/5 border-primary/20">
              <Check className="h-5 w-5 text-primary" />
              <div className="ml-2">
                <p className="font-semibold text-primary">
                  Dataset Selected: {formData.datasetName}
                </p>
                <p className="text-xs text-muted-foreground">
                  Features:{" "}
                  {formData.datasetFeatureSpace.length > 0
                    ? formData.datasetFeatureSpace.slice(0, 3).join(", ") +
                      (formData.datasetFeatureSpace.length > 3 ? "..." : "")
                    : "N/A"}
                  {formData.datasetFeatureSpace.length > 0 &&
                    ` (${formData.datasetFeatureSpace.length} total)`}
                </p>
                <p className="text-xs text-muted-foreground">
                  Target: {formData.datasetTargetColumn || "N/A"}
                </p>
              </div>
            </Alert>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
