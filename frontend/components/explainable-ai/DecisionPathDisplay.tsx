// frontend/components/explainable-ai/DecisionPathDisplay.tsx
// -----------------------------------------------------------------------------
// DecisionPathDisplay – React Flow visualisation of binary decision paths
// * False-labelled edges branch LEFT
// * True-labelled edges branch RIGHT
// * Single-child edges still branch according to their label
// -----------------------------------------------------------------------------
import React, { useEffect, useMemo, useState } from 'react';
import type {
  DecisionPathResultData,
  DecisionPathEdge as ApiEdge,
} from '@/types/api';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { InfoCircledIcon, Share1Icon } from '@radix-ui/react-icons';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  Node,
  Edge,
  Position,
  MarkerType,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';

// -----------------------------------------------------------------------------
// Styling constants
// -----------------------------------------------------------------------------
const BASE_NODE_STYLE: React.CSSProperties = {
  borderRadius: 6,
  padding: '6px 10px',
  fontSize: 11,
  width: 180,
  minHeight: 45,
  textAlign: 'center',
};

const EDGE_DEFAULTS = {
  type: 'smoothstep',
  markerEnd: {
    type: MarkerType.ArrowClosed,
    width: 15,
    height: 15,
  },
  animated: false,
} as const;

// -----------------------------------------------------------------------------
// Component
// -----------------------------------------------------------------------------
interface Props {
  data?: DecisionPathResultData | null;
}

