// frontend/app/prediction-insights/[id]/page.tsx
"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";

// UI Components
import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoCircledIcon, ExclamationTriangleIcon, CheckCircledIcon, ReloadIcon, PlayIcon, RocketIcon, BarChartIcon, CodeIcon, Share1Icon, ShuffleIcon, MixerHorizontalIcon, TargetIcon } from "@radix-ui/react-icons";
import { toast } from "sonner";

import { cn } from "@/lib/utils";

// API Services & Types
import { 
  getInferenceJobDetails, 
  getXAIResultsForJob, 
  triggerXAIProcessing,
  handleApiError 
} from "@/lib/apiService"; 

import {
  InferenceJobRead,
  XAIResultRead,
  FeatureImportanceResultData,
  SHAPResultData,
  LIMEResultData,
  CounterfactualResultData,
  DecisionPathResultData,
} from "@/types/api"; 

import { JobStatusEnum, XAIStatusEnum, XAITypeEnum } from "@/types/api/enums";

// XAI Display Components
import { FeatureImportanceDisplay } from "@/components/explainable-ai/FeatureImportanceDisplay";
import { ShapDisplay } from "@/components/explainable-ai/ShapDisplay";
import { LimeDisplay } from "@/components/explainable-ai/LimeDisplay";
import { DecisionPathDisplay } from "@/components/explainable-ai/DecisionPathDisplay";
import { CounterfactualsDisplay } from "@/components/explainable-ai/CounterfactualsDisplay";

