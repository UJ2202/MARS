# Stage 8: Console & Workflow Modals

**Phase:** 2 - Screen Overhauls
**Dependencies:** Stage 4 (Core Components - Modal), Stage 5 (Modes restructure)
**Risk Level:** High

## Objectives

1. Extract ConsoleOutput into a global `ConsoleModal` accessible from any screen via TopBar
2. Extract WorkflowDashboard into a global `WorkflowModal` accessible from any screen via TopBar
3. Both modals use the base Modal component from Stage 4
4. Modals are non-blocking, draggable, resizable, and keyboard-accessible
5. Console Modal supports: level filtering, search, auto-scroll, copy, download, clear
6. Workflow Modal supports: DAG visualization, execution timeline, controls
7. State piping: modals read from existing WebSocketContext state (no new data needed)
8. Feature flags for phased rollout

## Current State Analysis

### What We Have
- `ConsoleOutput.tsx`: Renders `consoleOutput[]` state from WebSocketContext with auto-scroll, clear, and running indicator
- `WorkflowDashboard.tsx`: Comprehensive workflow view with DAG, timeline, history, files, costs, and branch management
- Both are currently embedded as tabs in the right panel of `app/page.tsx`
- `AppShell.tsx` (from Stage 2) has placeholder comments for modal rendering
- `TopBar.tsx` (from Stage 2) has console and workflow icon buttons with `onOpenConsole`/`onOpenWorkflow` callbacks

### What We Need
- `ConsoleModal` wrapping ConsoleOutput with filter bar
- `WorkflowModal` wrapping WorkflowDashboard
- Both mounted at AppShell level (outside page content)
- Both receiving state from WebSocketContext
- TopBar buttons toggle modals open/close
- Contextual triggers (e.g., "View Logs" in Sessions) also open ConsoleModal

## Pre-Stage Verification

### Check Prerequisites
1. Stage 4 Modal component exists and works (focus trap, drag, resize, Esc)
2. ConsoleOutput and WorkflowDashboard render correctly
3. TopBar has onOpenConsole and onOpenWorkflow callbacks
4. AppShell's state includes consoleOpen and workflowOpen

## Implementation Tasks

### Task 1: Create ConsoleModal
**Objective:** Global console overlay with filtering and controls

**Files to Create:**
- `components/modals/ConsoleModal.tsx`

**Implementation:**

