import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface StepNavigationProps {
  currentStep: number;
  totalSteps: number;
  onNext: () => void;
  onBack: () => void;
  canGoNext?: boolean;
  nextLabel?: string;
  isLoading?: boolean;
}

export function StepNavigation({
  currentStep,
  totalSteps,
  onNext,
  onBack,
  canGoNext = true,
  nextLabel = 'Next',
  isLoading = false,
}: StepNavigationProps) {
  return (
    <div className="flex items-center justify-between py-4 px-4">
      <div className="max-w-6xl mx-auto w-full flex items-center justify-between">
        <Button
          variant="outline"
          onClick={onBack}
          disabled={currentStep === 0 || isLoading}
        >
          <ChevronLeft className="w-4 h-4 mr-2" />
          Back
        </Button>

        <span className="text-sm text-muted-foreground">
          Step {currentStep + 1} of {totalSteps}
        </span>

        <Button
          onClick={onNext}
          disabled={!canGoNext || isLoading}
          className="bg-gradient-primary"
        >
          {nextLabel}
          <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}
