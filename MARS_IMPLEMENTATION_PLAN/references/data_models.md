# Data Models Reference

TypeScript interfaces used across the MARS UI. All types are defined in the `types/` directory.

**CRITICAL: These interfaces represent backend contracts and must NOT be modified.**

## Core Types

### Session Types (`types/sessions.ts`)

```typescript
interface SessionDetail {
  session_id: string
  name: string
  mode: string
  status: string
  current_phase: string | null
  current_step: number | null
  created_at: string | null
  updated_at: string | null
  conversation_history: ConversationMessage[]
  context_variables: Record<string, any>
  plan_data: any | null
  config: Record<string, any>
}

interface ConversationMessage {
  role: string
  content: string
  agent?: string
  timestamp?: string
}

interface SessionRun {
  id: string
  mode: string
  agent: string
  model: string
  status: string
  task_description: string | null
  started_at: string | null
  completed_at: string | null
  is_branch: boolean
  meta: Record<string, any> | null
}

type SessionDetailTab =
  | "overview" | "dag" | "console" | "events" | "costs" | "files" | "config"
```

### DAG Types (`types/dag.ts`)

See `event_types.md` for DAGNodeData and DAGEdgeData.

### Cost Types (`types/cost.ts`)

```typescript
interface CostSummary {
  total_cost_usd: number
  total_tokens: number
  total_input_tokens: number
  total_output_tokens: number
  by_model: ModelCost[]
  by_agent: AgentCost[]
  by_step: StepCost[]
}

interface ModelCost {
  model: string
  cost_usd: number
  tokens: number
  input_tokens: number
  output_tokens: number
}

interface AgentCost {
  agent: string
  cost_usd: number
  tokens: number
}

interface StepCost {
  step_id: string
  step_number: number
  cost_usd: number
  tokens: number
}

interface CostTimeSeries {
  timestamp: string
  cumulative_cost: number
  cumulative_tokens: number
  model: string
}
```

### Branching Types (`types/branching.ts`)

```typescript
interface Branch {
  branch_id: string
  run_id: string
  parent_branch_id?: string
  branch_point_step_id?: string
  hypothesis?: string
  name: string
  created_at: string
  status: string
  is_main: boolean
}
```

### Table Types (`types/tables.ts`)

```typescript
interface WorkflowRow {
  id: string
  session_id: string
  task_description: string
  status: string
  agent: string
  model: string
  started_at?: string
  completed_at?: string
  total_cost?: number
  step_count?: number
}
```

### Retry Types (`types/retry.ts`)

```typescript
interface StepRetryStartedData {
  step_id: string
  step_number: number
  attempt_number: number
  max_attempts: number
  error_category: string
  error_pattern?: string
  success_probability?: number
  strategy: string
  suggestions: string[]
  has_user_feedback: boolean
}
```

## New MARS UI Types (`types/mars-ui.ts`)

These are NEW types created for the MARS UI overhaul. They do not represent backend contracts.

```typescript
// Navigation
type NavItem = {
  id: string
  label: string
  icon: string
  href: string
  badge?: number | string
}

// Modal
type ModalSize = 'sm' | 'md' | 'lg' | 'xl'
type ModalState = {
  consoleOpen: boolean
  workflowOpen: boolean
}

// Session Pills (TopBar)
type SessionPillData = {
  sessionId: string
  name: string
  status: 'active' | 'paused' | 'queued' | 'completed' | 'failed'
  progress?: number
  mode?: string
}

// Toasts
type ToastType = 'info' | 'success' | 'warning' | 'error'
type ToastData = {
  id: string
  type: ToastType
  title: string
  message?: string
  duration?: number
  action?: {
    label: string
    onClick: () => void
  }
}

// Mode Configuration (display mapping)
interface ModeConfig {
  id: string          // Backend mode ID (never changes)
  displayName: string // MARS display name
  description: string
  tags: string[]
  icon: string
  color: string
  quickStats?: string
}
```

---

**Last Updated:** 2026-02-18
