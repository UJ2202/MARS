import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Copy, Check, Download, RotateCcw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { DiscoveryState } from '@/types/discovery';
import { toast } from 'sonner';

interface SummaryProps {
  state: DiscoveryState;
  onReset: () => void;
}

export function Summary({ state, onReset }: SummaryProps) {
  const [copied, setCopied] = useState<string | null>(null);

  const handleCopy = async (type: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(type);
      toast.success('Copied to clipboard');
      setTimeout(() => setCopied(null), 2000);
    } catch (error) {
      toast.error('Failed to copy');
    }
  };

  const generateFullSummary = () => {
    const selectedOpportunity = state.opportunities.find((o) => o.id === state.selectedOpportunity);
    const selectedArchetype = state.solutionArchetypes.find((a) => a.id === state.selectedArchetype);
    const selectedFeatures = state.features.filter((f) => f.selected);

    return `# Product Discovery Summary

## Client Information
- **Client:** ${state.intakeData?.clientName}
- **Industry:** ${state.intakeData?.industry} - ${state.intakeData?.subIndustry}
- **Business Function:** ${state.intakeData?.businessFunction}
- **Discovery Type:** ${state.intakeData?.discoveryType}

## Problem Statement
${state.problemDefinition?.content}

## Selected Opportunity
**${selectedOpportunity?.title}**
${selectedOpportunity?.explanation}
- **Value Category:** ${selectedOpportunity?.valueCategory}
- **Why Now:** ${selectedOpportunity?.whyNow}

## Solution Archetype
**${selectedArchetype?.title}**
${selectedArchetype?.summary}

## Selected Features (${selectedFeatures?.length || 0})
${selectedFeatures?.map((f) => `- ${f.name} (${f.priority})`)?.join('\n') || 'No features selected'}

## Prototype Prompts
### Lovable
${state.prompts?.lovable}

### Google AI Studio
${state.prompts?.googleAI}

### General LLM
${state.prompts?.general}

## Presentation Slides
${state.slideContent}
`;
  };

  const selectedOpportunity = state.opportunities.find((o) => o.id === state.selectedOpportunity);
  const selectedArchetype = state.solutionArchetypes.find((a) => a.id === state.selectedArchetype);
  const selectedFeatures = state.features.filter((f) => f.selected);

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-foreground">
            Discovery Complete!
          </h2>
          <p className="text-muted-foreground mt-1">
            Here's your comprehensive product discovery summary
          </p>
        </div>
        <Button variant="outline" onClick={onReset}>
          <RotateCcw className="w-4 h-4 mr-2" />
          New Session
        </Button>
      </div>

      <Card className="shadow-elegant">
        <CardHeader>
          <CardTitle>Session Overview</CardTitle>
          <CardDescription>Key details from your discovery process</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <h3 className="font-semibold mb-2">Client</h3>
            <p className="text-muted-foreground">{state.intakeData?.clientName}</p>
            <p className="text-sm text-muted-foreground">
              {state.intakeData?.industry} - {state.intakeData?.subIndustry} •{' '}
              {state.intakeData?.businessFunction}
            </p>
          </div>

          <Separator />

          <div>
            <h3 className="font-semibold mb-2">Selected Opportunity</h3>
            <div className="flex items-start gap-2">
              <Badge>{selectedOpportunity?.valueCategory}</Badge>
              <p className="text-sm flex-1">{selectedOpportunity?.title}</p>
            </div>
          </div>

          <Separator />

          <div>
            <h3 className="font-semibold mb-2">Solution Archetype</h3>
            <p className="text-sm">{selectedArchetype?.title}</p>
          </div>

          <Separator />

          <div>
            <h3 className="font-semibold mb-2">Features</h3>
            <p className="text-sm text-muted-foreground">
              {selectedFeatures.length} features selected
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="shadow-elegant">
          <CardHeader>
            <CardTitle className="text-lg">Prototype Prompts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => handleCopy('lovable', state.prompts?.lovable || '')}
            >
              {copied === 'lovable' ? (
                <Check className="w-4 h-4 mr-2" />
              ) : (
                <Copy className="w-4 h-4 mr-2" />
              )}
              Copy Lovable Prompt
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => handleCopy('googleAI', state.prompts?.googleAI || '')}
            >
              {copied === 'googleAI' ? (
                <Check className="w-4 h-4 mr-2" />
              ) : (
                <Copy className="w-4 h-4 mr-2" />
              )}
              Copy Google AI Prompt
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => handleCopy('general', state.prompts?.general || '')}
            >
              {copied === 'general' ? (
                <Check className="w-4 h-4 mr-2" />
              ) : (
                <Copy className="w-4 h-4 mr-2" />
              )}
              Copy General Prompt
            </Button>
          </CardContent>
        </Card>

        <Card className="shadow-elegant">
          <CardHeader>
            <CardTitle className="text-lg">Export Options</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => handleCopy('slides', state.slideContent || '')}
            >
              {copied === 'slides' ? (
                <Check className="w-4 h-4 mr-2" />
              ) : (
                <Copy className="w-4 h-4 mr-2" />
              )}
              Copy Slide Content
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => handleCopy('full', generateFullSummary())}
            >
              {copied === 'full' ? (
                <Check className="w-4 h-4 mr-2" />
              ) : (
                <Copy className="w-4 h-4 mr-2" />
              )}
              Copy Full Summary
            </Button>
            <Button
              className="w-full justify-start bg-gradient-primary"
              onClick={() => {
                const blob = new Blob([generateFullSummary()], { type: 'text/markdown' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `discovery-${state.intakeData?.clientName?.replace(/\s+/g, '-').toLowerCase()}.md`;
                a.click();
                toast.success('Downloaded summary');
              }}
            >
              <Download className="w-4 h-4 mr-2" />
              Download as Markdown
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
