// frontend/components/jobs/hp-search/HpSearchJobStepper.tsx
import React from 'react';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface HpSearchJobStepperProps {
  currentStep: number;
  steps: { name: string; description?: string }[];
  onStepClick?: (stepIndex: number) => void;
  maxCompletedStep: number;
}

export const HpSearchJobStepper: React.FC<HpSearchJobStepperProps> = ({
  currentStep,
  steps,
  onStepClick,
  maxCompletedStep,
}) => {
  const TOTAL_STEPS = steps.length;
  const progressPercentage = TOTAL_STEPS > 1 ? ((currentStep - 1) / (TOTAL_STEPS - 1)) * 100 : 0;

  return (
    <nav aria-label="Progress" className="mb-8">
      <div className="flex justify-between items-center mb-2">
        {steps.map((step, stepIdx) => (
          <div key={step.name} className="flex flex-col items-center flex-1 relative">
            <div className={cn(
              "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-all z-10",
              stepIdx < currentStep ? "bg-primary text-primary-foreground" :
              stepIdx === currentStep - 1 ? "bg-primary text-primary-foreground scale-110" :
              "border bg-muted text-muted-foreground",
              onStepClick && stepIdx <= maxCompletedStep + 1 ? "cursor-pointer" : "cursor-default"
            )}
            onClick={() => onStepClick && onStepClick(stepIdx + 1)}>
              {stepIdx < currentStep - 1 || stepIdx < maxCompletedStep ? <Check className="h-5 w-5"/> : stepIdx + 1}
            </div>
            <p className={cn(
              "mt-1 text-xs text-center whitespace-nowrap",
              stepIdx === currentStep - 1 ? "font-semibold text-primary" : "text-muted-foreground"
            )}>
              {step.name}
            </p>
          </div>
        ))}
      </div>
    </nav>
  );
};