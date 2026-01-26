# Stage 4: HITL Approval System UI

**Phase:** 1 - Workflow Control
**Dependencies:** Stage 3 complete, Backend Stage 6 (HITL) complete
**Risk Level:** Medium

## Objectives

1. Enhance ApprovalDialog with rich context display
2. Create approval notification system
3. Implement approval queue for multiple pending approvals
4. Add approval history viewer
5. Support different approval types (plan, step, error)

## Current State Analysis

### What We Have
- Basic `ApprovalDialog.tsx` component exists
- `APPROVAL_REQUESTED` and `APPROVAL_RECEIVED` WebSocket events
- Approval state in WebSocket context

### What We Need
- Enhanced dialog with context viewer
- Toast/banner notifications for new approvals
- Queue display for multiple approvals
- Historical view of past approvals
- Different UI for plan vs step vs error approvals

## Implementation Tasks

### Task 1: Create Approval Types
**Files to Create:**
- `cmbagent-ui/types/approval.ts`

```typescript
// types/approval.ts

export type ApprovalCheckpointType =
  | 'after_planning'
  | 'before_step'
  | 'after_step'
  | 'on_error'
  | 'manual'
  | 'custom';

export type ApprovalAction =
  | 'approve'
  | 'reject'
  | 'modify'
  | 'skip'
  | 'retry';

export interface ApprovalRequest {
  approval_id: string;
  run_id: string;
  step_id?: string;
  checkpoint_type: ApprovalCheckpointType;
  action: string;
  description: string;
  context: ApprovalContext;
  options: ApprovalOption[];
  created_at: string;
  timeout_seconds?: number;
  required: boolean;
}

export interface ApprovalContext {
  current_step?: {
    number: number;
    description: string;
    agent: string;
  };
  previous_output?: string;
  proposed_action?: string;
  error_info?: {
    error_type: string;
    message: string;
    traceback?: string;
    retry_count?: number;
  };
  plan_summary?: string;
  affected_files?: string[];
  estimated_cost?: number;
  custom_data?: Record<string, any>;
}

export interface ApprovalOption {
  id: string;
  label: string;
  description?: string;
  action: ApprovalAction;
  is_default?: boolean;
}

export interface ApprovalResolution {
  approval_id: string;
  action: ApprovalAction;
  feedback?: string;
  resolved_at: string;
  resolved_by?: string;
}

export interface ApprovalHistoryItem {
  request: ApprovalRequest;
  resolution?: ApprovalResolution;
}
```

### Task 2: Create Enhanced Approval Dialog
**Files to Create:**
- `cmbagent-ui/components/approval/ApprovalDialog.tsx`

