/**
 * TypeScript types for the RFP (Request for Proposal) Proposal Generator.
 */

export type RfpStageStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface RfpStage {
    stage_number: number
    stage_name: string
    status: RfpStageStatus
    started_at?: string | null
    completed_at?: string | null
    error?: string | null
}

export interface RfpTaskState {
    task_id: string
    task: string
    status: string
    work_dir?: string | null
    created_at?: string | null
    stages: RfpStage[]
    current_stage?: number | null
    progress_percent: number
    total_cost_usd?: number | null
}

export interface RfpStageContent {
    stage_number: number
    stage_name: string
    status: string
    content?: string | null
    shared_state?: Record<string, unknown> | null
    output_files?: string[] | null
}

export interface RfpCreateResponse {
    task_id: string
    work_dir: string
    stages: RfpStage[]
}

export interface RfpRefineResponse {
    refined_content: string
    message: string
}

export interface RfpRefinementMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    timestamp: number
}

export interface RfpUploadedFile {
    name: string
    size: number
    path?: string
    status: 'pending' | 'uploading' | 'done' | 'error'
    error?: string
}

/** Wizard step mapping (0-indexed for Stepper) */
export type RfpWizardStep = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7
// 0 = Setup
// 1 = Requirements Analysis
// 2 = Tools & Technology
// 3 = Cloud & Infrastructure
// 4 = Implementation Plan
// 5 = Architecture Design
// 6 = Execution Strategy
// 7 = Final Proposal

export const RFP_STEP_LABELS = [
    'Setup',
    'Requirements',
    'Tools & Tech',
    'Cloud & Infra',
    'Implementation',
    'Architecture',
    'Execution',
    'Proposal',
] as const

/** Maps wizard step index to stage number (1-based). Step 0 (setup) has no stage. */
export const RFP_WIZARD_STEP_TO_STAGE: Record<number, number | null> = {
    0: null,
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
}

/** Shared state field names per stage */
export const RFP_STAGE_SHARED_KEYS: Record<number, string> = {
    1: 'requirements_analysis',
    2: 'tools_technology',
    3: 'cloud_infrastructure',
    4: 'implementation_plan',
    5: 'architecture_design',
    6: 'execution_strategy',
}

/** Stage display names */
export const RFP_STAGE_NAMES: Record<number, string> = {
    1: 'Requirements Analysis',
    2: 'Tools & Technology',
    3: 'Cloud & Infrastructure',
    4: 'Implementation Plan',
    5: 'Architecture Design',
    6: 'Execution Strategy',
    7: 'Proposal Compilation',
}

/** Available model options for stage configuration */
export const RFP_AVAILABLE_MODELS = [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-5.3', label: 'GPT-5.3' },
    { value: 'gpt-4.1-2025-04-14', label: 'GPT-4.1' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4o-mini-2024-07-18', label: 'GPT-4o Mini' },
    { value: 'o3-mini-2025-01-31', label: 'o3-mini' },
    { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
    { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
    { value: 'claude-sonnet-4-20250514', label: 'Claude Sonnet 4' },
    { value: 'claude-3.5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
]

/** Config overrides for RFP stages */
export interface RfpStageConfig {
    model?: string
}
