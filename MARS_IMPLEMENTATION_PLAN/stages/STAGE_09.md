# Stage 9: Parallel Sessions & Progress UX

**Phase:** 3 - Parallel Sessions & Polish
**Dependencies:** Stage 7 (Sessions Screen), Stage 8 (Modals)
**Risk Level:** High

## Objectives

1. Implement Global Session Switcher in TopBar with live progress pills
2. Allow multiple sessions to run in parallel with visible progress and controls
3. Per-session menu: Pause, Resume, Cancel, View Logs, Open Workflow, Rename, Pin
4. Real-time feedback: toast notifications on state changes
5. Inline error surfaces with remediation links (e.g., "Open Console")
6. Preserve existing event streams; no backend changes - UI subscribes to current sockets/polls

## Current State Analysis

### What We Have
- Single active session model: one WebSocket connection, one `currentRunId`
- `WebSocketContext` manages a single connection with `connect()`, `disconnect()`, `sendMessage()`
- Session list shows historical sessions from `GET /api/sessions`
- No parallel execution UI
- `SessionPill` component created in Stage 7 (but not yet integrated)

### What We Need
- **Multi-session state management:** Track multiple sessions simultaneously
- **TopBar Session Pills:** Show active/paused sessions with live progress
- **Session Context:** Extended WebSocket context or separate session manager context
- **Toast notifications:** On session state changes (started, completed, failed, paused)
- **Per-session actions:** Dropdown menu on each pill

## Important Architecture Note

The backend already supports multiple sessions (each with its own WebSocket connection via `/ws/{taskId}`). The current UI limitation is that it tracks only one session at a time via `WebSocketContext`. To support parallel sessions:

**Approach:** Create a `SessionManagerContext` that wraps multiple WebSocket connections. Each session gets its own state (consoleOutput, dagData, workflowStatus, etc.). The existing `WebSocketContext` can be extended or a new parallel context can be created.

**Simpler approach (recommended for this stage):** Keep the existing `WebSocketContext` for the "primary" active session. Add a `ParallelSessionsContext` that tracks metadata (status, progress) for background sessions via periodic polling (`GET /api/sessions`). When the user switches to a background session, the primary WebSocket reconnects to that session's task.

This avoids maintaining multiple concurrent WebSocket connections while still showing parallel session progress.

## Implementation Tasks

### Task 1: Create ParallelSessionsContext
**Objective:** Track multiple sessions' status and progress

**Files to Create:**
- `contexts/ParallelSessionsContext.tsx`

**Implementation:**

```typescript
interface ParallelSession {
  sessionId: string
  name: string
  mode: string
  status: 'active' | 'paused' | 'queued' | 'completed' | 'failed'
  progress: number  // 0-100
  currentStep?: string
  startedAt?: string
  pinned?: boolean
  error?: string
}

interface ParallelSessionsContextValue {
  sessions: ParallelSession[]
  activeSessionId: string | null
  setActiveSession: (sessionId: string) => void
  addSession: (session: ParallelSession) => void
  removeSession: (sessionId: string) => void
  updateSession: (sessionId: string, updates: Partial<ParallelSession>) => void
  renameSession: (sessionId: string, name: string) => void
  pinSession: (sessionId: string) => void
  unpinSession: (sessionId: string) => void
}
```

The context:
- Polls `GET /api/sessions` every 10-15s to update background session statuses
- Listens to WebSocketContext events for the active session
- Updates progress based on step completion events
- Fires toast notifications on state transitions

### Task 2: Create SessionPillBar Component
**Objective:** TopBar session pills showing live progress

**Files to Create:**
- `components/sessions/SessionPillBar.tsx`

**Implementation:**

Renders a horizontal row of `SessionPill` components for each session in `ParallelSessionsContext.sessions`. Features:
- Scrollable if too many pills
- Active session pill is highlighted
- Each pill shows: status dot, name (truncated), progress mini-ring
- Click pill to switch active session
- Right-click or dropdown for actions (Pause, Resume, Cancel, View Logs, Rename, Pin)

### Task 3: Integrate SessionPillBar into TopBar
**Objective:** Place session pills in the TopBar center area

**Files to Modify:**
- `components/layout/TopBar.tsx`

Replace the placeholder comment `{/* SessionPillBar will be added in Stage 9 */}` with:

```tsx
<SessionPillBar />
```

### Task 4: Create Toast Container
**Objective:** Global toast notification system

**Files to Create:**
- `components/core/ToastContainer.tsx`

**Implementation:**

