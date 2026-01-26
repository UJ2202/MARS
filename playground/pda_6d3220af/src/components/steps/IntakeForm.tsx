import { useState, useEffect } from 'react';
import type { IntakeFormData } from '../../types/discovery';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Spinner } from '@/components/ui/spinner';
import { getClientDetails } from '@/lib/llm-service';
import { toast } from 'sonner';
import { Sparkles } from 'lucide-react';

interface IntakeFormProps {
  initialData?: IntakeFormData;
  onSubmit: (data: IntakeFormData) => void;
}

const businessFunctions = [
  'Store Ops',
  'Supply Chain',
  'Merchandising',
  'E-commerce',
  'HR',
  'Finance',
  'Manufacturing',
  'Marketing',
];

const discoveryTypes = [
  'Problem',
  'Opportunity',
  'Pain Point',
  'Capability',
  'Open Discovery',
];

const outputOptions = [
  'Prototype Prompt',
  'Slides',
  'Opportunity Pack',
  'All',
];

export function IntakeForm({ initialData, onSubmit }: IntakeFormProps) {
  const [formData, setFormData] = useState<IntakeFormData>(
    initialData || {
      clientName: '',
      industry: '',
      subIndustry: '',
      clientContext: '',
      businessFunction: '',
      discoveryType: '',
      processType: 'new',
      existingFunctionality: '',
      problemKeywords: '',
      expectedOutput: ['All'],
    }
  );
  const [isLoadingClientDetails, setIsLoadingClientDetails] = useState(false);
  const [suggestedBusinessFunctions, setSuggestedBusinessFunctions] = useState<string[]>([]);

  // Debounced client name lookup
  useEffect(() => {
    if (!formData.clientName || formData.clientName.length < 3) {
      return;
    }

    const timeoutId = setTimeout(async () => {
      setIsLoadingClientDetails(true);
      try {
        const details = await getClientDetails(formData.clientName);
        
        if (details.industry || details.subIndustry) {
          const updates: Partial<IntakeFormData> = {};
          
          if (details.industry && !formData.industry) {
            updates.industry = details.industry;
          }
          if (details.subIndustry && !formData.subIndustry) {
            updates.subIndustry = details.subIndustry;
          }
          
          if (Object.keys(updates).length > 0) {
            updateFormData(updates);
            toast.success('Auto-populated industry details');
          }
          
          if (details.businessFunctions.length > 0) {
            setSuggestedBusinessFunctions(details.businessFunctions);
          }
        }
      } catch (error) {
        console.error('Error fetching client details:', error);
        toast.error('Could not auto-populate client details');
      } finally {
        setIsLoadingClientDetails(false);
      }
    }, 1000); // 1 second debounce

    return () => clearTimeout(timeoutId);
  }, [formData.clientName]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const updateFormData = (updates: Partial<IntakeFormData>) => {
    const newData = { ...formData, ...updates };
    setFormData(newData);
    onSubmit(newData); // Update parent state immediately
  };

  const toggleOutput = (output: string) => {
    let newOutput: string[];
    if (output === 'All') {
      newOutput = ['All'];
    } else {
      const filtered = formData.expectedOutput.filter((o) => o !== 'All');
      if (filtered.includes(output)) {
        newOutput = filtered.filter((o) => o !== output);
      } else {
        newOutput = [...filtered, output];
      }
    }
    updateFormData({ expectedOutput: newOutput });
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      <Card className="shadow-elegant">
        <CardHeader>
          <CardTitle className="text-3xl text-foreground">
            Discovery Intake
          </CardTitle>
          <CardDescription>
            Fill in the details to start your product discovery session
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="clientName">Client Name *</Label>
              <div className="relative">
                <Input
                  id="clientName"
                  value={formData.clientName}
                  onChange={(e) =>
                    updateFormData({ clientName: e.target.value })
                  }
                  required
                  placeholder="Enter client name"
                  className={isLoadingClientDetails ? 'pr-10' : ''}
                />
                {isLoadingClientDetails && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <Spinner className="h-4 w-4" />
                  </div>
                )}
              </div>
              {isLoadingClientDetails && (
                <p className="text-xs text-muted-foreground">
                  Looking up client details...
                </p>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="industry">Industry *</Label>
                <Input
                  id="industry"
                  value={formData.industry}
                  onChange={(e) =>
                    updateFormData({ industry: e.target.value })
                  }
                  required
                  placeholder="e.g., Retail"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="subIndustry">Sub-Industry *</Label>
                <Input
                  id="subIndustry"
                  value={formData.subIndustry}
                  onChange={(e) =>
                    updateFormData({ subIndustry: e.target.value })
                  }
                  required
                  placeholder="e.g., Fashion Retail"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="clientContext">Client Context *</Label>
              <Textarea
                id="clientContext"
                value={formData.clientContext}
                onChange={(e) =>
                  updateFormData({ clientContext: e.target.value })
                }
                required
                placeholder="Provide additional context about the client: company size, market position, digital maturity, strategic initiatives, current tech stack, organizational challenges, competitive landscape, etc."
                className="min-h-[120px]"
              />
              <p className="text-xs text-muted-foreground">
                This context will be used to enhance research, problem framing, opportunity creation, and solution design throughout the discovery process.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="businessFunction">Business Function *</Label>
              <Select
                value={formData.businessFunction}
                onValueChange={(value) =>
                  updateFormData({ businessFunction: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select business function" />
                </SelectTrigger>
                <SelectContent>
                  {suggestedBusinessFunctions.length > 0 && (
                    <>
                      <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                        Suggested for {formData.clientName}
                      </div>
                      {suggestedBusinessFunctions.map((func) => (
                        <SelectItem key={func} value={func} className="bg-accent/50">
                          <span className="flex items-center gap-2">
                            <Sparkles className="h-3.5 w-3.5 text-primary" />
                            {func}
                          </span>
                        </SelectItem>
                      ))}
                      <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground border-t">
                        All Functions
                      </div>
                    </>
                  )}
                  {businessFunctions
                    .filter((func) => !suggestedBusinessFunctions.includes(func))
                    .map((func) => (
                      <SelectItem key={func} value={func}>
                        {func}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="discoveryType">Type of Discovery *</Label>
              <Select
                value={formData.discoveryType}
                onValueChange={(value) =>
                  updateFormData({ discoveryType: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select discovery type" />
                </SelectTrigger>
                <SelectContent>
                  {discoveryTypes.map((type) => (
                    <SelectItem key={type} value={type}>
                      {type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="processType">Process Type *</Label>
              <Select
                value={formData.processType}
                onValueChange={(value: 'new' | 'existing') =>
                  updateFormData({ processType: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select process type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="new">New Process</SelectItem>
                  <SelectItem value="existing">Existing Process</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {formData.processType === 'existing' && (
              <div className="space-y-2">
                <Label htmlFor="existingFunctionality">Existing Functionality *</Label>
                <Textarea
                  id="existingFunctionality"
                  value={formData.existingFunctionality || ''}
                  onChange={(e) =>
                    updateFormData({ existingFunctionality: e.target.value })
                  }
                  required={formData.processType === 'existing'}
                  placeholder="Describe the existing functionality or process..."
                  className="min-h-[120px]"
                />
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="problemKeywords">Problem Keywords / Notes *</Label>
              <Textarea
                id="problemKeywords"
                value={formData.problemKeywords}
                onChange={(e) =>
                  updateFormData({ problemKeywords: e.target.value })
                }
                required
                placeholder="Describe the problem, pain points, or opportunity areas..."
                className="min-h-[120px]"
              />
            </div>

            <div className="space-y-2">
              <Label>Expected Output *</Label>
              <div className="space-y-2">
                {outputOptions.map((option) => (
                  <div key={option} className="flex items-center space-x-2">
                    <Checkbox
                      id={option}
                      checked={formData.expectedOutput.includes(option)}
                      onCheckedChange={() => toggleOutput(option)}
                    />
                    <Label
                      htmlFor={option}
                      className="text-sm font-normal cursor-pointer"
                    >
                      {option}
                    </Label>
                  </div>
                ))}
              </div>
            </div>

          </form>
        </CardContent>
      </Card>
    </div>
  );
}
