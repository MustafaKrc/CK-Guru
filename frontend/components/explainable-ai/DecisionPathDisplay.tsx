// frontend/components/explainable-ai/DecisionPathDisplay.tsx
import React, { useEffect, useMemo, useState } from 'react';
import { DecisionPathResultData, InstanceDecisionPath } from '@/types/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from '@/components/ui/alert';
import { InfoCircledIcon, Share1Icon } from '@radix-ui/react-icons'; // Using Share1Icon for Decision Path
import { Checkbox } from "@/components/ui/checkbox"; // For class selection
import { Label } from "@/components/ui/label";
import { ReactFlow, MiniMap, Controls, Background, Node, Edge, Position, MarkerType, ReactFlowProvider, useNodesState, useEdgesState, BackgroundVariant } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';

// Node and Edge defaults (can be refined for theme)
const nodeDefaults = {
  sourcePosition: Position.Right,
  targetPosition: Position.Left,
};

const edgeDefaults = {
    markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 15,
        height: 15,
    },
    animated: false,
};

// Reusable Graph Component
const DecisionPathGraph: React.FC<{ pathData: InstanceDecisionPath, graphId: string }> = ({ pathData, graphId }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    const initialNodes: Node[] = pathData.nodes.map((node, idx) => {
      const isLeaf = node.condition?.toLowerCase().includes("leaf");
      return {
        id: `${graphId}-node-${node.id}`, // Unique node ID per graph
        data: { 
          label: (
            <div className="text-[10px] leading-tight p-1 max-w-[160px] break-words">
                <div className="font-semibold truncate" title={node.condition || `Leaf (ID: ${node.id})`}>
                    {node.condition || `Leaf (ID: ${node.id})`}
                </div>
                {node.samples !== undefined && <div className="text-muted-foreground text-[9px]">Samples: {node.samples}</div>}
                {node.value && <div className="text-muted-foreground text-[9px]">Value: {JSON.stringify(node.value)}</div>}
            </div>
          )
        },
        position: { x: idx * 190, y: (idx % 3) * 70 }, // Adjusted layout
        type: isLeaf ? 'output' : 'default',
        style: { 
            border: `1px solid hsl(var(${isLeaf ? '--primary' : '--border'}))`, 
            borderRadius: '6px', // Slightly more rounded
            padding: '6px 10px', 
            fontSize: '11px',
            width: 170, 
            minHeight: 45,
            background: `hsl(var(${isLeaf ? '--primary' : '--card'}))`,
            color: `hsl(var(${isLeaf ? '--primary-foreground' : '--card-foreground'}))`,
        },
        ...nodeDefaults
      };
    });

    const initialEdges: Edge[] = pathData.edges.map(edge => ({
      id: `e-${graphId}-${edge.source}-${edge.target}`, // Unique edge ID
      source: `${graphId}-node-${edge.source}`,
      target: `${graphId}-node-${edge.target}`,
      label: edge.label,
      labelStyle: { fontSize: 9, fill: 'hsl(var(--muted-foreground))' },
      style: { strokeWidth: 1.5, stroke: 'hsl(var(--primary))' },
      markerEnd: { ...edgeDefaults.markerEnd, color: 'hsl(var(--primary))' },
    }));
    
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [pathData, graphId, setNodes, setEdges]);

  return (
    <div style={{ height: '300px', width: '100%' }} className="border rounded-md bg-muted/10 dark:bg-muted/5  relative mb-4">
       <ReactFlowProvider>
        <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            fitView
            nodesDraggable={false}
            nodesConnectable={false}
            attributionPosition="bottom-right"
            minZoom={0.2} // Allow zooming out more
        >
            <MiniMap nodeStrokeWidth={2} nodeColor={(n: Node) => n.style?.background as string || 'hsl(var(--border))'} zoomable pannable />
            <Controls 
                showInteractive={false} 
                className="[&_button]:bg-background [&_button]:fill-foreground [&_button]:border-border 
                           dark:[&_button]:bg-muted dark:[&_button]:fill-muted-foreground dark:[&_button]:border-border"
            />
            <Background gap={16} color="hsl(var(--border) / 0.2)" variant={BackgroundVariant.Dots} />
        </ReactFlow>
       </ReactFlowProvider>
    </div>
  );
};

interface DecisionPathDisplayProps {
  data?: DecisionPathResultData | null;
}