```tsx
'use client'

import { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { Toast } from '@/components/core'
import { ToastData } from '@/types/mars-ui'

interface ToastContextValue {
  addToast: (toast: Omit<ToastData, 'id'>) => void
  removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastData[]>([])

  const addToast = useCallback((toast: Omit<ToastData, 'id'>) => {
    const id = `toast_${Date.now()}`
    setToasts(prev => [...prev, { ...toast, id }])

    // Auto-dismiss
    const duration = toast.duration ?? 5000
    if (duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, duration)
    }
  }, [])

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      {/* Toast Stack */}
      <div
        className="fixed top-16 right-4 flex flex-col gap-2"
        style={{ zIndex: 'var(--mars-z-toast)' }}
        role="region"
        aria-label="Notifications"
      >
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            type={toast.type}
            title={toast.title}
            message={toast.message}
            onClose={() => removeToast(toast.id)}
            action={toast.action}
          />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within ToastProvider')
  return context
}
```

### Task 5: Wire Toast Notifications to Session Events
**Objective:** Show toasts when sessions change state

**Files to Modify:**
- `contexts/ParallelSessionsContext.tsx`

When session status changes:
- Session started: `{ type: 'info', title: 'Session started', message: 'Single-Pass Analysis is running' }`
- Session completed: `{ type: 'success', title: 'Session completed', message: 'Single-Pass Analysis finished', action: { label: 'View Results', onClick: () => ... } }`
- Session failed: `{ type: 'error', title: 'Session failed', message: 'Error in step 3', action: { label: 'Open Console', onClick: () => ... } }`
- Session paused: `{ type: 'warning', title: 'Session paused', message: 'Awaiting approval' }`

### Task 6: Add Toast and Session Providers
**Objective:** Integrate new providers into the provider tree

**Files to Modify:**
- `app/providers.tsx`

```tsx
import { ToastProvider } from '@/components/core/ToastContainer'
import { ParallelSessionsProvider } from '@/contexts/ParallelSessionsContext'

export function Providers({ children }: ProvidersProps) {
  return (
    <ThemeProvider>
      <WebSocketProvider>
        <ParallelSessionsProvider>
          <ToastProvider>
            {children}
          </ToastProvider>
        </ParallelSessionsProvider>
      </WebSocketProvider>
    </ThemeProvider>
  )
}
```

### Task 7: Add Telemetry Hooks
**Objective:** Basic telemetry for new UI interactions

**Files to Create:**
- `lib/telemetry.ts`

```typescript
export function trackEvent(event: string, data?: Record<string, any>) {
  // Placeholder for analytics integration
  if (typeof window !== 'undefined' && (window as any).__MARS_TELEMETRY__) {
    (window as any).__MARS_TELEMETRY__.track(event, data)
  }
  // Console log in debug mode
  if (process.env.NEXT_PUBLIC_DEBUG === 'true') {
    console.log(`[MARS Telemetry] ${event}`, data)
  }
}

// Predefined events
export const EVENTS = {
  MODAL_OPENED: 'modal_opened',
  MODAL_CLOSED: 'modal_closed',
  SESSION_LAUNCHED: 'session_launched',
  SESSION_SWITCHED: 'session_switched',
  SESSION_PAUSED: 'session_paused',
  SESSION_RESUMED: 'session_resumed',
  MODE_SELECTED: 'mode_selected',
  TASK_OPENED: 'task_opened',
  THEME_TOGGLED: 'theme_toggled',
}
```

## Files to Create (Summary)

```
contexts/
└── ParallelSessionsContext.tsx

components/
├── sessions/
│   └── SessionPillBar.tsx
└── core/
    └── ToastContainer.tsx

lib/
└── telemetry.ts
```

## Files to Modify

- `components/layout/TopBar.tsx` - Add SessionPillBar
- `app/providers.tsx` - Add Toast and ParallelSessions providers

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] TopBar shows session pills for active sessions
- [ ] Clicking a pill switches the active session
- [ ] Toast notifications appear on session state changes
- [ ] Toast auto-dismisses after duration
- [ ] Session status is updated via polling
- [ ] No new backend API calls beyond existing endpoints

### Should Pass
- [ ] Session pill shows live progress indicator
- [ ] Per-session dropdown menu works (Pause/Resume/Cancel/Rename/Pin)
- [ ] Error toasts include "Open Console" action
- [ ] Pinned sessions stay at front of pill bar
- [ ] Telemetry events fire in debug mode

## Rollback Procedure

If Stage 9 causes issues:
1. Remove SessionPillBar from TopBar
2. Remove ParallelSessionsProvider and ToastProvider from providers.tsx
3. Delete new context and components
4. Run `npm run build`

## Success Criteria

Stage 9 is complete when:
1. TopBar shows active session pills with progress
2. Session switching works
3. Toast notifications fire on state changes
4. Per-session actions are available
5. No backend changes required
6. Build passes

## Next Stage

Proceed to **Stage 10: Accessibility, Responsiveness, Performance & Polish**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
