"use client";

import { useEffect, useRef } from "react";

interface DecisionPathProps {
  data: {
    nodes: {
      id: string;
      condition: string;
      samples: number;
      value: number[];
    }[];
    edges: {
      source: string;
      target: string;
      label: string;
    }[];
    path: string[];
  };
}

export function DecisionPathVisualization({ data }: DecisionPathProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Set up dimensions
    const nodeWidth = 180;
    const nodeHeight = 80;
    const horizontalGap = 100;
    const verticalGap = 60;
    const leftPadding = 50;
    const topPadding = 40;

    // Calculate positions for each node
    const nodePositions: Record<string, { x: number; y: number }> = {};

    data.nodes.forEach((node, index) => {
      // For simplicity, we'll arrange nodes in a linear path
      // In a real implementation, you might want to calculate a tree layout
      nodePositions[node.id] = {
        x: leftPadding + index * (nodeWidth + horizontalGap),
        y: topPadding + (index % 2 === 0 ? 0 : verticalGap), // Slight zigzag for visibility
      };
    });

    // Draw edges
    data.edges.forEach((edge) => {
      const sourcePos = nodePositions[edge.source];
      const targetPos = nodePositions[edge.target];

      if (!sourcePos || !targetPos) return;

      const startX = sourcePos.x + nodeWidth;
      const startY = sourcePos.y + nodeHeight / 2;
      const endX = targetPos.x;
      const endY = targetPos.y + nodeHeight / 2;

      // Draw line
      ctx.strokeStyle =
        data.path.includes(edge.source) && data.path.includes(edge.target)
          ? "#4f46e5" // indigo-600 for the active path
          : "#cbd5e1"; // slate-300 for inactive paths
      ctx.lineWidth = data.path.includes(edge.source) && data.path.includes(edge.target) ? 3 : 1;

      ctx.beginPath();
      ctx.moveTo(startX, startY);

      // Create a curved line
      const controlX = (startX + endX) / 2;
      const controlY = startY;

      ctx.quadraticCurveTo(controlX, controlY, endX, endY);
      ctx.stroke();

      // Draw arrowhead
      const arrowSize = 8;
      const angle = Math.atan2(endY - controlY, endX - controlX);

      ctx.fillStyle =
        data.path.includes(edge.source) && data.path.includes(edge.target)
          ? "#4f46e5" // indigo-600
          : "#cbd5e1"; // slate-300

      ctx.beginPath();
      ctx.moveTo(endX, endY);
      ctx.lineTo(
        endX - arrowSize * Math.cos(angle - Math.PI / 6),
        endY - arrowSize * Math.sin(angle - Math.PI / 6)
      );
      ctx.lineTo(
        endX - arrowSize * Math.cos(angle + Math.PI / 6),
        endY - arrowSize * Math.sin(angle + Math.PI / 6)
      );
      ctx.fill();

      // Draw edge label
      ctx.fillStyle = "#64748b"; // slate-500
      ctx.font = "12px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(edge.label, controlX, controlY - 10);
    });

    // Draw nodes
    data.nodes.forEach((node) => {
      const pos = nodePositions[node.id];
      if (!pos) return;

      // Draw node rectangle
      const isInPath = data.path.includes(node.id);

      ctx.fillStyle = isInPath
        ? "rgba(79, 70, 229, 0.1)" // indigo-600 with low opacity
        : "rgba(226, 232, 240, 0.5)"; // slate-200 with opacity
      ctx.strokeStyle = isInPath
        ? "#4f46e5" // indigo-600
        : "#cbd5e1"; // slate-300
      ctx.lineWidth = isInPath ? 2 : 1;

      // Draw rounded rectangle
      ctx.beginPath();
      ctx.roundRect(pos.x, pos.y, nodeWidth, nodeHeight, [8]);
      ctx.fill();
      ctx.stroke();

      // Draw node content
      ctx.fillStyle = "#1e293b"; // slate-800
      ctx.font = isInPath ? "bold 14px Inter, sans-serif" : "14px Inter, sans-serif";
      ctx.textAlign = "center";

      // Condition text - might need to wrap for long conditions
      const condition = node.condition;
      const maxWidth = nodeWidth - 20;

      if (ctx.measureText(condition).width > maxWidth) {
        // Simple text wrapping
        const words = condition.split(" ");
        let line = "";
        let y = pos.y + 25;

        for (let i = 0; i < words.length; i++) {
          const testLine = line + words[i] + " ";
          const metrics = ctx.measureText(testLine);

          if (metrics.width > maxWidth && i > 0) {
            ctx.fillText(line, pos.x + nodeWidth / 2, y);
            line = words[i] + " ";
            y += 18;
          } else {
            line = testLine;
          }
        }

        ctx.fillText(line, pos.x + nodeWidth / 2, y);

        // Samples text
        ctx.fillStyle = "#64748b"; // slate-500
        ctx.font = "12px Inter, sans-serif";
        ctx.fillText(`Samples: ${node.samples}`, pos.x + nodeWidth / 2, pos.y + nodeHeight - 15);
      } else {
        // Single line text
        ctx.fillText(condition, pos.x + nodeWidth / 2, pos.y + 30);

        // Samples text
        ctx.fillStyle = "#64748b"; // slate-500
        ctx.font = "12px Inter, sans-serif";
        ctx.fillText(`Samples: ${node.samples}`, pos.x + nodeWidth / 2, pos.y + nodeHeight - 15);
      }
    });

    // Calculate canvas size based on node positions
    const maxX =
      Math.max(...Object.values(nodePositions).map((pos) => pos.x + nodeWidth)) + leftPadding;
    const maxY =
      Math.max(...Object.values(nodePositions).map((pos) => pos.y + nodeHeight)) + topPadding;

    canvas.width = maxX;
    canvas.height = maxY;
  }, [data]);

  return (
    <div className="w-full overflow-x-auto">
      <canvas ref={canvasRef} width={800} height={300} className="min-w-full h-auto" />
    </div>
  );
}
