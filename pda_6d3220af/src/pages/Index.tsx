import { useState, useEffect } from 'react';
import type { DiscoveryState, IntakeFormData, ResearchSummary, ProblemDefinition, OpportunityArea, SolutionArchetype, Feature } from '@/types/discovery';
import { StepIndicator } from '@/components/StepIndicator';
import { StepNavigation } from '@/components/StepNavigation';
import { IntakeForm } from '@/components/steps/IntakeForm';
import { ResearchSummary as ResearchSummaryComponent } from '@/components/steps/ResearchSummary';
import { ProblemDefinition as ProblemDefinitionComponent } from '@/components/steps/ProblemDefinition';
import { OpportunityAreas } from '@/components/steps/OpportunityAreas';
import { SolutionArchetypes } from '@/components/steps/SolutionArchetypes';
import { FeatureSetBuilder } from '@/components/steps/FeatureSetBuilder';
import { PromptGenerator } from '@/components/steps/PromptGenerator';
import { SlideGenerator } from '@/components/steps/SlideGenerator';
import { Summary } from '@/components/steps/Summary';

const STEP_LABELS = [
  'Intake',
  'Research',
  'Problem',
  'Opportunity',
  'Solution',
  'Features',
  'Prompts',
  'Slides',
  'Summary',
];

const STORAGE_KEY = 'discovery-state';

