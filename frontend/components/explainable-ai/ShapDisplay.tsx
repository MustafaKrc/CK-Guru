// frontend/components/explainable-ai/ShapDisplay.tsx
import React, { useState, useMemo, useEffect } from 'react';
import { SHAPResultData, InstanceSHAPResult } from '@/types/api';
import { XaiInstanceSelector } from './XaiInstanceSelector';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from '@/components/ui/alert';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, LabelList } from 'recharts';
import { InfoCircledIcon, ShuffleIcon } from '@radix-ui/react-icons';
import { Label } from '@/components/ui/label';

interface ShapDisplayProps {
  data?: SHAPResultData | null;
}

const CustomShapTooltip = ({ active, payload, label, baseValue }: any) => {
  if (active && payload && payload.length) {
    const shapValue = payload[0].value;
    const featureValue = payload[0].payload.feature_value_display; // Use pre-formatted display value
    const contribution = shapValue > 0 ? "Increases prediction" : "Decreases prediction";
    return (
      <div className="bg-popover border border-border p-2 shadow-lg rounded-md text-sm text-popover-foreground">
        <p className="font-bold text-popover-foreground">{label}</p>
        {featureValue !== undefined && <p className="text-muted-foreground">Feature Value: {featureValue}</p>}
        <p style={{ color: shapValue > 0 ? 'hsl(var(--destructive))' : 'hsl(var(--primary))' }}>
          SHAP Value: {shapValue.toFixed(4)} ({contribution})
        </p>
         {baseValue !== undefined && <p className="text-xs text-muted-foreground">Prediction = Base ({baseValue.toFixed(4)}) + Sum(SHAP)</p>}
      </div>
    );
  }
  return null;
};


export const ShapDisplay: React.FC<ShapDisplayProps> = ({ data }) => {
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | undefined>(undefined);

  const instances = useMemo(() => data?.instance_shap_values || [], [data]);

  useEffect(() => {
    if (instances.length > 0 && !selectedInstanceId) {
      const firstInstance = instances[0];
      // Construct a unique identifier, preferring class_name then file, then index
      const identifier = firstInstance.class_name || firstInstance.file || `instance_0`;
      setSelectedInstanceId(identifier);
    }
  }, [instances, selectedInstanceId]);

  const selectedInstanceData = useMemo(() => {
    if (!selectedInstanceId) return null;
    return instances.find(inst => 
        (inst.class_name || inst.file || `instance_${instances.indexOf(inst)}`) === selectedInstanceId
    );
  }, [instances, selectedInstanceId]);

  if (!data || instances.length === 0) {
    return (
      <Alert variant="default" className="text-foreground bg-card border-border">
        <InfoCircledIcon className="h-4 w-4 text-muted-foreground"/>
        <AlertDescription className="text-muted-foreground">No SHAP data available for this prediction.</AlertDescription>
      </Alert>
    );
  }
  
  // Format feature_value for display, handling objects/arrays
  const formatFeatureDisplayValue = (value: any): string => {
    if (typeof value === 'object' && value !== null) {
      return JSON.stringify(value);
    }
    if (typeof value === 'number' && !Number.isInteger(value)) {
      return value.toFixed(3);
    }
    return String(value);
  };

  const chartData = selectedInstanceData?.shap_values
    .map(item => ({ 
        ...item, 
        abs_value: Math.abs(item.value),
        feature_value_display: formatFeatureDisplayValue(item.feature_value), // Pre-format for tooltip
        fillColor: item.value > 0 ? 'hsl(var(--destructive))' : 'hsl(var(--primary))',
        labelFillColor: item.value > 0 ? 'hsl(var(--destructive-foreground))' : 'hsl(var(--primary-foreground))'
    }))
    .sort((a, b) => b.abs_value - a.abs_value)
    .slice(0, 20) // Top 20 features by absolute SHAP value
    .reverse(); // For horizontal bar chart, reverse to show most important at top

  const baseValue = selectedInstanceData?.base_value;
  const predictedValue = baseValue !== undefined && chartData 
    ? baseValue + chartData.reduce((sum, item) => sum + item.value, 0)
    : undefined;

  return (
    <Card className="bg-card text-card-foreground border-border">
      <CardHeader>
        <CardTitle className="flex items-center text-lg"><ShuffleIcon className="mr-2 h-5 w-5 text-primary"/>SHAP Values</CardTitle>
        <CardDescription className="text-muted-foreground">
          Explains how each feature contributed to pushing the model's prediction away from the baseline.
          Positive values (red) increase the prediction towards being defect-prone; negative values (blue) decrease it.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <XaiInstanceSelector
          instances={instances}
          selectedIdentifier={selectedInstanceId}
          onInstanceChange={setSelectedInstanceId}
          label="Select Code Instance (Class/File)"
          identifierKey="class_name" // Prioritize class_name for SHAP instance selection
        />
        {selectedInstanceData && (
            <div className="grid grid-cols-2 gap-4 text-sm mb-4 p-3 border rounded-md bg-muted/30 dark:bg-muted/20">
                <div>
                    <Label className="text-xs text-muted-foreground">Baseline (Average Outcome)</Label>
                    <p className="font-semibold text-lg">{baseValue !== undefined ? baseValue.toFixed(4) : "N/A"}</p>
                </div>
                <div>
                    <Label className="text-xs text-muted-foreground">Final Prediction for this Instance</Label>
                    <p className="font-semibold text-lg">{predictedValue !== undefined ? predictedValue.toFixed(4) : "N/A"}</p>
                </div>
            </div>
        )}
        {chartData && chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 35)}>
            <BarChart 
                data={chartData} 
                layout="vertical"
                margin={{ top: 5, right: 70, left: 120, bottom: 20 }} // Adjusted margins
            >
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5}/>
              <XAxis type="number" stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
              <YAxis 
                dataKey="name" 
                type="category" 
                width={170} // Adjusted for feature names
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} 
                interval={0} 
                stroke="hsl(var(--muted-foreground))"
              />
              <Tooltip content={<CustomShapTooltip baseValue={baseValue}/>} cursor={{ fill: 'hsl(var(--accent))', fillOpacity: 0.3 }}/>
              <Legend 
                verticalAlign="top" 
                height={36} 
                wrapperStyle={{ color: 'hsl(var(--foreground))', fontSize: '12px' }}
                payload={[
                    { value: 'Increases Defect Risk', type: 'square', color: 'hsl(var(--destructive))' },
                    { value: 'Decreases Defect Risk', type: 'square', color: 'hsl(var(--primary))' },
                ]}
              />
              <ReferenceLine x={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
              <Bar dataKey="shap_value" name="SHAP Value" radius={[0, 3, 3, 0]}>
                {chartData.map((entry, index) => (
                  <LabelList 
                    key={`label-${index}`} 
                    dataKey="shap_value" 
                    position={entry.value >= 0 ? "right" : "left"} 
                    offset={entry.value >= 0 ? 5 : 5} // Adjust offset for left/right
                    formatter={(value: number) => value.toFixed(3)} 
                    fontSize={9}
                    fill={entry.labelFillColor}
                  />
                ))}
                {/* Cell for dynamic fill */}
                {chartData.map((entry, index) => (
                    <Bar key={`cell-${index}`} dataKey="shap_value" fill={entry.fillColor} />
                ))}
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