# Stage 7: Sessions Screen

**Phase:** 2 - Screen Overhauls
**Dependencies:** Stage 4 (Core Components)
**Risk Level:** Medium

## Objectives

1. Move Sessions from the in-page tab (right panel of home page) to a dedicated `/sessions` route
2. Create `SessionScreen` component showing sessions grouped by status
3. Create `SessionCard` component for individual session entries
4. Show progress (stepper or %), duration, owner, and quick actions per session
5. Preserve all existing session functionality: resume, view logs, detail panel
6. Create `SessionPill` component for TopBar integration (used in Stage 9)

## Current State Analysis

### What We Have
- `components/SessionManager/SessionList.tsx`: Filterable session list using `GET /api/sessions`
- `components/SessionManager/SessionDetailPanel.tsx`: Multi-tab session detail view
- Sessions tab in `app/page.tsx` right panel: `rightPanelTab === 'sessions'`
- Session-related handlers in `page.tsx`:
  - `handleResumeSessionFromList()` - resumes any session mode
  - `handleViewSessionLogs()` - loads session history into console
  - `setSelectedSessionId()` - opens detail panel
- API endpoints used:
  - `GET /api/sessions` - list sessions
  - `GET /api/sessions/{id}` - session detail
  - `GET /api/sessions/{id}/history` - conversation history
  - `POST /api/sessions/{id}/resume` - resume session

### What We Need
- Dedicated `/sessions` page with full-width layout
- Sessions grouped by status: Active, Queued, Paused, Completed, Failed
- SessionCard with progress indicator, duration, mode badge, quick actions
- SessionPill for TopBar (implemented here, integrated in Stage 9)
- Session detail panel as a side drawer or inline expansion

## Pre-Stage Verification

### Check Prerequisites
1. Stage 4 complete: Core components available
2. `/sessions` route placeholder exists (from Stage 2)
3. Existing SessionManager components are intact

## Implementation Tasks

### Task 1: Create SessionCard Component
**Objective:** Rich card for session list entries

**Files to Create:**
- `components/sessions/SessionCard.tsx`

**Props:**
```typescript
interface SessionCardProps {
  session: {
    session_id: string
    name: string
    mode: string
    status: string  // 'active' | 'suspended' | 'completed' | 'failed' | 'queued' | 'paused'
    current_phase?: string
    current_step?: number
    created_at?: string
    updated_at?: string
    progress?: number  // 0-100
  }
  selected?: boolean
  onSelect: (id: string) => void
  onResume?: (id: string, mode?: string) => void
  onViewLogs?: (id: string, mode?: string) => void
  onPause?: (id: string) => void
  onCancel?: (id: string) => void
  compact?: boolean
}
```

Features:
- Status color indicator (left border or dot)
- Session name and mode badge
- Progress bar or step indicator
- Time elapsed / duration
- Quick action buttons (Resume, View Logs, Pause, Cancel)
- Selected state highlighting

### Task 2: Create SessionPill Component
**Objective:** Compact pill for TopBar session switcher

**Files to Create:**
- `components/sessions/SessionPill.tsx`

**Props:**
```typescript
interface SessionPillProps {
  sessionId: string
  name: string
  status: 'active' | 'paused' | 'queued' | 'completed' | 'failed'
  progress?: number
  active?: boolean  // Currently viewing this session
  onClick: (sessionId: string) => void
  onClose?: (sessionId: string) => void
}
```

Features:
- Compact inline pill (height ~28px)
- Status color dot
- Truncated session name
- Progress ring (small, optional)
- Close button to dismiss from bar
- Click to switch to session

### Task 3: Create SessionScreen Component
**Objective:** Full-page sessions view with grouped layout

**Files to Create:**
- `components/sessions/SessionScreen.tsx`

**Implementation:**

```tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { getApiUrl } from '@/lib/config'
import SessionCard from './SessionCard'
import { SessionDetailPanel } from '@/components/SessionManager/SessionDetailPanel'
import { EmptyState } from '@/components/core'
import { History } from 'lucide-react'

interface Session {
  session_id: string
  name: string
  mode: string
  status: string
  current_phase?: string
  current_step?: number
  created_at?: string
  updated_at?: string
}

const STATUS_GROUPS = [
  { key: 'active', label: 'Active', statuses: ['active'] },
  { key: 'queued', label: 'Queued', statuses: ['queued'] },
  { key: 'paused', label: 'Paused', statuses: ['suspended', 'paused'] },
  { key: 'completed', label: 'Completed', statuses: ['completed'] },
  { key: 'failed', label: 'Failed', statuses: ['failed'] },
]

export default function SessionScreen() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true)
      const response = await fetch(getApiUrl('/api/sessions'))
      if (!response.ok) throw new Error('Failed to fetch sessions')
      const data = await response.json()
      setSessions(data.sessions || data || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
    // Refresh every 30s
    const interval = setInterval(fetchSessions, 30000)
    return () => clearInterval(interval)
  }, [fetchSessions])

  const handleResume = async (sessionId: string, mode?: string) => {
    // Navigate to home page with session resume intent
    // This needs to integrate with the home page's handleResumeSessionFromList
    // For now, open in console view
    window.location.href = `/?resumeSession=${sessionId}`
  }

  const handleViewLogs = async (sessionId: string) => {
    // Open console modal with session logs (Stage 8 integration)
    setSelectedSessionId(sessionId)
  }

  const groupedSessions = STATUS_GROUPS.map((group) => ({
    ...group,
    sessions: sessions.filter((s) => group.statuses.includes(s.status)),
  })).filter((group) => group.sessions.length > 0)

  return (
    <div className="flex h-full">
      {/* Session List */}
      <div className={`${selectedSessionId ? 'w-1/2 border-r' : 'w-full'} p-6 overflow-y-auto`}
        style={{ borderColor: 'var(--mars-color-border)' }}
      >
        <div className="max-w-4xl mx-auto">
          <div className="mb-6">
            <h2 className="text-2xl font-semibold" style={{ color: 'var(--mars-color-text)' }}>
              Sessions
            </h2>
            <p className="text-sm mt-1" style={{ color: 'var(--mars-color-text-secondary)' }}>
              {sessions.length} total sessions
            </p>
          </div>

          {loading ? (
            <div>Loading sessions...</div>
          ) : error ? (
            <div style={{ color: 'var(--mars-color-danger)' }}>Error: {error}</div>
          ) : groupedSessions.length === 0 ? (
            <EmptyState
              icon={<History className="w-12 h-12" />}
              title="No active sessions"
              description="Launch a new workflow from the Modes screen to create a session."
              action={{ label: 'Go to Modes', onClick: () => window.location.href = '/' }}
            />
          ) : (
            <div className="space-y-8">
              {groupedSessions.map((group) => (
                <div key={group.key}>
                  <h3 className="text-sm font-medium uppercase tracking-wider mb-3"
                    style={{ color: 'var(--mars-color-text-tertiary)' }}
                  >
                    {group.label} ({group.sessions.length})
                  </h3>
                  <div className="space-y-2">
                    {group.sessions.map((session) => (
                      <SessionCard
                        key={session.session_id}
                        session={session}
                        selected={selectedSessionId === session.session_id}
                        onSelect={setSelectedSessionId}
                        onResume={handleResume}
                        onViewLogs={handleViewLogs}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Detail Panel */}
      {selectedSessionId && (
        <div className="w-1/2 h-full overflow-hidden">
          <SessionDetailPanel
            sessionId={selectedSessionId}
            onClose={() => setSelectedSessionId(null)}
            onResume={handleResume}
          />
        </div>
      )}
    </div>
  )
}
```

### Task 4: Update `/sessions` Route
**Objective:** Replace placeholder with SessionScreen

**Files to Modify:**
- `app/sessions/page.tsx`

```tsx
'use client'

import SessionScreen from '@/components/sessions/SessionScreen'

export default function SessionsPage() {
  return <SessionScreen />
}
```

### Task 5: Remove Sessions Tab from Home Page
**Objective:** Sessions are now a dedicated route, remove from right panel

**Files to Modify:**
- `app/page.tsx`

**Changes:**
- Remove `'sessions'` from `rightPanelTab` type
- Remove the Sessions tab button
- Remove the Sessions tab content
- Remove `selectedSessionId` state (moved to SessionScreen)
- Keep session-related handlers (handleResumeSessionFromList, handleViewSessionLogs) for now since they may be called from SessionScreen via router

**Verification:**
- [ ] Sessions tab no longer appears in home page right panel
- [ ] `/sessions` route shows the full SessionScreen
- [ ] Session list loads from API
- [ ] Session detail panel opens on click
- [ ] Session resume functionality works

### Task 6: Barrel Export Update
**Files to Modify:**
- `components/sessions/index.ts` (or create if not exists)

## Files to Create (Summary)

```
components/sessions/
├── SessionScreen.tsx
├── SessionCard.tsx
└── SessionPill.tsx
```

## Files to Modify

- `app/sessions/page.tsx` - Import SessionScreen
- `app/page.tsx` - Remove Sessions tab from right panel

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] `/sessions` route shows grouped session list
- [ ] Session list loads from `GET /api/sessions`
- [ ] Sessions are grouped by Active/Queued/Paused/Completed/Failed
- [ ] Session detail panel opens when selecting a session
- [ ] Sessions tab is removed from home page right panel
- [ ] Empty state shows when no sessions exist

### Should Pass
- [ ] SessionCard shows status indicator, mode badge, timestamps
- [ ] Resume action works from session list
- [ ] View Logs action opens session history
- [ ] Auto-refresh updates session list
- [ ] SessionPill component renders correctly (for Stage 9 use)

## Rollback Procedure

If Stage 7 causes issues:
1. Revert `app/sessions/page.tsx` to placeholder
2. Restore Sessions tab in `app/page.tsx`
3. Delete new session components
4. Run `npm run build`

## Success Criteria

Stage 7 is complete when:
1. Sessions has its own dedicated screen at `/sessions`
2. Sessions are grouped by status
3. Session detail panel works
4. Sessions tab removed from home page
5. All session API interactions preserved
6. Build passes

## Next Stage

Proceed to **Stage 8: Console & Workflow Modals**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
