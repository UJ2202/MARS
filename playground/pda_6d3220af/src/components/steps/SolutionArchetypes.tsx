import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { RefreshCw, Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { OpportunityArea, SolutionArchetype, IntakeFormData } from '@/types/discovery';
import { generateSolutionArchetypes } from '@/lib/llm-service';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface SolutionArchetypesProps {
  opportunity: OpportunityArea;
  intakeData: IntakeFormData;
  initialData?: SolutionArchetype[];
  selectedId?: string;
  onComplete: (archetypes: SolutionArchetype[], selectedId: string) => void;
}

export function SolutionArchetypes({
  opportunity,
  intakeData,
  initialData,
  selectedId,
  onComplete,
}: SolutionArchetypesProps) {
  const [isLoading, setIsLoading] = useState(!initialData);
  const [archetypes, setArchetypes] = useState<SolutionArchetype[]>(initialData || []);
  const [selected, setSelected] = useState<string | null>(selectedId || null);

  useEffect(() => {
    if (!initialData) {
      loadArchetypes();
    }
  }, []);

  const loadArchetypes = async () => {
    setIsLoading(true);
    try {
      const result = await generateSolutionArchetypes(opportunity, intakeData);
      setArchetypes(result);
      toast.success('Solution archetypes generated successfully');
    } catch (error) {
      toast.error('Failed to generate solution archetypes');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelect = (id: string) => {
    setSelected(id);
    onComplete(archetypes, id);
  };

  const handleRegenerate = () => {
    loadArchetypes();
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Spinner className="w-12 h-12 text-primary mb-4" />
        <h3 className="text-xl font-semibold mb-2">Creating Solution Archetypes</h3>
        <p className="text-muted-foreground">Designing potential solutions...</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-foreground">
            Solution Archetypes
          </h2>
          <p className="text-muted-foreground mt-1">
            Select the solution approach that fits best
          </p>
        </div>
        <Button variant="outline" onClick={handleRegenerate}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Regenerate
        </Button>
      </div>

      <div className="space-y-6">
        {archetypes.map((archetype) => {
          const isSelected = selected === archetype.id;

          return (
            <Card
              key={archetype.id}
              className={cn(
                'cursor-pointer transition-all duration-300 hover:shadow-elegant',
                isSelected
                  ? 'ring-2 ring-primary shadow-glow'
                  : 'hover:border-primary/50'
              )}
              onClick={() => handleSelect(archetype.id)}
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <Sparkles className="w-8 h-8 text-primary mb-2" />
                  {isSelected && <Badge className="bg-success">Selected</Badge>}
                </div>
                <CardTitle className="text-2xl">{archetype.title}</CardTitle>
                <CardDescription className="text-base">{archetype.summary}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="font-semibold text-sm mb-2">Target Personas</h4>
                    <ul className="space-y-1">
                      {archetype.personas.map((persona, idx) => (
                        <li key={idx} className="text-sm text-muted-foreground flex items-start">
                          <span className="text-primary mr-2">•</span>
                          {persona}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h4 className="font-semibold text-sm mb-2">Expected Benefits</h4>
                    <ul className="space-y-1">
                      {archetype.benefits.map((benefit, idx) => (
                        <li key={idx} className="text-sm text-muted-foreground flex items-start">
                          <span className="text-success mr-2">✓</span>
                          {benefit}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                {archetype.references && archetype.references.length > 0 && (
                  <div>
                    <h4 className="font-semibold text-sm mb-2">References</h4>
                    <ul className="space-y-1">
                      {archetype.references.map((ref, idx) => (
                        <li key={idx} className="text-xs text-muted-foreground">
                          {ref.startsWith('http') ? (
                            <a
                              href={ref}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary hover:underline"
                            >
                              {ref}
                            </a>
                          ) : (
                            <span>{ref}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
