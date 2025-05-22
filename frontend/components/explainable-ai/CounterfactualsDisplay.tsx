// frontend/components/explainable-ai/CounterfactualsDisplay.tsx
import React, { useState, useMemo, useEffect } from 'react';
import { CounterfactualResultData, InstanceCounterfactualResult, CounterfactualExample } from '@/types/api';
import { XaiInstanceSelector } from './XaiInstanceSelector';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Alert, AlertDescription } from '@/components/ui/alert';
import { InfoCircledIcon, ShuffleIcon } from '@radix-ui/react-icons';
import { Badge } from '@/components/ui/badge';

interface CounterfactualsDisplayProps {
  data?: CounterfactualResultData | null;
}

export const CounterfactualsDisplay: React.FC<CounterfactualsDisplayProps> = ({ data }) => {
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | undefined>(undefined);

  const instances = useMemo(() => data?.instance_counterfactuals || [], [data]);

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
            <AlertDescription>No counterfactual data available for this prediction.</AlertDescription>
        </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center"><ShuffleIcon className="mr-2 h-5 w-5"/>Counterfactual Explanations</CardTitle>
        <CardDescription>
          Shows minimal changes to feature values that would flip the prediction outcome.
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
          <div className="space-y-4">
            {selectedInstanceData.counterfactuals.map((cf, index) => (
              <Card key={index} className="bg-muted/50">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Counterfactual Example #{index + 1}</CardTitle>
                  <CardDescription>
                    If these features were changed, the predicted probability would be <Badge variant={cf.outcome_probability < 0.5 ? "default" : "destructive"}>{(cf.outcome_probability * 100).toFixed(1)}%</Badge>.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Feature Changed</TableHead>
                        <TableHead className="text-right">New Value</TableHead>
                        {/* Add Original Value if available from another source */}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {Object.entries(cf.features).map(([feature, value]) => (
                        <TableRow key={feature}>
                          <TableCell className="font-medium">{feature}</TableCell>
                          <TableCell className="text-right font-mono">{String(value)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : selectedInstanceId ? (
          <p className="text-sm text-muted-foreground">No counterfactual examples found for the selected instance.</p>
        ) : (
          <p className="text-sm text-muted-foreground">Select an instance to view counterfactuals.</p>
        )}
      </CardContent>
    </Card>
  );
};