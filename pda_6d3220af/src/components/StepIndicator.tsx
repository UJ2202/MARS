import { CheckCircle2, Circle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StepIndicatorProps {
  currentStep: number;
  totalSteps: number;
  stepLabels: string[];
}

export function StepIndicator({ currentStep, totalSteps, stepLabels }: StepIndicatorProps) {
  return (
    <div className="w-full py-6 px-4 bg-card border-b">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between relative">
          {/* Progress bar background */}
          <div 
            className="absolute top-4 h-0.5 bg-border" 
            style={{ 
              left: '32px',
              right: '32px',
              zIndex: 0 
            }} 
          />
          
          {/* Active progress bar */}
          <div
            className="absolute top-4 h-0.5 bg-primary transition-all duration-500"
            style={{
              left: '32px',
              width: `calc(${(currentStep / (totalSteps - 1)) * 100}% - 32px)`,
              zIndex: 1,
            }}
          />
          
          {/* Step markers */}
          {stepLabels.map((label, index) => (
            <div
              key={index}
              className="flex flex-col items-center relative"
              style={{ zIndex: 2 }}
            >
              <div
                className={cn(
                  'flex items-center justify-center w-8 h-8 rounded-full border-2 transition-all duration-300 bg-background',
                  index < currentStep
                    ? 'border-success bg-success'
                    : index === currentStep
                    ? 'border-primary bg-primary shadow-glow'
                    : 'border-border'
                )}
              >
                {index < currentStep ? (
                  <CheckCircle2 className="w-5 h-5 text-success-foreground" />
                ) : (
                  <Circle
                    className={cn(
                      'w-5 h-5',
                      index === currentStep ? 'text-primary-foreground' : 'text-muted-foreground'
                    )}
                  />
                )}
              </div>
              <span
                className={cn(
                  'mt-2 text-xs font-medium text-center max-w-[100px]',
                  index <= currentStep ? 'text-foreground' : 'text-muted-foreground'
                )}
              >
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
