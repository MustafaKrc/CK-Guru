"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";

// UI Components
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoCircledIcon, ExclamationTriangleIcon, CheckCircledIcon, ReloadIcon, PlayIcon } from "@radix-ui/react-icons";
import { toast } from "sonner";

// API Services & Types
import { 
  getInferenceJobDetails, 
  getXAIResultsForJob, 
  triggerXAIProcessing,
  handleApiError 
} from "../../../lib/apiService"; // Adjusted path
import {
  InferenceJobRead,
  XAIResultRead,
  XAITriggerResponse,
  JobStatusEnum,
  XAITypeEnum,
  XAIStatusEnum,
  FeatureImportanceResultData,
  SHAPResultData,
  LIMEResultData,
  CounterfactualResultData,
  DecisionPathResultData,
  // FilePredictionDetail, // Not directly used here, but available from ~/types/api
  // InferenceResultPackage, // Not directly used here, but available from ~/types/api
} from "~/types/api"; // Assuming path alias is configured for frontend/types/api


// XAI Components (Placeholders - these would ideally be more sophisticated)
const FeatureImportanceChart = ({ data }: { data: any }) => (
  <Card>
    <CardHeader><CardTitle>Feature Importances</CardTitle></CardHeader>
    <CardContent><pre className="text-xs bg-gray-100 p-2 rounded-md overflow-auto max-h-96">{JSON.stringify(data, null, 2)}</pre></CardContent>
  </Card>
);
const ShapValuesChart = ({ data, baseline }: { data: any, baseline?: number }) => (
   <Card>
    <CardHeader><CardTitle>SHAP Values (Instance 0)</CardTitle></CardHeader>
    <CardContent>
      {baseline !== undefined && <p className="text-sm text-muted-foreground">Baseline (Average Prediction): {baseline.toFixed(4)}</p>}
      <pre className="text-xs bg-gray-100 p-2 rounded-md overflow-auto max-h-96">{JSON.stringify(data, null, 2)}</pre>
    </CardContent>
  </Card>
);
const LimeExplanationDisplay = ({ data }: { data: any }) => (
 <Card>
    <CardHeader><CardTitle>LIME Explanations (Instance 0)</CardTitle></CardHeader>
    <CardContent><pre className="text-xs bg-gray-100 p-2 rounded-md overflow-auto max-h-96">{JSON.stringify(data, null, 2)}</pre></CardContent>
  </Card>
);
const CounterfactualExamplesDisplay = ({ data }: { data: any }) => (
  <Card>
    <CardHeader><CardTitle>Counterfactual Examples (Instance 0)</CardTitle></CardHeader>
    <CardContent><pre className="text-xs bg-gray-100 p-2 rounded-md overflow-auto max-h-96">{JSON.stringify(data, null, 2)}</pre></CardContent>
  </Card>
);
const DecisionPathVisualizer = ({ data }: { data: any }) => (
 <Card>
    <CardHeader><CardTitle>Decision Path (Instance 0)</CardTitle></CardHeader>
    <CardContent><pre className="text-xs bg-gray-100 p-2 rounded-md overflow-auto max-h-96">{JSON.stringify(data, null, 2)}</pre></CardContent>
  </Card>
);

