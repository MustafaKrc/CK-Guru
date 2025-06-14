// frontend/components/model-comparison/MetricsComparisonTable.tsx

import React from "react";
import { MLModelRead } from "@/types/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { ScrollArea, ScrollBar } from "../ui/scroll-area";

interface MetricsComparisonTableProps {
  selectedModels: MLModelRead[];
}

const METRICS_TO_DISPLAY: {
  key: string;
  label: string;
  higherIsBetter: boolean;
}[] = [
  { key: "accuracy", label: "Accuracy", higherIsBetter: true },
  { key: "f1_weighted", label: "F1 Score (Weighted)", higherIsBetter: true },
  { key: "precision_weighted", label: "Precision (Weighted)", higherIsBetter: true },
  { key: "recall_weighted", label: "Recall (Weighted)", higherIsBetter: true },
  { key: "roc_auc", label: "ROC AUC", higherIsBetter: true },
  { key: "log_loss", label: "Log Loss", higherIsBetter: false },
  { key: "training_time_seconds", label: "Training Time (s)", higherIsBetter: false },
];

const formatMetricValue = (value: any): string => {
  if (typeof value !== "number") return "N/A";
  if (value === 0) return "0.000";
  if (Math.abs(value) < 0.001) return value.toExponential(2);
  if (Math.abs(value) < 1) return value.toFixed(4);
  if (Math.abs(value) < 100) return value.toFixed(2);
  return value.toLocaleString();
};

export const MetricsComparisonTable: React.FC<MetricsComparisonTableProps> = ({
  selectedModels,
}) => {
  const findBestValue = (metricKey: string, higherIsBetter: boolean) => {
    const values = selectedModels
      .map((m) => m.performance_metrics?.[metricKey])
      .filter((v): v is number => typeof v === "number");

    if (values.length === 0) return null;

    return higherIsBetter ? Math.max(...values) : Math.min(...values);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Key Metrics Comparison</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="w-full whitespace-nowrap">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="min-w-[150px] sticky left-0 bg-card z-10">Metric</TableHead>
                {selectedModels.map((model) => (
                  <TableHead key={model.id} className="text-center">
                    {model.name} v{model.version}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {METRICS_TO_DISPLAY.map((metric) => {
                const bestValue = findBestValue(metric.key, metric.higherIsBetter);
                return (
                  <TableRow key={metric.key}>
                    <TableCell className="font-medium sticky left-0 bg-card z-10">
                      {metric.label}
                    </TableCell>
                    {selectedModels.map((model) => {
                      const value = model.performance_metrics?.[metric.key];
                      const isBest = value !== undefined && value !== null && value === bestValue;
                      return (
                        <TableCell
                          key={`${model.id}-${metric.key}`}
                          className="text-center font-mono text-xs"
                        >
                          <Badge
                            variant={isBest ? "default" : "secondary"}
                            className={cn(
                              isBest && "bg-green-600/80 text-white dark:bg-green-500/80"
                            )}
                          >
                            {formatMetricValue(value)}
                          </Badge>
                        </TableCell>
                      );
                    })}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <ScrollBar orientation="horizontal" />
        </ScrollArea>
      </CardContent>
    </Card>
  );
};
