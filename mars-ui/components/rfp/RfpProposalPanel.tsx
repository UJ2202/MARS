'use client'

import React, { useEffect, useState } from 'react'
import { ArrowLeft, Download, CheckCircle, Play, FileText, Eye, X } from 'lucide-react'
import { Button } from '@/components/core'
import ExecutionProgress from '@/components/deepresearch/ExecutionProgress'
import MarkdownRenderer from '@/components/files/MarkdownRenderer'
import type { useRfpTask } from '@/hooks/useRfpTask'
import { getApiUrl } from '@/lib/config'

interface RfpProposalPanelProps {
    hook: ReturnType<typeof useRfpTask>
    stageNum: number
    onBack: () => void
}

export default function RfpProposalPanel({ hook, stageNum, onBack }: RfpProposalPanelProps) {
    const {
        taskId,
        taskState,
        consoleOutput,
        isExecuting,
        executeStage,
        fetchStageContent,
        editableContent,
    } = hook

    const [contentLoaded, setContentLoaded] = useState(false)
    const [showFullView, setShowFullView] = useState(false)

    const stage = taskState?.stages.find(s => s.stage_number === stageNum)
    const isCompleted = stage?.status === 'completed'
    const isFailed = stage?.status === 'failed'
    const isNotStarted = stage?.status === 'pending'

    // Load content when completed
    useEffect(() => {
        if (isCompleted && !contentLoaded) {
            fetchStageContent(stageNum).then(() => setContentLoaded(true))
        }
    }, [isCompleted, contentLoaded, fetchStageContent, stageNum])

    // Pre-execution
    if (isNotStarted && !isExecuting) {
        return (
            <div className="max-w-3xl mx-auto space-y-3">
                <div className="flex items-center justify-between py-2">
                    <span className="text-sm font-semibold" style={{ color: 'var(--mars-color-text)' }}>
                        Proposal Compilation
                    </span>
                    <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
                        <Play className="w-3.5 h-3.5 mr-1.5" />
                        Generate Proposal
                    </Button>
                </div>
                <div className="flex justify-start pt-1">
                    <Button onClick={onBack} variant="secondary" size="sm">
                        <ArrowLeft className="w-4 h-4 mr-1" />
                        Back
                    </Button>
                </div>
            </div>
        )
    }

    // Running
    if (isExecuting || (stage?.status === 'running')) {
        return (
            <div className="max-w-4xl mx-auto space-y-4">
                <ExecutionProgress
                    consoleOutput={consoleOutput}
                    isExecuting={isExecuting}
                    stageName="Proposal Compilation"
                />
                <div className="flex justify-start">
                    <Button onClick={onBack} variant="secondary" size="sm" disabled={isExecuting}>
                        <ArrowLeft className="w-4 h-4 mr-1" />
                        Back
                    </Button>
                </div>
            </div>
        )
    }

    // Failed
    if (isFailed) {
        return (
            <div className="max-w-3xl mx-auto space-y-4">
                <ExecutionProgress
                    consoleOutput={consoleOutput}
                    isExecuting={false}
                    stageName="Proposal Compilation"
                />
                {stage?.error && (
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
                <div className="flex items-center gap-2">
                    <Button onClick={onBack} variant="secondary" size="sm">
                        <ArrowLeft className="w-4 h-4 mr-1" />
                        Back
                    </Button>
                    <Button onClick={() => executeStage(stageNum)} variant="primary" size="sm">
                        <Play className="w-4 h-4 mr-1" />
                        Retry
                    </Button>
                </div>
            </div>
        )
    }

    // Completed — show the proposal
    return (
        <div className="max-w-4xl mx-auto space-y-6">
            {/* Success banner */}
            <div
                className="flex items-center gap-3 p-4 rounded-mars-md"
                style={{
                    backgroundColor: 'var(--mars-color-success-subtle, rgba(16,185,129,0.1))',
                    border: '1px solid var(--mars-color-success, #10b981)',
                }}
            >
                <CheckCircle className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--mars-color-success)' }} />
                <div>
                    <p className="text-sm font-medium" style={{ color: 'var(--mars-color-success)' }}>
                        Proposal Generated Successfully
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--mars-color-text-secondary)' }}>
                        {taskState?.stages.filter(s => s.status === 'completed').length}/{taskState?.stages.length} stages completed
                        {taskState?.total_cost_usd != null && ` · Total cost: $${taskState.total_cost_usd.toFixed(4)}`}
                    </p>
                </div>
            </div>

            {/* Action buttons — PDF Download + View Online */}
            <div className="flex items-center gap-3">
                {taskId && (
                    <a
                        href={getApiUrl(`/api/rfp/${taskId}/download-pdf`)}
                        download="RFP_Proposal.pdf"
                    >
                        <Button variant="primary" size="sm">
                            <Download className="w-4 h-4 mr-1.5" />
                            Download PDF
                        </Button>
                    </a>
                )}
                <Button onClick={() => setShowFullView(true)} variant="secondary" size="sm">
                    <Eye className="w-4 h-4 mr-1.5" />
                    View Online
                </Button>
            </div>

            {/* Proposal preview (compact) */}
            <div
                className="rounded-mars-md border p-6 prose prose-sm max-w-none overflow-y-auto"
                style={{
                    backgroundColor: 'var(--mars-color-surface)',
                    borderColor: 'var(--mars-color-border)',
                    maxHeight: '500px',
                }}
            >
                <MarkdownRenderer content={editableContent || '(No content)'} />
            </div>

            {/* Download section — individual artifacts */}
            <div
                className="p-4 rounded-mars-md border"
                style={{
                    backgroundColor: 'var(--mars-color-surface-overlay)',
                    borderColor: 'var(--mars-color-border)',
                }}
            >
                <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--mars-color-text)' }}>
                    Generated Artifacts
                </h3>
                <div className="space-y-2">
                    {['requirements.md', 'tools.md', 'cloud.md', 'implementation.md', 'architecture.md', 'execution.md', 'proposal.md'].map((file) => (
                        <div
                            key={file}
                            className="flex items-center justify-between py-2 px-3 rounded-mars-sm"
                            style={{ backgroundColor: 'var(--mars-color-surface)' }}
                        >
                            <div className="flex items-center gap-2">
                                <FileText className="w-4 h-4" style={{ color: 'var(--mars-color-text-secondary)' }} />
                                <span className="text-sm" style={{ color: 'var(--mars-color-text)' }}>{file}</span>
                            </div>
                            {taskId && (
                                <a
                                    href={getApiUrl(`/api/rfp/${taskId}/download/${file}`)}
                                    className="text-xs font-medium hover:underline"
                                    style={{ color: 'var(--mars-color-primary)' }}
                                    download
                                >
                                    <Download className="w-3.5 h-3.5 inline mr-1" />
                                    Download
                                </a>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* Back */}
            <div className="flex justify-start">
                <Button onClick={onBack} variant="secondary" size="sm">
                    <ArrowLeft className="w-4 h-4 mr-1" />
                    Back
                </Button>
            </div>

            {/* Full-screen View Online modal */}
            {showFullView && (
                <div
                    className="fixed inset-0 z-50 flex flex-col"
                    style={{ backgroundColor: 'var(--mars-color-surface, #fff)' }}
                >
                    {/* Modal header */}
                    <div
                        className="flex items-center justify-between px-6 py-3 border-b"
                        style={{ borderColor: 'var(--mars-color-border)' }}
                    >
                        <h2 className="text-base font-semibold" style={{ color: 'var(--mars-color-text)' }}>
                            RFP Proposal — Full View
                        </h2>
                        <div className="flex items-center gap-2">
                            {taskId && (
                                <a href={getApiUrl(`/api/rfp/${taskId}/download-pdf`)} download="RFP_Proposal.pdf">
                                    <Button variant="primary" size="sm">
                                        <Download className="w-3.5 h-3.5 mr-1" />
                                        PDF
                                    </Button>
                                </a>
                            )}
                            <Button onClick={() => setShowFullView(false)} variant="secondary" size="sm">
                                <X className="w-4 h-4" />
                            </Button>
                        </div>
                    </div>
                    {/* Modal body — scrollable proposal */}
                    <div className="flex-1 overflow-y-auto px-8 py-6">
                        <div className="max-w-4xl mx-auto prose prose-sm">
                            <MarkdownRenderer content={editableContent || '(No content)'} />
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
