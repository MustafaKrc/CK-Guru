// frontend/components/explainable-ai/LimeDisplay.tsx
import React, { useState, useMemo, useEffect } from 'react';
import { LIMEResultData, InstanceLIMEResult } from '@/types/api';
import { XaiInstanceSelector } from './XaiInstanceSelector';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from '@/components/ui/alert';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, LabelList } from 'recharts';
import { InfoCircledIcon } from '@radix-ui/react-icons';

interface LimeDisplayProps {
  data?: LIMEResultData | null;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const weight = payload[0].value;
    const contribution = weight > 0 ? "Supports prediction" : "Opposes prediction";
    return (
      <div className="bg-background border p-2 shadow-lg rounded-md text-sm">
        <p className="font-bold">{label}</p> {/* label is the feature_condition */}
        <p style={{ color: weight > 0 ? 'hsl(var(--primary))' : 'hsl(var(--destructive))' }}>
          Weight: {weight.toFixed(4)} ({contribution})
        </p>
      </div>
    );
  }
  return null;
};


export const LimeDisplay: React.FC<LimeDisplayProps> = ({ data }) => {
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | undefined>(undefined);

  const instances = useMemo(() => data?.instance_lime_values || [], [data]);

 useEffect(() => {
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
        <AlertDescription>No LIME data available for this prediction.</AlertDescription>
      </Alert>
    );
  }
  
  const chartData = selectedInstanceData?.explanation
    .map(item => ({ name: item[0], weight: item[1] }))
    .sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight)) // Sort by absolute weight
    .slice(0, 15) // Top 15 features
    .reverse(); // For horizontal bar chart

  return (
    <Card>
      <CardHeader>
        <CardTitle>LIME (Local Interpretable Model-agnostic Explanations)</CardTitle>
        <CardDescription>
          Shows feature contributions for a specific prediction. Positive weights support the predicted class, negative weights oppose it.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <XaiInstanceSelector
          instances={instances}
          selectedIdentifier={selectedInstanceId}
          onInstanceChange={setSelectedInstanceId}
          label="Select Code Instance (Class/File)"
        />
        {chartData && chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 40)}>
            <BarChart 
                data={chartData} 
                layout="vertical" 
                margin={{ top: 5, right: 50, left: 200, bottom: 20 }} // Increased left margin
            >
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.3}/>
              <XAxis type="number" />
              <YAxis dataKey="name" type="category" width={200} tick={{ fontSize: 10 }} interval={0} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'hsl(var(--muted))' }} />
              <Legend verticalAlign="top" height={36}/>
              <ReferenceLine x={0} stroke="hsl(var(--border))" strokeWidth={2}/>
              <Bar dataKey="weight" name="LIME Weight" radius={[0,4,4,0]}>
                 {chartData.map((entry, index) => (
                  <LabelList 
                    key={`label-${index}`} 
                    dataKey="weight" 
                    position={entry.weight >= 0 ? "right" : "left"} 
                    offset={5}
                    formatter={(value: number) => value.toFixed(3)} 
                    fontSize={10}
                    fill={entry.weight >=0 ? 'hsl(var(--primary-foreground))' : 'hsl(var(--destructive-foreground))'}
                  />
                ))}
                {
                  chartData.map((entry, index) => (
                    <Bar key={`cell-${index}`} dataKey="weight" fill={entry.weight > 0 ? 'hsl(var(--primary))' : 'hsl(var(--destructive))'} />
                  ))
                }
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : selectedInstanceId ? (
          <p className="text-sm text-muted-foreground">No LIME explanations to display for the selected instance.</p>
        ) : (
           <p className="text-sm text-muted-foreground">Select an instance to view LIME explanations.</p>
        )}
      </CardContent>
    </Card>
  );
};