export const DecisionPathDisplay: React.FC<Props> = ({ data }) => {
  // ---------------------------------------------------------
  // Local state – selected instance(s) & React Flow
  // ---------------------------------------------------------
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const { resolvedTheme } = useTheme();

  const allPaths = useMemo(() => data?.instance_decision_paths ?? [], [data]);

  // Build list of unique instance identifiers ( class or file )
  const selectable = useMemo(() => {
    const map = new Map<string, { id: string; label: string }>();
    allPaths.forEach((p, idx) => {
      const id = p.class_name || p.file || `instance_${idx}`;
      if (!map.has(id)) {
        let label = p.class_name || p.file?.split('/')?.pop() || `Instance ${idx + 1}`;
        if (p.class_name && p.file) label = `${p.class_name} (${p.file.split('/').pop()})`;
        map.set(id, { id, label });
      }
    });
    return Array.from(map.values());
  }, [allPaths]);

  // Auto-select first instance on first render
  useEffect(() => {
    if (selectable.length && !selectedIds.length) setSelectedIds([selectable[0].id]);
  }, [selectable, selectedIds.length]);

  const visible = useMemo(
    () =>
      allPaths.filter((p, idx) => selectedIds.includes(p.class_name || p.file || `instance_${idx}`)),
    [allPaths, selectedIds]
  );

  // ---------------------------------------------------------
  // Layout algorithm – converts API trees to positioned React-Flow nodes
  // ---------------------------------------------------------
  useEffect(() => {
    // CSS var colours
    const COL = {
      primary: 'hsl(var(--primary))',
      primaryFg: 'hsl(var(--primary-foreground))',
      card: 'hsl(var(--card))',
      cardFg: 'hsl(var(--card-foreground))',
      border: 'hsl(var(--border))',
      mutedFg: 'hsl(var(--muted-foreground))',
      titleBg: 'hsl(var(--muted))',
      titleFg: 'hsl(var(--muted-foreground))',
    } as const;

    // Layout constants (reduced spacing)
    const NODE_W = BASE_NODE_STYLE.width as number;
    const LEVEL_Y = 120;        
    const BRANCH_X = NODE_W/2 
    const TREE_GAP = 160;      

    const newNodes: Node[] = [];
    const newEdges: Edge[] = [];

    let globalX = 0; // left edge for next tree

    visible.forEach((path, treeIdx) => {
      // capture start X for alignment
      const treeStartX = globalX;

      // ---------------------------
      // Build adjacency list
      // ---------------------------
      const adj = new Map<string, ApiEdge[]>();
      path.edges.forEach((e) => {
        if (!adj.has(e.source)) adj.set(e.source, []);
        adj.get(e.source)!.push(e);
      });

      // find root ( node with no incoming edges )
      const targets = new Set(path.edges.map((e) => e.target));
      const root = path.nodes.find((n) => !targets.has(n.id)) || path.nodes[0];
      if (!root) return;

      const instId = path.class_name || path.file || `instance_${treeIdx}`;
      const prefix = `${instId.replace(/[^a-zA-Z0-9]/g, '_')}_${treeIdx}`;

      let minX = globalX;
      let maxX = globalX + NODE_W;

      const locNodes: Node[] = [];
      const locEdges: Edge[] = [];

      // ---------------------------
      // Recursive placer
      // ---------------------------
      const place = (nodeId: string, x: number, y: number) => {
        if (locNodes.some((n) => n.id === `${prefix}-n-${nodeId}`)) return; // visited
        const apiNode = path.nodes.find((n) => n.id === nodeId);
        if (!apiNode) return;

        minX = Math.min(minX, x);
        maxX = Math.max(maxX, x + NODE_W);

        const isLeaf = !adj.has(nodeId) || adj.get(nodeId)!.length === 0;

        // Build node label JSX
        const label = (
          <div className="text-[10px] leading-tight p-1 max-w-[170px] break-words">
            <div className="font-semibold truncate" title={apiNode.condition || `Leaf (ID: ${apiNode.id})`}>
              {apiNode.condition || `Leaf (ID: ${apiNode.id})`}
            </div>
            {apiNode.samples !== undefined && (
              <div style={{ color: COL.mutedFg }} className="text-[9px]">
                Samples: {apiNode.samples}
              </div>
            )}
            {apiNode.value && (
              <div style={{ color: COL.mutedFg }} className="text-[9px]">
                Value: {JSON.stringify(apiNode.value)}
              </div>
            )}
          </div>
        );

        locNodes.push({
          id: `${prefix}-n-${nodeId}`,
          data: { label },
          position: { x, y },
          type: isLeaf ? 'output' : 'default',
          style: {
            ...BASE_NODE_STYLE,
            border: `1px solid ${COL.border}`,
            background: isLeaf ? COL.primary : COL.card,
            color: isLeaf ? COL.primaryFg : COL.cardFg,
          },
          sourcePosition: Position.Bottom,
          targetPosition: Position.Top,
        });

        // Recurse for children...
        // (unchanged)
        const children = adj.get(nodeId) ?? [];
        if (!children.length) return;

        // deterministic ordering: false-like first (left)
        const ordered = [...children].sort((a, b) => {
          const falseish = (e: ApiEdge) =>
            e.label?.toLowerCase().includes('false') || e.label?.includes('<=') || e.label?.includes('<');
          return falseish(a) === falseish(b) ? 0 : falseish(a) ? -1 : 1;
        });

        const childY = y + LEVEL_Y;

        if (ordered.length === 1) {
          const e = ordered[0];
          const falseish = e.label?.toLowerCase().includes('false') || e.label?.includes('<=') || e.label?.includes('<');
          const childX = falseish ? x - BRANCH_X : x + BRANCH_X;
          place(e.target, childX, childY);
          locEdges.push(makeEdge(prefix, nodeId, e));
          return;
        }

        if (ordered.length === 2) {
          const [left, right] = ordered;
          place(left.target, x - BRANCH_X, childY);
          place(right.target, x + BRANCH_X, childY);
          locEdges.push(makeEdge(prefix, nodeId, left));
          locEdges.push(makeEdge(prefix, nodeId, right));
        }
      };

      // Helper to create edge object (unchanged)
      const makeEdge = (
        pre: string,
        srcId: string,
        apiEdge: ApiEdge,
      ): Edge => ({
        id: `e-${pre}-${srcId}-${apiEdge.target}`,
        source: `${pre}-n-${srcId}`,
        target: `${pre}-n-${apiEdge.target}`,
        label: apiEdge.label,
        labelStyle: { fontSize: 9, fill: COL.mutedFg },
        style: { strokeWidth: 1.5, stroke: COL.primary },
        ...EDGE_DEFAULTS,
        markerEnd: { ...EDGE_DEFAULTS.markerEnd, color: COL.primary! },
      });

      // Kick-off recursion at root, aligned to treeStartX
      place(root.id, treeStartX, 55);

      // Add title node aligned with first node (root)
      locNodes.push({
        id: `${prefix}-title`,
        data: { label: instId },
        position: { x: treeStartX - (NODE_W / 4), y: 0 }, // aligned with root
        draggable: false,
        selectable: false,
        style: {
          ...BASE_NODE_STYLE,
          fontWeight: 'bold',
          fontSize: 13,
          background: COL.titleBg,
          color: COL.titleFg,
          border: `1px dashed ${COL.border}`,
          width: 'auto',
          minWidth: NODE_W + 20,
          padding: '8px 12px',
          textAlign: 'center',
        },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      });

      newNodes.push(...locNodes);
      newEdges.push(...locEdges);

      // advance globalX for next tree
      globalX = maxX + TREE_GAP;
    });

    setNodes(newNodes);
    setEdges(newEdges);
  }, [visible, resolvedTheme]);

  // ---------------------------------------------------------------------------
  // Guard – no data
  // ---------------------------------------------------------------------------
  if (!data || !allPaths.length) {
    return (
      <Alert variant="default" className="text-foreground bg-card border-border">
        <InfoCircledIcon className="h-4 w-4 text-muted-foreground" />
        <AlertDescription className="text-muted-foreground">
          No decision path data available for this prediction.
        </AlertDescription>
      </Alert>
    );
  }

  // ---------------------------------------------------------------------------
  // JSX
  // ---------------------------------------------------------------------------
  return (
    <Card className="bg-card text-card-foreground border-border">
      <CardHeader>
        <CardTitle className="flex items-center text-lg">
          <Share1Icon className="mr-2 h-5 w-5 text-primary" />
          Decision Paths
        </CardTitle>
        <CardDescription className="text-muted-foreground">
          False-labelled edges branch left; True-labelled edges branch right. Single-child branches follow the same rule.
        </CardDescription>
      </CardHeader>

      <CardContent>
        {/* Instance selector */}
        {selectable.length > 0 && (
          <div className="mb-6 p-3 border border-border rounded-md bg-muted/30 dark:bg-muted/20">
            <Label className="text-sm font-semibold mb-2 block text-foreground">
              Select instances:
            </Label>
            <ScrollArea className="max-h-32">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {selectable.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center space-x-2 p-1.5 rounded hover:bg-accent/50 dark:hover:bg-accent/30"
                  >
                    <Checkbox
                      id={`chk-${s.id}`}
                      checked={selectedIds.includes(s.id)}
                      onCheckedChange={() =>
                        setSelectedIds((prev) =>
                          prev.includes(s.id)
                            ? prev.filter((x) => x !== s.id)
                            : [...prev, s.id],
                        )
                      }
                    />
                    <Label
                      htmlFor={`chk-${s.id}`}
                      className="text-xs font-normal cursor-pointer truncate text-foreground"
                      title={s.label}
                    >
                      {s.label}
                    </Label>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        )}

        {/* Graph canvas */}
        {visible.length > 0 ? (
          <div
            style={{ height: '75vh', width: '100%' }}
            className="border border-border rounded-md bg-muted/10 dark:bg-muted/5 relative"
          >
            <ReactFlowProvider>
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                fitView
                fitViewOptions={{ padding: 0.3, minZoom: 0.05, maxZoom: 1.5 }}
                nodesDraggable
                nodesConnectable={false}
                attributionPosition="bottom-right"
                minZoom={0.02}
                maxZoom={2}
              >
                <MiniMap
                  nodeStrokeWidth={2}
                  nodeColor={(n: Node) =>
                    (n.style?.background as string) || 'hsl(var(--border))'
                  }
                  zoomable
                  pannable
                  className="!bg-background border border-border"
                />
                <Controls
                  showInteractive={false}
                  className={cn(
                    '[&_button]:bg-background [&_button]:fill-foreground [&_button]:border-border hover:[&_button]:bg-accent',
                    'dark:[&_button]:bg-muted dark:[&_button]:fill-muted-foreground dark:[&_button]:border-border dark:hover:[&_button]:bg-accent',
                  )}
                />
                <Background
                  gap={32}
                  size={2}
                  color={
                    resolvedTheme === 'dark'
                      ? 'hsl(var(--border) / 0.05)'
                      : 'hsl(var(--border) / 0.1)'
                  }
                  variant={BackgroundVariant.Dots}
                />
              </ReactFlow>
            </ReactFlowProvider>
          </div>
        ) : selectedIds.length ? (
          <p className="text-sm text-muted-foreground mt-4 text-center py-6">
            No decision paths found for the selected instance(s).
          </p>
        ) : (
          <p className="text-sm text-muted-foreground mt-4 text-center py-6">
            Select one or more instances to view their decision paths.
          </p>
        )}
      </CardContent>
    </Card>
  );
};
