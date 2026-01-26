import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { RefreshCw, Plus, ChevronDown, ChevronUp, Target, Users, TrendingUp } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import type { Feature, OpportunityArea, SolutionArchetype, IntakeFormData } from '@/types/discovery';
import { generateFeatures } from '@/lib/llm-service';
import { toast } from 'sonner';

interface FeatureSetBuilderProps {
  archetype: SolutionArchetype;
  opportunity: OpportunityArea;
  intakeData: IntakeFormData;
  initialData?: Feature[];
  onComplete: (features: Feature[]) => void;
}

export function FeatureSetBuilder({
  archetype,
  opportunity,
  intakeData,
  initialData,
  onComplete,
}: FeatureSetBuilderProps) {
  const [isLoading, setIsLoading] = useState(!initialData);
  const [features, setFeatures] = useState<Feature[]>(initialData || []);
  const [showAddFeature, setShowAddFeature] = useState(false);
  const [expandedFeatures, setExpandedFeatures] = useState<Set<string>>(new Set());
  const [newFeature, setNewFeature] = useState({ 
    name: '', 
    description: '', 
    strategicGoal: '', 
    userStories: [''], 
    successMetrics: [''], 
    bucket: '', 
    priority: 'Should' as 'Must' | 'Should' | 'Could' 
  });

  useEffect(() => {
    if (!initialData) {
      loadFeatures();
    }
  }, []);

  const loadFeatures = async () => {
    setIsLoading(true);
    try {
      const result = await generateFeatures(archetype, opportunity, intakeData);
      setFeatures(result);
      onComplete(result);
      toast.success('Feature set generated successfully');
    } catch (error) {
      toast.error('Failed to generate features');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleFeature = (id: string) => {
    const updated = features.map((f) =>
      f.id === id ? { ...f, selected: !f.selected } : f
    );
    setFeatures(updated);
    onComplete(updated);
  };

  const handleAddFeature = () => {
    if (!newFeature.name || !newFeature.description || !newFeature.bucket || !newFeature.strategicGoal) {
      toast.error('Please fill in all required fields');
      return;
    }

    const feature: Feature = {
      id: `custom-${Date.now()}`,
      ...newFeature,
      userStories: newFeature.userStories.filter(s => s.trim() !== ''),
      successMetrics: newFeature.successMetrics.filter(m => m.trim() !== ''),
      selected: true,
    };

    const updated = [...features, feature];
    setFeatures(updated);
    onComplete(updated);
    setNewFeature({ 
      name: '', 
      description: '', 
      strategicGoal: '', 
      userStories: [''], 
      successMetrics: [''], 
      bucket: '', 
      priority: 'Should' 
    });
    setShowAddFeature(false);
    toast.success('Custom feature added');
  };

  const handleRegenerate = () => {
    loadFeatures();
  };

  const toggleFeatureExpansion = (id: string) => {
    setExpandedFeatures(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Spinner className="w-12 h-12 text-primary mb-4" />
        <h3 className="text-xl font-semibold mb-2">Building Feature Set</h3>
        <p className="text-muted-foreground">Generating comprehensive features...</p>
      </div>
    );
  }

  const featuresByBucket = features.reduce((acc, feature) => {
    if (!acc[feature.bucket]) {
      acc[feature.bucket] = [];
    }
    acc[feature.bucket].push(feature);
    return acc;
  }, {} as Record<string, Feature[]>);

  const selectedCount = features.filter((f) => f.selected).length;

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-foreground">
            Feature Set Builder
          </h2>
          <p className="text-muted-foreground mt-1">
            {selectedCount} feature{selectedCount !== 1 ? 's' : ''} selected
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowAddFeature(!showAddFeature)}>
            <Plus className="w-4 h-4 mr-2" />
            Add Custom
          </Button>
          <Button variant="outline" onClick={handleRegenerate}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Regenerate
          </Button>
        </div>
      </div>

      {showAddFeature && (
        <Card className="shadow-elegant">
          <CardHeader>
            <CardTitle>Add Custom Feature</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4">
              <Input
                placeholder="Feature name"
                value={newFeature.name}
                onChange={(e) => setNewFeature({ ...newFeature, name: e.target.value })}
              />
              <Textarea
                placeholder="Feature description"
                value={newFeature.description}
                onChange={(e) => setNewFeature({ ...newFeature, description: e.target.value })}
                className="min-h-[80px]"
              />
              <Textarea
                placeholder="Strategic Goal (why it's being built)"
                value={newFeature.strategicGoal}
                onChange={(e) => setNewFeature({ ...newFeature, strategicGoal: e.target.value })}
                className="min-h-[60px]"
              />
              <div className="space-y-2">
                <label className="text-sm font-medium">User Stories</label>
                {newFeature.userStories.map((story, idx) => (
                  <Input
                    key={idx}
                    placeholder={`User story ${idx + 1} (As a...)`}
                    value={story}
                    onChange={(e) => {
                      const updated = [...newFeature.userStories];
                      updated[idx] = e.target.value;
                      setNewFeature({ ...newFeature, userStories: updated });
                    }}
                  />
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setNewFeature({ ...newFeature, userStories: [...newFeature.userStories, ''] })}
                >
                  + Add User Story
                </Button>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Success Metrics</label>
                {newFeature.successMetrics.map((metric, idx) => (
                  <Input
                    key={idx}
                    placeholder={`Success metric ${idx + 1}`}
                    value={metric}
                    onChange={(e) => {
                      const updated = [...newFeature.successMetrics];
                      updated[idx] = e.target.value;
                      setNewFeature({ ...newFeature, successMetrics: updated });
                    }}
                  />
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setNewFeature({ ...newFeature, successMetrics: [...newFeature.successMetrics, ''] })}
                >
                  + Add Success Metric
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Input
                  placeholder="Bucket/Category"
                  value={newFeature.bucket}
                  onChange={(e) => setNewFeature({ ...newFeature, bucket: e.target.value })}
                />
                <Select
                  value={newFeature.priority}
                  onValueChange={(value: any) => setNewFeature({ ...newFeature, priority: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Must">Must</SelectItem>
                    <SelectItem value="Should">Should</SelectItem>
                    <SelectItem value="Could">Could</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button onClick={handleAddFeature}>Add Feature</Button>
          </CardContent>
        </Card>
      )}

      <div className="space-y-6">
        {Object.entries(featuresByBucket).map(([bucket, bucketFeatures]) => (
          <Card key={bucket} className="shadow-elegant">
            <CardHeader>
              <CardTitle>{bucket}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {bucketFeatures.map((feature) => {
                  const isExpanded = expandedFeatures.has(feature.id);
                  return (
                    <Collapsible
                      key={feature.id}
                      open={isExpanded}
                      onOpenChange={() => toggleFeatureExpansion(feature.id)}
                    >
                      <div className="rounded-lg border hover:bg-accent/50 transition-colors">
                        <div className="flex items-start gap-3 p-4">
                          <Checkbox
                            id={feature.id}
                            checked={feature.selected}
                            onCheckedChange={() => handleToggleFeature(feature.id)}
                            className="mt-1"
                          />
                          <div className="flex-1 space-y-1">
                            <label
                              htmlFor={feature.id}
                              className="text-sm font-semibold cursor-pointer block"
                            >
                              {feature.name}
                            </label>
                            <p className="text-sm text-muted-foreground">
                              {feature.description}
                            </p>
                          </div>
                          <Badge
                            variant={
                              feature.priority === 'Must'
                                ? 'default'
                                : feature.priority === 'Should'
                                ? 'secondary'
                                : 'outline'
                            }
                            className="shrink-0"
                          >
                            {feature.priority}
                          </Badge>
                          <CollapsibleTrigger asChild>
                            <Button variant="ghost" size="sm" className="shrink-0">
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </Button>
                          </CollapsibleTrigger>
                        </div>
                        
                        <CollapsibleContent>
                          <div className="px-4 pb-4 space-y-4 border-t pt-4">
                            {/* Strategic Goal */}
                            <div className="space-y-2">
                              <div className="flex items-center gap-2 text-sm font-semibold">
                                <Target className="h-4 w-4 text-primary" />
                                Strategic Goal
                              </div>
                              <p className="text-sm text-muted-foreground pl-6">
                                {feature.strategicGoal}
                              </p>
                            </div>

                            {/* User Stories */}
                            <div className="space-y-2">
                              <div className="flex items-center gap-2 text-sm font-semibold">
                                <Users className="h-4 w-4 text-primary" />
                                User Stories
                              </div>
                              <ul className="space-y-1 pl-6">
                                {feature.userStories.map((story, idx) => (
                                  <li key={idx} className="text-sm text-muted-foreground">
                                    • {story}
                                  </li>
                                ))}
                              </ul>
                            </div>

                            {/* Success Metrics */}
                            <div className="space-y-2">
                              <div className="flex items-center gap-2 text-sm font-semibold">
                                <TrendingUp className="h-4 w-4 text-primary" />
                                Success Metrics
                              </div>
                              <ul className="space-y-1 pl-6">
                                {feature.successMetrics.map((metric, idx) => (
                                  <li key={idx} className="text-sm text-muted-foreground">
                                    • {metric}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </CollapsibleContent>
                      </div>
                    </Collapsible>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
