import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { RefreshCw, Copy, Check, ChevronRight } from 'lucide-react';
import type { Feature, IntakeFormData, LLMResponse, OpportunityArea, SolutionArchetype } from '@/types/discovery';
import { generateSlideContent } from '@/lib/llm-service';
import { toast } from 'sonner';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';

interface SlideGeneratorProps {
  intakeData: IntakeFormData;
  research: LLMResponse;
  problem: LLMResponse;
  opportunity: OpportunityArea;
  archetype: SolutionArchetype;
  features: Feature[];
  initialData?: string;
  onComplete: (content: string) => void;
}

interface SlideSection {
  title: string;
  content: string;
  number: number;
}

export function SlideGenerator({
  intakeData,
  research,
  problem,
  opportunity,
  archetype,
  features,
  initialData,
  onComplete,
}: SlideGeneratorProps) {
  const [isLoading, setIsLoading] = useState(!initialData);
  const [content, setContent] = useState(initialData || '');
  const [slides, setSlides] = useState<SlideSection[]>([]);
  const [copied, setCopied] = useState(false);

  const selectedFeatures = features.filter((f) => f.selected);

  // Parse markdown content into slide sections
  const parseSlides = (markdown: string): SlideSection[] => {
    try {
      const sections: SlideSection[] = [];
      const lines = markdown.split('\n');
      let currentSlide: SlideSection | null = null;
      let slideNumber = 1;

      for (const line of lines) {
        // Match slide titles (## Slide X: Title or ## Title)
        const slideMatch = line.match(/^##\s+(?:Slide\s+\d+:\s+)?(.+)$/);
        
        if (slideMatch) {
          if (currentSlide) {
            sections.push(currentSlide);
          }
          currentSlide = {
            title: slideMatch[1].trim(),
            content: '',
            number: slideNumber++,
          };
        } else if (currentSlide && line.trim()) {
          currentSlide.content += line + '\n';
        }
      }

      if (currentSlide) {
        sections.push(currentSlide);
      }

      return sections;
    } catch (error) {
      console.error('Failed to parse slides:', error);
      return [];
    }
  };

  useEffect(() => {
    if (!initialData) {
      loadSlideContent();
    } else {
      setSlides(parseSlides(initialData));
    }
  }, []);

  useEffect(() => {
    if (content) {
      setSlides(parseSlides(content));
    }
  }, [content]);

  const loadSlideContent = async () => {
    setIsLoading(true);
    try {
      const result = await generateSlideContent(
        intakeData,
        research.content,
        problem.content,
        opportunity,
        archetype,
        selectedFeatures
      );
      setContent(result);
      onComplete(result);
      toast.success('Slide content generated successfully');
    } catch (error) {
      toast.error('Failed to generate slide content');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegenerate = () => {
    loadSlideContent();
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      toast.success('Copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      toast.error('Failed to copy');
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Spinner className="w-12 h-12 text-primary mb-4" />
        <h3 className="text-xl font-semibold mb-2">Generating Slide Content</h3>
        <p className="text-muted-foreground">Creating presentation-ready content...</p>
      </div>
    );
  }

  const handleCopySlide = async (slideContent: string, slideTitle: string) => {
    try {
      await navigator.clipboard.writeText(slideContent);
      toast.success(`Copied "${slideTitle}" to clipboard`);
    } catch (error) {
      toast.error('Failed to copy');
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-foreground">
            Presentation Slides
          </h2>
          <p className="text-muted-foreground mt-1">
            {slides.length} slides ready for your presentation
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleCopy}>
            {copied ? (
              <Check className="w-4 h-4 mr-2" />
            ) : (
              <Copy className="w-4 h-4 mr-2" />
            )}
            Copy All
          </Button>
          <Button variant="outline" onClick={handleRegenerate}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Regenerate
          </Button>
        </div>
      </div>

      <div className="grid gap-6">
        {slides.map((slide, index) => (
          <Card 
            key={index} 
            className="shadow-elegant hover:shadow-2xl transition-all duration-300 border-l-4 border-l-primary bg-gradient-to-br from-card to-card/50"
          >
            <CardHeader className="pb-4">
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4 flex-1">
                  <div className="flex items-center justify-center w-12 h-12 rounded-full bg-primary/10 text-primary font-bold text-lg shrink-0">
                    {slide.number}
                  </div>
                  <div className="flex-1">
                    <CardTitle className="text-2xl mb-2 flex items-center gap-2">
                      {slide.title}
                    </CardTitle>
                    <CardDescription className="text-sm">
                      Slide {slide.number} of {slides.length}
                    </CardDescription>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleCopySlide(slide.content, slide.title)}
                  className="shrink-0"
                >
                  <Copy className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="bg-muted/30 rounded-lg p-6 border border-border/50">
                <MarkdownRenderer content={slide.content.trim()} />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {slides.length === 0 && content && (
        <Card className="shadow-elegant border-l-4 border-l-warning">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <span className="text-warning">⚠</span> Presentation Content (Raw Format)
                </CardTitle>
                <CardDescription>
                  Slide parsing unavailable - showing raw LLM response. You can still copy and format manually.
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopy}
              >
                {copied ? <Check className="w-4 h-4 mr-2" /> : <Copy className="w-4 h-4 mr-2" />}
                Copy
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="bg-muted/50 p-6 rounded-lg overflow-auto max-h-[700px] border border-border">
              <MarkdownRenderer content={content} />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
