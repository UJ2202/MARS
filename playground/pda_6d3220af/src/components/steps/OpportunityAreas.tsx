import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { RefreshCw, TrendingUp, Zap, Users, Shield } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { IntakeFormData, LLMResponse, OpportunityArea } from '@/types/discovery';
import { generateOpportunities } from '@/lib/llm-service';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface OpportunityAreasProps {
  intakeData: IntakeFormData;
  problemDefinition: LLMResponse;
  initialData?: OpportunityArea[];
  selectedId?: string;
  onComplete: (opportunities: OpportunityArea[], selectedId: string) => void;
}

const valueIcons = {
  Revenue: TrendingUp,
  Efficiency: Zap,
  Experience: Users,
  Risk: Shield,
};

export function OpportunityAreas({
  intakeData,
  problemDefinition,
  initialData,
  selectedId,
  onComplete,
}: OpportunityAreasProps) {
  const [isLoading, setIsLoading] = useState(!initialData);
  const [opportunities, setOpportunities] = useState<OpportunityArea[]>(initialData || []);
  const [selected, setSelected] = useState<string | null>(selectedId || null);

  useEffect(() => {
    if (!initialData) {
      loadOpportunities();
    }
  }, []);

  const loadOpportunities = async () => {
    setIsLoading(true);
    try {
      const result = await generateOpportunities(intakeData, problemDefinition.content);
      setOpportunities(result);
      toast.success('Opportunity areas generated successfully');
    } catch (error) {
      toast.error('Failed to generate opportunities');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelect = (id: string) => {
    setSelected(id);
    onComplete(opportunities, id);
  };

  const handleRegenerate = () => {
    loadOpportunities();
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Spinner className="w-12 h-12 text-primary mb-4" />
        <h3 className="text-xl font-semibold mb-2">Identifying Opportunities</h3>
        <p className="text-muted-foreground">Analyzing potential value areas...</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-foreground">
            Opportunity Areas
          </h2>
          <p className="text-muted-foreground mt-1">
            Select the opportunity you'd like to explore
          </p>
        </div>
        <Button variant="outline" onClick={handleRegenerate}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Regenerate
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {opportunities.map((opp) => {
          const Icon = valueIcons[opp.valueCategory];
          const isSelected = selected === opp.id;

          return (
            <Card
              key={opp.id}
              className={cn(
                'cursor-pointer transition-all duration-300 hover:shadow-elegant',
                isSelected
                  ? 'ring-2 ring-primary shadow-glow'
                  : 'hover:border-primary/50'
              )}
              onClick={() => handleSelect(opp.id)}
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <Icon className="w-8 h-8 text-primary mb-2" />
                  <Badge variant={isSelected ? 'default' : 'outline'}>
                    {opp.valueCategory}
                  </Badge>
                </div>
                <CardTitle className="text-xl">{opp.title}</CardTitle>
                <CardDescription>{opp.explanation}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <h4 className="font-semibold text-sm mb-2">KPIs Influenced</h4>
                  <ul className="space-y-1">
                    {opp.kpis.map((kpi, idx) => (
                      <li key={idx} className="text-sm text-muted-foreground flex items-start">
                        <span className="text-primary mr-2">•</span>
                        {kpi}
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold text-sm mb-2">Why Now</h4>
                  <p className="text-sm text-muted-foreground">{opp.whyNow}</p>
                </div>

                {isSelected && (
                  <Badge className="w-full justify-center bg-success">
                    Selected
                  </Badge>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
