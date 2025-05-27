// frontend/components/jobs/train/TrainingJobStepper.tsx
import React from 'react';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

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
  return (
    <nav aria-label="Progress" className="mb-8">
      <ol role="list" className="flex items-center justify-around">
        {steps.map((step, stepIdx) => (
          <li key={step.name} className={cn('relative flex-1', stepIdx !== steps.length - 1 ? 'pr-8 sm:pr-20' : '')}>
            {stepIdx < currentStep -1 || stepIdx <= maxCompletedStep ? ( // Completed step
              <>
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="h-0.5 w-full bg-primary" />
                </div>
                <button
                  type="button"
                  onClick={() => onStepClick && onStepClick(stepIdx + 1)}
                  disabled={!onStepClick}
                  className="relative flex h-8 w-8 items-center justify-center rounded-full bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  <Check className="h-5 w-5 text-primary-foreground" aria-hidden="true" />
                  <span className="sr-only">{step.name} - Completed</span>
                </button>
              </>
            ) : stepIdx === currentStep -1 ? ( // Current step
              <>
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="h-0.5 w-full bg-gray-200 dark:bg-gray-700" />
                </div>
                <button
                  type="button"
                  disabled
                  className="relative flex h-8 w-8 items-center justify-center rounded-full border-2 border-primary bg-background text-primary focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                  aria-current="step"
                >
                  <span className="h-2.5 w-2.5 rounded-full bg-primary" aria-hidden="true" />
                  <span className="sr-only">{step.name} - Current</span>
                </button>
              </>
            ) : ( // Upcoming step
              <>
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="h-0.5 w-full bg-gray-200 dark:bg-gray-700" />
                </div>
                <button
                  type="button"
                  onClick={() => onStepClick && onStepClick(stepIdx + 1)}
                  disabled={!onStepClick || stepIdx > maxCompletedStep +1} // Only allow clicking next incomplete step
                  className="group relative flex h-8 w-8 items-center justify-center rounded-full border-2 border-gray-300 bg-background hover:border-gray-400 disabled:hover:border-gray-300 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  <span className="h-2.5 w-2.5 rounded-full bg-transparent group-hover:bg-gray-300" aria-hidden="true" />
                  <span className="sr-only">{step.name} - Upcoming</span>
                </button>
              </>
            )}
             <p className="absolute -bottom-6 left-1/2 -translate-x-1/2 transform whitespace-nowrap text-center text-xs font-medium text-muted-foreground md:static md:bottom-auto md:left-auto md:translate-x-0 md:transform-none md:pt-1.5">
              {step.name}
            </p>
          </li>
        ))}
      </ol>
    </nav>
  );
};