```typescript
// components/approval/ApprovalDialog.tsx

'use client';

import { useState, useEffect } from 'react';
import {
  X,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Edit3,
  SkipForward,
  RotateCw,
  Clock,
  FileText,
  Code,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { ApprovalRequest, ApprovalAction, ApprovalContext } from '@/types/approval';

interface ApprovalDialogProps {
  approval: ApprovalRequest;
  onSubmit: (action: ApprovalAction, feedback?: string) => void;
  onCancel?: () => void;
}

const actionIcons: Record<ApprovalAction, React.ReactNode> = {
  approve: <CheckCircle className="w-5 h-5 text-green-400" />,
  reject: <XCircle className="w-5 h-5 text-red-400" />,
  modify: <Edit3 className="w-5 h-5 text-blue-400" />,
  skip: <SkipForward className="w-5 h-5 text-yellow-400" />,
  retry: <RotateCw className="w-5 h-5 text-orange-400" />,
};

const actionColors: Record<ApprovalAction, string> = {
  approve: 'bg-green-500/20 border-green-500/30 text-green-400 hover:bg-green-500/30',
  reject: 'bg-red-500/20 border-red-500/30 text-red-400 hover:bg-red-500/30',
  modify: 'bg-blue-500/20 border-blue-500/30 text-blue-400 hover:bg-blue-500/30',
  skip: 'bg-yellow-500/20 border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/30',
  retry: 'bg-orange-500/20 border-orange-500/30 text-orange-400 hover:bg-orange-500/30',
};

function ContextSection({ title, children, defaultOpen = false }: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2 bg-gray-700/50 hover:bg-gray-700 transition-colors"
      >
        <span className="text-sm font-medium text-gray-300">{title}</span>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400" />
        )}
      </button>
      {isOpen && (
        <div className="p-4 bg-gray-800/50">
          {children}
        </div>
      )}
    </div>
  );
}

export function ApprovalDialog({ approval, onSubmit, onCancel }: ApprovalDialogProps) {
  const [selectedAction, setSelectedAction] = useState<ApprovalAction | null>(
    approval.options.find((o) => o.is_default)?.action || null
  );
  const [feedback, setFeedback] = useState('');
  const [timeRemaining, setTimeRemaining] = useState<number | null>(
    approval.timeout_seconds || null
  );

  // Countdown timer
  useEffect(() => {
    if (timeRemaining === null || timeRemaining <= 0) return;

    const interval = setInterval(() => {
      setTimeRemaining((prev) => (prev !== null ? prev - 1 : null));
    }, 1000);

    return () => clearInterval(interval);
  }, [timeRemaining]);

  const handleSubmit = () => {
    if (!selectedAction) return;
    onSubmit(selectedAction, feedback.trim() || undefined);
  };

  const isError = approval.checkpoint_type === 'on_error';
  const isPlan = approval.checkpoint_type === 'after_planning';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-hidden bg-gray-900 rounded-xl border border-gray-700 shadow-2xl">
        {/* Header */}
        <div className={`flex items-center justify-between px-6 py-4 border-b border-gray-700 ${
          isError ? 'bg-red-500/10' : isPlan ? 'bg-blue-500/10' : 'bg-purple-500/10'
        }`}>
          <div className="flex items-center space-x-3">
            {isError ? (
              <AlertTriangle className="w-6 h-6 text-red-400" />
            ) : (
              <CheckCircle className="w-6 h-6 text-purple-400" />
            )}
            <div>
              <h2 className="text-lg font-semibold text-white">
                {isError ? 'Error - Action Required' : 'Approval Required'}
              </h2>
              <p className="text-sm text-gray-400">{approval.checkpoint_type.replace('_', ' ')}</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            {timeRemaining !== null && (
              <div className="flex items-center space-x-2 text-yellow-400">
                <Clock className="w-4 h-4" />
                <span className="text-sm font-mono">
                  {Math.floor(timeRemaining / 60)}:{(timeRemaining % 60).toString().padStart(2, '0')}
                </span>
              </div>
            )}
            {onCancel && (
              <button
                onClick={onCancel}
                className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-4 overflow-y-auto max-h-[60vh] space-y-4">
          {/* Description */}
          <div>
            <p className="text-white">{approval.description}</p>
          </div>

          {/* Context Sections */}
          {approval.context.current_step && (
            <ContextSection title="Current Step" defaultOpen>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <span className="text-gray-400">Step:</span>
                  <span className="text-white">#{approval.context.current_step.number}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-gray-400">Agent:</span>
                  <span className="text-white">{approval.context.current_step.agent}</span>
                </div>
                <p className="text-gray-300">{approval.context.current_step.description}</p>
              </div>
            </ContextSection>
          )}

          {approval.context.error_info && (
            <ContextSection title="Error Details" defaultOpen>
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <span className="text-gray-400">Type:</span>
                  <span className="text-red-400">{approval.context.error_info.error_type}</span>
                </div>
                <p className="text-red-300">{approval.context.error_info.message}</p>
                {approval.context.error_info.traceback && (
                  <pre className="mt-2 p-3 bg-gray-800 rounded text-xs text-gray-400 overflow-x-auto">
                    {approval.context.error_info.traceback}
                  </pre>
                )}
              </div>
            </ContextSection>
          )}

          {approval.context.previous_output && (
            <ContextSection title="Previous Output">
              <pre className="p-3 bg-gray-800 rounded text-sm text-gray-300 overflow-x-auto whitespace-pre-wrap">
                {approval.context.previous_output}
              </pre>
            </ContextSection>
          )}

          {approval.context.proposed_action && (
            <ContextSection title="Proposed Action" defaultOpen>
              <p className="text-gray-300">{approval.context.proposed_action}</p>
            </ContextSection>
          )}

          {approval.context.plan_summary && (
            <ContextSection title="Plan Summary" defaultOpen>
              <pre className="p-3 bg-gray-800 rounded text-sm text-gray-300 overflow-x-auto whitespace-pre-wrap">
                {approval.context.plan_summary}
              </pre>
            </ContextSection>
          )}

          {/* Action Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-3">
              Select Action
            </label>
            <div className="grid grid-cols-2 gap-2">
              {approval.options.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setSelectedAction(option.action)}
                  className={`flex items-center space-x-3 p-3 rounded-lg border transition-all ${
                    selectedAction === option.action
                      ? actionColors[option.action]
                      : 'border-gray-700 hover:border-gray-600'
                  }`}
                >
                  {actionIcons[option.action]}
                  <div className="text-left">
                    <span className="block text-sm font-medium">
                      {option.label}
                    </span>
                    {option.description && (
                      <span className="block text-xs text-gray-400">
                        {option.description}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Feedback Input */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Feedback / Instructions (Optional)
            </label>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Provide any additional context or instructions..."
              className="w-full h-24 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 px-6 py-4 border-t border-gray-700 bg-gray-800/50">
          {onCancel && (
            <button
              onClick={onCancel}
              className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            onClick={handleSubmit}
            disabled={!selectedAction}
            className="px-6 py-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded-lg transition-colors"
          >
            Submit
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Task 3: Create Approval Notification Banner
**Files to Create:**
- `cmbagent-ui/components/approval/ApprovalNotification.tsx`

```typescript
// components/approval/ApprovalNotification.tsx

