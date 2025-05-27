// frontend/app/model-comparison/page.tsx
"use client"

import React, { useState, useEffect, useMemo, useCallback, Suspense } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation" // For navigation actions
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Download, Info, Search, X, BarChart2, CheckSquare, Layers, Maximize2, Minimize2, RefreshCw, AlertTriangle } from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { Label } from "@/components/ui/label"
import { PageLoader } from "@/components/ui/page-loader"
import { toast } from "@/hooks/use-toast"

import { MainLayout } from "@/components/main-layout"
import { PageContainer } from "@/components/ui/page-container"

import { apiService, handleApiError } from "@/lib/apiService"
import { MLModelRead, PaginatedMLModelRead, ModelPerformanceMetrics } from "@/types/api/ml-model"

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip, // Alias to avoid conflict with shadcn Tooltip
  Legend as RechartsLegend, // Alias
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Cell, // For custom bar colors if needed
} from "recharts"
import { ChartContainer, ChartTooltipContent, ChartLegendContent } from "@/components/ui/chart" // shadcn/ui chart components


const MAX_SELECTED_MODELS = 5; // Allow up to 5 models for comparison visualization

// Define a more specific type for chart data to ensure consistency
interface ChartModelData {
  id: string;
  name: string; // Short name for chart labels
  version: number;
  model_type: string;
  metrics: ModelPerformanceMetrics & { // Flattened metrics for easier access
    training_time_seconds?: number;
    inference_latency_ms?: number;
  };
}

// Metrics for Radar Chart
const RADAR_CHART_METRICS: Array<{ key: keyof ModelPerformanceMetrics; label: string; range: [number, number] }> = [
  { key: "accuracy", label: "Accuracy", range: [0, 1] },
  { key: "f1_weighted", label: "F1 (Weighted)", range: [0, 1] },
  { key: "precision_weighted", label: "Precision (W)", range: [0, 1] },
  { key: "recall_weighted", label: "Recall (W)", range: [0, 1] },
  { key: "roc_auc", label: "AUC", range: [0, 1] },
];

// Metrics available for Bar Chart comparison
const BAR_CHART_METRIC_OPTIONS: Array<{ value: keyof ChartModelData['metrics']; label: string }> = [
  { value: "accuracy", label: "Accuracy" },
  { value: "f1_weighted", label: "F1 Score (Weighted)" },
  { value: "precision_weighted", label: "Precision (Weighted)" },
  { value: "recall_weighted", label: "Recall (Weighted)" },
  { value: "roc_auc", label: "ROC AUC" },
  { value: "log_loss", label: "Log Loss" },
  { value: "training_time_seconds", label: "Training Time (s)" },
  { value: "inference_latency_ms", label: "Inference Latency (ms)" },
];



