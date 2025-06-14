"use client";

import { useEffect, useRef } from "react";
import { useTheme } from "next-themes"; // Import useTheme

interface CounterfactualExplanationProps {
  data: {
    feature: string;
    currentValue: number;
    suggestedValue: number;
    impact: number;
  }[];
  currentProbability: number;
}

export function CounterfactualExplanation({
  data,
  currentProbability,
}: CounterfactualExplanationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { resolvedTheme } = useTheme(); // Get the resolved theme (light or dark)

  useEffect(() => {
    if (!canvasRef.current || !resolvedTheme) return; // Wait for theme to be resolved

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Get computed styles based on the current theme
    const rootStyle = getComputedStyle(document.documentElement);
    const colors = {
      text: rootStyle.getPropertyValue("--foreground").trim(),
      textMuted: rootStyle.getPropertyValue("--muted-foreground").trim(),
      primary: rootStyle.getPropertyValue("--primary").trim(), // For positive impact/new value
      destructive: rootStyle.getPropertyValue("--destructive").trim(), // For negative impact/current value if worse
      border: rootStyle.getPropertyValue("--border").trim(),
      accent: rootStyle.getPropertyValue("--accent").trim(), // Could be used for neutral lines
      // Define specific colors for positive/negative impacts if primary/destructive aren't semantically perfect
      // For this example, let's assume green for improvement (positive impact on probability reduction)
      // and red for detriment (negative impact on probability reduction).
      // If `impact` is change in defect probability, negative impact is good.
      positiveImpactColor: `hsl(${rootStyle.getPropertyValue("--primary").trim()})`, // Example: Blue if primary is blue (less defect)
      negativeImpactColor: `hsl(${rootStyle.getPropertyValue("--destructive").trim()})`, // Example: Red (more defect)
      currentMarkerColor: `hsl(${rootStyle.getPropertyValue("--destructive").trim()})`, // Assuming current is 'bad' state
      suggestedMarkerColor: `hsl(${rootStyle.getPropertyValue("--primary").trim()})`, // Assuming suggested is 'good' state
    };

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Set up dimensions
    const barHeight = 40;
    const barGap = 60;
    const leftPadding = 180;
    const rightPadding = 50;
    const topPadding = 40;
    const bottomPadding = 60;
    const maxBarWidth = canvas.width - leftPadding - rightPadding;

    // Calculate total height needed
    const totalHeight = topPadding + data.length * (barHeight + barGap) - barGap + bottomPadding;
    canvas.height = totalHeight;

    // Draw probability scale at the bottom
    const scaleY = totalHeight - bottomPadding + 30;
    const scaleWidth = maxBarWidth;

    // Draw scale line
    ctx.strokeStyle = `hsl(${colors.border})`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(leftPadding, scaleY);
    ctx.lineTo(leftPadding + scaleWidth, scaleY);
    ctx.stroke();

    // Draw ticks and labels
    for (let i = 0; i <= 10; i++) {
      const x = leftPadding + (i / 10) * scaleWidth;

      ctx.strokeStyle = `hsl(${colors.textMuted})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, scaleY - 5);
      ctx.lineTo(x, scaleY + 5);
      ctx.stroke();

      ctx.fillStyle = `hsl(${colors.textMuted})`;
      ctx.font = "12px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`${i * 10}%`, x, scaleY + 20);
    }

    // Draw scale label
    ctx.fillStyle = `hsl(${colors.textMuted})`;
    ctx.font = "14px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Defect Probability", leftPadding + scaleWidth / 2, scaleY + 40);

    // Draw counterfactuals
    data.forEach((item, index) => {
      const y = topPadding + index * (barHeight + barGap);

      // Draw feature name
      ctx.fillStyle = `hsl(${colors.textMuted})`; // Use theme color
      ctx.font = "14px Inter, sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(formatFeatureName(item.feature), leftPadding - 10, y + barHeight / 2);

      // Calculate positions
      const currentX = leftPadding + currentProbability * scaleWidth;
      const newProbability = Math.max(0, Math.min(1, currentProbability + item.impact));
      const newX = leftPadding + newProbability * scaleWidth;

      // Draw current value marker
      ctx.fillStyle = colors.currentMarkerColor; // Theme-aware
      ctx.beginPath();
      ctx.arc(currentX, y + barHeight / 2, 8, 0, Math.PI * 2);
      ctx.fill();

      // Draw new value marker
      ctx.fillStyle = colors.suggestedMarkerColor; // Theme-aware
      ctx.beginPath();
      ctx.arc(newX, y + barHeight / 2, 8, 0, Math.PI * 2);
      ctx.fill();

      // Draw arrow connecting the points
      ctx.strokeStyle = `hsl(${colors.textMuted})`; // Use theme color
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(currentX, y + barHeight / 2);
      ctx.lineTo(newX, y + barHeight / 2);
      ctx.stroke();

      // Draw arrowhead
      const arrowSize = 6;
      ctx.fillStyle = `hsl(${colors.textMuted})`; // Use theme color
      ctx.beginPath();
      if (newX < currentX) {
        // Arrow pointing left
        ctx.moveTo(newX, y + barHeight / 2);
        ctx.lineTo(newX + arrowSize, y + barHeight / 2 - arrowSize);
        ctx.lineTo(newX + arrowSize, y + barHeight / 2 + arrowSize);
      } else {
        // Arrow pointing right
        ctx.moveTo(newX, y + barHeight / 2);
        ctx.lineTo(newX - arrowSize, y + barHeight / 2 - arrowSize);
        ctx.lineTo(newX - arrowSize, y + barHeight / 2 + arrowSize);
      }
      ctx.fill();

      // Draw value labels
      ctx.fillStyle = `hsl(${colors.text})`; // Use theme text color
      ctx.font = "12px Inter, sans-serif";
      ctx.textAlign = "center";

      // Current value label
      ctx.fillText(`Current: ${item.currentValue}`, currentX, y + barHeight / 2 - 15);

      // New value label
      ctx.fillText(`Suggested: ${item.suggestedValue}`, newX, y + barHeight / 2 + 20);

      // Impact label
      const impactX = (currentX + newX) / 2;
      const impactText = `${item.impact < 0 ? "" : "+"}${(item.impact * 100).toFixed(0)}% probability`;

      // Determine color based on impact direction (negative impact is good for defect probability)
      ctx.fillStyle = item.impact < 0 ? colors.positiveImpactColor : colors.negativeImpactColor;
      ctx.font = "bold 12px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(impactText, impactX, y + barHeight / 2 + 40);
    });
  }, [data, currentProbability, resolvedTheme]); // Add resolvedTheme to dependency array

  // Helper function to format feature names
  const formatFeatureName = (name: string) => {
    return name
      .replace(/([A-Z])/g, " $1") // Add space before capital letters
      .replace(/^./, (str) => str.toUpperCase()); // Capitalize first letter
  };

  return (
    <div className="w-full">
      <canvas ref={canvasRef} width={800} height={400} className="w-full h-auto" />
    </div>
  );
}
