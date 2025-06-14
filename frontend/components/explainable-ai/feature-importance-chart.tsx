"use client";

import { useEffect, useRef } from "react";

interface FeatureImportanceProps {
  data: {
    feature: string;
    importance: number;
    value?: number | string;
  }[];
  compact?: boolean;
}

export function FeatureImportanceChart({ data, compact = false }: FeatureImportanceProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Sort data by importance
    const sortedData = [...data].sort((a, b) => b.importance - a.importance);

    // Set up dimensions
    const barHeight = compact ? 25 : 40;
    const barGap = compact ? 15 : 20;
    const leftPadding = 180;
    const rightPadding = 50;
    const topPadding = 20;
    const bottomPadding = 20;
    const maxBarWidth = canvas.width - leftPadding - rightPadding;

    // Calculate total height needed
    const totalHeight =
      topPadding + sortedData.length * (barHeight + barGap) - barGap + bottomPadding;
    canvas.height = totalHeight;

    // Draw bars
    sortedData.forEach((item, index) => {
      const y = topPadding + index * (barHeight + barGap);
      const barWidth = item.importance * maxBarWidth;

      // Draw feature name
      ctx.fillStyle = "#64748b"; // text color
      ctx.font = compact ? "12px Inter, sans-serif" : "14px Inter, sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(formatFeatureName(item.feature), leftPadding - 10, y + barHeight / 2 + 5);

      // Draw bar
      const gradient = ctx.createLinearGradient(leftPadding, 0, leftPadding + barWidth, 0);
      gradient.addColorStop(0, "rgba(79, 70, 229, 0.8)"); // indigo-600 with opacity
      gradient.addColorStop(1, "rgba(79, 70, 229, 0.4)"); // indigo-600 with lower opacity

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.roundRect(leftPadding, y, barWidth, barHeight, [4]);
      ctx.fill();

      // Draw importance percentage
      ctx.fillStyle = "#1e293b"; // text color
      ctx.font = compact ? "12px Inter, sans-serif" : "14px Inter, sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(
        `${(item.importance * 100).toFixed(0)}%`,
        leftPadding + barWidth + 10,
        y + barHeight / 2 + 5
      );

      // Draw value if available and not in compact mode
      if (item.value !== undefined && !compact) {
        ctx.fillStyle = "#64748b"; // text color
        ctx.font = "12px Inter, sans-serif";
        ctx.textAlign = "left";
        ctx.fillText(`Value: ${item.value}`, leftPadding + barWidth + 60, y + barHeight / 2 + 5);
      }
    });
  }, [data, compact]);

  // Helper function to format feature names
  const formatFeatureName = (name: string) => {
    return name
      .replace(/([A-Z])/g, " $1") // Add space before capital letters
      .replace(/^./, (str) => str.toUpperCase()); // Capitalize first letter
  };

  return (
    <div className="w-full">
      <canvas ref={canvasRef} width={800} height={compact ? 200 : 400} className="w-full h-auto" />
    </div>
  );
}
