/**
 * TypeScript types for the Denario Research Paper wizard.
 */

export type DenarioStageStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface DenarioStage {
  stage_number: number
  stage_name: string
  status: DenarioStageStatus
  started_at?: string | null
  completed_at?: string | null
  error?: string | null
}

export interface DenarioTaskState {
  task_id: string
  task: string
  status: string
  work_dir?: string | null
  created_at?: string | null
  stages: DenarioStage[]
  current_stage?: number | null
  progress_percent: number
  total_cost_usd?: number | null
}

export interface DenarioStageContent {
  stage_number: number
  stage_name: string
  status: string
  content?: string | null
  shared_state?: Record<string, unknown> | null
  output_files?: string[] | null
}

export interface DenarioCreateResponse {
  task_id: string
  work_dir: string
  stages: DenarioStage[]
}

export interface DenarioRefineResponse {
  refined_content: string
  message: string
}

export interface RefinementMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface UploadedFile {
  name: string
  size: number
  path?: string
  status: 'pending' | 'uploading' | 'done' | 'error'
  error?: string
}

/** Wizard step mapping (0-indexed for Stepper) */
export type DenarioWizardStep = 0 | 1 | 2 | 3 | 4
// 0 = Setup, 1 = Idea Review, 2 = Method Review, 3 = Experiment, 4 = Paper

export const DENARIO_STEP_LABELS = [
  'Setup',
  'Idea Generation',
  'Method Development',
  'Experiment',
  'Paper',
] as const

/** Maps wizard step index to stage number (1-based) for API calls. Step 0 (setup) has no stage. */
export const WIZARD_STEP_TO_STAGE: Record<number, number | null> = {
  0: null,
  1: 1,
  2: 2,
  3: 3,
  4: 4,
}

export const STAGE_SHARED_KEYS: Record<number, string> = {
  1: 'research_idea',
  2: 'methodology',
  3: 'results',
}
