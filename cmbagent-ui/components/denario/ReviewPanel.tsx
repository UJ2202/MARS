'use client'

import React, { useState, useCallback, useEffect, useRef } from 'react'
import { Eye, Edit3, Save, ArrowRight, ArrowLeft, Play, Loader2 } from 'lucide-react'
import { Button } from '@/components/core'
import RefinementChat from './RefinementChat'
import ExecutionProgress from './ExecutionProgress'
import MarkdownRenderer from '@/components/files/MarkdownRenderer'
import type { useDenarioTask } from '@/hooks/useDenarioTask'

interface ReviewPanelProps {
  hook: ReturnType<typeof useDenarioTask>
  stageNum: number
  stageName: string
  sharedKey: string
  onNext: () => void
  onBack: () => void
}

export default function ReviewPanel({
  hook,
  stageNum,
  stageName,
  sharedKey,
  onNext,
  onBack,
}: ReviewPanelProps) {
  const {
    taskState,
    editableContent,
    setEditableContent,
    refinementMessages,
    consoleOutput,
    isExecuting,
    executeStage,
    fetchStageContent,
    saveStageContent,
    refineContent,
  } = hook

  const [mode, setMode] = useState<'edit' | 'preview'>('edit')
  const [isSaving, setIsSaving] = useState(false)
  const [saveIndicator, setSaveIndicator] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [contentLoaded, setContentLoaded] = useState(false)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const executingRef = useRef(false)

  // Determine if stage is completed (has content to show)
  const stage = taskState?.stages.find(s => s.stage_number === stageNum)
  const isStageCompleted = stage?.status === 'completed'
  const isStageRunning = stage?.status === 'running' || isExecuting
  const isStageNotStarted = stage?.status === 'pending'
  const isStageFailed = stage?.status === 'failed'

  // Load content when stage is completed
  useEffect(() => {
    if (isStageCompleted && !contentLoaded) {
      fetchStageContent(stageNum).then(() => setContentLoaded(true))
    }
  }, [isStageCompleted, contentLoaded, fetchStageContent, stageNum])

  // Auto-execute if stage hasn't started yet (guarded against double-fire)
  useEffect(() => {
    if (isStageNotStarted && !isExecuting && !executingRef.current) {
      executingRef.current = true
      executeStage(stageNum)
    }
  }, [isStageNotStarted, isExecuting, executeStage, stageNum])

  // Auto-save with debounce
  const handleContentChange = useCallback((value: string) => {
    setEditableContent(value)
    setSaveIndicator('idle')

    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(async () => {
      if (isStageCompleted) {
        setSaveIndicator('saving')
        await saveStageContent(stageNum, value, sharedKey)
        setSaveIndicator('saved')
        setTimeout(() => setSaveIndicator('idle'), 2000)
      }
    }, 1000)
  }, [isStageCompleted, saveStageContent, setEditableContent, stageNum, sharedKey])

  // Manual save
  const handleSave = useCallback(async () => {
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    setIsSaving(true)
    await saveStageContent(stageNum, editableContent, sharedKey)
    setIsSaving(false)
    setSaveIndicator('saved')
    setTimeout(() => setSaveIndicator('idle'), 2000)
  }, [saveStageContent, stageNum, editableContent, sharedKey])

  // Refinement handler
  const handleRefine = useCallback(async (message: string) => {
    return refineContent(stageNum, message, editableContent)
  }, [refineContent, stageNum, editableContent])

  // Apply refined content from chat
  const handleApply = useCallback((content: string) => {
    setEditableContent(content)
    if (isStageCompleted) {
      saveStageContent(stageNum, content, sharedKey)
    }
  }, [setEditableContent, isStageCompleted, saveStageContent, stageNum, sharedKey])

  // Handle next with save
  const handleNext = useCallback(async () => {
    if (isStageCompleted) {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
      await saveStageContent(stageNum, editableContent, sharedKey)
    }
    onNext()
  }, [isStageCompleted, saveStageContent, stageNum, editableContent, sharedKey, onNext])

  // Show failure state with retry option
  if (isStageFailed && !isExecuting) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <div
          className="rounded-mars-md border p-6 text-center"
          style={{
            borderColor: 'var(--mars-color-error)',
            backgroundColor: 'var(--mars-color-error-subtle, rgba(239,68,68,0.1))',
          }}
        >
          <p className="text-sm font-medium mb-2" style={{ color: 'var(--mars-color-error)' }}>
            {stageName} failed
          </p>
          {hook.error && (
            <p className="text-xs mb-4" style={{ color: 'var(--mars-color-text-secondary)' }}>
              {hook.error}
            </p>
          )}
          <Button
            onClick={() => {
              executingRef.current = false
              executeStage(stageNum)
            }}
            variant="primary"
            size="sm"
          >
            <Play className="w-4 h-4 mr-1" />
            Retry
          </Button>
        </div>
        {consoleOutput.length > 0 && (
          <ExecutionProgress
            consoleOutput={consoleOutput}
            isExecuting={false}
            stageName={stageName}
          />
        )}
        <div className="flex justify-start pt-2">
          <Button onClick={onBack} variant="secondary" size="sm">
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
        </div>
      </div>
    )
  }

  // Show execution progress if stage is still running
  if (isStageRunning && !isStageCompleted) {
    return (
      <div className="max-w-3xl mx-auto">
        <ExecutionProgress
          consoleOutput={consoleOutput}
          isExecuting={true}
          stageName={stageName}
        />
      </div>
    )
  }

  return (
    <div className="flex flex-col" style={{ minHeight: '500px' }}>
      {/* Split view: Editor (60%) + Chat (40%) */}
      <div className="flex flex-1 gap-4" style={{ minHeight: '400px' }}>
        {/* Editor panel */}
        <div
          className="flex-[3] flex flex-col rounded-mars-md border overflow-hidden"
          style={{
            borderColor: 'var(--mars-color-border)',
            backgroundColor: 'var(--mars-color-surface)',
          }}
        >
          {/* Editor toolbar */}
          <div
            className="flex items-center justify-between px-4 py-2 border-b flex-shrink-0"
            style={{ borderColor: 'var(--mars-color-border)' }}
          >
            <div className="flex items-center gap-2">
              <span
                className="text-sm font-medium"
                style={{ color: 'var(--mars-color-text)' }}
              >
                {stageName}
              </span>

              {/* Save indicator */}
              {saveIndicator === 'saving' && (
                <span className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>
                  Saving...
                </span>
              )}
              {saveIndicator === 'saved' && (
                <span className="text-xs" style={{ color: 'var(--mars-color-success)' }}>
                  Saved
                </span>
              )}
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setMode('edit')}
                className="flex items-center gap-1 px-2 py-1 text-xs rounded-mars-sm transition-colors"
                style={{
                  backgroundColor: mode === 'edit' ? 'var(--mars-color-primary-subtle)' : 'transparent',
                  color: mode === 'edit' ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)',
                }}
              >
                <Edit3 className="w-3 h-3" />
                Edit
              </button>
              <button
                onClick={() => setMode('preview')}
                className="flex items-center gap-1 px-2 py-1 text-xs rounded-mars-sm transition-colors"
                style={{
                  backgroundColor: mode === 'preview' ? 'var(--mars-color-primary-subtle)' : 'transparent',
                  color: mode === 'preview' ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)',
                }}
              >
                <Eye className="w-3 h-3" />
                Preview
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="flex items-center gap-1 px-2 py-1 text-xs rounded-mars-sm transition-colors ml-2"
                style={{
                  color: 'var(--mars-color-text-secondary)',
                }}
              >
                <Save className="w-3 h-3" />
                Save
              </button>
            </div>
          </div>

          {/* Editor / Preview */}
          <div className="flex-1 overflow-y-auto">
            {mode === 'edit' ? (
              <textarea
                value={editableContent}
                onChange={(e) => handleContentChange(e.target.value)}
                className="w-full h-full p-4 font-mono text-sm resize-none outline-none bg-transparent"
                style={{ color: 'var(--mars-color-text)', minHeight: '100%' }}
                spellCheck={false}
              />
            ) : (
              <div className="p-4">
                <MarkdownRenderer content={editableContent} />
              </div>
            )}
          </div>
        </div>

        {/* Chat panel */}
        <div
          className="flex-[2] rounded-mars-md border overflow-hidden flex flex-col"
          style={{
            borderColor: 'var(--mars-color-border)',
            backgroundColor: 'var(--mars-color-surface)',
          }}
        >
          <RefinementChat
            messages={refinementMessages}
            onSend={handleRefine}
            onApply={handleApply}
          />
        </div>
      </div>

      {/* Navigation buttons */}
      <div className="flex items-center justify-between pt-4 mt-4">
        <Button
          onClick={onBack}
          variant="secondary"
          size="sm"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
        <Button
          onClick={handleNext}
          variant="primary"
          size="sm"
          disabled={!isStageCompleted}
        >
          Next
          <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  )
}