```tsx
'use client'

import { useState, useCallback, useMemo } from 'react'
import { Modal } from '@/components/core'
import ConsoleOutput from '@/components/ConsoleOutput'
import { useWebSocketContext } from '@/contexts/WebSocketContext'
import { Search, Download, Trash2, ArrowDown } from 'lucide-react'

interface ConsoleModalProps {
  open: boolean
  onClose: () => void
}

type LogLevel = 'all' | 'info' | 'warning' | 'error'

export default function ConsoleModal({ open, onClose }: ConsoleModalProps) {
  const { consoleOutput, isRunning, clearConsole } = useWebSocketContext()
  const [filterLevel, setFilterLevel] = useState<LogLevel>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)

  const filteredOutput = useMemo(() => {
    let output = consoleOutput

    // Filter by level (text-based matching only, no emoji matching)
    if (filterLevel !== 'all') {
      output = output.filter((line) => {
        const lower = line.toLowerCase()
        switch (filterLevel) {
          case 'error': return lower.includes('error') || lower.includes('failed') || lower.includes('exception')
          case 'warning': return lower.includes('warning') || lower.includes('warn')
          case 'info': return !lower.includes('error') && !lower.includes('warning') && !lower.includes('failed')
          default: return true
        }
      })
    }

    // Filter by search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      output = output.filter((line) => line.toLowerCase().includes(q))
    }

    return output
  }, [consoleOutput, filterLevel, searchQuery])

  const handleCopyAll = useCallback(() => {
    navigator.clipboard.writeText(filteredOutput.join('\n'))
  }, [filteredOutput])

  const handleDownload = useCallback(() => {
    const blob = new Blob([filteredOutput.join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mars-console-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }, [filteredOutput])

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Console"
      size="lg"
      draggable
      resizable
    >
      {/* Filter Bar */}
      <div className="flex items-center gap-2 p-3 border-b"
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        {/* Level Filter */}
        <div className="flex items-center gap-1 rounded-mars-md p-0.5"
          style={{ backgroundColor: 'var(--mars-color-surface-overlay)' }}
        >
          {(['all', 'info', 'warning', 'error'] as LogLevel[]).map((level) => (
            <button
              key={level}
              onClick={() => setFilterLevel(level)}
              className={`px-2 py-1 text-xs rounded-mars-sm capitalize transition-colors ${
                filterLevel === level
                  ? 'bg-[var(--mars-color-primary)] text-white'
                  : 'text-[var(--mars-color-text-secondary)] hover:text-[var(--mars-color-text)]'
              }`}
            >
              {level}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="flex-1 relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          />
          <input
            type="text"
            placeholder="Search logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-mars-sm border"
            style={{
              backgroundColor: 'var(--mars-color-surface)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
          />
        </div>

        {/* Actions */}
        <button onClick={handleCopyAll} title="Copy all" className="p-1.5 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)]">
          <span className="text-xs" style={{ color: 'var(--mars-color-text-secondary)' }}>Copy</span>
        </button>
        <button onClick={handleDownload} title="Download logs" className="p-1.5 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)]">
          <Download className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-text-secondary)' }} />
        </button>
        <button onClick={clearConsole} title="Clear console" className="p-1.5 rounded-mars-sm hover:bg-[var(--mars-color-bg-hover)]">
          <Trash2 className="w-3.5 h-3.5" style={{ color: 'var(--mars-color-text-secondary)' }} />
        </button>
        <button
          onClick={() => setAutoScroll(!autoScroll)}
          title={autoScroll ? 'Auto-scroll on' : 'Auto-scroll off'}
          className={`p-1.5 rounded-mars-sm ${autoScroll ? 'bg-[var(--mars-color-primary-subtle)]' : 'hover:bg-[var(--mars-color-bg-hover)]'}`}
        >
          <ArrowDown className="w-3.5 h-3.5" style={{ color: autoScroll ? 'var(--mars-color-primary)' : 'var(--mars-color-text-secondary)' }} />
        </button>
      </div>

      {/* Console Content */}
      <div className="flex-1 min-h-0 overflow-hidden"
        style={{ backgroundColor: 'var(--mars-color-console-bg)' }}
      >
        <ConsoleOutput
          output={filteredOutput}
          isRunning={isRunning}
          onClear={clearConsole}
        />
      </div>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-3 py-1.5 text-xs border-t"
        style={{
          borderColor: 'var(--mars-color-border)',
          color: 'var(--mars-color-text-tertiary)',
        }}
      >
        <span>{filteredOutput.length} lines {filterLevel !== 'all' ? `(${filterLevel} filter)` : ''}</span>
        {isRunning && (
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: 'var(--mars-color-success)' }} />
            Live
          </span>
        )}
      </div>
    </Modal>
  )
}
```

### Task 2: Refactor ConsoleOutput to Replace Emojis with Lucide Icons
**Objective:** Replace all emoji status prefix rendering in ConsoleOutput with Lucide icon components

**Files to Modify:**
- `components/ConsoleOutput.tsx`

**Current State:** Console lines are prefixed with emoji characters for status:
- Errors: `❌` prefix
- Warnings: `⚠️` prefix
- Success: `✅` prefix

**Changes:**
Replace emoji prefixes with inline Lucide icon components:

```tsx
import { XCircle, AlertTriangle, CheckCircle, Info } from 'lucide-react'

// Replace emoji prefix logic with icon rendering:
// Error lines:   <XCircle className="w-3.5 h-3.5 inline-block mr-1.5" style={{ color: 'var(--mars-color-danger)' }} />
// Warning lines: <AlertTriangle className="w-3.5 h-3.5 inline-block mr-1.5" style={{ color: 'var(--mars-color-warning)' }} />
// Success lines: <CheckCircle className="w-3.5 h-3.5 inline-block mr-1.5" style={{ color: 'var(--mars-color-success)' }} />
// Info lines:    <Info className="w-3.5 h-3.5 inline-block mr-1.5" style={{ color: 'var(--mars-color-info)' }} />
```

Remove all emoji character literals (`❌`, `⚠️`, `✅`, `🔄`, etc.) from the rendering logic. The backend may still send lines containing emojis in the text payload; those should be stripped or left as-is in the raw text, but the UI prefix rendering must use Lucide icons exclusively.

