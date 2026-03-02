'use client'

import React, { useState, useCallback } from 'react'
import { Sparkles, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/core'
import FileUploadZone from './FileUploadZone'
import type { useDenarioTask } from '@/hooks/useDenarioTask'

interface SetupPanelProps {
  hook: ReturnType<typeof useDenarioTask>
  onNext: () => void
}

export default function SetupPanel({ hook, onNext }: SetupPanelProps) {
  const { createTask, uploadFile, uploadedFiles, isLoading } = hook
  const [description, setDescription] = useState('')
  const [dataDescription, setDataDescription] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const handleSubmit = useCallback(async () => {
    if (!description.trim()) return

    // Create task, then navigate to step 1 (idea review).
    // ReviewPanel auto-executes the stage when it mounts and sees status=pending.
    await createTask(description, dataDescription || undefined)
    onNext()
  }, [description, dataDescription, createTask, onNext])

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Research description */}
      <div>
        <label
          className="block text-sm font-medium mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Research Description
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe your research question, area of investigation, or the study you want to pursue..."
          rows={5}
          className="w-full rounded-mars-md border p-3 text-sm resize-none outline-none transition-colors"
          style={{
            backgroundColor: 'var(--mars-color-surface)',
            borderColor: 'var(--mars-color-border)',
            color: 'var(--mars-color-text)',
          }}
        />
        <p
          className="text-xs mt-1"
          style={{ color: 'var(--mars-color-text-tertiary)' }}
        >
          Be specific about your research goals. The AI will generate ideas based on this description.
        </p>
      </div>

      {/* Data description */}
      <div>
        <label
          className="block text-sm font-medium mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Data Description (Optional)
        </label>
        <textarea
          value={dataDescription}
          onChange={(e) => setDataDescription(e.target.value)}
          placeholder="Describe any data you have or plan to use (e.g., Planck satellite data, SDSS galaxy catalog, simulated N-body data...)"
          rows={3}
          className="w-full rounded-mars-md border p-3 text-sm resize-none outline-none transition-colors"
          style={{
            backgroundColor: 'var(--mars-color-surface)',
            borderColor: 'var(--mars-color-border)',
            color: 'var(--mars-color-text)',
          }}
        />
      </div>

      {/* File upload */}
      <div>
        <label
          className="block text-sm font-medium mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Upload Data Files (Optional)
        </label>
        <FileUploadZone
          files={uploadedFiles}
          onUpload={uploadFile}
          disabled={isLoading}
        />
      </div>

      {/* Advanced settings */}
      <div>
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-2 text-xs font-medium"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          Advanced Settings
        </button>
        {showAdvanced && (
          <div
            className="mt-3 p-4 rounded-mars-md border space-y-3"
            style={{
              backgroundColor: 'var(--mars-color-surface-overlay)',
              borderColor: 'var(--mars-color-border)',
            }}
          >
            <p
              className="text-xs"
              style={{ color: 'var(--mars-color-text-tertiary)' }}
            >
              Model and execution settings can be customized per-stage in future releases.
              Default models: GPT-4o (idea), GPT-4.1 (method/experiment), Gemini 2.5 Flash (paper).
            </p>
          </div>
        )}
      </div>

      {/* Submit button */}
      <div className="flex justify-end pt-2">
        <Button
          onClick={handleSubmit}
          disabled={!description.trim() || isLoading}
          variant="primary"
          size="md"
        >
          {isLoading ? (
            <>Generating...</>
          ) : (
            <>
              <Sparkles className="w-4 h-4 mr-2" />
              Generate Ideas
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