function ModelComparisonPageContent() {
  const router = useRouter();

  // --- State ---
  const [allModels, setAllModels] = useState<MLModelRead[]>([]);
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  
  const [comparisonMetricKey, setComparisonMetricKey] = useState<keyof ChartModelData['metrics']>("accuracy");
  
  const [searchQuerySelection, setSearchQuerySelection] = useState("");
  const [typeFilterSelection, setTypeFilterSelection] = useState("all");
  
  const [searchQueryTable, setSearchQueryTable] = useState("");
  const [typeFilterTable, setTypeFilterTable] = useState("all");

  const [activeTab, setActiveTab] = useState("comparison");
  
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [availableModelTypes, setAvailableModelTypes] = useState<string[]>([]);

  // --- Data Fetching ---
  const fetchAllModels = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Fetch a large number of models, assuming comparison page benefits from seeing many.
      // Backend pagination can be added later if performance becomes an issue.
      const response = await apiService.getModels({ limit: 200 }); 
      const fetchedModels = response.items || [];
      setAllModels(fetchedModels);

      const types = Array.from(new Set(fetchedModels.map(m => m.model_type))).sort();
      setAvailableModelTypes(types);

    } catch (err) {
      handleApiError(err, "Failed to load models");
      setError(err instanceof Error ? err.message : "Could not load models.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllModels();
  }, [fetchAllModels]);

  const filteredModelsForSelectionList = useMemo(() => {
    return allModels.filter(model => {
      const nameMatch = model.name.toLowerCase().includes(searchQuerySelection.toLowerCase()) ||
                        model.version.toString().includes(searchQuerySelection.toLowerCase());
      const typeMatch = typeFilterSelection === "all" || model.model_type === typeFilterSelection;
      return nameMatch && typeMatch;
    });
  }, [allModels, searchQuerySelection, typeFilterSelection]);

  const filteredModelsForTable = useMemo(() => {
    return allModels.filter(model => {
      const nameMatch = model.name.toLowerCase().includes(searchQueryTable.toLowerCase()) ||
                        model.version.toString().includes(searchQueryTable.toLowerCase());
      const typeMatch = typeFilterTable === "all" || model.model_type === typeFilterTable;
      return nameMatch && typeMatch;
    });
  }, [allModels, searchQueryTable, typeFilterTable]);
  
  const selectedModelsData = useMemo<ChartModelData[]>(() => {
    return selectedModelIds.map(id => {
      const model = allModels.find(m => m.id.toString() === id);
      if (!model) return null;
      // Ensure performance_metrics exists before trying to spread it
      const perfMetrics = model.performance_metrics || {};
      return {
        id: model.id.toString(),
        name: `${model.name} v${model.version}`, // This will be used for dataKeys in radar
        version: model.version,
        model_type: model.model_type,
        metrics: { 
          ...perfMetrics, // Spread existing metrics
          // Explicitly map known metrics to ensure they are numbers or undefined
          accuracy: typeof perfMetrics.accuracy === 'number' ? perfMetrics.accuracy : undefined,
          precision_weighted: typeof perfMetrics.precision_weighted === 'number' ? perfMetrics.precision_weighted : undefined,
          recall_weighted: typeof perfMetrics.recall_weighted === 'number' ? perfMetrics.recall_weighted : undefined,
          f1_weighted: typeof perfMetrics.f1_weighted === 'number' ? perfMetrics.f1_weighted : undefined,
          roc_auc: typeof perfMetrics.roc_auc === 'number' ? perfMetrics.roc_auc : undefined,
          log_loss: typeof perfMetrics.log_loss === 'number' ? perfMetrics.log_loss : undefined,
          training_time_seconds: typeof perfMetrics.training_time_seconds === 'number' ? perfMetrics.training_time_seconds : undefined,
          inference_latency_ms: typeof perfMetrics.inference_latency_ms === 'number' ? perfMetrics.inference_latency_ms : undefined,
        }
      };
    }).filter(Boolean) as ChartModelData[];
  }, [selectedModelIds, allModels]);

  const radarChartFormattedData = useMemo(() => {
    if (selectedModelsData.length === 0) return [];
    
    return RADAR_CHART_METRICS.map(metricInfo => {
      const radarPoint: { subject: string; fullMark: number; [modelName: string]: string | number } = {
        subject: metricInfo.label,
        fullMark: metricInfo.range[1], // Use the max of the range as fullMark
      };
      selectedModelsData.forEach(model => {
        // Use model.name as the key, which is unique (`ModelName vVersion`)
        radarPoint[model.name] = model.metrics[metricInfo.key] ?? 0; 
      });
      return radarPoint;
    });
  }, [selectedModelsData]);

  const barChartData = useMemo(() => {
    return selectedModelsData.map(model => ({
      name: model.name, // This is `${model.name} v${model.version}`
      [comparisonMetricKey]: model.metrics[comparisonMetricKey] ?? 0 
    }));
  }, [selectedModelsData, comparisonMetricKey]);

  // --- Event Handlers ---
  const handleToggleModelSelection = (modelId: string) => {
    setSelectedModelIds(prev => {
      if (prev.includes(modelId)) {
        return prev.filter(id => id !== modelId);
      } else {
        if (prev.length >= MAX_SELECTED_MODELS) {
          toast({
            title: "Selection Limit Reached",
            description: `You can select up to ${MAX_SELECTED_MODELS} models for comparison.`,
            variant: "default"
          });
          // Option 1: Replace oldest, Option 2: Prevent adding
          // For now, prevent adding more:
          return prev; 
          // Or replace oldest: return [...prev.slice(1), modelId];
        }
        return [...prev, modelId];
      }
    });
  };

  const handleClearSelection = () => setSelectedModelIds([]);

  const handleCompareSelectedFromTable = () => {
    if (selectedModelIds.length < 1) { // Allow comparing even 1 model initially in charts
      toast({ title: "No Models Selected", description: "Please select models from the table to compare.", variant: "default" });
      return;
    }
    setActiveTab("comparison");
    // selectedModelIds is already updated, so the Comparison tab will reflect this.
  };

  const handleExportReport = () => { // Placeholder
    toast({ title: "Export Report", description: "This feature is coming soon!" });
  };
  
  const formatMetricValue = (value: any): string => {
    if (typeof value === 'number') {
        // Heuristic for deciding decimal places
        if (Math.abs(value) < 0.0001 && value !== 0) return value.toExponential(2);
        if (Math.abs(value) < 1) return value.toFixed(3);
        if (Math.abs(value) < 100) return value.toFixed(2);
        return value.toFixed(0);
    }
    return String(value ?? 'N/A');
  };

  // --- Loading and Error UI (moved after all hooks) ---
  if (isLoading && allModels.length === 0) {
    return <PageLoader message="Loading models for comparison..." />;
  }

  if (error) {
    return (
        <MainLayout>
            <PageContainer title="Error Loading Models" description={error}>
                <Alert variant="destructive" className="mb-4">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Loading Failed</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
                </Alert>
                <Button onClick={() => fetchAllModels()}><RefreshCw className="mr-2 h-4 w-4"/>Try Again</Button>
            </PageContainer>
        </MainLayout>
    );
  }

  const RECHARTS_COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff7300", "#00C49F", "#FFBB28", "#FF8042"];

  // --- Render JSX ---
  return (
    <MainLayout>
      <PageContainer
        title="Model Comparison"
        description="Select and compare machine learning models based on their performance metrics and characteristics."
        actions={<Button variant="outline" onClick={handleExportReport}><Download className="mr-2 h-4 w-4" />Export Report</Button>}
      >
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as "comparison" | "models")} className="space-y-6">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="comparison">Visual Comparison</TabsTrigger>
            <TabsTrigger value="models">Model List & Selection</TabsTrigger>
          </TabsList>

          {/* Comparison Tab */}
          <TabsContent value="comparison" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Model Selection for Visual Comparison</CardTitle>
                <CardDescription>
                  Select up to {MAX_SELECTED_MODELS} models. Currently selected: {selectedModelIds.length}.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2 mb-4">
                  {selectedModelsData.length > 0 ? (
                    <>
                      {selectedModelsData.map(model => (
                        <Badge key={model.id} variant="secondary" className="text-xs px-2 py-1">
                          {model.name}
                          <button onClick={() => handleToggleModelSelection(model.id.toString())} className="ml-1.5 text-muted-foreground hover:text-foreground">
                            <X className="h-3 w-3" />
                          </button>
                        </Badge>
                      ))}
                      <Button variant="ghost" size="sm" onClick={handleClearSelection} className="h-6 px-2 text-xs">Clear All</Button>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">No models selected. Choose from the "Model List & Selection" tab or below.</p>
                  )}
                </div>
                <div className="flex flex-col sm:flex-row gap-4">
                  <div className="relative flex-grow">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      placeholder="Search models by name/version..."
                      value={searchQuerySelection}
                      onChange={(e) => setSearchQuerySelection(e.target.value)}
                      className="h-9 pl-10"
                    />
                  </div>
                  <Select value={typeFilterSelection} onValueChange={setTypeFilterSelection} disabled={availableModelTypes.length === 0}>
                    <SelectTrigger className="h-9 w-full sm:w-[200px]">
                      <SelectValue placeholder="All Model Types" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Model Types</SelectItem>
                      {availableModelTypes.map(type => (<SelectItem key={type} value={type}>{type}</SelectItem>))}
                    </SelectContent>
                  </Select>
                </div>
                <ScrollArea className="h-48 rounded-md border p-2">
                  {filteredModelsForSelectionList.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">No models match filters.</p>
                  ) : (
                    filteredModelsForSelectionList.map(model => (
                      <div key={model.id} className="flex items-center space-x-3 p-1.5 hover:bg-accent rounded-md">
                        <Checkbox
                          id={`select-comp-${model.id}`}
                          checked={selectedModelIds.includes(model.id.toString())}
                          onCheckedChange={() => handleToggleModelSelection(model.id.toString())}
                        />
                        <Label htmlFor={`select-comp-${model.id}`} className="text-sm font-normal cursor-pointer flex-grow">
                          {model.name} v{model.version} <Badge variant="outline" className="text-xs ml-1">{model.model_type}</Badge>
                        </Label>
                      </div>
                    ))
                  )}
                </ScrollArea>
              </CardContent>
            </Card>

            {selectedModelsData.length > 0 ? (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle>Performance Metric Comparison</CardTitle>
                    <div className="flex items-center mt-1">
                        <Label htmlFor="comparison-metric-select" className="mr-2 text-sm text-muted-foreground">Metric:</Label>
                        <Select value={comparisonMetricKey as string} onValueChange={(val) => setComparisonMetricKey(val as keyof ChartModelData['metrics'])}>
                            <SelectTrigger id="comparison-metric-select" className="h-8 text-xs w-auto sm:w-[220px]">
                                <SelectValue placeholder="Select metric" />
                            </SelectTrigger>
                            <SelectContent>
                                {BAR_CHART_METRIC_OPTIONS.map(opt => (
                                    <SelectItem key={opt.value} value={opt.value as string} className="text-xs">{opt.label}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {/* give the container a positive height so RC can measure itself */}
                    <div className="w-full h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={barChartData}
                          layout="vertical"
                          margin={{ top: 5, right: 20, bottom: 20, left: 20 }}
                          barCategoryGap="20%"
                        >
                          <CartesianGrid strokeDasharray="3 3" opacity={0.5} />

                          <XAxis
                            type="number"
                            domain={['auto', 'auto']}
                            tickFormatter={formatMetricValue}
                            allowDecimals
                            style={{ fontSize: "0.7rem" }}
                          />

                          <YAxis
                            dataKey="name"
                            type="category"
                            width={120}
                            interval={0}
                            style={{ fontSize: "0.7rem" }}
                            tickFormatter={(v) => (v.length > 15 ? v.slice(0, 13) + "…" : v)}
                          />

                          <RechartsTooltip
                            cursor={{ fill: "hsl(var(--accent))", fillOpacity: 0.3 }}
                            contentStyle={{
                              backgroundColor: "hsl(var(--background))",
                              border: "1px solid hsl(var(--border))",
                              borderRadius: "var(--radius)",
                            }}
                            labelStyle={{ color: "hsl(var(--foreground))", fontWeight: "bold" }}
                            itemStyle={{ color: "hsl(var(--foreground))" }}
                            formatter={(v: number) => formatMetricValue(v)}
                          />

                          <Bar
                            dataKey={comparisonMetricKey}
                            radius={[0, 4, 4, 0]}
                            barSize={Math.max(15, 40 - selectedModelsData.length * 3)}
                          >
                            {barChartData.map((_, i) => (
                              <Cell
                                key={`cell-${i}`}
                                fill={RECHARTS_COLORS[i % RECHARTS_COLORS.length]}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>

                {/* ... Model Stats Card ... (no changes needed here unless `model_size_mb` was displayed) ... */}
                <Card className="lg:col-span-1">
                  <CardHeader><CardTitle>Selected Model Stats</CardTitle></CardHeader>
                  <CardContent>
                    <ScrollArea className="max-h-[320px]">
                        <div className="space-y-4">
                        {selectedModelsData.map(model => (
                            <div key={model.id} className="text-xs p-2 border rounded-md">
                            <h4 className="font-semibold text-sm mb-1">{model.name}</h4>
                            <p>Type: <Badge variant="outline" className="text-xs">{model.model_type}</Badge></p>
                            <p>Training Time: {formatMetricValue(model.metrics.training_time_seconds)} s</p>
                            <p>Inference Latency: {formatMetricValue(model.metrics.inference_latency_ms)} ms</p>
                            </div>
                        ))}
                        </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
                
                <Card className="lg:col-span-full">
                  <CardHeader><CardTitle>Overall Metrics Radar</CardTitle></CardHeader>
                  <CardContent>
                    {radarChartFormattedData.length > 0 ? (
                        <ChartContainer config={{}} className="min-h-[400px] aspect-video">
                          <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarChartFormattedData}>
                            <PolarGrid opacity={0.5}/>
                            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }}/>
                            <PolarRadiusAxis angle={30} domain={[0, 1]} tickFormatter={(tick) => tick.toFixed(1)} style={{ fontSize: '0.6rem' }}/>
                            {selectedModelsData.map((model, index) => ( // Loop through selected models to create a Radar for each
                                <Radar 
                                    key={model.id}
                                    name={model.name} // This name will appear in Legend and Tooltip
                                    dataKey={model.name} // The key in radarChartFormattedData that holds this model's values
                                    stroke={RECHARTS_COLORS[index % RECHARTS_COLORS.length]}
                                    fill={RECHARTS_COLORS[index % RECHARTS_COLORS.length]}
                                    fillOpacity={0.25} 
                                />
                            ))}
                            <RechartsLegend wrapperStyle={{ fontSize: '0.75rem', paddingTop: '20px' }}/>
                            <RechartsTooltip 
                                contentStyle={{ backgroundColor: 'hsl(var(--background))', border: '1px solid hsl(var(--border))', borderRadius: 'var(--radius)'}}
                                labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: 'bold' }}
                                itemStyle={{ color: 'hsl(var(--foreground))' }}
                                formatter={(value: number, name: string, entry: any) => {
                                    // 'name' here is the dataKey of the Radar (e.g., model.name)
                                    // 'value' is the metric value for that model on the current axis
                                    // 'entry.payload.subject' is the metric name (e.g., "Accuracy")
                                    return `${formatMetricValue(value)} (${entry.payload.subject})`;
                                }}
                            />
                          </RadarChart>
                        </ChartContainer>
                    ) : (
                         <div className="flex items-center justify-center h-[400px] border rounded-md border-dashed">
                            <p className="text-muted-foreground">Select models to view radar comparison.</p>
                        </div>
                    )}
                  </CardContent>
                </Card>

              </div>
            ) : (
              // ... Alert when no models selected for comparison ...
              <Alert variant="default" className="mt-6">
                <Info className="h-4 w-4" />
                <AlertTitle>No Models Selected for Comparison</AlertTitle>
                <AlertDescription>
                  Please select models from the "Model List & Selection" tab or use the quick selection panel above to see comparison charts.
                </AlertDescription>
              </Alert>
            )}
          </TabsContent>

          {/* Models Tab - Update Table Columns */}
          <TabsContent value="models" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>All Available Models</CardTitle>
                <CardDescription>Select models from this list to add them to the comparison.</CardDescription>
                 <div className="flex flex-col sm:flex-row gap-4 pt-4">
                  <Input
                    placeholder="Search models by name/version..."
                    value={searchQueryTable}
                    onChange={(e) => setSearchQueryTable(e.target.value)}
                    className="h-9 flex-grow"
                  />
                  <Select value={typeFilterTable} onValueChange={setTypeFilterTable} disabled={availableModelTypes.length === 0}>
                    <SelectTrigger className="h-9 w-full sm:w-[200px]">
                      <SelectValue placeholder="All Model Types" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Model Types</SelectItem>
                      {availableModelTypes.map(type => (<SelectItem key={type} value={type}>{type}</SelectItem>))}
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12"><CheckSquare className="h-4 w-4"/></TableHead>
                        <TableHead>Name & Version</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Accuracy</TableHead>
                        <TableHead>F1 (Weighted)</TableHead>
                        <TableHead>ROC AUC</TableHead> {/* Added ROC AUC */}
                        <TableHead>Training Time (s)</TableHead>
                        <TableHead>Last Updated</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredModelsForTable.length === 0 ? (
                        <TableRow><TableCell colSpan={9} className="text-center py-8 text-muted-foreground">No models found.</TableCell></TableRow> // Adjusted colSpan
                      ) : (
                        filteredModelsForTable.map(model => (
                          <TableRow key={model.id} className={selectedModelIds.includes(model.id.toString()) ? "bg-accent/50 dark:bg-accent/20" : ""}>
                            <TableCell>
                              <Checkbox
                                id={`table-select-${model.id}`}
                                checked={selectedModelIds.includes(model.id.toString())}
                                onCheckedChange={() => handleToggleModelSelection(model.id.toString())}
                              />
                            </TableCell>
                            <TableCell className="font-medium text-sm">
                                <Link href={`/models/${model.id}`} className="hover:underline">{model.name}</Link>
                                <span className="block text-xs text-muted-foreground">v{model.version}</span>
                            </TableCell>
                            <TableCell><Badge variant="outline" className="text-xs">{model.model_type}</Badge></TableCell>
                            <TableCell className="text-xs">{formatMetricValue(model.performance_metrics?.accuracy)}</TableCell>
                            <TableCell className="text-xs">{formatMetricValue(model.performance_metrics?.f1_weighted)}</TableCell>
                            <TableCell className="text-xs">{formatMetricValue(model.performance_metrics?.roc_auc)}</TableCell> {/* Display ROC AUC */}
                            <TableCell className="text-xs">{formatMetricValue(model.performance_metrics?.training_time_seconds)}</TableCell>
                            <TableCell className="text-xs">{new Date(model.updated_at).toLocaleDateString()}</TableCell>
                            <TableCell className="text-right">
                                <Button variant="ghost" size="sm" asChild>
                                    <Link href={`/models/${model.id}`}>Details</Link>
                                </Button>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
              <CardFooter className="justify-end">
                  <Button onClick={handleCompareSelectedFromTable} disabled={selectedModelIds.length === 0}>
                    <BarChart2 className="mr-2 h-4 w-4" /> View Comparison ({selectedModelIds.length})
                  </Button>
              </CardFooter>
            </Card>
          </TabsContent>
        </Tabs>
      </PageContainer>
    </MainLayout>
  );
}

export default function ModelComparisonPage() {
  return (
    <Suspense fallback={<PageLoader message="Loading model comparison..." />}>
      <ModelComparisonPageContent />
    </Suspense>
  );
}