**Verification:**
- [ ] No emoji characters are rendered by ConsoleOutput
- [ ] Status prefixes display as Lucide SVG icons
- [ ] Icon colors match MARS design tokens (danger, warning, success, info)
- [ ] Console readability is maintained

### Task 3: Create WorkflowModal
**Objective:** Global workflow overlay with DAG, timeline, controls

**Files to Create:**
- `components/modals/WorkflowModal.tsx`

**Implementation:**

```tsx
'use client'

import { Modal } from '@/components/core'
import { WorkflowDashboard } from '@/components/workflow'
import { useWebSocketContext } from '@/contexts/WebSocketContext'

interface WorkflowModalProps {
  open: boolean
  onClose: () => void
  // These handlers are passed from the page that owns the workflow state
  onPause?: () => void
  onResume?: () => void
  onCancel?: () => void
  onPlayFromNode?: (nodeId: string) => void
  // Additional workflow props
  elapsedTime?: string
  branches?: any[]
  currentBranchId?: string
  workflowHistory?: any[]
  onCreateBranch?: (...args: any[]) => void
  onSelectBranch?: (id: string) => void
  onViewBranch?: (id: string) => void
  onCompareBranches?: (a: string, b: string) => void
  onViewWorkflow?: (w: any) => void
  onResumeWorkflow?: (w: any) => void
  onBranchWorkflow?: (w: any) => void
}

export default function WorkflowModal({
  open,
  onClose,
  onPause,
  onResume,
  onCancel,
  onPlayFromNode,
  elapsedTime = '0:00',
  branches = [],
  currentBranchId,
  workflowHistory = [],
  onCreateBranch,
  onSelectBranch,
  onViewBranch,
  onCompareBranches,
  onViewWorkflow,
  onResumeWorkflow,
  onBranchWorkflow,
}: WorkflowModalProps) {
  const {
    workflowStatus,
    isRunning,
    dagData,
    costSummary,
    costTimeSeries,
    filesUpdatedCounter,
  } = useWebSocketContext()

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Workflow"
      size="xl"
      draggable
      resizable
    >
      <div className="h-[600px] overflow-hidden">
        <WorkflowDashboard
          status={workflowStatus || (isRunning ? 'executing' : 'draft')}
          dagData={dagData}
          elapsedTime={elapsedTime}
          branches={branches}
          currentBranchId={currentBranchId}
          workflowHistory={workflowHistory}
          costSummary={costSummary}
          costTimeSeries={costTimeSeries}
          filesUpdatedCounter={filesUpdatedCounter}
          onPause={onPause || (() => {})}
          onResume={onResume || (() => {})}
          onCancel={onCancel || (() => {})}
          onPlayFromNode={onPlayFromNode || (() => {})}
          onCreateBranch={onCreateBranch || (() => {})}
          onSelectBranch={onSelectBranch || (() => {})}
          onViewBranch={onViewBranch || (() => {})}
          onCompareBranches={onCompareBranches || (() => {})}
          onViewWorkflow={onViewWorkflow || (() => {})}
          onResumeWorkflow={onResumeWorkflow || (() => {})}
          onBranchWorkflow={onBranchWorkflow || (() => {})}
        />
      </div>
    </Modal>
  )
}
```

### Task 4: Integrate Modals into AppShell
**Objective:** Mount modals at the AppShell level so they're available on all pages

**Files to Modify:**
- `components/layout/AppShell.tsx`

**Changes:**

```tsx
import ConsoleModal from '@/components/modals/ConsoleModal'
import WorkflowModal from '@/components/modals/WorkflowModal'

// In the return, after the main content area:
<ConsoleModal
  open={consoleOpen}
  onClose={() => setConsoleOpen(false)}
/>
<WorkflowModal
  open={workflowOpen}
  onClose={() => setWorkflowOpen(false)}
/>
```

**Note on State:** The WorkflowModal needs handler callbacks (onPause, onResume, etc.) that currently live in `page.tsx`. There are two approaches:

**Approach A (Recommended):** Lift workflow action handlers to a context or keep them in page.tsx and pass them through AppShell via context/callbacks.

**Approach B:** WorkflowModal reads state from WebSocketContext (already done) but provides its own action buttons that call `sendMessage()` directly from the context.