'use client';

import { Bell, X } from 'lucide-react';

interface ApprovalNotificationProps {
  count: number;
  onView: () => void;
  onDismiss?: () => void;
}

export function ApprovalNotification({ count, onView, onDismiss }: ApprovalNotificationProps) {
  if (count === 0) return null;

  return (
    <div className="fixed top-20 right-4 z-40 animate-slide-in-right">
      <div className="flex items-center space-x-3 px-4 py-3 bg-purple-500/20 border border-purple-500/30 rounded-lg shadow-lg backdrop-blur">
        <div className="relative">
          <Bell className="w-5 h-5 text-purple-400" />
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-purple-500 text-white text-xs font-bold rounded-full flex items-center justify-center">
            {count}
          </span>
        </div>
        <span className="text-purple-300">
          {count === 1 ? '1 approval pending' : `${count} approvals pending`}
        </span>
        <button
          onClick={onView}
          className="px-3 py-1 bg-purple-500/30 hover:bg-purple-500/50 text-purple-200 text-sm rounded transition-colors"
        >
          View
        </button>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="p-1 hover:bg-purple-500/30 rounded transition-colors"
          >
            <X className="w-4 h-4 text-purple-400" />
          </button>
        )}
      </div>
    </div>
  );
}
```

### Task 4: Create Approval Queue Component
**Files to Create:**
- `cmbagent-ui/components/approval/ApprovalQueue.tsx`

```typescript
// components/approval/ApprovalQueue.tsx

'use client';

import { Clock, AlertTriangle, CheckCircle } from 'lucide-react';
import { ApprovalRequest } from '@/types/approval';

interface ApprovalQueueProps {
  approvals: ApprovalRequest[];
  onSelectApproval: (approval: ApprovalRequest) => void;
}

const checkpointColors: Record<string, string> = {
  after_planning: 'border-l-blue-500',
  before_step: 'border-l-purple-500',
  after_step: 'border-l-purple-500',
  on_error: 'border-l-red-500',
  manual: 'border-l-yellow-500',
};

