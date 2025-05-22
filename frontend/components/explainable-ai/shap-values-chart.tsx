"use client"

import { useEffect, useRef } from "react"

interface FeatureSHAPValueDisplay { // Renamed to avoid conflict if FeatureSHAPValue is imported
  feature: string;
  value: number;
  // feature_value?: any; // Not used in current chart logic, can be omitted for clarity here
}

interface ShapValuesProps {
  data: FeatureSHAPValueDisplay[];
  baseline?: number; // Make baseline an optional top-level prop
}

export function ShapValuesChart({ data, baseline }: ShapValuesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvasRef.current || !baseline === undefined) return; // Ensure baseline is also available if needed by drawing logic

    const canvas = canvasRef.current
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Sort data by absolute value
    const sortedData = [...data].sort((a, b) => Math.abs(b.value) - Math.abs(a.value))

    // Set up dimensions
    const barHeight = 40
    const barGap = 20
    const leftPadding = 180
    const centerX = canvas.width / 2
    const rightPadding = 50
    const topPadding = 20
    const bottomPadding = 40
    const maxBarWidth = (canvas.width - leftPadding - rightPadding) / 2

    // Calculate total height needed
    const totalHeight = topPadding + sortedData.length * (barHeight + barGap) - barGap + bottomPadding
    canvas.height = totalHeight

    // Draw baseline
    ctx.strokeStyle = "#94a3b8" // slate-400
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(centerX, topPadding - 10)
    ctx.lineTo(centerX, totalHeight - bottomPadding + 10)
    ctx.stroke()

    // Draw baseline label
    ctx.fillStyle = "#64748b" // slate-500
    ctx.font = "12px Inter, sans-serif"
    ctx.textAlign = "center"
    // Use the passed 'baseline' prop for the label
    ctx.fillText(`Baseline: ${baseline?.toFixed(2) ?? 'N/A'}`, centerX, totalHeight - bottomPadding + 25)

    // Draw bars
    sortedData.forEach((item, index) => {
      const y = topPadding + index * (barHeight + barGap)
      const barWidth = Math.abs(item.value) * maxBarWidth

      // Draw feature name
      ctx.fillStyle = "#64748b" // text color
      ctx.font = "14px Inter, sans-serif"
      ctx.textAlign = "right"
      ctx.fillText(formatFeatureName(item.feature), leftPadding - 10, y + barHeight / 2 + 5)

      // Determine bar direction and color
      const isPositive = item.value >= 0
      const startX = isPositive ? centerX : centerX - barWidth
      const gradientStartX = isPositive ? centerX : centerX - barWidth
      const gradientEndX = isPositive ? centerX + barWidth : centerX

      // Draw bar
      const gradient = ctx.createLinearGradient(gradientStartX, 0, gradientEndX, 0)
      if (isPositive) {
        gradient.addColorStop(0, "rgba(220, 38, 38, 0.4)") // red-600 with opacity
        gradient.addColorStop(1, "rgba(220, 38, 38, 0.8)") // red-600 with higher opacity
      } else {
        gradient.addColorStop(0, "rgba(37, 99, 235, 0.8)") // blue-600 with higher opacity
        gradient.addColorStop(1, "rgba(37, 99, 235, 0.4)") // blue-600 with opacity
      }

      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.roundRect(startX, y, barWidth, barHeight, [4])
      ctx.fill()

      // Draw value
      const textX = isPositive ? centerX + barWidth + 10 : centerX - barWidth - 10
      ctx.fillStyle = "#1e293b" // text color
      ctx.font = "14px Inter, sans-serif"
      ctx.textAlign = isPositive ? "left" : "right"
      ctx.fillText(item.value.toFixed(2), textX, y + barHeight / 2 + 5)
    })

    // Draw legend
    const legendY = totalHeight - bottomPadding + 25

    // Positive impact
    ctx.fillStyle = "rgba(220, 38, 38, 0.8)" // red-600
    ctx.beginPath()
    ctx.roundRect(centerX + 100, legendY - 10, 20, 10, [4])
    ctx.fill()

    ctx.fillStyle = "#64748b" // text color
    ctx.font = "12px Inter, sans-serif"
    ctx.textAlign = "left"
    ctx.fillText("Pushes toward prediction", centerX + 130, legendY)

    // Negative impact
    ctx.fillStyle = "rgba(37, 99, 235, 0.8)" // blue-600
    ctx.beginPath()
    ctx.roundRect(centerX - 200, legendY - 10, 20, 10, [4])
    ctx.fill()

    ctx.fillStyle = "#64748b" // text color
    ctx.font = "12px Inter, sans-serif"
    ctx.textAlign = "right"
    ctx.fillText("Pushes away from prediction", centerX - 210, legendY)
  }, [data, baseline]) // Add baseline to dependency array

  // Helper function to format feature names
  const formatFeatureName = (name: string) => {
    return name
      .replace(/([A-Z])/g, " $1") // Add space before capital letters
      .replace(/^./, (str) => str.toUpperCase()) // Capitalize first letter
  }

  return (
    <div className="w-full">
      <canvas ref={canvasRef} width={800} height={400} className="w-full h-auto" />
    </div>
  )
}
