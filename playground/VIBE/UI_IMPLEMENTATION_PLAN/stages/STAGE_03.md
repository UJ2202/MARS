# Stage 3: Workflow State Dashboard & Controls

**Phase:** 1 - Workflow Control
**Dependencies:** Stage 1 & 2 complete
**Risk Level:** Low-Medium

## Objectives

1. Create comprehensive workflow state dashboard
2. Implement workflow controls (pause, resume, cancel)
3. Show execution progress with visual indicators
4. Display workflow timeline with step history
5. Add workflow summary cards with key metrics

## Current State Analysis

### What We Have
- Basic workflow status in context
- Console output display
- Result display component
- `WORKFLOW_STATE_CHANGED` events from WebSocket

### What We Need
- Visual state indicator bar
- Pause/Resume/Cancel buttons
- Progress bar showing overall completion
- Timeline showing step execution history
- Summary cards (cost, time, steps completed)

## Implementation Tasks

### Task 1: Create Status Badge Component
**Objective:** Reusable status indicator

**Files to Create:**
- `cmbagent-ui/components/common/StatusBadge.tsx`

**Implementation:**
```typescript
// components/common/StatusBadge.tsx

'use client';

import {
  Clock,
  Play,
  CheckCircle,
  XCircle,
  Pause,
  HelpCircle,
  RotateCw,
  Loader2,
} from 'lucide-react';

type WorkflowStatus =
  | 'draft'
  | 'planning'
  | 'executing'
  | 'paused'
  | 'waiting_approval'
  | 'completed'
  | 'failed'
  | 'cancelled';

interface StatusBadgeProps {
  status: WorkflowStatus | string;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  showLabel?: boolean;
  pulse?: boolean;
}

const statusConfig: Record<
  WorkflowStatus,
  {
    label: string;
    icon: React.ReactNode;
    bgColor: string;
    textColor: string;
    borderColor: string;
  }
> = {
  draft: {
    label: 'Draft',
    icon: <Clock className="w-full h-full" />,
    bgColor: 'bg-gray-500/20',
    textColor: 'text-gray-400',
    borderColor: 'border-gray-500/30',
  },
  planning: {
    label: 'Planning',
    icon: <Loader2 className="w-full h-full animate-spin" />,
    bgColor: 'bg-blue-500/20',
    textColor: 'text-blue-400',
    borderColor: 'border-blue-500/30',
  },
  executing: {
    label: 'Executing',
    icon: <Play className="w-full h-full" />,
    bgColor: 'bg-blue-500/20',
    textColor: 'text-blue-400',
    borderColor: 'border-blue-500/30',
  },
  paused: {
    label: 'Paused',
    icon: <Pause className="w-full h-full" />,
    bgColor: 'bg-yellow-500/20',
    textColor: 'text-yellow-400',
    borderColor: 'border-yellow-500/30',
  },
  waiting_approval: {
    label: 'Waiting Approval',
    icon: <HelpCircle className="w-full h-full animate-pulse" />,
    bgColor: 'bg-purple-500/20',
    textColor: 'text-purple-400',
    borderColor: 'border-purple-500/30',
  },
  completed: {
    label: 'Completed',
    icon: <CheckCircle className="w-full h-full" />,
    bgColor: 'bg-green-500/20',
    textColor: 'text-green-400',
    borderColor: 'border-green-500/30',
  },
  failed: {
    label: 'Failed',
    icon: <XCircle className="w-full h-full" />,
    bgColor: 'bg-red-500/20',
    textColor: 'text-red-400',
    borderColor: 'border-red-500/30',
  },
  cancelled: {
    label: 'Cancelled',
    icon: <XCircle className="w-full h-full" />,
    bgColor: 'bg-gray-500/20',
    textColor: 'text-gray-400',
    borderColor: 'border-gray-500/30',
  },
};

const sizeClasses = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-3 py-1 text-sm',
  lg: 'px-4 py-1.5 text-base',
};

const iconSizes = {
  sm: 'w-3 h-3',
  md: 'w-4 h-4',
  lg: 'w-5 h-5',
};

export function StatusBadge({
  status,
  size = 'md',
  showIcon = true,
  showLabel = true,
  pulse = false,
}: StatusBadgeProps) {
  const config = statusConfig[status as WorkflowStatus] || statusConfig.draft;
  const isActive = status === 'executing' || status === 'planning';

  return (
    <div
      className={`
        inline-flex items-center space-x-1.5 rounded-full border font-medium
        ${config.bgColor} ${config.textColor} ${config.borderColor}
        ${sizeClasses[size]}
        ${pulse || isActive ? 'animate-pulse' : ''}
      `}
    >
      {showIcon && (
        <div className={iconSizes[size]}>
          {config.icon}
        </div>
      )}
      {showLabel && <span>{config.label}</span>}
    </div>
  );
}
```

