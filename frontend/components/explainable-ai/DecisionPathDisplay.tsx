// frontend/components/explainable-ai/DecisionPathDisplay.tsx
import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { DecisionPathResultData, InstanceDecisionPath } from '@/types/api';
import { XaiInstanceSelector } from './XaiInstanceSelector';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { InfoCircledIcon } from '@radix-ui/react-icons';
import { ReactFlow, MiniMap, Controls, Background, Node, Edge, Position, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css'; // Import ReactFlow styles

interface DecisionPathDisplayProps {
  data?: DecisionPathResultData | null;
}

const nodeDefaults = {
  sourcePosition: Position.Right,
  targetPosition: Position.Left,
  style: { 
    border: '1px solid hsl(var(--border))', 
    borderRadius: '0.375rem',
    padding: '10px 15px', 
    fontSize: '12px',
    width: 180,
    background: 'hsl(var(--card))',
    color: 'hsl(var(--card-foreground))'
  },
};

const edgeDefaults = {
    markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 20,
        height: 20,
        color: 'hsl(var(--primary))',
    },
    style: {
        strokeWidth: 1.5,
        stroke: 'hsl(var(--primary))',
    },
    animated: false, // Set to true for animated edges
};

export const DecisionPathDisplay: React.FC<DecisionPathDisplayProps> = ({ data }) => {
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | undefined>(undefined);
  const [selectedPathIndex, setSelectedPathIndex] = useState<number>(0);

  const instances = useMemo(() => data?.instance_decision_paths || [], [data]);

  useEffect(() => {
    if (instances.length > 0 && !selectedInstanceId) {
      const firstInstance = instances[0];
      setSelectedInstanceId(firstInstance.class_name || firstInstance.file || `instance_0`);
      setSelectedPathIndex(0);
    }
  }, [instances, selectedInstanceId]);

  const pathsForSelectedInstance = useMemo(() => {
    if (!selectedInstanceId) return [];
    return instances.filter(inst => (inst.class_name || inst.file || `instance_${instances.indexOf(inst)}`) === selectedInstanceId);
  }, [instances, selectedInstanceId]);

  const currentPathData = useMemo(() => {
    return pathsForSelectedInstance[selectedPathIndex];
  }, [pathsForSelectedInstance, selectedPathIndex]);

  const { nodes: flowNodes, edges: flowEdges } = useMemo(() => {
    if (!currentPathData) return { nodes: [], edges: [] };

    const initialNodes: Node[] = currentPathData.nodes.map((node, idx) => ({
      id: node.id,
      data: { 
        label: (
            <div className="text-xs">
                <div className="font-semibold">{node.condition || `Leaf (ID: ${node.id})`}</div>
                {node.samples !== undefined && <div className="text-muted-foreground">Samples: {node.samples}</div>}
                {node.value && <div className="text-muted-foreground">Value: {JSON.stringify(node.value)}</div>}
            </div>
        )
      },
      position: { x: idx * 250, y: (idx % 2) * 100 }, // Basic layout
      ...nodeDefaults,
      type: node.condition?.toLowerCase().includes("leaf") ? 'output' : 'default',
      style: {
        ...nodeDefaults.style,
        background: node.condition?.toLowerCase().includes("leaf") ? 'hsl(var(--primary))' : 'hsl(var(--card))',
        color: node.condition?.toLowerCase().includes("leaf") ? 'hsl(var(--primary-foreground))' : 'hsl(var(--card-foreground))',
        borderColor: node.condition?.toLowerCase().includes("leaf") ? 'hsl(var(--primary))' : 'hsl(var(--border))',
      }
    }));

    const initialEdges: Edge[] = currentPathData.edges.map(edge => ({
      id: `e-${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      labelStyle: { fontSize: 10, fill: 'hsl(var(--muted-foreground))' },
      ...edgeDefaults,
    }));

    return { nodes: initialNodes, edges: initialEdges };
  }, [currentPathData]);

  if (!data || instances.length === 0) {
    return (
       <Alert variant="default">
        <InfoCircledIcon className="h-4 w-4"/>
        <AlertDescription>No decision path data available for this prediction.</AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Decision Path</CardTitle>
        <CardDescription>
          Visualizes the path taken through a decision tree (or a tree in an ensemble) for a specific instance.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <XaiInstanceSelector
          instances={instances}
          selectedIdentifier={selectedInstanceId}
          onInstanceChange={(id) => { setSelectedInstanceId(id); setSelectedPathIndex(0);}}
          label="Select Code Instance (Class/File)"
        />
        {pathsForSelectedInstance.length > 1 && (
          <div className="mb-4">
            <Label htmlFor="path-selector" className="text-sm font-medium">Select Path for Instance</Label>
            <Select value={selectedPathIndex.toString()} onValueChange={(val) => setSelectedPathIndex(parseInt(val))}>
              <SelectTrigger id="path-selector" className="w-full md:w-[200px] mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {pathsForSelectedInstance.map((_, index) => (
                  <SelectItem key={index} value={index.toString()}>Path {index + 1}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        {currentPathData ? (
          <div style={{ height: '500px', width: '100%' }} className="border rounded-md bg-muted/30">
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              fitView
              nodesDraggable={false}
              nodesConnectable={false}
            >
              <MiniMap nodeStrokeWidth={3} zoomable pannable />
              <Controls />
              <Background />
            </ReactFlow>
          </div>
        ) : selectedInstanceId ? (
          <p className="text-sm text-muted-foreground">No decision path to display for this selection.</p>
        ) : (
           <p className="text-sm text-muted-foreground">Select an instance to view its decision path.</p>
        )}
      </CardContent>
    </Card>
  );
};