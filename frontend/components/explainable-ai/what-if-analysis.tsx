"use client"

import { useState, useEffect } from "react"
import { Slider } from "@/components/ui/slider"
import { Label } from "@/components/ui/label"

interface WhatIfAnalysisProps {
  features: {
    name: string
    value: number
    min: number
    max: number
  }[]
  currentProbability: number
}

export function WhatIfAnalysis({ features, currentProbability }: WhatIfAnalysisProps) {
  const [values, setValues] = useState<Record<string, number>>({})
  const [newProbability, setNewProbability] = useState(currentProbability)

  // Initialize values
  useEffect(() => {
    const initialValues: Record<string, number> = {}
    features.forEach((feature) => {
      initialValues[feature.name] = feature.value
    })
    setValues(initialValues)
  }, [features])

  // Simulate probability change based on feature changes
  useEffect(() => {
    if (Object.keys(values).length === 0) return

    // This is a simplified model for demonstration
    // In a real app, you would call an API to get the new prediction

    let probabilityChange = 0

    features.forEach((feature) => {
      const originalValue = feature.value
      const newValue = values[feature.name] || originalValue
      const normalizedChange = (newValue - originalValue) / (feature.max - feature.min)

      // Different features affect probability differently
      switch (feature.name) {
        case "cyclomaticComplexity":
          probabilityChange += normalizedChange * 0.3 // 30% weight
          break
        case "linesAdded":
          probabilityChange += normalizedChange * 0.2 // 20% weight
          break
        case "cognitiveComplexity":
          probabilityChange += normalizedChange * 0.15 // 15% weight
          break
        default:
          probabilityChange += normalizedChange * 0.1 // 10% weight
      }
    })

    // Calculate new probability
    const newProb = Math.max(0, Math.min(1, currentProbability + probabilityChange))
    setNewProbability(newProb)
  }, [values, features, currentProbability])

  const handleSliderChange = (name: string, value: number[]) => {
    setValues((prev) => ({
      ...prev,
      [name]: value[0],
    }))
  }

  // Format feature name for display
  const formatFeatureName = (name: string) => {
    return name
      .replace(/([A-Z])/g, " $1") // Add space before capital letters
      .replace(/^./, (str) => str.toUpperCase()) // Capitalize first letter
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-6">
        {features.map((feature) => (
          <div key={feature.name} className="space-y-2">
            <div className="flex justify-between">
              <Label htmlFor={feature.name}>{formatFeatureName(feature.name)}</Label>
              <span className="text-sm font-medium">{values[feature.name] || feature.value}</span>
            </div>
            <Slider
              id={feature.name}
              min={feature.min}
              max={feature.max}
              step={1}
              value={[values[feature.name] || feature.value]}
              onValueChange={(value) => handleSliderChange(feature.name, value)}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{feature.min}</span>
              <span>{feature.max}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 bg-muted rounded-md">
        <div className="flex justify-between items-center mb-2">
          <h4 className="font-medium">Predicted Probability</h4>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-primary/60"></div>
            <span className="text-sm">Original</span>
            <div className="w-3 h-3 rounded-full bg-primary"></div>
            <span className="text-sm">New</span>
          </div>
        </div>

        <div className="relative h-8 bg-muted-foreground/20 rounded-full overflow-hidden">
          {/* Original probability bar */}
          <div
            className="absolute top-0 left-0 h-full bg-primary/60"
            style={{ width: `${currentProbability * 100}%` }}
          ></div>

          {/* New probability bar */}
          <div className="absolute top-0 left-0 h-full bg-primary" style={{ width: `${newProbability * 100}%` }}></div>

          {/* Probability markers */}
          <div className="absolute top-0 left-0 w-full h-full flex justify-between px-2 items-center text-xs text-white font-medium">
            <span>0%</span>
            <span>25%</span>
            <span>50%</span>
            <span>75%</span>
            <span>100%</span>
          </div>
        </div>

        <div className="flex justify-between mt-4">
          <div>
            <div className="text-sm text-muted-foreground">Original</div>
            <div className="text-lg font-bold">{(currentProbability * 100).toFixed(1)}%</div>
          </div>
          <div className="text-right">
            <div className="text-sm text-muted-foreground">New</div>
            <div className="text-lg font-bold">{(newProbability * 100).toFixed(1)}%</div>
          </div>
        </div>

        <div className="mt-4 text-sm text-muted-foreground">
          {newProbability < currentProbability ? (
            <p>
              These changes would <span className="text-success font-medium">reduce</span> the probability of defects by{" "}
              {((currentProbability - newProbability) * 100).toFixed(1)}%.
            </p>
          ) : newProbability > currentProbability ? (
            <p>
              These changes would <span className="text-destructive font-medium">increase</span> the probability of
              defects by {((newProbability - currentProbability) * 100).toFixed(1)}%.
            </p>
          ) : (
            <p>These changes would have no significant impact on the prediction.</p>
          )}
        </div>
      </div>
    </div>
  )
}