### Task 2: Create Progress Bar Component
**Objective:** Visual progress indicator

**Files to Create:**
- `cmbagent-ui/components/common/ProgressBar.tsx`

**Implementation:**
```typescript
// components/common/ProgressBar.tsx

'use client';

interface ProgressBarProps {
  progress: number; // 0-100
  label?: string;
  showPercentage?: boolean;
  size?: 'sm' | 'md' | 'lg';
  color?: 'blue' | 'green' | 'yellow' | 'red';
  animated?: boolean;
}

const colorClasses = {
  blue: 'bg-blue-500',
  green: 'bg-green-500',
  yellow: 'bg-yellow-500',
  red: 'bg-red-500',
};

const sizeClasses = {
  sm: 'h-1',
  md: 'h-2',
  lg: 'h-3',
};

export function ProgressBar({
  progress,
  label,
  showPercentage = true,
  size = 'md',
  color = 'blue',
  animated = false,
}: ProgressBarProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress));

  return (
    <div className="w-full">
      {(label || showPercentage) && (
        <div className="flex items-center justify-between mb-1">
          {label && <span className="text-xs text-gray-400">{label}</span>}
          {showPercentage && (
            <span className="text-xs text-gray-400">{Math.round(clampedProgress)}%</span>
          )}
        </div>
      )}
      <div className={`w-full bg-gray-700 rounded-full overflow-hidden ${sizeClasses[size]}`}>
        <div
          className={`
            ${sizeClasses[size]} ${colorClasses[color]} rounded-full transition-all duration-500
            ${animated ? 'animate-pulse' : ''}
          `}
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
    </div>
  );
}
```

### Task 3: Create Workflow Controls Component
**Objective:** Pause/Resume/Cancel buttons

**Files to Create:**
- `cmbagent-ui/components/workflow/WorkflowControls.tsx`

