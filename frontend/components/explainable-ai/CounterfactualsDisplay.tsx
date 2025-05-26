// frontend/components/explainable-ai/CounterfactualsDisplay.tsx
import React, { useState, useMemo, useEffect } from 'react';
import { CounterfactualResultData, CounterfactualExample, InstanceCounterfactualResult } from '@/types/api';
import { XaiInstanceSelector } from './XaiInstanceSelector'; // Assuming this is generalized
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from '@/components/ui/alert';
import { InfoCircledIcon, ShuffleIcon, ArrowRightIcon, CheckIcon, Cross1Icon, TargetIcon } from '@radix-ui/react-icons';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress'; // For visualizing probability change
import { cn } from '@/lib/utils'; // Import cn for conditional classNames

interface CounterfactualsDisplayProps {
  data?: CounterfactualResultData | null;
  originalInstanceData?: { 
    features: Record<string, any>;
    predictionProbability: number;
  } | null;
}

export const CounterfactualsDisplay: React.FC<CounterfactualsDisplayProps> = ({ data, originalInstanceData }) => {
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | undefined>(undefined);

  const instances = useMemo(() => data?.instance_counterfactuals || [], [data]);

  useEffect(() => {
    if (instances.length > 0 && !selectedInstanceId) {
      const firstInstance = instances[0];
      setSelectedInstanceId(firstInstance.class_name || firstInstance.file || `instance_0`);
    }
  }, [instances, selectedInstanceId]);

  const selectedInstanceData: InstanceCounterfactualResult | undefined = useMemo(() => {
    if (!selectedInstanceId) return undefined;
    return instances.find(inst => (inst.class_name || inst.file || `instance_${instances.indexOf(inst)}`) === selectedInstanceId);
  }, [instances, selectedInstanceId]);

  if (!data || instances.length === 0) {
    return (
        <Alert variant="default" className="text-foreground bg-card border-border">
            <InfoCircledIcon className="h-4 w-4 text-muted-foreground"/>
            <AlertDescription className="text-muted-foreground">No counterfactual data available for this prediction.</AlertDescription>
        </Alert>
    );
  }

  const renderFeatureChange = (feature: string, cfValue: any, originalValue?: any) => {
    const valueChanged = originalValue !== undefined && originalValue !== cfValue;
    return (
        <TableRow key={feature} className={cn(valueChanged ? "bg-accent/50 dark:bg-accent/20" : "", "hover:bg-accent/30 dark:hover:bg-accent/15")}>
            <TableCell className="font-medium text-xs py-2 text-foreground">{feature}</TableCell>
            {originalInstanceData && (
                <TableCell className="text-right font-mono text-xs py-2 text-muted-foreground">{String(originalValue ?? 'N/A')}</TableCell>
            )}
            <TableCell className={`text-right font-mono text-xs py-2 ${valueChanged ? 'text-primary font-semibold' : 'text-foreground'}`}>{String(cfValue)}</TableCell>
        </TableRow>
    );
  };

  return (
    <Card className="bg-card text-card-foreground border-border">
      <CardHeader>
        <CardTitle className="flex items-center text-lg"><ShuffleIcon className="mr-2 h-5 w-5 text-primary"/>Counterfactual Explanations</CardTitle>
        <CardDescription className="text-muted-foreground">
          Minimal changes to feature values that would alter the prediction outcome.
          {originalInstanceData && (
            <span className="block mt-1 text-xs">
                Original Prediction Probability: 
                <Badge 
                    variant={originalInstanceData.predictionProbability > 0.5 ? "destructive" : "default"}
                    className="ml-1.5 px-1.5 py-0.5 text-xs"
                >
                    {(originalInstanceData.predictionProbability * 100).toFixed(1)}%
                </Badge>
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <XaiInstanceSelector
          instances={instances}
          selectedIdentifier={selectedInstanceId}
          onInstanceChange={setSelectedInstanceId}
          label="Select Code Instance (Class/File)"
        />
        {selectedInstanceData && selectedInstanceData.counterfactuals.length > 0 ? (
          <ScrollArea className="max-h-[calc(100vh-400px)] pr-3"> {/* Adjust max-h as needed */}
            <div className="space-y-6">
              {selectedInstanceData.counterfactuals.map((cf, index) => {
                const probDiff = originalInstanceData ? cf.outcome_probability - originalInstanceData.predictionProbability : 0;
                const isImprovement = probDiff < 0; // Assuming lower probability is an improvement (less defect-prone)
                
                return (
                <Card key={index} className="bg-muted/30 dark:bg-muted/20 border-border shadow-sm overflow-hidden">
                  <CardHeader className="pb-3 pt-4">
                    <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-2">
                        <CardTitle className="text-md font-semibold">Counterfactual Suggestion #{index + 1}</CardTitle>
                        <div className="flex items-center space-x-2 self-start sm:self-center">
                            <span className="text-xs text-muted-foreground">New Probability:</span>
                            <Badge 
                                variant={cf.outcome_probability < 0.5 ? "default" : "destructive"}
                                className="px-2 py-1 text-xs"
                            >
                                <TargetIcon className="mr-1.5 h-3.5 w-3.5"/>
                                {(cf.outcome_probability * 100).toFixed(1)}%
                            </Badge>
                        </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {originalInstanceData && (
                        <div className="mb-3 text-xs flex items-center">
                            <span className="text-muted-foreground">Impact:</span>
                            <span className={`ml-1.5 font-semibold ${isImprovement ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                {probDiff !== 0 ? `${probDiff > 0 ? '+' : ''}${(probDiff * 100).toFixed(1)}% change` : "No change"}
                            </span>
                            {isImprovement ? <CheckIcon className="ml-1 h-4 w-4 text-green-600 dark:text-green-400"/> : (probDiff !== 0 && <Cross1Icon className="ml-1 h-3.5 w-3.5 text-red-600 dark:text-red-400"/>)}
                            <Progress 
                                value={Math.abs(probDiff)*100} 
                                className="w-20 h-1.5 ml-2 bg-muted-foreground/20" // Added background for the track
                                indicatorClassName={cn(
                                    isImprovement ? "bg-green-500" : "bg-destructive"
                                )}
                            />
                        </div>
                    )}
                    <p className="text-xs text-muted-foreground mb-2">If the following features were changed as shown:</p>
                    <div className="rounded-md border border-border overflow-hidden">
                        <Table className="text-xs">
                        <TableHeader>
                            <TableRow className="bg-muted/50 dark:bg-muted/10 hover:bg-muted/60 dark:hover:bg-muted/15">
                            <TableHead className="py-1.5 px-2">Feature</TableHead>
                            {originalInstanceData && <TableHead className="text-right py-1.5 px-2">Original Value</TableHead>}
                            <TableHead className="text-right py-1.5 px-2">Suggested Value</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {Object.entries(cf.features).map(([feature, value]) => 
                                renderFeatureChange(feature, value, originalInstanceData?.features[feature])
                            )}
                        </TableBody>
                        </Table>
                    </div>
                  </CardContent>
                </Card>
              )})}
            </div>
          </ScrollArea>
        ) : selectedInstanceId ? (
          <p className="text-sm text-muted-foreground mt-4 text-center py-6">No counterfactual examples found for the selected instance.</p>
        ) : (
          <p className="text-sm text-muted-foreground mt-4 text-center py-6">Select an instance to view counterfactuals.</p>
        )}
      </CardContent>
    </Card>
  );
};