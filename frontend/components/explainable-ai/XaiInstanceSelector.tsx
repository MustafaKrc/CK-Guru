// frontend/components/explainable-ai/XaiInstanceSelector.tsx
import React, { useMemo } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";

interface Instance {
  file?: string | null;
  class_name?: string | null;
  [key: string]: any; // Allow other properties
}

interface XaiInstanceSelectorProps {
  instances: Instance[];
  selectedIdentifier: string | undefined; // Can be undefined if nothing is selected
  onInstanceChange: (identifier: string) => void;
  label?: string;
  identifierKey?: "class_name" | "file"; // What to use as the primary key for selection logic
}

export const XaiInstanceSelector: React.FC<XaiInstanceSelectorProps> = ({
  instances,
  selectedIdentifier,
  onInstanceChange,
  label = "Select Instance",
  identifierKey = "class_name"
}) => {
  if (!instances || instances.length === 0) {
    return null; // Don't render if no instances
  }

  // Create unique display names and identifiers for the dropdown
  // Prioritize class_name, then file, then a generated ID
  const uniqueOptions = useMemo(() => {
    const optionMap = new Map<string, { value: string; label: string }>();
    instances.forEach((inst, index) => {
      let id: string;
      let displayLabel: string;

      if (identifierKey === "class_name" && inst.class_name) {
        id = inst.class_name;
        displayLabel = inst.class_name;
        if (inst.file) displayLabel += ` (${inst.file.split('/').pop()})`;
      } else if (identifierKey === "file" && inst.file) {
        id = inst.file;
        displayLabel = inst.file.split('/').pop() || inst.file; // Show filename
        if (inst.class_name) displayLabel += ` [${inst.class_name}]`;
      } else if (inst.class_name) { // Fallback logic if identifierKey is not perfectly matched
        id = inst.class_name;
        displayLabel = inst.class_name;
      } else if (inst.file) {
        id = inst.file;
        displayLabel = inst.file.split('/').pop() || inst.file;
      }
      else {
        id = `instance_${index}`;
        displayLabel = `Instance ${index + 1}`;
      }
      
      if (!optionMap.has(id)) { // Ensure unique IDs for SelectItem values
        optionMap.set(id, { value: id, label: displayLabel });
      }
    });
    return Array.from(optionMap.values());
  }, [instances, identifierKey]);


  if (uniqueOptions.length <= 1 && uniqueOptions.length > 0) {
    // If only one instance, no need for a selector.
    // The parent component should handle this by directly using the single instance.
    // Or, you could display the single instance name here.
    // For simplicity, let's not render the selector if only one option.
    // Parent should default to this single instance if selector is not rendered.
     if(selectedIdentifier !== uniqueOptions[0].value) {
        // Auto-select if not already selected (e.g. on initial load)
        // This might cause an infinite loop if not handled carefully in parent.
        // Better to let parent default.
     }
    return (
      <div className="mb-4">
        <Label className="text-sm font-medium text-muted-foreground">{label}:</Label>
        <p className="text-sm mt-1">{uniqueOptions[0].label}</p>
      </div>
    );
  }
  
  if (uniqueOptions.length === 0) {
     return <p className="text-sm text-muted-foreground mb-4">No instances available for selection.</p>;
  }


  return (
    <div className="mb-6">
      <Label htmlFor="xai-instance-selector" className="text-base font-semibold mb-2 block">
        {label}
      </Label>
      <Select
        value={selectedIdentifier || ""}
        onValueChange={onInstanceChange}
      >
        <SelectTrigger id="xai-instance-selector" className="w-full md:w-[350px] text-sm">
          <SelectValue placeholder="Choose an instance to inspect..." />
        </SelectTrigger>
        <SelectContent>
          {uniqueOptions.map(({ value, label: displayLabel }) => (
            <SelectItem key={value} value={value} className="text-sm">
              {displayLabel}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};