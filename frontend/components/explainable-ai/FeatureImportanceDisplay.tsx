// frontend/components/explainable-ai/FeatureImportanceDisplay.tsx
import React from 'react';
import { FeatureImportanceResultData } from '@/types/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LabelList } from 'recharts';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { InfoCircledIcon } from '@radix-ui/react-icons';

interface FeatureImportanceDisplayProps {
  data?: FeatureImportanceResultData | null;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-background border p-2 shadow-lg rounded-md text-sm">
        <p className="font-bold">{label}</p>
        <p className="text-primary">{`Importance: ${payload[0].value.toFixed(4)}`}</p>
      </div>
    );
  }
  return null;
};


export const FeatureImportanceDisplay: React.FC<FeatureImportanceDisplayProps> = ({ data }) => {
  if (!data || !data.feature_importances || data.feature_importances.length === 0) {
    return (
        <Alert variant="default">
            <InfoCircledIcon className="h-4 w-4"/>
            <AlertDescription>No feature importance data available for this prediction.</AlertDescription>
        </Alert>
    );
  }

  const chartData = data.feature_importances
    .filter(fi => fi.importance > 0.001) // Filter out very low importance features
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 15); // Display top 15 features

  return (
    <Card>
      <CardHeader>
        <CardTitle>Global Feature Importances</CardTitle>
        <CardDescription>Shows the most influential features for the model's predictions overall. Higher values indicate greater impact.</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer
          width="100%"
          height={300 + chartData.length * 10} // Adjust height dynamically
        >
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 100, bottom: 5 }} // Increased left margin for labels
          >
            <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.3}/>
            <XAxis type="number" domain={[0, 'dataMax + 0.05']} tickFormatter={(tick) => tick.toFixed(2)} />
            <YAxis 
              dataKey="feature" 
              type="category" 
              width={150} // Adjust width for longer feature names
              tick={{ fontSize: 12 }}
              interval={0} // Show all labels
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'hsl(var(--muted))' }} />
            <Legend verticalAlign="top" height={36}/>
            <Bar dataKey="importance" name="Importance" fill="hsl(var(--primary))" radius={[0, 4, 4, 0]}>
              <LabelList dataKey="importance" position="right" formatter={(value: number) => value.toFixed(3)} fontSize={10} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};