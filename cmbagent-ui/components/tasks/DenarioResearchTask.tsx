'use client'

import React, { useEffect, useCallback } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/core'
import Stepper from '@/components/core/Stepper'
import type { StepperStep } from '@/components/core/Stepper'
import { useDenarioTask } from '@/hooks/useDenarioTask'
import { DENARIO_STEP_LABELS, WIZARD_STEP_TO_STAGE } from '@/types/denario'
import type { DenarioWizardStep } from '@/types/denario'
import SetupPanel from '@/components/denario/SetupPanel'
import ReviewPanel from '@/components/denario/ReviewPanel'
import ExecutionPanel from '@/components/denario/ExecutionPanel'
import PaperPanel from '@/components/denario/PaperPanel'

interface DenarioResearchTaskProps {
  onBack: () => void
  resumeTaskId?: string | null
}

export default function DenarioResearchTask({ onBack, resumeTaskId }: DenarioResearchTaskProps) {
  const hook = useDenarioTask()
  const {
    taskId,
    taskState,
    currentStep,
    isLoading,
    error,
    isExecuting,
    setCurrentStep,
    resumeTask,
    clearError,
  } = hook

  // Resume on mount if resumeTaskId provided
  useEffect(() => {
    if (resumeTaskId) {
      resumeTask(resumeTaskId)
    }
  }, [resumeTaskId, resumeTask])

  // Build stepper steps from taskState
  const stepperSteps: StepperStep[] = DENARIO_STEP_LABELS.map((label, idx) => {
    const stageNum = WIZARD_STEP_TO_STAGE[idx]
    let status: StepperStep['status'] = 'pending'

    if (idx === currentStep) {
      status = 'active'
    } else if (idx < currentStep) {
      status = 'completed'
    }

    // Override with real stage status if task exists
    if (taskState && stageNum) {
      const stage = taskState.stages.find(s => s.stage_number === stageNum)
      if (stage) {
        if (stage.status === 'completed') status = 'completed'
        else if (stage.status === 'failed') status = 'failed'
        else if (stage.status === 'running') status = 'active'
      }
    }

    // Step 0 (setup) is completed once task is created
    if (idx === 0 && taskId) {
      status = 'completed'
    }

    return { id: `step-${idx}`, label, status }
  })

  const goNext = useCallback(() => {
    if (currentStep < 4) {
      setCurrentStep((currentStep + 1) as DenarioWizardStep)
    }
  }, [currentStep, setCurrentStep])

  const goBack = useCallback(() => {
    if (currentStep > 0 && !isExecuting) {
      setCurrentStep((currentStep - 1) as DenarioWizardStep)
    }
  }, [currentStep, isExecuting, setCurrentStep])

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={onBack}
          className="p-2 rounded-mars-md transition-colors hover:bg-[var(--mars-color-surface-overlay)]"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h2
            className="text-2xl font-semibold"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Research Paper
          </h2>
          <p
            className="text-sm mt-0.5"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            Generate a research paper through interactive stages
          </p>
        </div>
        {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
          <div
            className="ml-auto text-xs px-3 py-1.5 rounded-mars-md"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              color: 'var(--mars-color-text-secondary)',
            }}
          >
            Cost: ${taskState.total_cost_usd.toFixed(4)}
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div
          className="mb-4 p-3 rounded-mars-md flex items-center justify-between text-sm"
          style={{
            backgroundColor: 'var(--mars-color-danger-subtle)',
            color: 'var(--mars-color-danger)',
            border: '1px solid var(--mars-color-danger)',
          }}
        >
          <span>{error}</span>
          <button onClick={clearError} className="ml-2 font-medium underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Stepper */}
      <div className="mb-8">
        <Stepper steps={stepperSteps} orientation="horizontal" size="sm" />
      </div>

      {/* Panel content */}
      <div>
        {currentStep === 0 && (
          <SetupPanel hook={hook} onNext={goNext} />
        )}
        {currentStep === 1 && (
          <ReviewPanel
            hook={hook}
            stageNum={1}
            stageName="Idea Generation"
            sharedKey="research_idea"
            onNext={goNext}
            onBack={goBack}
          />
        )}
        {currentStep === 2 && (
          <ReviewPanel
            hook={hook}
            stageNum={2}
            stageName="Method Development"
            sharedKey="methodology"
            onNext={goNext}
            onBack={goBack}
          />
        )}
        {currentStep === 3 && (
          <ExecutionPanel
            hook={hook}
            stageNum={3}
            stageName="Experiment Execution"
            onNext={goNext}
            onBack={goBack}
          />
        )}
        {currentStep === 4 && (
          <PaperPanel
            hook={hook}
            stageNum={4}
            onBack={goBack}
          />
        )}
      </div>
    </div>
  )
}
