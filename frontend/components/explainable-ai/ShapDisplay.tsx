// frontend/components/explainable-ai/ShapDisplay.tsx
import React, { useState, useMemo, useEffect } from 'react';
import { SHAPResultData, InstanceSHAPResult } from '@/types/api';
import { XaiInstanceSelector } from './XaiInstanceSelector';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from '@/components/ui/alert';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, LabelList } from 'recharts';
import { InfoCircledIcon } from '@radix-ui/react-icons';

interface ShapDisplayProps {
  data?: SHAPResultData | null;
}

const CustomTooltip = ({ active, payload, label, baseValue }: any) => {
  if (active && payload && payload.length) {
    const shapValue = payload[0].value;
    const featureValue = payload[0].payload.feature_value;
    const contribution = shapValue > 0 ? "Increases prediction" : "Decreases prediction";
    return (
      <div className="bg-background border p-2 shadow-lg rounded-md text-sm">
        <p className="font-bold">{label}</p>
        {featureValue !== undefined && <p className="text-muted-foreground">Feature Value: {featureValue}</p>}
        <p style={{ color: shapValue > 0 ? 'hsl(var(--destructive))' : 'hsl(var(--primary))' }}>
          SHAP Value: {shapValue.toFixed(4)} ({contribution})
        </p>
         {baseValue !== undefined && <p className="text-xs">Prediction = Base ({baseValue.toFixed(4)}) + Sum of SHAP values</p>}
      </div>
    );
  }
  return null;
};


export const ShapDisplay: React.FC<ShapDisplayProps> = ({ data }) => {
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | undefined>(undefined);

  const instances = useMemo(() => data?.instance_shap_values || [], [data]);

  useEffect(() => {
    // Auto-select the first instance if available and none is selected
    if (instances.length > 0 && !selectedInstanceId) {
      const firstInstance = instances[0];
      setSelectedInstanceId(firstInstance.class_name || firstInstance.file || `instance_0`);
    }
  }, [instances, selectedInstanceId]);

  const selectedInstanceData = useMemo(() => {
    if (!selectedInstanceId) return null;
    return instances.find(inst => (inst.class_name || inst.file || `instance_${instances.indexOf(inst)}`) === selectedInstanceId);
  }, [instances, selectedInstanceId]);

  if (!data || instances.length === 0) {
    return (
      <Alert variant="default">
        <InfoCircledIcon className="h-4 w-4"/>
        <AlertDescription>No SHAP data available for this prediction.</AlertDescription>
      </Alert>
    );
  }
  
  const chartData = selectedInstanceData?.shap_values
    .map(item => ({ ...item, abs_value: Math.abs(item.value) }))
    .sort((a, b) => b.abs_value - a.abs_value)
    .slice(0, 15) // Top 15 features by absolute SHAP value
    .map(item => ({
        name: item.feature,
        shap_value: item.value,
        feature_value: item.feature_value
    }))
    .reverse(); // For horizontal bar chart, reverse to show most important at top

  const baseValue = selectedInstanceData?.base_value;

  return (
    <Card>
      <CardHeader>
        <CardTitle>SHAP (SHapley Additive exPlanations) Values</CardTitle>
        <CardDescription>
          Explains how each feature contributed to pushing the model's prediction away from the baseline (average prediction).
          Positive SHAP values increase the prediction, negative values decrease it.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <XaiInstanceSelector
          instances={instances}
          selectedIdentifier={selectedInstanceId}
          onInstanceChange={setSelectedInstanceId}
          label="Select Code Instance (Class/File)"
        />
        {selectedInstanceData && baseValue !== undefined && (
             <p className="text-sm mb-4">
                <strong>Baseline Prediction (Average):</strong> {baseValue.toFixed(4)}
             </p>
        )}
        {chartData && chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 40)}>
            <BarChart 
                data={chartData} 
                layout="vertical"
                margin={{ top: 5, right: 50, left: 100, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.3}/>
              <XAxis type="number" />
              <YAxis dataKey="name" type="category" width={150} tick={{ fontSize: 11 }} interval={0} />
              <Tooltip content={<CustomTooltip baseValue={baseValue}/>} cursor={{ fill: 'hsl(var(--muted))' }}/>
              <Legend verticalAlign="top" height={36}/>
              <ReferenceLine x={0} stroke="hsl(var(--border))" strokeWidth={2} />
              <Bar dataKey="shap_value" name="SHAP Value" radius={[0, 4, 4, 0]}>
                {chartData.map((entry, index) => (
                  <LabelList 
                    key={`label-${index}`} 
                    dataKey="shap_value" 
                    position={entry.shap_value >= 0 ? "right" : "left"} 
                    offset={5}
                    formatter={(value: number) => value.toFixed(3)} 
                    fontSize={10}
                    fill={entry.shap_value >=0 ? 'hsl(var(--destructive-foreground))' : 'hsl(var(--primary-foreground))'}
                  />
                ))}
                {/* Conditional fill based on value */}
                {
                  chartData.map((entry, index) => (
                    <Bar key={`cell-${index}`} dataKey="shap_value" fill={entry.shap_value > 0 ? 'hsl(var(--destructive))' : 'hsl(var(--primary))'} />
                  ))
                }
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : selectedInstanceId ? (
          <p className="text-sm text-muted-foreground">No SHAP values to display for the selected instance.</p>
        ) : (
           <p className="text-sm text-muted-foreground">Select an instance to view SHAP values.</p>
        )}
      </CardContent>
    </Card>
  );
};