const PredictionInsightDetailPage = () => {
  const params = useParams();
  const router = useRouter();
  const inferenceJobId = params.id as string; // Ensure this is correctly typed, string if from URL

  const [inferenceJobDetails, setInferenceJobDetails] = useState<InferenceJobRead | null>(null);
  const [xaiResults, setXaiResults] = useState<XAIResultRead[] | null>(null);
  const [isLoading, setIsLoading] = useState(true); // Combined loading state for initial fetch
  const [isTriggering, setIsTriggering] = useState(false); // Specific loading state for XAI trigger
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>(""); // Default active tab

  const fetchAllData = useCallback(async (showLoadingToast = false) => {
    if (!inferenceJobId) return;
    if(showLoadingToast) toast.loading("Refreshing XAI data...", {id: "fetch-data-toast"});

    setIsLoading(true); 
    setError(null);

    try {
      // Use dedicated service functions
      const jobDetailsPromise = getInferenceJobDetails(inferenceJobId);
      const xaiResultsPromise = getXAIResultsForJob(inferenceJobId);
      
      const [jobDetailsResponse, xaiResultsResponse] = await Promise.all([jobDetailsPromise, xaiResultsPromise]);
      
      setInferenceJobDetails(jobDetailsResponse);
      setXaiResults(xaiResultsResponse);

      // Logic to set active tab (remains the same as provided in the full example)
      if (xaiResultsResponse && xaiResultsResponse.length > 0) {
        if (!activeTab || !xaiResultsResponse.find(r => r.xai_type === activeTab)) {
            const firstSuccessOrPending = xaiResultsResponse.find(r => r.status === XAIStatusEnum.SUCCESS || r.status === XAIStatusEnum.PENDING || r.status === XAIStatusEnum.IN_PROGRESS);
            if (firstSuccessOrPending) {
                setActiveTab(firstSuccessOrPending.xai_type);
            } else if (xaiResultsResponse[0]) {
                setActiveTab(xaiResultsResponse[0].xai_type);
            }
        }
      } else {
        setActiveTab(""); // No results, no active tab
      }
      if(showLoadingToast) toast.success("Data refreshed!", {id: "fetch-data-toast"});
    } catch (err) {
      const defaultMessage = "Failed to load insight details.";
      // Assuming service functions throw ApiError or similar that handleApiError can process
      handleApiError(err, defaultMessage); 
      if (err instanceof Error) setError(err.message); else setError(defaultMessage);
      // No need to call toast.error if handleApiError already does it.
      // Based on apiService.ts, handleApiError shows the toast.
    } finally {
      setIsLoading(false);
    }
  }, [inferenceJobId, activeTab]);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  const handleTriggerXAI = async () => {
    if (!inferenceJobId || inferenceJobDetails?.status !== JobStatusEnum.SUCCESS) {
        toast.warning("XAI can only be triggered for successful inference jobs.");
        return;
    }
    setIsTriggering(true);
    setError(null);
    toast.loading("Triggering XAI generation...", { id: "trigger-xai-toast" });

    try {
      // Use dedicated service function
      const response = await triggerXAIProcessing(inferenceJobId);
      toast.success(response.message || "XAI generation started.", { id: "trigger-xai-toast" });
      setTimeout(() => fetchAllData(true), 3000); // Re-fetch with toast after a delay
    } catch (err) {
      const defaultMessage = "Failed to trigger XAI generation.";
      handleApiError(err, defaultMessage); // handleApiError shows the toast
      if (err instanceof Error) setError(err.message); else setError(defaultMessage);
    } finally {
      setIsTriggering(false);
    }
  };

  const getXAIStatusBadge = (status: XAIStatusEnum, message?: string | null) => {
    let icon = <InfoCircledIcon className="mr-1" />;
    let variant: "success" | "destructive" | "secondary" | "outline" | "warning" = "secondary";

    switch (status) {
      case XAIStatusEnum.SUCCESS: icon = <CheckCircledIcon className="mr-1" />; variant = "success"; break;
      case XAIStatusEnum.FAILURE: icon = <ExclamationTriangleIcon className="mr-1" />; variant = "destructive"; break;
      case XAIStatusEnum.PENDING: variant = "outline"; break;
      case XAIStatusEnum.IN_PROGRESS: variant = "secondary"; break;
      case XAIStatusEnum.NOT_APPLICABLE: variant = "warning"; break;
      default: break;
    }
    return <Badge variant={variant} className="ml-2 text-xs whitespace-nowrap" title={message || status}>{icon}{status}</Badge>;
  };

  const getJobStatusBadge = (status: JobStatusEnum) => {
    // Simplified version from previous task for brevity
    switch (status) {
      case JobStatusEnum.SUCCESS: return <Badge variant="success">Success</Badge>;
      case JobStatusEnum.FAILURE: return <Badge variant="destructive">Failure</Badge>;
      default: return <Badge variant="secondary">{status}</Badge>;
    }
  };

  // Prepare available XAI types for tabs, prioritizing successful ones
  const availableXaiTabs = Object.values(XAITypeEnum).filter(type => 
    xaiResults?.some(r => r.xai_type === type)
  ).sort((a,b) => { // Sort to put SUCCESS ones first, then PENDING/IN_PROGRESS
    const statusA = xaiResults?.find(r => r.xai_type === a)?.status === XAIStatusEnum.SUCCESS ? 0 : 1;
    const statusB = xaiResults?.find(r => r.xai_type === b)?.status === XAIStatusEnum.SUCCESS ? 0 : 1;
    return statusA - statusB;
  });


  if (isLoading && !inferenceJobDetails && !xaiResults) { // Initial full page load
    return (
      <div className="container mx-auto p-4 space-y-6">
        <Skeleton className="h-8 w-1/4" /> {/* Back button */}
        <Skeleton className="h-10 w-1/2" /> {/* Title */}
        <Card>
          <CardHeader><Skeleton className="h-6 w-1/3" /></CardHeader>
          <CardContent className="space-y-3">
            {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-5 w-full" />)}
          </CardContent>
        </Card>
        <Skeleton className="h-12 w-full" /> {/* Tabs Skeleton */}
        <Card>
          <CardHeader><Skeleton className="h-6 w-1/3" /></CardHeader>
          <CardContent><Skeleton className="h-40 w-full" /></CardContent>
        </Card>
      </div>
    );
  }

  if (error && !inferenceJobDetails && !xaiResults) { // Critical error loading initial data
    return (
      <div className="container mx-auto p-4 flex justify-center items-center h-[calc(100vh-200px)]">
        <Alert variant="destructive" className="max-w-lg">
          <ExclamationTriangleIcon className="h-4 w-4" />
          <AlertTitle>Error Loading Page</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
          <Button onClick={() => fetchAllData(true)} className="mt-4">Try Again</Button>
        </Alert>
      </div>
    );
  }
  
  const renderXAIContent = (xaiType: XAITypeEnum) => {
    const result = xaiResults?.find(r => r.xai_type === xaiType);
    if (!result) return <Alert variant="default"><InfoCircledIcon className="mr-2 h-4 w-4"/>No data available for this explanation type.</Alert>;

    switch (result.status) {
      case XAIStatusEnum.SUCCESS:
        if (!result.result_data) return <Alert variant="warning"><ExclamationTriangleIcon className="mr-2 h-4 w-4"/>Explanation data is missing.</Alert>;
        switch (xaiType) {
          case XAITypeEnum.FEATURE_IMPORTANCE:
            return <FeatureImportanceChart data={(result.result_data as FeatureImportanceResultData).feature_importances} />;
          case XAITypeEnum.SHAP: {
            const shapData = result.result_data as SHAPResultData;
            return shapData.instance_shap_values && shapData.instance_shap_values.length > 0 ? (
              <ShapValuesChart data={shapData.instance_shap_values[0].shap_values} baseline={shapData.instance_shap_values[0].base_value} />
            ) : <Alert variant="default"><InfoCircledIcon className="mr-2 h-4 w-4"/>No SHAP instances found.</Alert>;
          }
          case XAITypeEnum.LIME: {
            const limeData = result.result_data as LIMEResultData;
             return limeData.instance_lime_values && limeData.instance_lime_values.length > 0 ? (
              <LimeExplanationDisplay data={limeData.instance_lime_values[0].explanation} />
            ) : <Alert variant="default"><InfoCircledIcon className="mr-2 h-4 w-4"/>No LIME instances found.</Alert>;
          }
           case XAITypeEnum.COUNTERFACTUAL: {
            const cfData = result.result_data as CounterfactualResultData;
            return cfData.instance_counterfactuals && cfData.instance_counterfactuals.length > 0 ? (
              <CounterfactualExamplesDisplay data={cfData.instance_counterfactuals[0].counterfactuals} />
            ) : <Alert variant="default"><InfoCircledIcon className="mr-2 h-4 w-4"/>No Counterfactual instances found.</Alert>;
          }
          case XAITypeEnum.DECISION_PATH: {
            const dpData = result.result_data as DecisionPathResultData;
            return dpData.instance_decision_paths && dpData.instance_decision_paths.length > 0 ? (
               <DecisionPathVisualizer data={dpData.instance_decision_paths[0]} />
            ) : <Alert variant="default"><InfoCircledIcon className="mr-2 h-4 w-4"/>No Decision Path instances found.</Alert>;
          }
          default:
            return <Alert variant="warning">Unsupported XAI type for display.</Alert>;
        }
      case XAIStatusEnum.PENDING:
      case XAIStatusEnum.IN_PROGRESS:
        return (
          <Alert variant="default" className="flex items-center">
            <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
            Explanation generation is {result.status.toLowerCase()}. Please check back soon.
            {result.status_message && <p className="text-xs mt-1">{result.status_message}</p>}
          </Alert>
        );
      case XAIStatusEnum.FAILURE:
        return (
          <Alert variant="destructive">
            <ExclamationTriangleIcon className="mr-2 h-4 w-4" />
            Explanation generation failed: {result.status_message || "Unknown error."}
          </Alert>
        );
      default:
        return <Alert variant="outline">{result.status_message || `Status: ${result.status}`}</Alert>;
    }
  };

  return (
    <div className="container mx-auto p-4 space-y-6">
      <Button variant="outline" onClick={() => router.back()} className="mb-4">
        &larr; Back to Insights List
      </Button>

      <Card>
        <CardHeader className="flex flex-row justify-between items-start">
          <div>
            <CardTitle className="text-2xl">Inference Job #{inferenceJobDetails?.id || inferenceJobId}</CardTitle>
            {inferenceJobDetails && (
              <CardDescription>
                Model ID: {inferenceJobDetails.ml_model_id} | 
                Created: {new Date(inferenceJobDetails.created_at).toLocaleString()} | 
                Status: {getJobStatusBadge(inferenceJobDetails.status)}
                {inferenceJobDetails.input_reference.commit_hash && (
                    <span className="block text-xs text-gray-500 mt-1">
                      Commit: {String(inferenceJobDetails.input_reference.commit_hash).substring(0, 12)}...
                    </span>
                  )}
              </CardDescription>
            )}
          </div>
          {inferenceJobDetails?.status === JobStatusEnum.SUCCESS && (
            <Button onClick={handleTriggerXAI} disabled={isTriggering || isLoading} size="sm">
              {isTriggering ? <ReloadIcon className="mr-2 h-4 w-4 animate-spin" /> : <PlayIcon className="mr-2 h-4 w-4" />}
              {xaiResults && xaiResults.length > 0 ? "Regenerate Explanations" : "Generate Explanations"}
            </Button>
          )}
        </CardHeader>
        {inferenceJobDetails?.status !== JobStatusEnum.SUCCESS && (
             <CardContent>
                <Alert variant="info">
                    <InfoCircledIcon className="h-4 w-4"/>
                    <AlertTitle>XAI Not Available</AlertTitle>
                    <AlertDescription>
                        Explainability features can only be generated for successfully completed inference jobs. Current status: {inferenceJobDetails?.status}.
                    </AlertDescription>
                </Alert>
             </CardContent>
        )}
      </Card>
      
      {error && (!inferenceJobDetails || !xaiResults) && ( // Display general error if main data is missing
         <Alert variant="destructive" className="max-w-full">
          <ExclamationTriangleIcon className="h-4 w-4" />
          <AlertTitle>Page Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}


      {inferenceJobDetails?.status === JobStatusEnum.SUCCESS && (
        (isLoading && !xaiResults) ? ( // Loading XAI results specifically
            <Tabs defaultValue={XAITypeEnum.FEATURE_IMPORTANCE} className="w-full">
                <TabsList className="grid w-full grid-cols-3 md:grid-cols-5">
                    {Object.values(XAITypeEnum).map(type => <Skeleton key={type} className="h-10"/>)}
                </TabsList>
                <TabsContent value={XAITypeEnum.FEATURE_IMPORTANCE}><Skeleton className="h-60 w-full mt-4"/></TabsContent>
            </Tabs>
        ) : xaiResults && availableXaiTabs.length > 0 ? (
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {availableXaiTabs.map((type) => (
                <TabsTrigger key={type} value={type} disabled={isLoading}>
                  {type.replace(/_/g, ' ')}
                  {xaiResults.find(r => r.xai_type === type) && getXAIStatusBadge(xaiResults.find(r => r.xai_type === type)!.status)}
                </TabsTrigger>
              ))}
            </TabsList>
            {availableXaiTabs.map((type) => (
              <TabsContent key={type} value={type} className="mt-4">
                {renderXAIContent(type)}
              </TabsContent>
            ))}
          </Tabs>
        ) : (
          !isLoading && ( // Only show if not loading and no results/tabs
            <Card className="mt-6">
              <CardHeader>
                <CardTitle>No Explanations Available</CardTitle>
              </CardHeader>
              <CardContent>
                <p>No XAI results have been generated for this inference job yet, or the existing ones are not displayable.</p>
                <p className="mt-2">If the inference job was successful, you can try generating them.</p>
                {/* Trigger button already available above, but can add another one here if needed */}
              </CardContent>
            </Card>
          )
        )
      )}
    </div>
  );
};

export default PredictionInsightDetailPage;
