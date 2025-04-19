"use client"

import { useEffect, useRef } from "react"

interface CounterfactualExplanationProps {
  data: {
    feature: string
    currentValue: number
    suggestedValue: number
    impact: number
  }[]
  currentProbability: number
}

export function CounterfactualExplanation({ data, currentProbability }: CounterfactualExplanationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Set up dimensions
    const barHeight = 40
    const barGap = 60
    const leftPadding = 180
    const rightPadding = 50
    const topPadding = 40
    const bottomPadding = 60
    const maxBarWidth = canvas.width - leftPadding - rightPadding

    // Calculate total height needed
    const totalHeight = topPadding + data.length * (barHeight + barGap) - barGap + bottomPadding
    canvas.height = totalHeight

    // Draw probability scale at the bottom
    const scaleY = totalHeight - bottomPadding + 30
    const scaleWidth = maxBarWidth

    // Draw scale line
    ctx.strokeStyle = "#e2e8f0" // slate-200
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(leftPadding, scaleY)
    ctx.lineTo(leftPadding + scaleWidth, scaleY)
    ctx.stroke()

    // Draw ticks and labels
    for (let i = 0; i <= 10; i++) {
      const x = leftPadding + (i / 10) * scaleWidth

      ctx.strokeStyle = "#94a3b8" // slate-400
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(x, scaleY - 5)
      ctx.lineTo(x, scaleY + 5)
      ctx.stroke()

      ctx.fillStyle = "#64748b" // slate-500
      ctx.font = "12px Inter, sans-serif"
      ctx.textAlign = "center"
      ctx.fillText(`${i * 10}%`, x, scaleY + 20)
    }

    // Draw scale label
    ctx.fillStyle = "#64748b" // slate-500
    ctx.font = "14px Inter, sans-serif"
    ctx.textAlign = "center"
    ctx.fillText("Defect Probability", leftPadding + scaleWidth / 2, scaleY + 40)

    // Draw counterfactuals
    data.forEach((item, index) => {
      const y = topPadding + index * (barHeight + barGap)

      // Draw feature name
      ctx.fillStyle = "#64748b" // text color
      ctx.font = "14px Inter, sans-serif"
      ctx.textAlign = "right"
      ctx.fillText(formatFeatureName(item.feature), leftPadding - 10, y + barHeight / 2)

      // Calculate positions
      const currentX = leftPadding + currentProbability * scaleWidth
      const newProbability = Math.max(0, Math.min(1, currentProbability + item.impact))
      const newX = leftPadding + newProbability * scaleWidth

      // Draw current value marker
      ctx.fillStyle = "#f43f5e" // rose-500
      ctx.beginPath()
      ctx.arc(currentX, y + barHeight / 2, 8, 0, Math.PI * 2)
      ctx.fill()

      // Draw new value marker
      ctx.fillStyle = "#10b981" // emerald-500
      ctx.beginPath()
      ctx.arc(newX, y + barHeight / 2, 8, 0, Math.PI * 2)
      ctx.fill()

      // Draw arrow connecting the points
      ctx.strokeStyle = "#94a3b8" // slate-400
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(currentX, y + barHeight / 2)
      ctx.lineTo(newX, y + barHeight / 2)
      ctx.stroke()

      // Draw arrowhead
      const arrowSize = 6
      ctx.fillStyle = "#94a3b8" // slate-400
      ctx.beginPath()
      if (newX < currentX) {
        // Arrow pointing left
        ctx.moveTo(newX, y + barHeight / 2)
        ctx.lineTo(newX + arrowSize, y + barHeight / 2 - arrowSize)
        ctx.lineTo(newX + arrowSize, y + barHeight / 2 + arrowSize)
      } else {
        // Arrow pointing right
        ctx.moveTo(newX, y + barHeight / 2)
        ctx.lineTo(newX - arrowSize, y + barHeight / 2 - arrowSize)
        ctx.lineTo(newX - arrowSize, y + barHeight / 2 + arrowSize)
      }
      ctx.fill()

      // Draw value labels
      ctx.fillStyle = "#1e293b" // slate-800
      ctx.font = "12px Inter, sans-serif"
      ctx.textAlign = "center"

      // Current value label
      ctx.fillText(`Current: ${item.currentValue}`, currentX, y + barHeight / 2 - 15)

      // New value label
      ctx.fillText(`Suggested: ${item.suggestedValue}`, newX, y + barHeight / 2 + 20)

      // Impact label
      const impactX = (currentX + newX) / 2
      const impactText = `${item.impact < 0 ? "" : "+"}${(item.impact * 100).toFixed(0)}% probability`

      ctx.fillStyle = item.impact < 0 ? "#10b981" : "#f43f5e" // emerald-500 or rose-500
      ctx.font = "bold 12px Inter, sans-serif"
      ctx.textAlign = "center"
      ctx.fillText(impactText, impactX, y + barHeight / 2 + 40)
    })
  }, [data, currentProbability])

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