The recommended approach for this stage is **Approach B** - the WorkflowModal can call `sendMessage()` from WebSocketContext for pause/resume/cancel since these are simple message sends. The complex handlers (branching, play from node) can be stubbed and enhanced later.

### Task 5: Update Page Components
**Objective:** Remove inline Console and Workflow from page tabs since they're now modals

**Files to Modify:**
- `app/page.tsx`

**Changes:**

In the run view (when a mode is selected), the right panel previously showed Console, Workflow, Results, Sessions tabs. After Stage 5 (Results removed) and Stage 7 (Sessions removed), only Console and Workflow remain.

Now with Stage 8, these are also modals. The right panel in run view becomes:
- A simplified information display showing the currently active task status
- Or the right panel is removed entirely, with the TaskInput taking full width

**Strategy:** Keep the Console tab inline in the run view as a compact view, but also allow opening the full ConsoleModal. The Workflow tab in the run view can be replaced with a "Open Workflow" button that opens the modal.

This provides both inline and modal access patterns.

**Verification:**
- [ ] Console Modal opens from TopBar icon
- [ ] Workflow Modal opens from TopBar icon
- [ ] Both modals show correct live data from WebSocketContext
- [ ] Modals can be opened from any page (/, /tasks, /sessions)
- [ ] Modals are draggable and resizable
- [ ] Esc closes modals
- [ ] Focus returns to trigger after close
- [ ] Background app remains interactive (non-blocking)

### Task 6: Feature Flags
**Objective:** Allow phased rollout of modals

**Files to Create or Modify:**
- `lib/features.ts` (new)

```typescript
export const FEATURES = {
  CONSOLE_MODAL: true,   // Set to false to revert to inline
  WORKFLOW_MODAL: true,  // Set to false to revert to inline
}
```

Use these flags in AppShell to conditionally render modals.

## Files to Create (Summary)

```
components/modals/
├── ConsoleModal.tsx
└── WorkflowModal.tsx

lib/
└── features.ts
```

## Files to Modify

- `components/layout/AppShell.tsx` - Mount modals
- `app/page.tsx` - Adjust right panel (optional: keep inline Console + add modal triggers)

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] Console Modal shows all console output from WebSocketContext
- [ ] Workflow Modal shows DAG/timeline from WebSocketContext
- [ ] Both modals accessible from TopBar on every page
- [ ] Modals are draggable (header) and resizable (edges)
- [ ] Esc closes modal, focus returns to trigger
- [ ] Background app is not blocked
- [ ] Console filter (level + search) works
- [ ] Console copy and download work

### Should Pass
- [ ] Console auto-scroll toggle works
- [ ] Console shows line count and live indicator
- [ ] Workflow Modal shows correct status (executing/paused/completed)
- [ ] Modal size presets work (lg for Console, xl for Workflow)
- [ ] Feature flags can disable modals

## Common Issues and Solutions

### Issue 1: WebSocket State Not Available in Modal
**Symptom:** ConsoleModal shows empty output
**Solution:** Ensure modals are rendered inside the `WebSocketProvider` tree. Since AppShell is inside Providers (which includes WebSocketProvider), this should work. Verify the context is available.

### Issue 2: WorkflowDashboard Sizing
**Symptom:** DAG visualization doesn't render properly in modal
**Solution:** XYFlow (ReactFlow) requires a container with explicit height. Set `h-[600px]` or similar on the modal content wrapper. The DAG component may need `resize` event handling.

### Issue 3: Multiple Modals Overlapping
**Symptom:** Console and Workflow modals stack incorrectly
**Solution:** Both use `--mars-z-modal`. When both are open, the last-opened should be on top. Track z-index incrementally or bring-to-front on click.

## Rollback Procedure

If Stage 8 causes issues:
1. Remove modal imports from AppShell
2. Restore Console and Workflow tabs in page.tsx right panel
3. Delete `components/modals/` directory
4. Delete `lib/features.ts`
5. Run `npm run build`

## Success Criteria

Stage 8 is complete when:
1. Console Modal works globally from TopBar
2. Workflow Modal works globally from TopBar
3. Both use base Modal component (drag, resize, keyboard)
4. Live data from WebSocket streams into modals
5. Feature flags allow disabling modals
6. Build passes

## Next Stage

Proceed to **Stage 9: Parallel Sessions & Progress UX**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
