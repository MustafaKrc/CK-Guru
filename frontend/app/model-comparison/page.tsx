// frontend/app/model-comparison/page.tsx
"use client";

import React, { useState, useEffect, useCallback, useMemo, Suspense } from "react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { RefreshCw, AlertTriangle, Download } from "lucide-react";
import { toast } from "@/components/ui/use-toast";

import { MainLayout } from "@/components/main-layout";
import { PageContainer } from "@/components/ui/page-container";
import { PageLoader } from "@/components/ui/page-loader";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";

import { apiService, handleApiError } from "@/lib/apiService";
import { MLModelRead } from "@/types/api";

import { ModelSelectionPanel } from "@/components/model-comparison/ModelSelectionPanel";
import { ComparisonCanvas } from "@/components/model-comparison/ComparisonCanvas";

export const MAX_SELECTED_MODELS = 5; // Increased limit slightly

function ModelComparisonPageContent() {
  const [allModels, setAllModels] = useState<MLModelRead[]>([]);
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* TODO: we must use server side filtering later */
  const fetchAllModels = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiService.getModels({ limit: 500 });
      setAllModels(response.items || []);
    } catch (err) {
      handleApiError(err, "Failed to load models");
      setError(err instanceof Error ? err.message : "Could not load models.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllModels();
  }, [fetchAllModels]);

  const selectedModels = useMemo(() => {
    return selectedModelIds
      .map(id => allModels.find(m => String(m.id) === id))
      .filter((m): m is MLModelRead => !!m);
  }, [selectedModelIds, allModels]);

  const handleToggleModelSelection = useCallback((modelId: string) => {
    setSelectedModelIds(prev => {
      if (prev.includes(modelId)) {
        return prev.filter(id => id !== modelId);
      }
      if (prev.length >= MAX_SELECTED_MODELS) {
        toast({
          title: "Selection Limit Reached",
          description: `You can select up to ${MAX_SELECTED_MODELS} models for comparison.`,
          variant: "default"
        });
        return prev;
      }
      return [...prev, modelId];
    });
  }, []);
  
  const handleExportReport = () => {
    toast({ title: "Export Report", description: "This feature is coming soon!" });
  };


  if (isLoading) {
    return <PageLoader message="Loading models for comparison..." />;
  }

  if (error) {
    return (
      <MainLayout>
        <PageContainer title="Error Loading Models" description={error}>
          <Alert variant="destructive" className="mb-4">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Loading Failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Button onClick={fetchAllModels}><RefreshCw className="mr-2 h-4 w-4"/>Try Again</Button>
        </PageContainer>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <PageContainer
        title="Model Comparison"
        description="Select and compare models based on their performance metrics."
        actions={<Button variant="outline" onClick={handleExportReport}><Download className="mr-2 h-4 w-4" />Export Report</Button>}
        className="p-0 pt-0 md:p-0"
      >
        <div className="h-[calc(100vh-theme(spacing.24))]">
          <ResizablePanelGroup direction="horizontal" className="h-full rounded-none border-none">
            <ResizablePanel defaultSize={20} minSize={20} maxSize={40}>
              <ModelSelectionPanel
                allModels={allModels}
                selectedIds={selectedModelIds}
                onToggleSelection={handleToggleModelSelection}
                isLoading={isLoading}
              />
            </ResizablePanel>
            <ResizableHandle withHandle />
            <ResizablePanel defaultSize={70} minSize={60}>
              <ComparisonCanvas selectedModels={selectedModels} />
            </ResizablePanel>
          </ResizablePanelGroup>
        </div>
      </PageContainer>
    </MainLayout>
  );
}

export default function ModelComparisonPage() {
  return (
    <Suspense fallback={<PageLoader message="Loading model comparison..." />}>
      <ModelComparisonPageContent />
    </Suspense>
  );
}