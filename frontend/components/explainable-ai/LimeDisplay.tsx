// frontend/components/explainable-ai/LimeDisplay.tsx
import React, { useState, useMemo, useEffect } from 'react';
import { LIMEResultData } from '@/types/api';
import { XaiInstanceSelector } from './XaiInstanceSelector';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from '@/components/ui/alert';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, LabelList } from 'recharts';
import { InfoCircledIcon, RocketIcon } from '@radix-ui/react-icons';
import { Label } from '@/components/ui/label';

interface LimeDisplayProps {
  data?: LIMEResultData | null;
}

const CustomLimeTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const weight = payload[0].value;
    const contribution = weight > 0 ? "Supports this prediction" : "Opposes this prediction";
    return (
      <div className="bg-popover border border-border p-2 shadow-lg rounded-md text-sm text-popover-foreground">
        <p className="font-bold text-popover-foreground max-w-xs break-words">{label}</p> {/* label is the feature_condition */}
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
      const identifier = firstInstance.class_name || firstInstance.file || `instance_0`;
      setSelectedInstanceId(identifier);
    }
  }, [instances, selectedInstanceId]);

  const selectedInstanceData = useMemo(() => {
    if (!selectedInstanceId) return null;
    return instances.find(inst => (inst.class_name || inst.file || `instance_${instances.indexOf(inst)}`) === selectedInstanceId);
  }, [instances, selectedInstanceId]);

  if (!data || instances.length === 0) {
    return (
      <Alert variant="default" className="text-foreground bg-card border-border">
        <InfoCircledIcon className="h-4 w-4 text-muted-foreground"/>
        <AlertDescription className="text-muted-foreground">No LIME data available for this prediction.</AlertDescription>
      </Alert>
    );
  }
  
  const chartData = selectedInstanceData?.explanation
    .map(item => ({ 
        name: item[0], // feature condition
        weight: item[1],
        fillColor: item[1] > 0 ? 'hsl(var(--primary))' : 'hsl(var(--destructive))',
        labelFillColor: item[1] > 0 ? 'hsl(var(--primary-foreground))' : 'hsl(var(--destructive-foreground))'
    }))
    .sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight)) // Sort by absolute weight
    .slice(0, 15) // Top 15 features
    .reverse(); // For horizontal bar chart

  return (
    <Card className="bg-card text-card-foreground border-border">
      <CardHeader>
        <CardTitle className="flex items-center text-lg"><RocketIcon className="mr-2 h-5 w-5 text-primary"/>LIME Explanations</CardTitle>
        <CardDescription className="text-muted-foreground">
          Local Interpretable Model-agnostic Explanations. Shows feature contributions for a specific prediction.
          Positive weights (blue) support the predicted class, negative weights (red) oppose it.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <XaiInstanceSelector
          instances={instances}
          selectedIdentifier={selectedInstanceId}
          onInstanceChange={setSelectedInstanceId}
          label="Select Code Instance (Class/File)"
          identifierKey="class_name"
        />
        {chartData && chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 35)}>
            <BarChart 
                data={chartData} 
                layout="vertical" 
                margin={{ top: 5, right: 70, left: 200, bottom: 20 }} // Increased left margin for longer conditions
            >
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5}/>
              <XAxis type="number" stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} />
              <YAxis 
                dataKey="name" 
                type="category" 
                width={250} // Adjusted for feature conditions
                tickFormatter={(value) => value.length > 35 ? value.substring(0,32) + '...' : value} // Truncate long labels
                tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} 
                interval={0} 
                stroke="hsl(var(--muted-foreground))"
              />
              <Tooltip content={<CustomLimeTooltip />} cursor={{ fill: 'hsl(var(--accent))', fillOpacity: 0.3 }} />
              <Legend 
                verticalAlign="top" 
                height={36} 
                wrapperStyle={{ color: 'hsl(var(--foreground))', fontSize: '12px' }}
                payload={[
                    { value: 'Supports Prediction', type: 'square', color: 'hsl(var(--primary))' },
                    { value: 'Opposes Prediction', type: 'square', color: 'hsl(var(--destructive))' },
                ]}
              />
              <ReferenceLine x={0} stroke="hsl(var(--border))" strokeWidth={1.5}/>
              <Bar dataKey="weight" name="LIME Weight" radius={[0,3,3,0]}>
                 {chartData.map((entry, index) => (
                  <LabelList 
                    key={`label-${index}`} 
                    dataKey="weight" 
                    position={entry.weight >= 0 ? "right" : "left"} 
                    offset={5}
                    formatter={(value: number) => value.toFixed(3)} 
                    fontSize={9}
                    fill={entry.labelFillColor}
                  />
                ))}
                {
                  chartData.map((entry, index) => (
                    <Bar key={`cell-${index}`} dataKey="weight" fill={entry.fillColor} />
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