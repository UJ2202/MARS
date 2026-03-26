'use client'

import React, { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Play, Timer } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from '@/components/deepresearch/ExecutionProgress'
import type { useNewsPulseTask } from '@/hooks/useNewsPulseTask'

interface NpExecutionPanelProps {
  hook: ReturnType<typeof useNewsPulseTask>
  stageNum: number
  stageName: string
  onNext: () => void
  onBack: () => void
}

export default function NpExecutionPanel({
  hook,
  stageNum,
  stageName,
  onNext,
  onBack,
}: NpExecutionPanelProps) {
  const { taskState, consoleOutput, isExecuting, executeStage } = hook
  const [elapsed, setElapsed] = useState(0)

  const stage = taskState?.stages.find(s => s.stage_number === stageNum)
  const isCompleted = stage?.status === 'completed'
  const isFailed = stage?.status === 'failed'
  const isNotStarted = stage?.status === 'pending'

  // Timer
  useEffect(() => {
    if (!isExecuting) return
    const interval = setInterval(() => setElapsed(prev => prev + 1), 1000)
    return () => clearInterval(interval)
  }, [isExecuting])

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  // Not started
  if (isNotStarted && !isExecuting) {
    return (
      <div className="max-w-3xl mx-auto space-y-3">
        <div className="flex items-center justify-between py-2">
          <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>
            {stageName}
          </span>
          <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
            <Play className="w-3.5 h-3.5 mr-1.5" />
            Run {stageName}
          </Button>
        </div>
        <div className="flex items-center justify-between mt-4">
          <Button onClick={onBack} variant="secondary" size="sm">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      {/* Timer */}
      {isExecuting && (
        <div className="flex items-center justify-end gap-2">
          <Timer className="w-4 h-4" style={{ color: 'var(--mars-color-text-tertiary)' }} />
          <span className="text-xs font-mono" style={{ color: 'var(--mars-color-text-secondary)' }}>
            {formatTime(elapsed)}
          </span>
        </div>
      )}

      {/* Console */}
      <ExecutionProgress
        consoleOutput={consoleOutput}
        isExecuting={isExecuting}
        stageName={stageName}
      />

      {/* Navigation */}
      <div className="flex items-center justify-between mt-4">
        <Button onClick={onBack} variant="secondary" size="sm" disabled={isExecuting}>
          <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back
        </Button>
        {isCompleted && (
          <Button onClick={onNext} variant="primary" size="sm">
            View Report <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        )}
        {isFailed && (
          <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
            <Play className="w-3.5 h-3.5 mr-1.5" /> Retry
          </Button>
        )}
      </div>
    </div>
  )
}
