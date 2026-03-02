'use client'

import React, { useEffect, useCallback, useState } from 'react'
import { ArrowLeft, ArrowRight, Play, Timer, DollarSign } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from './ExecutionProgress'
import type { useDenarioTask } from '@/hooks/useDenarioTask'

interface ExecutionPanelProps {
  hook: ReturnType<typeof useDenarioTask>
  stageNum: number
  stageName: string
  onNext: () => void
  onBack: () => void
}

export default function ExecutionPanel({
  hook,
  stageNum,
  stageName,
  onNext,
  onBack,
}: ExecutionPanelProps) {
  const {
    taskState,
    consoleOutput,
    isExecuting,
    executeStage,
  } = hook

  const [elapsed, setElapsed] = useState(0)

  const stage = taskState?.stages.find(s => s.stage_number === stageNum)
  const isCompleted = stage?.status === 'completed'
  const isFailed = stage?.status === 'failed'
  const isNotStarted = stage?.status === 'pending'

  // Auto-execute
  useEffect(() => {
    if (isNotStarted && !isExecuting) {
      executeStage(stageNum)
    }
  }, [isNotStarted, isExecuting, executeStage, stageNum])

  // Timer
  useEffect(() => {
    if (!isExecuting) return
    const interval = setInterval(() => {
      setElapsed(prev => prev + 1)
    }, 1000)
    return () => clearInterval(interval)
  }, [isExecuting])

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Stats bar */}
      <div className="flex items-center gap-6">
        {(isExecuting || elapsed > 0) && (
          <div
            className="flex items-center gap-2 text-xs"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <Timer className="w-3.5 h-3.5" />
            {formatTime(elapsed)}
          </div>
        )}
        {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
          <div
            className="flex items-center gap-2 text-xs"
            style={{ color: 'var(--mars-color-text-secondary)' }}
          >
            <DollarSign className="w-3.5 h-3.5" />
            ${taskState.total_cost_usd.toFixed(4)}
          </div>
        )}
      </div>

      {/* Execution output */}
      <ExecutionProgress
        consoleOutput={consoleOutput}
        isExecuting={isExecuting}
        stageName={stageName}
      />

      {/* Error display */}
      {isFailed && stage?.error && (
        <div
          className="p-3 rounded-mars-md text-sm"
          style={{
            backgroundColor: 'var(--mars-color-danger-subtle)',
            color: 'var(--mars-color-danger)',
            border: '1px solid var(--mars-color-danger)',
          }}
        >
          {stage.error}
        </div>
      )}

      {/* Retry button for failed stages */}
      {isFailed && (
        <div className="flex justify-center">
          <Button
            onClick={() => executeStage(stageNum)}
            variant="primary"
            size="sm"
          >
            <Play className="w-4 h-4 mr-1" />
            Retry
          </Button>
        </div>
      )}

      {/* Navigation */}
      <div className="flex items-center justify-between pt-4">
        <Button
          onClick={onBack}
          variant="secondary"
          size="sm"
          disabled={isExecuting}
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
        <Button
          onClick={onNext}
          variant="primary"
          size="sm"
          disabled={!isCompleted}
        >
          Next: Paper Generation
          <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  )
}