export default function Index() {
  const [state, setState] = useState<DiscoveryState>(() => {
    // Load from localStorage if available
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.error('Failed to load saved state:', e);
      }
    }
    return {
      currentStep: 0,
      intakeData: null,
      researchSummary: null,
      problemDefinition: null,
      opportunities: [],
      selectedOpportunity: null,
      solutionArchetypes: [],
      selectedArchetype: null,
      features: [],
      selectedSolution: null,
      prompts: {},
      slideContent: null,
    };
  });

  // Auto-save to localStorage
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const handleNext = () => {
    if (canGoNext()) {
      setState({ ...state, currentStep: state.currentStep + 1 });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleBack = () => {
    setState({ ...state, currentStep: Math.max(0, state.currentStep - 1) });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleReset = () => {
    localStorage.removeItem(STORAGE_KEY);
    setState({
      currentStep: 0,
      intakeData: null,
      researchSummary: null,
      problemDefinition: null,
      opportunities: [],
      selectedOpportunity: null,
      solutionArchetypes: [],
      selectedArchetype: null,
      features: [],
      selectedSolution: null,
      prompts: {},
      slideContent: null,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const canGoNext = (): boolean => {
    switch (state.currentStep) {
      case 0:
        return !!(
          state.intakeData &&
          state.intakeData.clientName &&
          state.intakeData.industry &&
          state.intakeData.subIndustry &&
          state.intakeData.clientContext &&
          state.intakeData.businessFunction &&
          state.intakeData.discoveryType &&
          state.intakeData.problemKeywords &&
          state.intakeData.expectedOutput.length > 0
        );
      case 1:
        return !!state.researchSummary;
      case 2:
        return !!state.problemDefinition;
      case 3:
        return !!state.selectedOpportunity;
      case 4:
        return !!state.selectedArchetype;
      case 5:
        return state.features.filter((f) => f.selected).length > 0;
      case 6:
        return !!state.prompts?.lovable;
      case 7:
        return !!state.slideContent;
      case 8:
        return false; // Last step
      default:
        return false;
    }
  };

  const renderStep = () => {
    switch (state.currentStep) {
      case 0:
        return (
          <IntakeForm
            initialData={state.intakeData || undefined}
            onSubmit={(data: IntakeFormData) => {
              setState({ ...state, intakeData: data });
            }}
          />
        );
      case 1:
        return state.intakeData ? (
          <ResearchSummaryComponent
            intakeData={state.intakeData}
            initialData={state.researchSummary || undefined}
            onComplete={(data: ResearchSummary) => {
              setState({ ...state, researchSummary: data });
            }}
          />
        ) : null;
      case 2:
        return state.intakeData && state.researchSummary ? (
          <ProblemDefinitionComponent
            intakeData={state.intakeData}
            researchSummary={state.researchSummary}
            initialData={state.problemDefinition || undefined}
            onComplete={(data: ProblemDefinition) => {
              setState({ ...state, problemDefinition: data });
            }}
          />
        ) : null;
      case 3:
        return state.intakeData && state.problemDefinition ? (
          <OpportunityAreas
            intakeData={state.intakeData}
            problemDefinition={state.problemDefinition}
            initialData={state.opportunities.length > 0 ? state.opportunities : undefined}
            selectedId={state.selectedOpportunity || undefined}
            onComplete={(opportunities: OpportunityArea[], selectedId: string) => {
              setState({ ...state, opportunities, selectedOpportunity: selectedId });
            }}
          />
        ) : null;
      case 4:
        const selectedOpp = state.opportunities.find((o) => o.id === state.selectedOpportunity);
        return selectedOpp && state.intakeData ? (
          <SolutionArchetypes
            opportunity={selectedOpp}
            intakeData={state.intakeData}
            initialData={state.solutionArchetypes.length > 0 ? state.solutionArchetypes : undefined}
            selectedId={state.selectedArchetype || undefined}
            onComplete={(archetypes: SolutionArchetype[], selectedId: string) => {
              setState({ ...state, solutionArchetypes: archetypes, selectedArchetype: selectedId });
            }}
          />
        ) : null;
      case 5:
        const selectedArch = state.solutionArchetypes.find((a) => a.id === state.selectedArchetype);
        const selectedOpp5 = state.opportunities.find((o) => o.id === state.selectedOpportunity);
        return selectedArch && selectedOpp5 && state.intakeData ? (
          <FeatureSetBuilder
            archetype={selectedArch}
            opportunity={selectedOpp5}
            intakeData={state.intakeData}
            initialData={state.features.length > 0 ? state.features : undefined}
            onComplete={(features: Feature[]) => {
              setState({ ...state, features });
            }}
          />
        ) : null;
      case 6:
        const selectedArch6 = state.solutionArchetypes.find((a) => a.id === state.selectedArchetype);
        const selectedOpp6 = state.opportunities.find((o) => o.id === state.selectedOpportunity);
        return state.intakeData && selectedOpp6 && selectedArch6 ? (
          <PromptGenerator
            intakeData={state.intakeData}
            opportunity={selectedOpp6}
            archetype={selectedArch6}
            features={state.features}
            initialData={state.prompts?.lovable ? state.prompts : undefined}
            onComplete={(prompts) => {
              setState({ ...state, prompts });
            }}
          />
        ) : null;
      case 7:
        const selectedArch7 = state.solutionArchetypes.find((a) => a.id === state.selectedArchetype);
        const selectedOpp7 = state.opportunities.find((o) => o.id === state.selectedOpportunity);
        return state.intakeData && state.researchSummary && state.problemDefinition && selectedOpp7 && selectedArch7 ? (
          <SlideGenerator
            intakeData={state.intakeData}
            research={state.researchSummary}
            problem={state.problemDefinition}
            opportunity={selectedOpp7}
            archetype={selectedArch7}
            features={state.features}
            initialData={state.slideContent || undefined}
            onComplete={(content: string) => {
              setState({ ...state, slideContent: content });
            }}
          />
        ) : null;
      case 8:
        return <Summary state={state} onReset={handleReset} />;
      default:
        return null;
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gradient-subtle">
      {/* Header */}
      <header className="bg-card border-b shadow-sm flex-shrink-0">
        <div className="max-w-7xl mx-auto py-6 px-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">
              Product Discovery Assistant
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              AI-powered workshop tool for internal teams
            </p>
          </div>
          {state.currentStep > 0 && (
            <button
              onClick={() => {
                if (confirm('Are you sure you want to start a new session? All current progress will be lost.')) {
                  handleReset();
                }
              }}
              className="px-4 py-2 text-sm font-medium text-destructive hover:text-destructive-foreground hover:bg-destructive border border-destructive rounded-lg transition-colors"
            >
              🔄 New Session
            </button>
          )}
        </div>
      </header>

      {/* Progress Indicator */}
      <div className="flex-shrink-0">
        <StepIndicator
          currentStep={state.currentStep}
          totalSteps={STEP_LABELS.length}
          stepLabels={STEP_LABELS}
        />
      </div>

      {/* Main Content - Scrollable */}
      <main className="flex-1 overflow-y-auto pb-6">
        {renderStep()}
      </main>

      {/* Navigation - Fixed at Bottom */}
      {state.currentStep < 8 && (
        <div className="flex-shrink-0 border-t bg-card">
          <StepNavigation
            currentStep={state.currentStep}
            totalSteps={STEP_LABELS.length}
            onNext={handleNext}
            onBack={handleBack}
            canGoNext={canGoNext()}
            nextLabel={state.currentStep === 0 ? 'Start Discovery' : 'Next'}
          />
        </div>
      )}
    </div>
  );
}
