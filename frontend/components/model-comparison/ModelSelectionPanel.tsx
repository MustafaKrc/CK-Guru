// frontend/components/model-comparison/ModelSelectionPanel.tsx

import React, { useMemo, useState } from "react";
import { MLModelRead } from "@/types/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useDebounce } from "@/hooks/useDebounce";
import { Skeleton } from "../ui/skeleton";
import { MAX_SELECTED_MODELS } from "@/app/model-comparison/page";

interface ModelSelectionPanelProps {
  allModels: MLModelRead[];
  selectedIds: string[];
  onToggleSelection: (modelId: string) => void;
  isLoading: boolean;
}

export const ModelSelectionPanel: React.FC<ModelSelectionPanelProps> = ({
  allModels,
  selectedIds,
  onToggleSelection,
  isLoading,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearch = useDebounce(searchQuery, 300);

  const filteredModels = useMemo(() => {
    return allModels.filter(model => 
      model.name.toLowerCase().includes(debouncedSearch.toLowerCase()) ||
      model.model_type.toLowerCase().includes(debouncedSearch.toLowerCase())
    );
  }, [allModels, debouncedSearch]);

  const renderContent = () => {
    if (isLoading) {
      return <div className="space-y-3 p-2">{Array.from({length: 10}).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}</div>;
    }
    if (filteredModels.length === 0) {
      return <p className="text-center text-sm text-muted-foreground p-4">No models found.</p>;
    }
    return (
      <div className="space-y-2 p-2">
        {filteredModels.map(model => (
          <div
            key={model.id}
            className="flex items-center space-x-3 p-2 rounded-md hover:bg-accent has-[:checked]:bg-accent/50"
          >
            <Checkbox
              id={`select-comp-${model.id}`}
              checked={selectedIds.includes(String(model.id))}
              onCheckedChange={() => onToggleSelection(String(model.id))}
            />
            <Label
              htmlFor={`select-comp-${model.id}`}
              className="text-sm font-normal cursor-pointer flex-grow space-y-0.5"
            >
              <div className="font-medium truncate" title={model.name}>{model.name}</div>
              <div className="text-xs text-muted-foreground">v{model.version} • {model.model_type}</div>
            </Label>
          </div>
        ))}
      </div>
    );
  };

  return (
    <Card className="h-full flex flex-col">
      <CardHeader>
        <CardTitle>Select Models</CardTitle>
        <CardDescription>
          Choose up to {MAX_SELECTED_MODELS} models to compare. 
          <Badge variant="secondary" className="ml-2">{selectedIds.length} / {MAX_SELECTED_MODELS} selected</Badge>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-grow flex flex-col gap-4 overflow-hidden p-4 pt-0">
        <Input
          placeholder="Search by name or type..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
        />
        <ScrollArea className="flex-grow rounded-md border">
          {renderContent()}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};