'use client'

import React, { useEffect, useState } from 'react'
import { ArrowLeft, Download, FileText, Image, File, CheckCircle, Loader2, Play } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from './ExecutionProgress'
import type { useDenarioTask } from '@/hooks/useDenarioTask'
import { getApiUrl } from '@/lib/config'

interface PaperPanelProps {
  hook: ReturnType<typeof useDenarioTask>
  stageNum: number
  onBack: () => void
}

export default function PaperPanel({ hook, stageNum, onBack }: PaperPanelProps) {
  const {
    taskId,
    taskState,
    consoleOutput,
    isExecuting,
    executeStage,
    fetchStageContent,
  } = hook

  const [artifacts, setArtifacts] = useState<string[]>([])

  const stage = taskState?.stages.find(s => s.stage_number === stageNum)
  const isCompleted = stage?.status === 'completed'
  const isFailed = stage?.status === 'failed'
  const isNotStarted = stage?.status === 'pending'

  // Auto-execute paper generation
  useEffect(() => {
    if (isNotStarted && !isExecuting) {
      executeStage(stageNum)
    }
  }, [isNotStarted, isExecuting, executeStage, stageNum])

  // Load artifacts when complete
  useEffect(() => {
    if (isCompleted && taskId) {
      fetchStageContent(stageNum).then(content => {
        if (content?.output_files) {
          setArtifacts(content.output_files)
        }
      })
    }
  }, [isCompleted, taskId, fetchStageContent, stageNum])

  const getFileIcon = (path: string) => {
    if (path.endsWith('.tex') || path.endsWith('.pdf')) return <FileText className="w-4 h-4" />
    if (path.endsWith('.png') || path.endsWith('.jpg') || path.endsWith('.jpeg')) return <Image className="w-4 h-4" />
    return <File className="w-4 h-4" />
  }

  const getFileName = (path: string) => {
    return path.split('/').pop() || path
  }

  // Show execution progress while running
  if (isExecuting || (stage?.status === 'running' && !isCompleted)) {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <ExecutionProgress
          consoleOutput={consoleOutput}
          isExecuting={true}
          stageName="Paper Generation"
        />
        <div className="flex justify-start pt-4">
          <Button onClick={onBack} variant="secondary" size="sm" disabled={isExecuting}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back
          </Button>
        </div>
      </div>
    )
  }

  // Completion view
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Success header */}
      {isCompleted && (
        <div
          className="flex items-center gap-3 p-4 rounded-mars-md"
          style={{
            backgroundColor: 'var(--mars-color-success-subtle)',
            border: '1px solid var(--mars-color-success)',
          }}
        >
          <CheckCircle className="w-6 h-6" style={{ color: 'var(--mars-color-success)' }} />
          <div>
            <p
              className="text-sm font-medium"
              style={{ color: 'var(--mars-color-text)' }}
            >
              Research Paper Complete
            </p>
            <p
              className="text-xs"
              style={{ color: 'var(--mars-color-text-secondary)' }}
            >
              All 4 stages completed successfully.
            </p>
          </div>
        </div>
      )}

      {/* Error */}
      {isFailed && (
        <div
          className="p-4 rounded-mars-md"
          style={{
            backgroundColor: 'var(--mars-color-danger-subtle)',
            border: '1px solid var(--mars-color-danger)',
          }}
        >
          <p
            className="text-sm font-medium"
            style={{ color: 'var(--mars-color-danger)' }}
          >
            Paper generation failed
          </p>
          {stage?.error && (
            <p className="text-xs mt-1" style={{ color: 'var(--mars-color-text-secondary)' }}>
              {stage.error}
            </p>
          )}
          <Button
            onClick={() => executeStage(stageNum)}
            variant="primary"
            size="sm"
            className="mt-3"
          >
            <Play className="w-4 h-4 mr-1" />
            Retry
          </Button>
        </div>
      )}

      {/* Artifacts */}
      {artifacts.length > 0 && (
        <div>
          <h3
            className="text-sm font-medium mb-3"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Generated Artifacts
          </h3>
          <div className="space-y-2">
            {artifacts.map((path, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-4 py-3 rounded-mars-md border"
                style={{
                  backgroundColor: 'var(--mars-color-surface)',
                  borderColor: 'var(--mars-color-border)',
                }}
              >
                <span style={{ color: 'var(--mars-color-text-secondary)' }}>
                  {getFileIcon(path)}
                </span>
                <span
                  className="flex-1 text-sm"
                  style={{ color: 'var(--mars-color-text)' }}
                >
                  {getFileName(path)}
                </span>
                <a
                  href={getApiUrl(`/api/files/content?path=${encodeURIComponent(path)}`)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs font-medium"
                  style={{ color: 'var(--mars-color-primary)' }}
                >
                  <Download className="w-3.5 h-3.5" />
                  Download
                </a>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cost summary */}
      {taskState?.total_cost_usd != null && taskState.total_cost_usd > 0 && (
        <div
          className="p-4 rounded-mars-md border"
          style={{
            backgroundColor: 'var(--mars-color-surface-overlay)',
            borderColor: 'var(--mars-color-border)',
          }}
        >
          <h3
            className="text-sm font-medium mb-2"
            style={{ color: 'var(--mars-color-text)' }}
          >
            Cost Summary
          </h3>
          <div className="flex items-center gap-6">
            <div>
              <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>Total Cost</p>
              <p className="text-lg font-semibold" style={{ color: 'var(--mars-color-text)' }}>
                ${taskState.total_cost_usd.toFixed(4)}
              </p>
            </div>
            <div>
              <p className="text-xs" style={{ color: 'var(--mars-color-text-tertiary)' }}>Stages</p>
              <p className="text-lg font-semibold" style={{ color: 'var(--mars-color-text)' }}>
                {taskState.stages.filter(s => s.status === 'completed').length}/4
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-4">
        <Button onClick={onBack} variant="secondary" size="sm">
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
      </div>
    </div>
  )
}
