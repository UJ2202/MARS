import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { RefreshCw, Lightbulb, TrendingUp, Users, Target } from 'lucide-react';
import { EditableContent } from '../EditableContent';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown } from 'lucide-react';
import { IntakeFormData, ResearchSummary as ResearchSummaryType } from '@/types/discovery';
import { generateResearchSummary } from '@/lib/llm-service';
import { toast } from 'sonner';
import { MarkdownRenderer } from '../MarkdownRenderer';

interface ResearchSummaryProps {
  intakeData: IntakeFormData;
  initialData?: ResearchSummaryType;
  onComplete: (data: ResearchSummaryType) => void;
}

export function ResearchSummary({ intakeData, initialData, onComplete }: ResearchSummaryProps) {
  const [isLoading, setIsLoading] = useState(!initialData);
  const [data, setData] = useState<ResearchSummaryType | null>(initialData || null);
  const [sectionsOpen, setSectionsOpen] = useState<{ [key: string]: boolean }>({
    marketTrends: true,
    competitorMoves: true,
    industryPainPoints: true,
    workshopAngles: true,
    references: false,
  });

  useEffect(() => {
    if (!initialData) {
      loadResearch();
    }
  }, []);

  const loadResearch = async () => {
    setIsLoading(true);
    try {
      const result = await generateResearchSummary(intakeData);
      setData(result);
      onComplete(result);
      toast.success('Research summary generated successfully');
    } catch (error) {
      toast.error('Failed to generate research summary');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegenerate = () => {
    loadResearch();
  };

  const handleEdit = (field: keyof ResearchSummaryType, newContent: string) => {
    if (data) {
      // Convert string back to array (split by lines that start with "- ")
      const arrayValue = newContent.split('\n').filter(line => line.trim());
      const updated = { ...data, [field]: arrayValue };
      setData(updated);
      onComplete(updated);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Spinner className="w-12 h-12 text-primary mb-4" />
        <h3 className="text-xl font-semibold mb-2">Generating Research Summary</h3>
        <p className="text-muted-foreground">Analyzing market trends and industry insights...</p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const sections = [
    { 
      key: 'marketTrends', 
      title: 'Market Trends', 
      description: 'Key market trends and dynamics',
      icon: TrendingUp,
      color: 'text-blue-500'
    },
    { 
      key: 'competitorMoves', 
      title: 'Competitor Moves', 
      description: 'Notable competitor activities and strategies',
      icon: Users,
      color: 'text-purple-500'
    },
    { 
      key: 'industryPainPoints', 
      title: 'Industry Pain Points', 
      description: 'Critical challenges in this space',
      icon: Target,
      color: 'text-red-500'
    },
    { 
      key: 'workshopAngles', 
      title: 'Workshop Angles', 
      description: 'Strategic approaches for discovery',
      icon: Lightbulb,
      color: 'text-amber-500'
    },
  ];

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-3xl font-bold text-foreground">
            Research Summary
          </h2>
          <p className="text-muted-foreground mt-1">
            AI-generated insights for {intakeData.clientName}
          </p>
        </div>
        <Button variant="outline" onClick={handleRegenerate}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Regenerate
        </Button>
      </div>

      <div className="grid gap-4">
        {sections.map(({ key, title, description, icon: Icon, color }) => (
          <Card key={key} className="shadow-elegant border-l-4 hover:shadow-lg transition-all duration-300">
            <Collapsible
              open={sectionsOpen[key]}
              onOpenChange={(open) => setSectionsOpen({ ...sectionsOpen, [key]: open })}
            >
              <CardHeader className="cursor-pointer pb-3 hover:bg-accent/5 transition-colors">
                <CollapsibleTrigger className="flex items-center justify-between w-full">
                  <div className="flex items-start gap-3">
                    <div className={`mt-1 ${color}`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="text-left">
                      <CardTitle className="text-lg font-semibold">{title}</CardTitle>
                      <CardDescription className="text-xs mt-1">{description}</CardDescription>
                    </div>
                  </div>
                  <ChevronDown
                    className={`w-5 h-5 transition-transform flex-shrink-0 text-muted-foreground ${
                      sectionsOpen[key] ? 'transform rotate-180' : ''
                    }`}
                  />
                </CollapsibleTrigger>
              </CardHeader>
              <CollapsibleContent>
                <CardContent className="pt-0 pb-6">
                  <div className="bg-accent/5 rounded-lg p-4">
                    {Array.isArray(data[key as keyof ResearchSummaryType]) ? (
                      <div className="space-y-3">
                        {(data[key as keyof ResearchSummaryType] as string[])?.map((item, idx) => (
                          <div key={idx} className="flex gap-3 group">
                            <span className="text-primary font-semibold text-sm mt-0.5 flex-shrink-0">
                              {idx + 1}.
                            </span>
                            <div className="flex-1">
                              <MarkdownRenderer content={item} className="text-sm" />
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EditableContent
                        content={(data[key as keyof ResearchSummaryType] as string) || ''}
                        onSave={(newContent) => handleEdit(key as keyof ResearchSummaryType, newContent)}
                      />
                    )}
                  </div>
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        ))}

        {data.references && data.references.length > 0 && (
          <Card className="shadow-elegant border-l-4 border-l-green-500 bg-gradient-to-r from-green-50/50 to-transparent dark:from-green-950/20">
            <Collapsible
              open={sectionsOpen.references}
              onOpenChange={(open) => setSectionsOpen({ ...sectionsOpen, references: open })}
            >
              <CardHeader className="cursor-pointer pb-3 hover:bg-accent/5 transition-colors">
                <CollapsibleTrigger className="flex items-center justify-between w-full">
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">📚</span>
                    <div className="text-left">
                      <CardTitle className="text-lg font-semibold">References & Sources</CardTitle>
                      <CardDescription className="text-xs mt-1">Citations and authoritative sources</CardDescription>
                    </div>
                  </div>
                  <ChevronDown
                    className={`w-5 h-5 transition-transform text-muted-foreground ${
                      sectionsOpen.references ? 'transform rotate-180' : ''
                    }`}
                  />
                </CollapsibleTrigger>
              </CardHeader>
              <CollapsibleContent>
                <CardContent className="pt-0 pb-6">
                  <div className="bg-background/50 rounded-lg p-4">
                    <ul className="space-y-2.5">
                      {data.references.map((ref, idx) => (
                        <li key={idx} className="text-sm flex gap-3 hover:bg-accent/10 p-2 rounded transition-colors">
                          <span className="font-semibold text-green-600 dark:text-green-400 flex-shrink-0">[{idx + 1}]</span>
                          <MarkdownRenderer content={ref} className="text-muted-foreground flex-1" />
                        </li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        )}
      </div>
    </div>
  );
}
