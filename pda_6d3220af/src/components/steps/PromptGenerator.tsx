import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { RefreshCw, Copy, Check } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Feature, IntakeFormData, OpportunityArea, SolutionArchetype } from '@/types/discovery';
import { generatePrompts } from '@/lib/llm-service';
import { toast } from 'sonner';

interface PromptGeneratorProps {
  intakeData: IntakeFormData;
  opportunity: OpportunityArea;
  archetype: SolutionArchetype;
  features: Feature[];
  initialData?: { lovable: string; googleAI: string; general: string };
  onComplete: (prompts: { lovable: string; googleAI: string; general: string }) => void;
}

export function PromptGenerator({
  intakeData,
  opportunity,
  archetype,
  features,
  initialData,
  onComplete,
}: PromptGeneratorProps) {
  const [isLoading, setIsLoading] = useState(!initialData);
  const [prompts, setPrompts] = useState(initialData || { lovable: '', googleAI: '', general: '' });
  const [copiedPrompt, setCopiedPrompt] = useState<string | null>(null);

  const selectedFeatures = features.filter((f) => f.selected);

  useEffect(() => {
    if (!initialData) {
      loadPrompts();
    }
  }, []);

  const loadPrompts = async () => {
    setIsLoading(true);
    try {
      const result = await generatePrompts(intakeData, opportunity, archetype, selectedFeatures);
      
      // Check if parsing failed (all prompts are "Failed to generate")
      if (result.lovable === 'Failed to generate' && result.googleAI === 'Failed to generate' && result.general === 'Failed to generate') {
        toast.warning('Prompts generated but may need formatting');
      } else {
        toast.success('Prompts generated successfully');
      }
      
      setPrompts(result);
      onComplete(result);
    } catch (error) {
      toast.error('Failed to generate prompts');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegenerate = () => {
    loadPrompts();
  };

  const handleCopy = async (type: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedPrompt(type);
      toast.success('Copied to clipboard');
      setTimeout(() => setCopiedPrompt(null), 2000);
    } catch (error) {
      toast.error('Failed to copy');
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Spinner className="w-12 h-12 text-primary mb-4" />
        <h3 className="text-xl font-semibold mb-2">Generating Prompts</h3>
        <p className="text-muted-foreground">Creating platform-specific prompts...</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-foreground">
            Prototype Prompts
          </h2>
          <p className="text-muted-foreground mt-1">
            Ready-to-use prompts for different platforms
          </p>
        </div>
        <Button variant="outline" onClick={handleRegenerate}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Regenerate
        </Button>
      </div>

      <Tabs defaultValue="lovable" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="lovable">Lovable</TabsTrigger>
          <TabsTrigger value="googleAI">Google AI Studio</TabsTrigger>
          <TabsTrigger value="general">General LLM</TabsTrigger>
        </TabsList>

        <TabsContent value="lovable">
          <Card className="shadow-elegant">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Lovable App Prompt</CardTitle>
                  <CardDescription>
                    Optimized for Lovable's AI app builder
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopy('lovable', prompts.lovable)}
                >
                  {copiedPrompt === 'lovable' ? (
                    <Check className="w-4 h-4 mr-2" />
                  ) : (
                    <Copy className="w-4 h-4 mr-2" />
                  )}
                  Copy
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <pre className="whitespace-pre-wrap text-sm bg-muted p-4 rounded-lg overflow-auto max-h-[600px]">
                {prompts.lovable}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="googleAI">
          <Card className="shadow-elegant">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Google AI Studio Prompt</CardTitle>
                  <CardDescription>
                    Optimized for Google's Gemini model
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopy('googleAI', prompts.googleAI)}
                >
                  {copiedPrompt === 'googleAI' ? (
                    <Check className="w-4 h-4 mr-2" />
                  ) : (
                    <Copy className="w-4 h-4 mr-2" />
                  )}
                  Copy
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <pre className="whitespace-pre-wrap text-sm bg-muted p-4 rounded-lg overflow-auto max-h-[600px]">
                {prompts.googleAI}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="general">
          <Card className="shadow-elegant">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>General LLM Prompt</CardTitle>
                  <CardDescription>
                    Works with any LLM platform
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopy('general', prompts.general)}
                >
                  {copiedPrompt === 'general' ? (
                    <Check className="w-4 h-4 mr-2" />
                  ) : (
                    <Copy className="w-4 h-4 mr-2" />
                  )}
                  Copy
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <pre className="whitespace-pre-wrap text-sm bg-muted p-4 rounded-lg overflow-auto max-h-[600px]">
                {prompts.general}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