export function ApprovalQueue({ approvals, onSelectApproval }: ApprovalQueueProps) {
  if (approvals.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400">
        <CheckCircle className="w-5 h-5 mr-2" />
        <span>No pending approvals</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Pending Approvals ({approvals.length})
      </h3>
      {approvals.map((approval) => (
        <button
          key={approval.approval_id}
          onClick={() => onSelectApproval(approval)}
          className={`w-full text-left p-4 bg-gray-800/50 hover:bg-gray-800 border-l-4 rounded-r-lg transition-colors ${
            checkpointColors[approval.checkpoint_type] || 'border-l-gray-500'
          }`}
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium text-white truncate">
              {approval.action}
            </span>
            {approval.checkpoint_type === 'on_error' && (
              <AlertTriangle className="w-4 h-4 text-red-400" />
            )}
          </div>
          <p className="text-xs text-gray-400 truncate">{approval.description}</p>
          <div className="flex items-center mt-2 text-xs text-gray-500">
            <Clock className="w-3 h-3 mr-1" />
            <span>{new Date(approval.created_at).toLocaleTimeString()}</span>
          </div>
        </button>
      ))}
    </div>
  );
}
```

### Task 5: Create Approval History Component
**Files to Create:**
- `cmbagent-ui/components/approval/ApprovalHistory.tsx`

```typescript
// components/approval/ApprovalHistory.tsx

'use client';

import { CheckCircle, XCircle, Edit3, SkipForward, RotateCw, Clock } from 'lucide-react';
import { ApprovalHistoryItem, ApprovalAction } from '@/types/approval';

interface ApprovalHistoryProps {
  history: ApprovalHistoryItem[];
}

const actionIcons: Record<ApprovalAction, React.ReactNode> = {
  approve: <CheckCircle className="w-4 h-4 text-green-400" />,
  reject: <XCircle className="w-4 h-4 text-red-400" />,
  modify: <Edit3 className="w-4 h-4 text-blue-400" />,
  skip: <SkipForward className="w-4 h-4 text-yellow-400" />,
  retry: <RotateCw className="w-4 h-4 text-orange-400" />,
};

export function ApprovalHistory({ history }: ApprovalHistoryProps) {
  if (history.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400">
        <span>No approval history</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Approval History ({history.length})
      </h3>
      {history.map((item) => (
        <div
          key={item.request.approval_id}
          className="p-4 bg-gray-800/30 rounded-lg border border-gray-700"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-white">
              {item.request.action}
            </span>
            {item.resolution && (
              <div className="flex items-center space-x-1">
                {actionIcons[item.resolution.action]}
                <span className="text-xs text-gray-400 capitalize">
                  {item.resolution.action}
                </span>
              </div>
            )}
          </div>
          <p className="text-xs text-gray-400 truncate mb-2">
            {item.request.description}
          </p>
          {item.resolution?.feedback && (
            <p className="text-xs text-gray-300 italic bg-gray-700/50 p-2 rounded">
              "{item.resolution.feedback}"
            </p>
          )}
          <div className="flex items-center mt-2 text-xs text-gray-500">
            <Clock className="w-3 h-3 mr-1" />
            <span>
              {item.resolution
                ? new Date(item.resolution.resolved_at).toLocaleString()
                : new Date(item.request.created_at).toLocaleString()}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
```

### Task 6: Create Approval Index Export
**Files to Create:**
- `cmbagent-ui/components/approval/index.ts`

```typescript
// components/approval/index.ts
export { ApprovalDialog } from './ApprovalDialog';
export { ApprovalNotification } from './ApprovalNotification';
export { ApprovalQueue } from './ApprovalQueue';
export { ApprovalHistory } from './ApprovalHistory';
```

## Files to Create (Summary)

```
cmbagent-ui/
├── types/
│   └── approval.ts
└── components/
    └── approval/
        ├── index.ts
        ├── ApprovalDialog.tsx
        ├── ApprovalNotification.tsx
        ├── ApprovalQueue.tsx
        └── ApprovalHistory.tsx
```

## Verification Criteria

### Must Pass
- [ ] ApprovalDialog renders with all context sections
- [ ] Action selection works correctly
- [ ] Feedback input captures user text
- [ ] Submit button disabled until action selected
- [ ] Notification banner shows with correct count
- [ ] Queue lists multiple approvals
- [ ] History displays past resolutions

### Should Pass
- [ ] Timeout countdown works
- [ ] Context sections expand/collapse
- [ ] Error approvals highlighted
- [ ] Responsive on mobile

## Success Criteria

Stage 4 is complete when:
1. Enhanced ApprovalDialog working
2. Notification system alerts users
3. Multiple approvals queued correctly
4. History shows past decisions
5. Integration with WebSocket events works

## Next Stage

Once Stage 4 is verified complete, proceed to:
**Stage 5: Retry UI with Context Display**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-16
