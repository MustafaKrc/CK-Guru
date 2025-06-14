// frontend/components/jobs/train/TrainingJobStepper.tsx
import React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface TrainingJobStepperProps {
  currentStep: number;
  steps: { name: string; description?: string }[];
  onStepClick?: (stepIndex: number) => void; // Allow clicking to navigate (if steps are completed)
  maxCompletedStep: number;
}

export const TrainingJobStepper: React.FC<TrainingJobStepperProps> = ({
  currentStep,
  steps,
  onStepClick,
  maxCompletedStep,
}) => {
  const TOTAL_STEPS = steps.length;

  const progressPercentage = TOTAL_STEPS > 1 ? ((currentStep - 1) / (TOTAL_STEPS - 1)) * 100 : 0;

  const circleHalfWidth = 16;
  const lineHeight = 0.5; // h-0.5 for the line

  return (
    <nav aria-label="Progress" className="mb-8">
      {/* Container for the circles and the lines */}
      <div className="relative w-full">
        {/* Background grey line (full width from center of first to center of last circle) */}
        {/* `left` and `right` position the line relative to its parent `.relative` container. */}
        {/* `top` centers it vertically with the `h-8` step buttons (32px total height, center at 16px. Line is 0.5px (2px), so top is 16-1=15px) */}
        <div className="absolute left-[16px] right-[16px] top-[15px] h-0.5 bg-gray-200 dark:bg-gray-700 z-0"></div>

        {/* Progress blue line (dynamically sized) */}
        {/* `transition-all duration-300 ease-in-out` for smooth progress animation */}
        <div
          className="absolute left-[16px] top-[15px] h-0.5 bg-primary z-0 transition-all duration-300 ease-in-out"
          style={{
            width: `calc(${progressPercentage}% * (100% - ${2 * circleHalfWidth}px) / 100)`,
          }}
          // This calculates the width as a percentage of the *actual track length* (total width minus two half-circle widths)
          // `calc(${progressPercentage}% * (100% - 32px) / 100)`
        ></div>

        {/* List of steps (circles and labels) */}
        {/* `relative z-10` ensures this list and its children are above the lines */}
        <ol role="list" className="flex justify-between items-center w-full relative z-10">
          {steps.map((step, stepIdx) => (
            <li key={step.name} className="flex flex-col items-center flex-1">
              {" "}
              {/* No `relative` here, as the parent `div` handles it */}
              {/* Step Circle/Icon button */}
              {/* `relative z-10` here ensures the button is on top of the line segments it's sitting on */}
              <div className="relative z-10">
                {stepIdx < currentStep - 1 || stepIdx <= maxCompletedStep ? ( // Completed step
                  <button
                    type="button"
                    onClick={() => onStepClick && onStepClick(stepIdx + 1)}
                    disabled={!onStepClick}
                    className="flex h-8 w-8 items-center justify-center rounded-full bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 text-primary-foreground"
                  >
                    <Check className="h-5 w-5" aria-hidden="true" />
                    <span className="sr-only">{step.name} - Completed</span>
                  </button>
                ) : stepIdx === currentStep - 1 ? ( // Current step
                  <button
                    type="button"
                    disabled // Current step is usually not clickable to navigate to itself
                    className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground scale-110 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 transition-transform"
                    aria-current="step"
                  >
                    <span className="text-sm font-medium">{stepIdx + 1}</span>{" "}
                    {/* Display step number */}
                    <span className="sr-only">{step.name} - Current</span>
                  </button>
                ) : (
                  // Upcoming step
                  <button
                    type="button"
                    onClick={() => onStepClick && onStepClick(stepIdx + 1)}
                    disabled={!onStepClick || stepIdx > maxCompletedStep + 1} // Only allow clicking next incomplete step
                    className="group flex h-8 w-8 items-center justify-center rounded-full border-2 border-gray-300 bg-background hover:border-gray-400 disabled:hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                  >
                    <span
                      className="h-2.5 w-2.5 rounded-full bg-transparent group-hover:bg-gray-300"
                      aria-hidden="true"
                    />
                    <span className="sr-only">{step.name} - Upcoming</span>
                  </button>
                )}
              </div>
              {/* Step Name (label) - positioned below the circle */}
              <p className="mt-1 text-xs font-medium text-muted-foreground whitespace-nowrap text-center">
                {step.name}
              </p>
            </li>
          ))}
        </ol>
      </div>
      {/* Overall step count display, moved outside the ol for clearer separation */}
      <div className="text-sm text-muted-foreground text-right mt-4">
        Step {currentStep} of {TOTAL_STEPS}
      </div>
    </nav>
  );
};