**Implementation:**
```typescript
// components/workflow/WorkflowControls.tsx

'use client';

import { useState } from 'react';
import { Play, Pause, Square, RotateCw, AlertTriangle } from 'lucide-react';

interface WorkflowControlsProps {
  status: string;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  onRetry?: () => void;
  disabled?: boolean;
}

export function WorkflowControls({
  status,
  onPause,
  onResume,
  onCancel,
  onRetry,
  disabled = false,
}: WorkflowControlsProps) {
  const [confirmCancel, setConfirmCancel] = useState(false);

  const canPause = status === 'executing' || status === 'planning';
  const canResume = status === 'paused';
  const canCancel = ['executing', 'planning', 'paused', 'waiting_approval'].includes(status);
  const canRetry = status === 'failed';

  const handleCancel = () => {
    if (confirmCancel) {
      onCancel?.();
      setConfirmCancel(false);
    } else {
      setConfirmCancel(true);
      // Auto-reset after 3 seconds
      setTimeout(() => setConfirmCancel(false), 3000);
    }
  };

  return (
    <div className="flex items-center space-x-2">
      {/* Pause Button */}
      {canPause && (
        <button
          onClick={onPause}
          disabled={disabled}
          className="flex items-center space-x-2 px-4 py-2 bg-yellow-500/20 hover:bg-yellow-500/30
                     text-yellow-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Pause className="w-4 h-4" />
          <span>Pause</span>
        </button>
      )}

      {/* Resume Button */}
      {canResume && (
        <button
          onClick={onResume}
          disabled={disabled}
          className="flex items-center space-x-2 px-4 py-2 bg-green-500/20 hover:bg-green-500/30
                     text-green-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play className="w-4 h-4" />
          <span>Resume</span>
        </button>
      )}

      {/* Cancel Button */}
      {canCancel && (
        <button
          onClick={handleCancel}
          disabled={disabled}
          className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors
                      disabled:opacity-50 disabled:cursor-not-allowed
                      ${confirmCancel
                        ? 'bg-red-500 hover:bg-red-600 text-white'
                        : 'bg-red-500/20 hover:bg-red-500/30 text-red-400'
                      }`}
        >
          {confirmCancel ? (
            <>
              <AlertTriangle className="w-4 h-4" />
              <span>Confirm Cancel?</span>
            </>
          ) : (
            <>
              <Square className="w-4 h-4" />
              <span>Cancel</span>
            </>
          )}
        </button>
      )}

      {/* Retry Button */}
      {canRetry && (
        <button
          onClick={onRetry}
          disabled={disabled}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-500/20 hover:bg-blue-500/30
                     text-blue-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RotateCw className="w-4 h-4" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}
```

### Task 4: Create Workflow State Bar
**Objective:** Visual indicator bar at top of workflow view

**Files to Create:**
- `cmbagent-ui/components/workflow/WorkflowStateBar.tsx`

**Implementation:**
```typescript
// components/workflow/WorkflowStateBar.tsx

'use client';

import { Clock, DollarSign, Layers, Timer } from 'lucide-react';
import { StatusBadge } from '@/components/common/StatusBadge';
import { ProgressBar } from '@/components/common/ProgressBar';
import { WorkflowControls } from './WorkflowControls';

interface WorkflowStateBarProps {
  status: string;
  progress: number;
  totalSteps: number;
  completedSteps: number;
  totalCost?: number;
  elapsedTime?: string;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
}

export function WorkflowStateBar({
  status,
  progress,
  totalSteps,
  completedSteps,
  totalCost = 0,
  elapsedTime = '0:00',
  onPause,
  onResume,
  onCancel,
}: WorkflowStateBarProps) {
  return (
    <div className="bg-gray-800/50 backdrop-blur border border-gray-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        {/* Status and Controls */}
        <div className="flex items-center space-x-4">
          <StatusBadge status={status} size="lg" />
          <WorkflowControls
            status={status}
            onPause={onPause}
            onResume={onResume}
            onCancel={onCancel}
          />
        </div>

        {/* Quick Stats */}
        <div className="flex items-center space-x-6">
          {/* Steps */}
          <div className="flex items-center space-x-2 text-gray-400">
            <Layers className="w-4 h-4" />
            <span className="text-sm">
              <span className="text-white font-medium">{completedSteps}</span>
              <span className="mx-1">/</span>
              <span>{totalSteps}</span>
              <span className="ml-1">steps</span>
            </span>
          </div>

          {/* Time */}
          <div className="flex items-center space-x-2 text-gray-400">
            <Timer className="w-4 h-4" />
            <span className="text-sm text-white font-medium">{elapsedTime}</span>
          </div>

          {/* Cost */}
          <div className="flex items-center space-x-2 text-gray-400">
            <DollarSign className="w-4 h-4" />
            <span className="text-sm text-white font-medium">
              ${totalCost.toFixed(4)}
            </span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <ProgressBar
        progress={progress}
        label="Overall Progress"
        animated={status === 'executing'}
        color={status === 'failed' ? 'red' : status === 'completed' ? 'green' : 'blue'}
      />
    </div>
  );
}
```

### Task 5: Create Workflow Timeline Component
**Objective:** Show step execution history

**Files to Create:**
- `cmbagent-ui/components/workflow/WorkflowTimeline.tsx`

**Implementation:**
```typescript
// components/workflow/WorkflowTimeline.tsx

'use client';

import { CheckCircle, XCircle, Clock, Play, Pause, RotateCw } from 'lucide-react';

interface TimelineStep {
  id: string;
  stepNumber: number;
  description: string;
  status: string;
  startedAt?: string;
  completedAt?: string;
  duration?: string;
  agent?: string;
  error?: string;
}

interface WorkflowTimelineProps {
  steps: TimelineStep[];
  currentStepId?: string;
}

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Clock className="w-4 h-4 text-gray-400" />,
  running: <Play className="w-4 h-4 text-blue-400 animate-pulse" />,
  completed: <CheckCircle className="w-4 h-4 text-green-400" />,
  failed: <XCircle className="w-4 h-4 text-red-400" />,
  paused: <Pause className="w-4 h-4 text-yellow-400" />,
  retrying: <RotateCw className="w-4 h-4 text-orange-400 animate-spin" />,
};

const statusColors: Record<string, string> = {
  pending: 'border-gray-600',
  running: 'border-blue-500 bg-blue-500/10',
  completed: 'border-green-500',
  failed: 'border-red-500 bg-red-500/10',
  paused: 'border-yellow-500',
  retrying: 'border-orange-500 bg-orange-500/10',
};