export const DecisionPathDisplay: React.FC<DecisionPathDisplayProps> = ({ data }) => {
  const [selectedClassNames, setSelectedClassNames] = useState<string[]>([]);

  const allInstancePaths = useMemo(() => data?.instance_decision_paths || [], [data]);

  const uniqueClassFiles = useMemo(() => {
    const classFileMap = new Map<string, { id: string, displayLabel: string }>();
    allInstancePaths.forEach((inst, index) => {
      const identifier = inst.class_name || inst.file || `unknown_instance_${index}`;
      if (!classFileMap.has(identifier)) {
        let displayLabel = inst.class_name || inst.file?.split('/').pop() || `Instance ${index + 1}`;
        if (inst.class_name && inst.file) displayLabel = `${inst.class_name} (${inst.file.split('/').pop()})`;
        classFileMap.set(identifier, { id: identifier, displayLabel });
      }
    });
    return Array.from(classFileMap.values());
  }, [allInstancePaths]);

  // Auto-select first class if none selected
  useEffect(() => {
    if (uniqueClassFiles.length > 0 && selectedClassNames.length === 0) {
      setSelectedClassNames([uniqueClassFiles[0].id]);
    }
  }, [uniqueClassFiles, selectedClassNames]);

  const handleClassSelectionChange = (classFileId: string) => {
    setSelectedClassNames(prev =>
      prev.includes(classFileId)
        ? prev.filter(id => id !== classFileId)
        : [...prev, classFileId]
    );
  };

  const pathsToDisplay = useMemo(() => {
    return allInstancePaths.filter(inst => 
        selectedClassNames.includes(inst.class_name || inst.file || `unknown_instance_${allInstancePaths.indexOf(inst)}`)
    );
  }, [allInstancePaths, selectedClassNames]);


  if (!data || allInstancePaths.length === 0) {
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
        <CardTitle className="flex items-center"><Share1Icon className="mr-2 h-5 w-5 text-primary"/>Decision Paths</CardTitle>
        <CardDescription>
          Visualizes the path(s) taken through decision tree(s) for selected instances.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {uniqueClassFiles.length > 0 && (
            <div className="mb-6 p-3 border rounded-md">
                <Label className="text-sm font-semibold mb-2 block">Select Instances to Display Paths:</Label>
                <ScrollArea className="max-h-32">
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                        {uniqueClassFiles.map(cf => (
                            <div key={cf.id} className="flex items-center space-x-2 p-1.5 rounded hover:bg-accent">
                                <Checkbox
                                    id={`class-checkbox-${cf.id}`}
                                    checked={selectedClassNames.includes(cf.id)}
                                    onCheckedChange={() => handleClassSelectionChange(cf.id)}
                                />
                                <Label htmlFor={`class-checkbox-${cf.id}`} className="text-xs font-normal cursor-pointer truncate" title={cf.displayLabel}>
                                    {cf.displayLabel}
                                </Label>
                            </div>
                        ))}
                    </div>
                </ScrollArea>
            </div>
        )}

        {pathsToDisplay.length > 0 ? (
          <div className="space-y-6">
            {pathsToDisplay.map((pathData, index) => {
                const instanceIdentifier = pathData.class_name || pathData.file || `instance_${allInstancePaths.indexOf(pathData)}`;
                const pathsForThisIdentifier = allInstancePaths.filter(p => (p.class_name || p.file || `instance_${allInstancePaths.indexOf(p)}`) === instanceIdentifier);
                const pathIndexOfType = pathsForThisIdentifier.indexOf(pathData);

                return (
                    <div key={`path-graph-container-${instanceIdentifier}-${index}`}>
                        <h4 className="text-md font-semibold mb-2 text-center">
                            Path for: {instanceIdentifier} {pathsForThisIdentifier.length > 1 ? `(Tree ${pathIndexOfType + 1})` : ''}
                        </h4>
                        <DecisionPathGraph pathData={pathData} graphId={`${instanceIdentifier}-path-${pathIndexOfType}`} />
                    </div>
                )
            })}
          </div>
        ) : selectedClassNames.length > 0 ? (
          <p className="text-sm text-muted-foreground mt-4 text-center py-6">No decision paths found for the selected instance(s).</p>
        ) : (
           <p className="text-sm text-muted-foreground mt-4 text-center py-6">Select one or more instances to view their decision paths.</p>
        )}
      </CardContent>
    </Card>
  );
};