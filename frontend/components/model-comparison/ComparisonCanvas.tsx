// frontend/components/model-comparison/ComparisonCanvas.tsx

import React from "react";
import { MLModelRead } from "@/types/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { BarChart3 } from "lucide-react";

import { MetricsComparisonTable } from "./MetricsComparisonTable";
import { PerformanceBarChart } from "./PerformanceBarChart";
import { PerformanceRadarChart } from "./PerformanceRadarChart";

interface ComparisonCanvasProps {
  selectedModels: MLModelRead[];
}

export const ComparisonCanvas: React.FC<ComparisonCanvasProps> = ({ selectedModels }) => {
  if (selectedModels.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-lg border-2 border-dashed bg-muted/50 p-8 text-center">
        <div>
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-4">
            <BarChart3 className="h-6 w-6 text-primary" />
          </div>
          <h3 className="text-lg font-semibold">Select Models to Compare</h3>
          <p className="text-muted-foreground mt-2">
            Use the panel on the left to select one or more models.
            <br />
            Their performance metrics will be displayed here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full overflow-auto">
      <div className="p-4 space-x-6 min-w-max">
        <MetricsComparisonTable selectedModels={selectedModels} />
        <PerformanceBarChart selectedModels={selectedModels} />
        <PerformanceRadarChart selectedModels={selectedModels} />
      </div>
    </ScrollArea>
  );
};