export function WorkflowTimeline({ steps, currentStepId }: WorkflowTimelineProps) {
  if (steps.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400">
        <p>No steps yet</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {steps.map((step, index) => (
        <div
          key={step.id}
          className={`
            relative flex items-start p-3 rounded-lg border-l-4 transition-all
            ${statusColors[step.status] || statusColors.pending}
            ${step.id === currentStepId ? 'ring-2 ring-blue-400/50' : ''}
          `}
        >
          {/* Connection Line */}
          {index < steps.length - 1 && (
            <div className="absolute left-5 top-10 bottom-0 w-px bg-gray-700 -ml-px" />
          )}

          {/* Status Icon */}
          <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-gray-800 border border-gray-700 mr-3">
            {statusIcons[step.status] || statusIcons.pending}
          </div>

          {/* Content */}
          <div className="flex-grow min-w-0">
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-400">Step {step.stepNumber}</span>
                {step.agent && (
                  <span className="text-xs px-2 py-0.5 bg-gray-700 rounded text-gray-300">
                    {step.agent}
                  </span>
                )}
              </div>
              {step.duration && (
                <span className="text-xs text-gray-400">{step.duration}</span>
              )}
            </div>

            <p className="text-sm text-white truncate" title={step.description}>
              {step.description}
            </p>

            {step.error && (
              <p className="text-xs text-red-400 mt-1 truncate" title={step.error}>
                {step.error}
              </p>
            )}

            {/* Time Info */}
            {(step.startedAt || step.completedAt) && (
              <div className="flex items-center space-x-4 mt-1 text-xs text-gray-500">
                {step.startedAt && (
                  <span>Started: {new Date(step.startedAt).toLocaleTimeString()}</span>
                )}
                {step.completedAt && (
                  <span>Ended: {new Date(step.completedAt).toLocaleTimeString()}</span>
                )}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
```

### Task 6: Create Main Workflow Dashboard
**Objective:** Combine all workflow components

**Files to Create:**
- `cmbagent-ui/components/workflow/WorkflowDashboard.tsx`

**Implementation:**
```typescript
// components/workflow/WorkflowDashboard.tsx

'use client';

import { useState, useMemo } from 'react';
import { WorkflowStateBar } from './WorkflowStateBar';
import { WorkflowTimeline } from './WorkflowTimeline';
import { DAGVisualization } from '@/components/dag';
import { LayoutGrid, Timeline, GitBranch, DollarSign } from 'lucide-react';

interface WorkflowDashboardProps {
  status: string;
  dagData: { nodes: any[]; edges: any[] } | null;
  totalCost?: number;
  elapsedTime?: string;
  onPause?: () => void;
  onResume?: () => void;
  onCancel?: () => void;
  onPlayFromNode?: (nodeId: string) => void;
}

type TabId = 'dag' | 'timeline' | 'branches' | 'cost';

export function WorkflowDashboard({
  status,
  dagData,
  totalCost = 0,
  elapsedTime = '0:00',
  onPause,
  onResume,
  onCancel,
  onPlayFromNode,
}: WorkflowDashboardProps) {
  const [activeTab, setActiveTab] = useState<TabId>('dag');

  // Calculate progress from DAG data
  const { progress, totalSteps, completedSteps, timelineSteps } = useMemo(() => {
    if (!dagData || dagData.nodes.length === 0) {
      return { progress: 0, totalSteps: 0, completedSteps: 0, timelineSteps: [] };
    }

    const total = dagData.nodes.length;
    const completed = dagData.nodes.filter(
      (n) => n.status === 'completed'
    ).length;
    const failed = dagData.nodes.filter((n) => n.status === 'failed').length;
    const prog = total > 0 ? ((completed + failed) / total) * 100 : 0;

    const timeline = dagData.nodes
      .filter((n) => n.step_number !== undefined)
      .sort((a, b) => (a.step_number || 0) - (b.step_number || 0))
      .map((n) => ({
        id: n.id,
        stepNumber: n.step_number || 0,
        description: n.label || n.id,
        status: n.status || 'pending',
        startedAt: n.started_at,
        completedAt: n.completed_at,
        agent: n.agent,
        error: n.error,
      }));

    return {
      progress: prog,
      totalSteps: total,
      completedSteps: completed,
      timelineSteps: timeline,
    };
  }, [dagData]);

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'dag', label: 'DAG View', icon: <LayoutGrid className="w-4 h-4" /> },
    { id: 'timeline', label: 'Timeline', icon: <Timeline className="w-4 h-4" /> },
    { id: 'branches', label: 'Branches', icon: <GitBranch className="w-4 h-4" /> },
    { id: 'cost', label: 'Cost', icon: <DollarSign className="w-4 h-4" /> },
  ];

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* State Bar */}
      <WorkflowStateBar
        status={status}
        progress={progress}
        totalSteps={totalSteps}
        completedSteps={completedSteps}
        totalCost={totalCost}
        elapsedTime={elapsedTime}
        onPause={onPause}
        onResume={onResume}
        onCancel={onCancel}
      />

      {/* Tab Navigation */}
      <div className="flex items-center space-x-2 border-b border-gray-700 pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors
              ${activeTab === tab.id
                ? 'bg-blue-500/20 text-blue-400'
                : 'text-gray-400 hover:bg-gray-700/50'
              }
            `}
          >
            {tab.icon}
            <span className="text-sm">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-grow min-h-0 overflow-hidden">
        {activeTab === 'dag' && (
          <div className="h-full bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
            <DAGVisualization
              dagData={dagData}
              onPlayFromNode={onPlayFromNode}
            />
          </div>
        )}

        {activeTab === 'timeline' && (
          <div className="h-full overflow-y-auto bg-gray-900/50 rounded-xl border border-gray-700 p-4">
            <WorkflowTimeline steps={timelineSteps} />
          </div>
        )}

        {activeTab === 'branches' && (
          <div className="h-full flex items-center justify-center text-gray-400">
            <p>Branch view will be implemented in Stage 6</p>
          </div>
        )}

        {activeTab === 'cost' && (
          <div className="h-full flex items-center justify-center text-gray-400">
            <p>Cost dashboard will be implemented in Stage 8</p>
          </div>
        )}
      </div>
    </div>
  );
}
```

### Task 7: Create Index Export
**Objective:** Export all workflow components

**Files to Create:**
- `cmbagent-ui/components/workflow/index.ts`

**Implementation:**
```typescript
// components/workflow/index.ts
export { WorkflowDashboard } from './WorkflowDashboard';
export { WorkflowStateBar } from './WorkflowStateBar';
export { WorkflowTimeline } from './WorkflowTimeline';
export { WorkflowControls } from './WorkflowControls';
```

### Task 8: Create Common Components Index
**Objective:** Export common components

**Files to Create:**
- `cmbagent-ui/components/common/index.ts`

**Implementation:**
```typescript
// components/common/index.ts
export { StatusBadge } from './StatusBadge';
export { ProgressBar } from './ProgressBar';
export { ConnectionStatus } from './ConnectionStatus';
```

## Files to Create (Summary)

```
cmbagent-ui/components/
├── common/
│   ├── index.ts
│   ├── StatusBadge.tsx
│   ├── ProgressBar.tsx
│   └── ConnectionStatus.tsx (from Stage 1)
└── workflow/
    ├── index.ts
    ├── WorkflowDashboard.tsx
    ├── WorkflowStateBar.tsx
    ├── WorkflowTimeline.tsx
    └── WorkflowControls.tsx
```

## Verification Criteria

### Must Pass
- [ ] StatusBadge shows correct colors and icons for all states
- [ ] ProgressBar animates smoothly
- [ ] WorkflowControls show correct buttons per state
- [ ] Pause/Resume/Cancel buttons trigger callbacks
- [ ] WorkflowStateBar displays all metrics
- [ ] WorkflowTimeline shows steps in order
- [ ] WorkflowDashboard tabs switch correctly
- [ ] Integration with WebSocket context works

### Should Pass
- [ ] Responsive on different screen sizes
- [ ] Animations smooth and not jarring
- [ ] Cancel confirmation works
- [ ] Timeline scrolls for many steps

### Testing Steps
```bash
# Build to check types
cd cmbagent-ui && npm run build

# Start dev server
npm run dev

# Test each component:
# 1. Check StatusBadge with different statuses
# 2. Check ProgressBar at 0%, 50%, 100%
# 3. Test WorkflowControls button visibility
# 4. Test tab switching in dashboard
```

## Common Issues and Solutions

### Issue 1: Controls Don't Match State
**Symptom:** Wrong buttons shown
**Solution:** Check status string matches expected values

### Issue 2: Progress Not Updating
**Symptom:** Progress bar stuck
**Solution:** Ensure DAG node statuses are being updated

### Issue 3: Timeline Not Scrolling
**Symptom:** Can't see all steps
**Solution:** Add overflow-y-auto to container

## Success Criteria

Stage 3 is complete when:
1. All common components working
2. WorkflowControls functional
3. WorkflowStateBar displays correctly
4. WorkflowTimeline shows step history
5. WorkflowDashboard integrates all views
6. All verification criteria pass

## Next Stage

Once Stage 3 is verified complete, proceed to:
**Stage 4: HITL Approval System UI**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-16
