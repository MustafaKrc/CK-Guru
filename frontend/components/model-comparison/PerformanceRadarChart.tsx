// frontend/components/model-comparison/PerformanceRadarChart.tsx

import React, { useMemo } from "react";
import { MLModelRead } from "@/types/api";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend as RechartsLegend,
  Tooltip as RechartsTooltip,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type RadarMetricKey = "accuracy" | "f1_weighted" | "precision_weighted" | "recall_weighted" | "roc_auc";

const RADAR_METRICS: { key: RadarMetricKey; label: string }[] = [
  { key: "accuracy", label: "Accuracy" },
  { key: "f1_weighted", label: "F1 (Weighted)" },
  { key: "precision_weighted", label: "Precision" },
  { key: "recall_weighted", label: "Recall" },
  { key: "roc_auc", label: "ROC AUC" },
];

const RECHARTS_COLORS = [
    "#3b82f6", "#10b981", "#f59e0b", "#ef4444", 
    "#8b5cf6", "#06b6d4", "#f97316", "#84cc16"
];

export const PerformanceRadarChart: React.FC<{ selectedModels: MLModelRead[] }> = ({
  selectedModels,
}) => {
  const radarData = useMemo(() => {
    return RADAR_METRICS.map(metric => {
        const dataPoint: { subject: string; [key: string]: string | number } = {
            subject: metric.label,
        };
        selectedModels.forEach(model => {
            const modelKey = `${model.name} v${model.version}`;
            dataPoint[modelKey] = model.performance_metrics?.[metric.key] ?? 0;
        });
        return dataPoint;
    });
  }, [selectedModels]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Overall Performance Radar</CardTitle>
        <CardDescription>A holistic view of model performance across key metrics (normalized 0-1).</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
            <PolarGrid stroke="hsl(var(--border))" opacity={0.5} />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} />
            <PolarRadiusAxis angle={30} domain={[0, 1]} tickFormatter={t => t.toFixed(2)} fontSize={10} />
            
            {selectedModels.map((model, index) => (
                <Radar
                    key={model.id}
                    name={`${model.name} v${model.version}`}
                    dataKey={`${model.name} v${model.version}`}
                    stroke={RECHARTS_COLORS[index % RECHARTS_COLORS.length]}
                    fill={RECHARTS_COLORS[index % RECHARTS_COLORS.length]}
                    fillOpacity={0.2}
                />
            ))}

            <RechartsLegend wrapperStyle={{fontSize: "12px", paddingTop: "20px"}}/>
            <RechartsTooltip
                contentStyle={{
                    backgroundColor: "hsl(var(--background))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "var(--radius)",
                    fontSize: "12px"
                }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};