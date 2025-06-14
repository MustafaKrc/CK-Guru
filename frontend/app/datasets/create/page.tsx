// frontend/app/datasets/create/page.tsx
"use client";

import React, { useState, useEffect, useCallback, Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { MainLayout } from "@/components/main-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/ui/page-container";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ArrowLeft,
  ArrowRight,
  HelpCircle,
  Info,
  Loader2,
  AlertCircle,
  Link,
  Check,
  Database,
  GitBranch,
  ListFilter,
  TargetIcon,
  CheckCircle2,
  WandSparkles,
  Settings2,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { PageLoader } from "@/components/ui/page-loader";

import { apiService, handleApiError, ApiError } from "@/lib/apiService";
import { Repository, PaginatedRepositoryRead } from "@/types/api/repository";
import { RuleDefinition } from "@/types/api/rule";
import {
  DatasetCreatePayload,
  DatasetTaskResponse,
  CleaningRuleConfig as BackendCleaningRuleConfig,
  FeatureSelectionConfig,
} from "@/types/api/dataset";
import { FeatureSelectionDefinition } from "@/types/api/feature-selection";
import { FeatureSelectionStep } from "./FeatureSelectionStep";

import { STATIC_AVAILABLE_METRICS, STATIC_AVAILABLE_TARGETS, MetricDefinition } from "./constants";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";

// Frontend internal state for cleaning rules
interface InternalCleaningRuleConfig extends RuleDefinition {
  enabled: boolean;
  userParams: Record<string, any>;
}

const WIZARD_STEPS = [
  { name: "Source Data", description: "Select repository and provide details." },
  { name: "Features & Target", description: "Choose features and target variable." },
  { name: "Data Cleaning", description: "Configure data preprocessing rules." },
  { name: "Feature Selection", description: "Optionally reduce feature space." },
  { name: "Review & Submit", description: "Finalize and start generating." },
];
const TOTAL_STEPS = WIZARD_STEPS.length;

function CreateDatasetPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const preselectedRepoId = searchParams.get("repository");

  const [currentStep, setCurrentStep] = useState(1);

  // Step 1 State
  const [repositoryId, setRepositoryId] = useState<string>(preselectedRepoId || "");
  const [datasetName, setDatasetName] = useState("");
  const [datasetDescription, setDatasetDescription] = useState("");

  // Step 2 State
  const [selectedFeatureColumns, setSelectedFeatureColumns] = useState<string[]>([]);
  const [searchTermFeatures, setSearchTermFeatures] = useState("");
  const [selectedTargetColumn, setSelectedTargetColumn] = useState<string>(
    STATIC_AVAILABLE_TARGETS[0]?.id || "is_buggy"
  );

  // Step 3 State
  const [configuredCleaningRules, setConfiguredCleaningRules] = useState<
    InternalCleaningRuleConfig[]
  >([]);

  // Step 4 State
  const [featureSelectionConfig, setFeatureSelectionConfig] =
    useState<FeatureSelectionConfig | null>(null);

  // Fetched Data State
  const [availableRepositories, setAvailableRepositories] = useState<Repository[]>([]);
  const [isLoadingRepos, setIsLoadingRepos] = useState(true);
  const [availableRuleDefinitions, setAvailableRuleDefinitions] = useState<RuleDefinition[]>([]);
  const [isLoadingRules, setIsLoadingRules] = useState(true);
  const [availableAlgorithms, setAvailableAlgorithms] = useState<FeatureSelectionDefinition[]>([]);
  const [isLoadingAlgos, setIsLoadingAlgos] = useState(true);

  // Form Submission State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchRepositories = useCallback(async () => {
    setIsLoadingRepos(true);
    try {
      const response = await apiService.getRepositories({ limit: 200 });
      setAvailableRepositories(response.items || []);
      if (preselectedRepoId && response.items.find((r) => r.id.toString() === preselectedRepoId)) {
        setRepositoryId(preselectedRepoId);
      }
    } catch (err) {
      handleApiError(err, "Failed to load repositories");
    } finally {
      setIsLoadingRepos(false);
    }
  }, [preselectedRepoId]);

  const fetchCleaningRuleDefinitions = useCallback(async () => {
    setIsLoadingRules(true);
    try {
      const data = await apiService.getAvailableCleaningRules();
      setAvailableRuleDefinitions(data || []);
      const initialConfiguredRules = (data || []).map((def) => ({
        ...def,
        enabled: true,
        userParams: def.parameters.reduce(
          (acc, param) => {
            acc[param.name] =
              param.default !== undefined ? param.default : getDefaultValueForType(param.type);
            return acc;
          },
          {} as Record<string, any>
        ),
      }));
      setConfiguredCleaningRules(initialConfiguredRules);
    } catch (err) {
      handleApiError(err, "Failed to load cleaning rules");
      setConfiguredCleaningRules([]);
    } finally {
      setIsLoadingRules(false);
    }
  }, []);

  const fetchFeatureSelectionAlgorithms = useCallback(async () => {
    setIsLoadingAlgos(true);
    try {
      const data = await apiService.getAvailableFeatureSelectionAlgorithms();
      setAvailableAlgorithms(data || []);
    } catch (err) {
      handleApiError(err, "Failed to load feature selection algorithms");
      setAvailableAlgorithms([]);
    } finally {
      setIsLoadingAlgos(false);
    }
  }, []);

  const getDefaultValueForType = (type: string): any => {
    switch (type) {
      case "integer":
      case "float":
        return 0;
      case "boolean":
        return false;
      case "string":
      default:
        return "";
    }
  };

  useEffect(() => {
    fetchRepositories();
    fetchCleaningRuleDefinitions();
    fetchFeatureSelectionAlgorithms();
  }, [fetchRepositories, fetchCleaningRuleDefinitions, fetchFeatureSelectionAlgorithms]);

  const handleFeatureToggle = (metricId: string) => {
    setSelectedFeatureColumns((prev) =>
      prev.includes(metricId) ? prev.filter((id) => id !== metricId) : [...prev, metricId]
    );
  };

  const handleSelectAllFeatures = (group?: MetricDefinition["group"]) => {
    const allMetricIdsInGroup = STATIC_AVAILABLE_METRICS.filter(
      (metric) => !group || metric.group === group
    ).map((metric) => metric.id);
    const allSelectedInGroup = allMetricIdsInGroup.every((id) =>
      selectedFeatureColumns.includes(id)
    );
    if (allSelectedInGroup) {
      setSelectedFeatureColumns((prev) => prev.filter((id) => !allMetricIdsInGroup.includes(id)));
    } else {
      setSelectedFeatureColumns((prev) => [...new Set([...prev, ...allMetricIdsInGroup])]);
    }
  };

  const handleRuleEnabledChange = (ruleName: string, checked: boolean) => {
    setConfiguredCleaningRules((prev) =>
      prev.map((rule) => (rule.name === ruleName ? { ...rule, enabled: checked } : rule))
    );
  };

  const handleRuleParamChange = (ruleName: string, paramName: string, value: any) => {
    setConfiguredCleaningRules((prev) =>
      prev.map((rule) =>
        rule.name === ruleName
          ? { ...rule, userParams: { ...rule.userParams, [paramName]: value } }
          : rule
      )
    );
  };

  const validateStep1 = () => {
    if (!repositoryId) {
      setFormError("Please select a repository.");
      return false;
    }
    if (!datasetName.trim()) {
      setFormError("Dataset name is required.");
      return false;
    }
    setFormError(null);
    return true;
  };

  const validateStep2 = () => {
    if (selectedFeatureColumns.length === 0) {
      setFormError("Please select at least one feature column.");
      return false;
    }
    if (!selectedTargetColumn) {
      setFormError("Please select a target column.");
      return false;
    }
    setFormError(null);
    return true;
  };

  const validateStep3 = () => {
    setFormError(null);
    return true;
  };

  const validateStep4 = () => {
    setFormError(null);
    return true;
  };

  const validateStep5 = () => {
    setFormError(null);
    return true;
  };

  const handleNextStep = () => {
    if (currentStep === 1 && !validateStep1()) return;
    if (currentStep === 2 && !validateStep2()) return;
    if (currentStep === 3 && !validateStep3()) return;
    if (currentStep === 4 && !validateStep4()) return;
    if (currentStep < TOTAL_STEPS) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handlePreviousStep = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleSubmit = async () => {
    if (!validateStep1() || !validateStep2() || !validateStep3() || !validateStep4()) {
      toast({
        title: "Validation Error",
        description: formError || "Please check previous steps for errors.",
        variant: "destructive",
      });
      return;
    }

    setIsSubmitting(true);
    setFormError(null);

    const payloadConfigCleaningRules: BackendCleaningRuleConfig[] = configuredCleaningRules
      .filter((rule) => rule.enabled)
      .map((rule) => ({ name: rule.name, enabled: rule.enabled, params: rule.userParams }));

    const payload: DatasetCreatePayload = {
      name: datasetName,
      description: datasetDescription || undefined,
      config: {
        feature_columns: selectedFeatureColumns,
        target_column: selectedTargetColumn,
        cleaning_rules: payloadConfigCleaningRules,
        feature_selection: featureSelectionConfig,
      },
    };

    try {
      const response = await apiService.createDataset(repositoryId, payload);
      toast({
        title: "Dataset Creation Task Submitted",
        description: `Dataset "${datasetName}" (ID: ${response.dataset_id}) is being generated. Task ID: ${response.task_id}`,
      });
      router.push(`/datasets/${response.dataset_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        handleApiError(err, "Failed to create dataset");
        setFormError("An unexpected error occurred.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const filteredMetrics = STATIC_AVAILABLE_METRICS.filter(
    (metric) =>
      metric.name.toLowerCase().includes(searchTermFeatures.toLowerCase()) ||
      metric.id.toLowerCase().includes(searchTermFeatures.toLowerCase()) ||
      metric.group.toLowerCase().includes(searchTermFeatures.toLowerCase())
  );

  const groupedMetrics = useMemo(() => {
    return filteredMetrics.reduce(
      (acc, metric) => {
        (acc[metric.group] = acc[metric.group] || []).push(metric);
        return acc;
      },
      {} as Record<MetricDefinition["group"], MetricDefinition[]>
    );
  }, [filteredMetrics]);

  const SectionCard: React.FC<{
    title: string;
    icon: React.ReactNode;
    children: React.ReactNode;
  }> = ({ title, icon, children }) => (
    <Card>
      <CardHeader className="pb-3 pt-4">
        <CardTitle className="text-base font-semibold flex items-center">
          <span className="mr-2 h-4 w-4 text-primary">{icon}</span>
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-sm space-y-3">{children}</CardContent>
    </Card>
  );

  const KeyValueItem: React.FC<{
    label: string;
    value?: string | number | null;
    badge?: boolean;
  }> = ({ label, value, badge }) => (
    <div className="flex justify-between items-start py-1.5 border-b border-dashed last:border-b-0">
      <dt className="text-muted-foreground">{label}:</dt>
      <dd className="font-medium text-right break-all">
        {value === null || value === undefined ? (
          <span className="text-muted-foreground italic">N/A</span>
        ) : badge ? (
          <Badge variant="secondary" className="text-xs">
            {String(value)}
          </Badge>
        ) : (
          String(value)
        )}
      </dd>
    </div>
  );

  return (
    <MainLayout>
      <PageContainer>
        <div className="flex items-center gap-4 mb-6">
          <Button
            variant="outline"
            size="icon"
            onClick={() => (currentStep === 1 ? router.back() : handlePreviousStep())}
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="sr-only">Back</span>
          </Button>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Create Dataset</h1>
        </div>

        <div className="flex justify-between items-center mb-6">
          <div className="flex space-x-2">
            {[1, 2, 3, 4, 5].map((stepNum) => (
              <div
                key={stepNum}
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-all
                            ${
                              currentStep === stepNum
                                ? "bg-primary text-primary-foreground scale-110"
                                : currentStep > stepNum
                                  ? "bg-primary/80 text-primary-foreground"
                                  : "border bg-muted text-muted-foreground"
                            }`}
              >
                {currentStep > stepNum ? <Check className="h-4 w-4" /> : stepNum}
              </div>
            ))}
          </div>
          <div className="text-sm text-muted-foreground">
            Step {currentStep} of {TOTAL_STEPS}
          </div>
        </div>

        {formError && (
          <Alert variant="destructive" className="mb-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{formError}</AlertDescription>
          </Alert>
        )}

        {currentStep === 1 && (
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>
                Select a repository and provide general details for your dataset.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="repositoryId">Repository *</Label>
                {isLoadingRepos ? (
                  <Skeleton className="h-10 w-full" />
                ) : availableRepositories.length === 0 ? (
                  <Alert variant="default">
                    <Info className="h-4 w-4" />
                    <AlertDescription>
                      No repositories found.{" "}
                      <Link href="/repositories" className="underline">
                        Add a repository first.
                      </Link>
                    </AlertDescription>
                  </Alert>
                ) : (
                  <Select value={repositoryId} onValueChange={setRepositoryId} required>
                    <SelectTrigger id="repositoryId">
                      <SelectValue placeholder="Select a repository..." />
                    </SelectTrigger>
                    <SelectContent>
                      {availableRepositories.map((repo) => (
                        <SelectItem key={repo.id} value={repo.id.toString()}>
                          {repo.name} (ID: {repo.id})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="datasetName">Dataset Name *</Label>
                <Input
                  id="datasetName"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  placeholder="e.g., My Project - Commit Defects Dataset"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="datasetDescription">Description (Optional)</Label>
                <Textarea
                  id="datasetDescription"
                  value={datasetDescription}
                  onChange={(e) => setDatasetDescription(e.target.value)}
                  placeholder="A brief description of this dataset's purpose and scope."
                  rows={3}
                />
              </div>
            </CardContent>
            <CardFooter className="flex justify-end">
              <Button
                onClick={handleNextStep}
                disabled={isLoadingRepos || !repositoryId || !datasetName.trim()}
              >
                Next <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardFooter>
          </Card>
        )}

        {currentStep === 2 && (
          <Card>
            <CardHeader>
              <CardTitle>Feature & Target Selection</CardTitle>
              <CardDescription>
                Choose the features and the target variable for your dataset.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="feature-search">Search Features</Label>
                <Input
                  id="feature-search"
                  placeholder="Type to filter features..."
                  value={searchTermFeatures}
                  onChange={(e) => setSearchTermFeatures(e.target.value)}
                />
              </div>
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-lg font-medium">
                    Available Features ({selectedFeatureColumns.length} selected) *
                  </h3>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => handleSelectAllFeatures()}>
                      {STATIC_AVAILABLE_METRICS.every((m) => selectedFeatureColumns.includes(m.id))
                        ? "Deselect All"
                        : "Select All"}
                    </Button>
                    {Object.keys(groupedMetrics).map((groupName) => (
                      <Button
                        key={groupName}
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          handleSelectAllFeatures(groupName as MetricDefinition["group"])
                        }
                      >
                        {groupedMetrics[groupName as MetricDefinition["group"]].every((m) =>
                          selectedFeatureColumns.includes(m.id)
                        )
                          ? `Deselect ${groupName}`
                          : `Select ${groupName}`}
                      </Button>
                    ))}
                  </div>
                </div>
                <TooltipProvider delayDuration={100}>
                  <ScrollArea className="h-[400px] rounded-md border p-4">
                    {Object.entries(groupedMetrics).map(([groupName, metricsInGroup]) => (
                      <div key={groupName} className="mb-4">
                        <h4 className="text-md font-semibold mb-2 sticky top-0 bg-background/95 py-1 z-10">
                          {groupName} (
                          {
                            metricsInGroup.filter((m) => selectedFeatureColumns.includes(m.id))
                              .length
                          }
                          /{metricsInGroup.length})
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-3">
                          {metricsInGroup.map((metric) => (
                            <div key={metric.id} className="flex items-center space-x-2">
                              <Checkbox
                                id={`metric-${metric.id}`}
                                checked={selectedFeatureColumns.includes(metric.id)}
                                onCheckedChange={() => handleFeatureToggle(metric.id)}
                              />
                              <Label
                                htmlFor={`metric-${metric.id}`}
                                className="text-sm font-normal cursor-pointer"
                              >
                                {metric.name}
                              </Label>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <button
                                    type="button"
                                    className="cursor-help"
                                    onClick={(e) => e.preventDefault()}
                                  >
                                    <HelpCircle className="h-4 w-4 text-muted-foreground" />
                                  </button>
                                </TooltipTrigger>
                                <TooltipContent className="max-w-xs text-sm">
                                  <p className="font-bold">
                                    {metric.name}{" "}
                                    <span className="text-xs font-normal text-muted-foreground">
                                      ({metric.group})
                                    </span>
                                  </p>
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    {metric.description}
                                  </p>
                                </TooltipContent>
                              </Tooltip>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </ScrollArea>
                </TooltipProvider>
              </div>
              <Separator />
              <div className="space-y-4">
                <h3 className="text-lg font-medium">Target Column *</h3>
                <Select
                  value={selectedTargetColumn}
                  onValueChange={setSelectedTargetColumn}
                  required
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select target variable..." />
                  </SelectTrigger>
                  <SelectContent>
                    {STATIC_AVAILABLE_TARGETS.map((target) => (
                      <SelectItem key={target.id} value={target.id}>
                        {target.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-sm text-muted-foreground">
                  {STATIC_AVAILABLE_TARGETS.find((t) => t.id === selectedTargetColumn)?.description}
                </p>
              </div>
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button variant="outline" onClick={handlePreviousStep}>
                <ArrowLeft className="mr-2 h-4 w-4" /> Previous
              </Button>
              <Button
                onClick={handleNextStep}
                disabled={selectedFeatureColumns.length === 0 || !selectedTargetColumn}
              >
                Next <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardFooter>
          </Card>
        )}

        {currentStep === 3 && (
          <Card>
            <CardHeader>
              <CardTitle>Data Cleaning Rules</CardTitle>
              <CardDescription>
                Configure rules to preprocess and clean your dataset.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {isLoadingRules ? (
                <Skeleton className="h-40 w-full" />
              ) : availableRuleDefinitions.length === 0 ? (
                <Alert variant="default">
                  <Info className="h-4 w-4" />
                  <AlertDescription>No cleaning rules available from the backend.</AlertDescription>
                </Alert>
              ) : (
                <ScrollArea className="h-[50vh]">
                  <div className="pr-4 space-y-4">
                    {configuredCleaningRules.map((rule) => (
                      <div
                        key={rule.name}
                        className="space-y-3 pt-4 border-t first:border-t-0 first:pt-0"
                      >
                        <div className="flex items-start space-x-3">
                          <Switch
                            id={`rule-switch-${rule.name}`}
                            checked={rule.enabled}
                            onCheckedChange={(checked) =>
                              handleRuleEnabledChange(rule.name, Boolean(checked))
                            }
                            className="mt-1"
                          />
                          <div className="flex-grow grid gap-1.5 leading-none">
                            <Label
                              htmlFor={`rule-switch-${rule.name}`}
                              className="text-base font-semibold cursor-pointer"
                            >
                              {rule.name
                                .replace(/_/g, " ")
                                .replace(/\b\w/g, (l) => l.toUpperCase())}
                            </Label>
                            <p className="text-sm text-muted-foreground">{rule.description}</p>
                          </div>
                        </div>
                        {rule.enabled && rule.parameters && rule.parameters.length > 0 && (
                          <div className="ml-7 pl-4 border-l space-y-4 py-3">
                            {rule.parameters.map((paramDef) => (
                              <div key={paramDef.name} className="space-y-1.5">
                                <div className="flex items-center space-x-2">
                                  <Label
                                    htmlFor={`${rule.name}-${paramDef.name}`}
                                    className="text-sm"
                                  >
                                    {paramDef.name.replace(/_/g, " ")}
                                  </Label>
                                  <TooltipProvider delayDuration={100}>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <HelpCircle className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                                      </TooltipTrigger>
                                      <TooltipContent>
                                        <p>{paramDef.description}</p>
                                      </TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                </div>
                                <Input
                                  type={paramDef.type === "integer" ? "number" : "text"}
                                  id={`${rule.name}-${paramDef.name}`}
                                  value={String(
                                    rule.userParams[paramDef.name] ?? paramDef.default ?? ""
                                  )}
                                  onChange={(e) =>
                                    handleRuleParamChange(rule.name, paramDef.name, e.target.value)
                                  }
                                  className="h-9"
                                  placeholder={`Default: ${paramDef.default}`}
                                />
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button variant="outline" onClick={handlePreviousStep}>
                <ArrowLeft className="mr-2 h-4 w-4" /> Previous
              </Button>
              <Button onClick={handleNextStep}>
                Next <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </CardFooter>
          </Card>
        )}

        {currentStep === 4 && (
          <>
            <FeatureSelectionStep
              availableAlgorithms={availableAlgorithms}
              selectionConfig={featureSelectionConfig}
              onConfigChange={setFeatureSelectionConfig}
            />
            <div className="flex justify-between mt-6">
              <Button variant="outline" onClick={handlePreviousStep}>
                <ArrowLeft className="mr-2 h-4 w-4" /> Previous
              </Button>
              <Button onClick={handleNextStep}>
                Next <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </>
        )}

        {currentStep === 5 && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <CheckCircle2 className="mr-2 h-5 w-5 text-primary" />
                  Review & Submit
                </CardTitle>
                <CardDescription>
                  Review all configurations below before submitting the job to generate your
                  dataset.
                </CardDescription>
              </CardHeader>
            </Card>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <SectionCard title="General Information" icon={<GitBranch />}>
                <KeyValueItem
                  label="Repository"
                  value={
                    availableRepositories.find((r) => r.id.toString() === repositoryId)?.name ||
                    `ID: ${repositoryId}`
                  }
                />
                <KeyValueItem label="Dataset Name" value={datasetName} />
                {datasetDescription && (
                  <div>
                    <Label className="text-xs text-muted-foreground uppercase block mb-1">
                      Description
                    </Label>
                    <p className="text-xs italic bg-muted/30 p-2 rounded-md whitespace-pre-wrap">
                      {datasetDescription}
                    </p>
                  </div>
                )}
              </SectionCard>
              <SectionCard title="Data Structure" icon={<Database />}>
                <KeyValueItem label="Target Column" value={selectedTargetColumn} badge />
                <div>
                  <Label className="text-xs text-muted-foreground uppercase block mb-1">
                    Features ({selectedFeatureColumns.length})
                  </Label>
                  <ScrollArea className="h-28 rounded-md border bg-muted/30 p-2">
                    <ul className="list-disc list-inside pl-2 text-xs space-y-0.5">
                      {selectedFeatureColumns.map((f) => (
                        <li key={f} className="truncate" title={f}>
                          {f}
                        </li>
                      ))}
                    </ul>
                  </ScrollArea>
                </div>
              </SectionCard>
              <SectionCard title="Processing Pipeline" icon={<ListFilter />}>
                <div>
                  <Label className="text-xs text-muted-foreground uppercase block mb-1">
                    Data Cleaning ({configuredCleaningRules.filter((r) => r.enabled).length}{" "}
                    enabled)
                  </Label>
                  <ScrollArea className="h-32 rounded-md border bg-muted/30 p-2">
                    {configuredCleaningRules.filter((r) => r.enabled).length > 0 ? (
                      <ul className="space-y-1.5 text-xs">
                        {configuredCleaningRules
                          .filter((r) => r.enabled)
                          .map((rule) => (
                            <li
                              key={rule.name}
                              className="border-b border-dashed pb-1.5 last:pb-0 last:border-0"
                            >
                              <p className="font-medium">{rule.name}</p>
                              {Object.keys(rule.userParams).length > 0 && (
                                <dl className="mt-1 pl-3 text-xs">
                                  {Object.entries(rule.userParams).map(([key, val]) => (
                                    <KeyValueItem key={key} label={key} value={String(val)} />
                                  ))}
                                </dl>
                              )}
                            </li>
                          ))}
                      </ul>
                    ) : (
                      <p className="text-xs italic text-muted-foreground p-2">
                        No cleaning rules enabled.
                      </p>
                    )}
                  </ScrollArea>
                </div>
                <Separator className="my-3" />
                <div>
                  <Label className="text-xs text-muted-foreground uppercase block mb-1">
                    Feature Selection
                  </Label>
                  {featureSelectionConfig ? (
                    <div className="text-xs p-2 rounded-md bg-muted/30 border">
                      <p className="font-medium">
                        {availableAlgorithms.find((a) => a.name === featureSelectionConfig.name)
                          ?.display_name || featureSelectionConfig.name}
                      </p>
                      {Object.keys(featureSelectionConfig.params).length > 0 && (
                        <dl className="mt-1 pt-1 border-t border-dashed">
                          {Object.entries(featureSelectionConfig.params).map(([key, val]) => (
                            <KeyValueItem key={key} label={key} value={String(val)} />
                          ))}
                        </dl>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs italic text-muted-foreground p-2">
                      Feature selection is disabled.
                    </p>
                  )}
                </div>
              </SectionCard>
            </div>
            <div className="flex justify-between mt-8">
              <Button variant="outline" onClick={handlePreviousStep}>
                <ArrowLeft className="mr-2 h-4 w-4" /> Previous
              </Button>
              <Button onClick={handleSubmit} disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Submitting...
                  </>
                ) : (
                  "Submit & Generate Dataset"
                )}
              </Button>
            </div>
          </div>
        )}
      </PageContainer>
    </MainLayout>
  );
}

function CheckmarkIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export default function CreateDatasetPage() {
  return (
    <Suspense fallback={<PageLoader message="Loading dataset creation form..." />}>
      <CreateDatasetPageContent />
    </Suspense>
  );
}
