// frontend/components/explainable-ai/FeatureImportanceDisplay.tsx
import React from 'react';
import { FeatureImportanceResultData } from '@/types/api'; 
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LabelList } from 'recharts';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { InfoCircledIcon, BarChartIcon } from '@radix-ui/react-icons'; 

interface FeatureImportanceDisplayProps {
  data?: FeatureImportanceResultData | null;
}

const CustomFeatureImportanceTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-popover border border-border p-2 shadow-lg rounded-md text-sm text-popover-foreground">
        <p className="font-bold text-popover-foreground">{label}</p>
        {/* Ensure tooltip text color is also theme-aware if not covered by popover-foreground */}
        <p style={{ color: 'hsl(var(--primary))' }}>{`Importance: ${payload[0].value.toFixed(4)}`}</p>
      </div>
    );
  }
  return null;
};


export const FeatureImportanceDisplay: React.FC<FeatureImportanceDisplayProps> = ({ data }) => {
  if (!data || !data.feature_importances || data.feature_importances.length === 0) {
    return (
        <Alert variant="default" className="text-foreground bg-card border-border">
            <InfoCircledIcon className="h-4 w-4 text-muted-foreground"/>
            <AlertDescription className="text-muted-foreground">No feature importance data available for this prediction.</AlertDescription>
        </Alert>
    );
  }

  const chartData = data.feature_importances
    .filter(fi => fi.importance > 0.0001) 
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 20); 

  return (
    <Card className="bg-card text-card-foreground border-border">
      <CardHeader>
        <CardTitle className="flex items-center text-lg"><BarChartIcon className="mr-2 h-5 w-5 text-primary"/>Global Feature Importances</CardTitle>
        <CardDescription className="text-muted-foreground">
            Shows the most influential features for the model's predictions overall. Higher values indicate greater impact.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={Math.max(300, chartData.length * 30)}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 50, left: 120, bottom: 5 }} // Increased right margin for LabelList
          >
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.5}/>
            <XAxis 
                type="number" 
                domain={[0, 'dataMax + 0.05']} 
                tickFormatter={(tick) => tick.toFixed(2)} 
                stroke="hsl(var(--muted-foreground))" 
                tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
            />
            <YAxis 
              dataKey="feature" 
              type="category" 
              width={170} 
              tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
              interval={0} 
              stroke="hsl(var(--muted-foreground))"
            />
            <Tooltip 
                content={<CustomFeatureImportanceTooltip />} 
                cursor={{ fill: 'hsl(var(--accent))', fillOpacity: 0.3 }} 
            />
            <Legend 
                verticalAlign="top" 
                height={36} 
                wrapperStyle={{ color: 'hsl(var(--foreground))', fontSize: '12px' }}
            />
            <Bar dataKey="importance" name="Importance" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]}>
              <LabelList 
                dataKey="importance" 
                position="right" 
                formatter={(value: number) => value.toFixed(3)} 
                fontSize={10} 
                fill="hsl(var(--foreground))" // Changed from primary-foreground for better contrast on primary bar
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};