const PredictionInsightDetailPage = () => {
  const params = useParams();
  const router = useRouter();
  const inferenceJobId = params.id as string;

  const [inferenceJobDetails, setInferenceJobDetails] = useState<InferenceJobRead | null>(null);
  const [xaiResults, setXaiResults] = useState<XAIResultRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isTriggering, setIsTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("");

  const fetchAllData = useCallback(async (showLoadingToast = false) => {
    if (!inferenceJobId) return;
    if (showLoadingToast) toast.loading("Refreshing XAI data...", { id: `fetch-data-${inferenceJobId}` });

    setIsLoading(true);
    setError(null);

    try {
      const jobDetailsPromise = getInferenceJobDetails(inferenceJobId);
      const xaiResultsPromise = getXAIResultsForJob(inferenceJobId);
      
      const [jobDetailsResponse, xaiResultsResponse] = await Promise.all([jobDetailsPromise, xaiResultsPromise]);
      
      setInferenceJobDetails(jobDetailsResponse);
      setXaiResults(xaiResultsResponse || []);

      if (xaiResultsResponse && xaiResultsResponse.length > 0) {
        const currentActiveTabIsValid = activeTab && xaiResultsResponse.some(r => r.xai_type === activeTab && r.status === XAIStatusEnum.SUCCESS);
        if (!currentActiveTabIsValid) {
            const firstSuccess = xaiResultsResponse.find(r => r.status === XAIStatusEnum.SUCCESS);
            if (firstSuccess) {
                setActiveTab(firstSuccess.xai_type);
            } else {
                 const firstPendingOrRunning = xaiResultsResponse.find(r => r.status === XAIStatusEnum.PENDING || r.status === XAIStatusEnum.RUNNING);
                 if(firstPendingOrRunning) setActiveTab(firstPendingOrRunning.xai_type);
                 else if (xaiResultsResponse[0]) setActiveTab(xaiResultsResponse[0].xai_type);
                 else setActiveTab(XAITypeEnum.FEATURE_IMPORTANCE);
            }
        }
      } else {
        setActiveTab(XAITypeEnum.FEATURE_IMPORTANCE); // Default if no results
      }
      if (showLoadingToast) toast.success("Data refreshed!", { id: `fetch-data-${inferenceJobId}` });
    } catch (err) {
      const defaultMessage = "Failed to load insight details.";
      handleApiError(err, defaultMessage); 
      if (err instanceof Error) setError(err.message); else setError(defaultMessage);
    } finally {
      setIsLoading(false);
    }
  }, [inferenceJobId, activeTab]);

  useEffect(() => {
    fetchAllData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inferenceJobId]); 

  const handleTriggerXAI = async () => {
    if (!inferenceJobId || inferenceJobDetails?.status !== JobStatusEnum.SUCCESS) {
        toast.warning("XAI can only be triggered for successful inference jobs.");
        return;
    }
    setIsTriggering(true);
    setError(null);
    const triggerToastId = `trigger-xai-${inferenceJobId}`;
    toast.loading("Triggering XAI generation...", { id: triggerToastId });

    try {
      const response = await triggerXAIProcessing(inferenceJobId);
      toast.success(response.message || "XAI generation tasks submitted.", { id: triggerToastId });
      setTimeout(() => fetchAllData(true), 3000); 
    } catch (err) {
      const defaultMessage = "Failed to trigger XAI generation.";
      toast.dismiss(triggerToastId); // Dismiss the loading toast
      handleApiError(err, defaultMessage); // handleApiError will show its own toast
      if (err instanceof Error) setError(err.message); else setError(defaultMessage);
    } finally {
      setIsTriggering(false);
    }
  };

  const getXAIStatusBadge = (status: XAIStatusEnum, message?: string | null) => {
    let icon: React.ReactNode = <InfoCircledIcon className="mr-1 h-3 w-3" />;
    let variant: "default" | "destructive" | "secondary" | "outline" = "secondary";
    let text = status.charAt(0) + status.slice(1).toLowerCase();

    switch (status) {
      case XAIStatusEnum.SUCCESS: icon = <CheckCircledIcon className="mr-1 h-3 w-3" />; variant = "default"; text="Success"; break;
      case XAIStatusEnum.FAILED: icon = <ExclamationTriangleIcon className="mr-1 h-3 w-3" />; variant = "destructive"; text="Failed"; break;
      case XAIStatusEnum.PENDING: icon = <ReloadIcon className="mr-1 h-3 w-3 animate-spin" />; variant = "outline"; text="Pending"; break;
      case XAIStatusEnum.RUNNING: icon = <ReloadIcon className="mr-1 h-3 w-3 animate-spin" />; variant = "secondary"; text="Running"; break;
      default: break;
    }
    return <Badge variant={variant} className="ml-2 text-xs whitespace-nowrap py-0.5 px-1.5" title={message || status}>{icon}{text}</Badge>;
  };

  const getJobStatusBadge = (status?: JobStatusEnum) => {
    if (!status) return <Badge variant="secondary">Unknown</Badge>;
    switch (status) {
      case JobStatusEnum.SUCCESS: return <Badge variant="default" className="bg-green-600 hover:bg-green-700">Success</Badge>;
      case JobStatusEnum.FAILED: return <Badge variant="destructive">Failure</Badge>;
      default: return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const xaiTypeIcons: Record<XAITypeEnum, React.ReactNode> = {
    [XAITypeEnum.FEATURE_IMPORTANCE]: <TargetIcon className="mr-1 sm:mr-2 h-3.5 w-3.5 sm:h-4 sm:w-4"/>,
    [XAITypeEnum.SHAP]: <MixerHorizontalIcon className="mr-1 sm:mr-2 h-3.5 w-3.5 sm:h-4 sm:w-4"/>,
    [XAITypeEnum.LIME]: <RocketIcon className="mr-1 sm:mr-2 h-3.5 w-3.5 sm:h-4 sm:w-4"/>,
    [XAITypeEnum.COUNTERFACTUALS]: <ShuffleIcon className="mr-1 sm:mr-2 h-3.5 w-3.5 sm:h-4 sm:w-4"/>,
    [XAITypeEnum.DECISION_PATH]: <Share1Icon className="mr-1 sm:mr-2 h-3.5 w-3.5 sm:h-4 sm:w-4"/>,
  };
  
  const availableXaiTabs = useMemo(() => {
    const order: XAITypeEnum[] = Object.values(XAITypeEnum); // Use defined order
    return order.filter(type => 
        xaiResults?.some(r => r.xai_type === type)
    );
  }, [xaiResults]);

  useEffect(() => {
    // Auto-select tab logic refined
    if (!activeTab && availableXaiTabs.length > 0) {
      const firstSuccess = availableXaiTabs.find(type => xaiResults.find(r => r.xai_type === type)?.status === XAIStatusEnum.SUCCESS);
      if (firstSuccess) {
        setActiveTab(firstSuccess);
      } else {
        const firstInProgress = availableXaiTabs.find(type => xaiResults.find(r => r.xai_type === type)?.status === XAIStatusEnum.RUNNING || xaiResults.find(r => r.xai_type === type)?.status === XAIStatusEnum.PENDING);
        setActiveTab(firstInProgress || availableXaiTabs[0] || XAITypeEnum.FEATURE_IMPORTANCE);
      }
    } else if (activeTab && !availableXaiTabs.includes(activeTab as XAITypeEnum) && availableXaiTabs.length > 0) {
        // If current activeTab is no longer valid (e.g. data removed), switch to first available
        setActiveTab(availableXaiTabs[0]);
    } else if (availableXaiTabs.length === 0) {
        setActiveTab(XAITypeEnum.FEATURE_IMPORTANCE); // Default if nothing available
    }
  }, [availableXaiTabs, activeTab, xaiResults]);

  const renderXAIContent = (xaiType: XAITypeEnum) => {
    const result = xaiResults?.find(r => r.xai_type === xaiType);
    if (!result) return <Alert variant="default" className="mt-4"><InfoCircledIcon className="mr-2 h-4 w-4"/>No data available yet for this explanation type. Try generating explanations.</Alert>;

    switch (result.status) {
      case XAIStatusEnum.SUCCESS:
        if (!result.result_data) return <Alert variant="default" className="mt-4"><ExclamationTriangleIcon className="mr-2 h-4 w-4"/>Explanation data is missing though status is success.</Alert>;
        switch (xaiType) {
          case XAITypeEnum.FEATURE_IMPORTANCE:
            return <FeatureImportanceDisplay data={result.result_data as FeatureImportanceResultData} />;
          case XAITypeEnum.SHAP:
            return <ShapDisplay data={result.result_data as SHAPResultData} />;
          case XAITypeEnum.LIME:
            return <LimeDisplay data={result.result_data as LIMEResultData} />;
          case XAITypeEnum.COUNTERFACTUALS:
            return <CounterfactualsDisplay data={result.result_data as CounterfactualResultData} originalInstanceData={inferenceJobDetails?.prediction_result ? { features: inferenceJobDetails.input_reference.features || {}, predictionProbability: inferenceJobDetails.prediction_result.max_bug_probability } : null }/>;
          case XAITypeEnum.DECISION_PATH:
            return <DecisionPathDisplay data={result.result_data as DecisionPathResultData} />;
          default:
            return <Alert variant="default" className="mt-4">Unsupported XAI type for display: {xaiType}</Alert>;
        }
      case XAIStatusEnum.PENDING:
      case XAIStatusEnum.RUNNING:
        return (
          <Alert variant="default" className="flex items-center mt-4 py-6 justify-center">
            <ReloadIcon className="mr-2 h-5 w-5 animate-spin" />
            <div className="text-center">
                <p className="font-medium">Explanation generation is {result.status.toLowerCase()}.</p>
                <p className="text-xs text-muted-foreground">{result.status_message || "Please check back soon."}</p>
            </div>
          </Alert>
        );
      case XAIStatusEnum.FAILED:
        return (
          <Alert variant="destructive" className="mt-4 py-6">
            <ExclamationTriangleIcon className="mr-2 h-5 w-5" />
            <div>
                <AlertTitle>Explanation Generation Failed</AlertTitle>
                <AlertDescription>{result.status_message || "An unknown error occurred."}</AlertDescription>
            </div>
          </Alert>
        );
      default:
        return <Alert variant="default" className="mt-4">{result.status_message || `Status: ${result.status}`}</Alert>;
    }
  };

  const renderMainContent = () => {
    if (!inferenceJobDetails) {
        // This case should be covered by the main page loading skeleton
        return <Alert variant="default"><InfoCircledIcon className="h-4 w-4" /> Inference job details not found or still loading.</Alert>
    }
    
    const predictionOutcome = inferenceJobDetails.prediction_result?.commit_prediction;
    const outcomeText = predictionOutcome === 1 ? "Defect-Prone" : predictionOutcome === 0 ? "Clean" : "N/A";
    const outcomeVariant : "default" | "destructive" | "secondary" = predictionOutcome === 1 ? "destructive" : predictionOutcome === 0 ? "default" : "secondary";

    return (
      <>
        <Card className="mb-6">
          <CardHeader>
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center">
                <div className="mb-3 md:mb-0">
                    <CardTitle className="text-xl md:text-2xl">
                        Inference Overview
                    </CardTitle>
                    <CardDescription className="mt-1 text-xs md:text-sm">
                        Summary of the prediction for job ID {inferenceJobDetails.id}.
                    </CardDescription>
                </div>
                {inferenceJobDetails.prediction_result && (
                    <Badge variant={outcomeVariant} className="text-sm md:text-base px-3 py-1.5 self-start md:self-center">
                        Prediction: {outcomeText}
                    </Badge>
                )}
            </div>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 text-sm">
            <div className="space-y-1 p-3 border rounded-md bg-muted/30">
                <p className="text-xs text-muted-foreground">Model ID</p>
                <p className="font-semibold"><Link href={`/models/${inferenceJobDetails.ml_model_id}`} className="text-primary hover:underline">{inferenceJobDetails.ml_model_id}</Link></p>
            </div>
            <div className="space-y-1 p-3 border rounded-md bg-muted/30">
                <p className="text-xs text-muted-foreground">Commit Hash</p>
                <p className="font-mono text-xs" title={String(inferenceJobDetails.input_reference?.commit_hash)}>{String(inferenceJobDetails.input_reference?.commit_hash).substring(0,12) || "N/A"}...</p>
            </div>
             <div className="space-y-1 p-3 border rounded-md bg-muted/30">
                <p className="text-xs text-muted-foreground">Max Bug Probability</p>
                <p className="font-semibold">{inferenceJobDetails.prediction_result?.max_bug_probability?.toFixed(4) ?? "N/A"}</p>
            </div>
             <div className="space-y-1 p-3 border rounded-md bg-muted/30">
                <p className="text-xs text-muted-foreground">Files Analyzed</p>
                <p className="font-semibold">{inferenceJobDetails.prediction_result?.num_files_analyzed ?? "N/A"}</p>
            </div>
          </CardContent>
        </Card>

        {inferenceJobDetails.status !== JobStatusEnum.SUCCESS ? (
          <Alert variant="default" className="mb-6">
            <InfoCircledIcon className="h-4 w-4" />
            <AlertTitle>XAI Not Available</AlertTitle>
            <AlertDescription>
              Explainability features can only be generated for successfully completed inference jobs. Current job status: {getJobStatusBadge(inferenceJobDetails.status)}.
            </AlertDescription>
          </Alert>
        ) : (isLoading && !xaiResults?.length) ? (
          <Tabs defaultValue={XAITypeEnum.FEATURE_IMPORTANCE} className="w-full">
            {/* Skeleton TabsList - simplified for brevity, ensure it matches structure */}
            <TabsList className="grid w-full grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-1 bg-muted p-1 rounded-lg">
              {Object.values(XAITypeEnum).map(type => (
                <TabsTrigger value={type} key={type} disabled className="h-auto py-2 px-1.5 text-xs sm:text-sm">
                  <Skeleton className="h-5 w-full" />
                  <Skeleton className="h-4 w-1/2 mt-1" />
                </TabsTrigger>
              ))}
            </TabsList>
            <TabsContent value={XAITypeEnum.FEATURE_IMPORTANCE} className="mt-4"><Skeleton className="h-80 w-full" /></TabsContent>
          </Tabs>
        ) : availableXaiTabs.length > 0 && activeTab ? (
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-1 bg-muted p-1 rounded-lg h-auto min-h-[60px]">
              {availableXaiTabs.map((type) => {
                const xaiResult = xaiResults.find(r => r.xai_type === type);
                const isActive = activeTab === type;
                return (
                  <TabsTrigger
                    key={type}
                    value={type}
                    disabled={isLoading}
                    className={cn(
                      "flex-col h-full min-h-[52px] py-2 px-1.5 text-xs sm:text-sm transition-all rounded-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 items-center justify-center", 
                      isActive
                        ? "bg-primary text-primary-foreground shadow-sm" 
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground", 
                      "data-[disabled]:opacity-50 data-[disabled]:pointer-events-none" 
                    )}
                  >
                    <span className="flex items-center mb-0.5">
                      {xaiTypeIcons[type as XAITypeEnum]}
                      {type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                    {xaiResult && getXAIStatusBadge(xaiResult.status, xaiResult.status_message)}
                  </TabsTrigger>
                );
              })}
            </TabsList>
            {availableXaiTabs.map((type) => (
              <TabsContent key={type} value={type} className="mt-6">
                {renderXAIContent(type as XAITypeEnum)}
              </TabsContent>
            ))}
          </Tabs>
        ) : (
            !isLoading && (
                <Card className="mt-6">
                    <CardHeader><CardTitle>No Explanations Available</CardTitle></CardHeader>
                    <CardContent>
                        <p>No XAI results have been generated for this inference job yet.</p>
                        <p className="mt-2">If the inference job was successful, you can try generating them using the button at the top of the page.</p>
                    </CardContent>
                </Card>
            )
        )}
      </>
    );
  };
  
   if (isLoading && !inferenceJobDetails && !xaiResults) {
    return (
      <MainLayout>
        <PageContainer title="Loading Prediction Insights...">
          <Skeleton className="h-12 w-1/2 mb-6" />
          <Skeleton className="h-64 w-full" />
        </PageContainer>
      </MainLayout>
    );
  }

  if (error && !inferenceJobDetails && !xaiResults) {
    return (
      <MainLayout>
        <PageContainer title="Error Loading Insights" description={error}>
          <Alert variant="destructive">
            <ExclamationTriangleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error || "Could not load prediction insights."}</AlertDescription>
          </Alert>
          <Button onClick={() => fetchAllData(true)} className="mt-4">Try Again</Button>
        </PageContainer>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <PageContainer
        title={`Prediction Insights: Job #${inferenceJobDetails?.id || inferenceJobId}`}
        description={
          inferenceJobDetails ? (
            <span className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              <span>Model ID: 
                <Link href={`/models/${inferenceJobDetails.ml_model_id}`} className="text-primary hover:underline ml-1">{inferenceJobDetails.ml_model_id}</Link>
              </span>
              <span>Status: {getJobStatusBadge(inferenceJobDetails.status)}</span>
              {inferenceJobDetails.input_reference?.commit_hash && (
                <span className="text-xs text-muted-foreground">
                  Commit: {String(inferenceJobDetails.input_reference.commit_hash).substring(0, 12)}...
                </span>
              )}
            </span>
          ) : "Loading job details..."
        }
        actions={
          <div className="flex gap-2">
             <Button variant="outline" onClick={() => fetchAllData(true)} disabled={isLoading || isTriggering} size="sm">
              <ReloadIcon className={`mr-2 h-4 w-4 ${(isLoading || isTriggering) ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            {inferenceJobDetails?.status === JobStatusEnum.SUCCESS && (
              <Button onClick={handleTriggerXAI} disabled={isTriggering || isLoading} size="sm">
                {isTriggering ? <ReloadIcon className="mr-2 h-4 w-4 animate-spin" /> : <RocketIcon className="mr-2 h-4 w-4" />}
                {xaiResults && xaiResults.filter(r => r.status === XAIStatusEnum.SUCCESS).length > 0 ? "Regenerate All" : "Generate Explanations"}
              </Button>
            )}
          </div>
        }
      >
        {renderMainContent()}
      </PageContainer>
    </MainLayout>
  );
};

export default PredictionInsightDetailPage;