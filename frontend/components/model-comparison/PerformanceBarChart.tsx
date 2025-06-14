// frontend/components/model-comparison/PerformanceBarChart.tsx

import React, { useMemo, useState } from "react";
import { MLModelRead } from "@/types/api";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend as RechartsLegend,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "../ui/label";

// Define a type for the metrics we can compare
type ComparableConceptMetricKey =
  | "accuracy"
  | "f1_weighted"
  | "precision_weighted"
  | "recall_weighted"
  | "roc_auc"
  | "log_loss"
  | "training_time_seconds";

const BAR_CHART_METRIC_OPTIONS: {
  value: ComparableConceptMetricKey;
  label: string;
}[] = [
  { value: "accuracy", label: "Accuracy" },
  { value: "f1_weighted", label: "F1 Score (Weighted)" },
  { value: "precision_weighted", label: "Precision (Weighted)" },
  { value: "recall_weighted", label: "Recall (Weighted)" },
  { value: "roc_auc", label: "ROC AUC" },
  { value: "log_loss", label: "Log Loss" },
  { value: "training_time_seconds", label: "Training Time (s)" },
];

const RECHARTS_COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#f97316",
  "#84cc16",
];

const formatMetricValue = (value: any): string => {
  if (typeof value !== "number") return "N/A";
  if (value === 0) return "0.000";
  if (Math.abs(value) < 0.001) return value.toExponential(2);
  if (Math.abs(value) < 1) return value.toFixed(4);
  if (Math.abs(value) < 100) return value.toFixed(2);
  return value.toLocaleString();
};

export const PerformanceBarChart: React.FC<{ selectedModels: MLModelRead[] }> = ({
  selectedModels,
}) => {
  const [metricKey, setMetricKey] = useState<ComparableConceptMetricKey>("f1_weighted");

  const chartData = useMemo(() => {
    return selectedModels.map((model) => ({
      name: `${model.name} v${model.version}`,
      value: model.performance_metrics?.[metricKey] ?? 0,
    }));
  }, [selectedModels, metricKey]);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <CardTitle>Performance Metric Comparison</CardTitle>
            <CardDescription>Compare models on a specific metric.</CardDescription>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Label htmlFor="metric-select" className="text-sm shrink-0">
              Metric:
            </Label>
            <Select
              value={metricKey}
              onValueChange={(v) => setMetricKey(v as ComparableConceptMetricKey)}
            >
              <SelectTrigger id="metric-select" className="w-full sm:w-[220px]">
                <SelectValue placeholder="Select a metric" />
              </SelectTrigger>
              <SelectContent>
                {BAR_CHART_METRIC_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={Math.max(250, chartData.length * 40)}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 100, right: 50 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
            <XAxis
              type="number"
              stroke="hsl(var(--muted-foreground))"
              fontSize={10}
              tickFormatter={formatMetricValue}
            />
            <YAxis
              dataKey="name"
              type="category"
              width={150}
              tick={{ fontSize: 11 }}
              stroke="hsl(var(--muted-foreground))"
              interval={0}
            />
            <RechartsTooltip
              cursor={{ fill: "hsl(var(--accent))", fillOpacity: 0.3 }}
              contentStyle={{
                backgroundColor: "hsl(var(--background))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "var(--radius)",
                fontSize: "12px",
              }}
              formatter={(value) => formatMetricValue(value)}
            />
            <Bar
              dataKey="value"
              name={BAR_CHART_METRIC_OPTIONS.find((m) => m.value === metricKey)?.label || "Value"}
              barSize={25}
              radius={[0, 4, 4, 0]}
            >
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={RECHARTS_COLORS[index % RECHARTS_COLORS.length]}
                />
              ))}
              <LabelList
                dataKey="value"
                position="right"
                formatter={(v: any) => formatMetricValue(v)}
                fontSize={10}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};
