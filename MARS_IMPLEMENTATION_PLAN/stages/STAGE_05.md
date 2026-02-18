# Stage 5: Modes Gallery Redesign

**Phase:** 2 - Screen Overhauls
**Dependencies:** Stage 4 (Core Components)
**Risk Level:** High

## Objectives

1. Convert the current home page (`app/page.tsx`) from a task submission form with right-panel tabs into a visual ModeCard gallery
2. Create `ModeGallery` and `ModeCard` components in `components/modes/`
3. Update mode display names with punchy, memorable branding (Quickfire, Pathfinder, Spark Lab, etc.) — NOT domain tasks
4. Remove the Results tab from the right panel (content remains accessible in context)
5. Preserve ALL existing task submission, console, workflow, copilot, approval, and session-resumption functionality
6. ModeCards should show title, description, tags, primary CTA, and hover micro-interactions

## Current State Analysis

### What We Have
- `app/page.tsx` (940 lines): Monolithic page component with:
  - TaskInput on the left (task submission form with mode selection, model config)
  - Right panel tabs: Console, Workflow, Results, Sessions
  - Copilot mode layout (2/3 chat + 1/3 workflow/results)
  - All handler functions (submit, pause, resume, cancel, approvals, branches, sessions)
  - All state management (rightPanelTab, copilot, branches, sessions, elapsed time)

### What We Need
- Default view: ModeCard gallery grid showing available execution modes
- When a mode is selected: transition to the run view (TaskInput + Console/Workflow)
- Results tab removed (ResultDisplay can be shown contextually within workflow modal or inline)
- Mode display names that reflect the **execution capability/pattern**, NOT specific domain tasks

### Modes vs Tasks: Critical Distinction

**Modes** are execution patterns that showcase what the system can do — they define *how* the AI agent operates:
- Direct single-pass execution, multi-step planning, interactive collaboration, etc.
- Each mode is a distinct algorithmic/workflow strategy
- Modes are selected as the "engine" for any given run

**Tasks** (implemented in Stage 6) are domain-specific workflows that *use* a mode:
- "Product Analysis", "Competitive Landscape Review", "Weekly AI Report" are tasks, NOT modes
- Tasks bundle a mode + configuration + domain context
- Tasks share core components (Console, Workspace, Workflow, etc.) with modes
- Different tasks can use the same mode with different configurations

### Updated Mode Display Names

These names describe the **execution capability** in professional, enterprise-appropriate language:

  1. Single-Pass Analysis (backend: `one-shot`) — Execute a single analytical pass on the input without iterative planning
  2. Multi-Step Research (backend: `planning-control`) — Break down complex queries into coordinated steps with planning and control flow
  3. Hypothesis Generation (backend: `idea-generation`) — Systematically generate, evaluate, and rank multiple hypotheses
  4. Document Extraction (backend: `ocr`) — Extract structured text and data from documents and images via OCR
  5. Literature Review (backend: `arxiv`) — Retrieve and analyze academic papers and research publications
  6. Input Enrichment (backend: `enhance-input`) — Augment raw input with OCR, summarization, and multi-source context before processing
  7. Human-in-the-Loop (backend: `hitl-interactive`) — Guided workflow with approval checkpoints at each decision point
  8. Copilot Chat (backend: `copilot`) — Interactive conversational interface for iterative, open-ended queries

**CRITICAL:** The mode IDs sent to the backend (`one-shot`, `planning-control`, etc.) must NOT change. Only the display names change.

## Pre-Stage Verification

### Check Prerequisites
1. Stage 4 complete: Core components available
2. AppShell is rendering
3. Build passes

## Implementation Tasks

### Task 1: Create Mode Configuration Map
**Objective:** Define the mapping between display names and backend mode IDs

**Files to Create:**
- `lib/modes.ts`

**Implementation:**

```typescript
// lib/modes.ts

export interface ModeConfig {
  id: string                  // Backend mode ID (DO NOT CHANGE)
  displayName: string         // New MARS display name
  description: string         // User-facing description
  tags: string[]              // Categorization tags
  icon: string                // Lucide icon name
  color: string               // Gradient or accent color
  quickStats?: string         // Optional quick stat
}

export const MARS_MODES: ModeConfig[] = [
  {
    id: 'one-shot',
    displayName: 'Single-Pass Analysis',
    description: 'Execute a single analytical pass on the input without iterative planning. Suitable for well-defined queries with clear scope.',
    tags: ['Analysis', 'Direct'],
    icon: 'Zap',
    color: 'from-blue-500 to-cyan-500',
  },
  {
    id: 'planning-control',
    displayName: 'Multi-Step Research',
    description: 'Break down complex queries into coordinated steps with planning and control flow. Each stage builds on prior results.',
    tags: ['Planning', 'Multi-step'],
    icon: 'Map',
    color: 'from-purple-500 to-indigo-500',
  },
  {
    id: 'idea-generation',
    displayName: 'Hypothesis Generation',
    description: 'Systematically generate, evaluate, and rank multiple hypotheses. Compare alternatives against defined criteria.',
    tags: ['Hypothesis', 'Evaluation'],
    icon: 'Lightbulb',
    color: 'from-amber-500 to-orange-500',
  },
  {
    id: 'ocr',
    displayName: 'Document Extraction',
    description: 'Extract structured text and data from documents and images via OCR. Convert unstructured content into processable output.',
    tags: ['OCR', 'Extraction'],
    icon: 'FileText',
    color: 'from-teal-500 to-green-500',
  },
  {
    id: 'arxiv',
    displayName: 'Literature Review',
    description: 'Retrieve and analyze academic papers and research publications. Identify key findings, methods, and citations.',
    tags: ['Research', 'Academic'],
    icon: 'BookOpen',
    color: 'from-rose-500 to-pink-500',
  },
  {
    id: 'enhance-input',
    displayName: 'Input Enrichment',
    description: 'Augment raw input with OCR, summarization, and multi-source context before processing. Improves downstream analysis quality.',
    tags: ['Enrichment', 'Pre-processing'],
    icon: 'Layers',
    color: 'from-sky-500 to-blue-500',
  },
  {
    id: 'hitl-interactive',
    displayName: 'Human-in-the-Loop',
    description: 'Guided workflow with approval checkpoints at each decision point. Review and steer agent actions before they execute.',
    tags: ['Approval', 'Guided'],
    icon: 'Users',
    color: 'from-emerald-500 to-teal-500',
  },
  {
    id: 'copilot',
    displayName: 'Copilot Chat',
    description: 'Interactive conversational interface for iterative, open-ended queries. Back-and-forth dialogue with persistent context.',
    tags: ['Conversational', 'Iterative'],
    icon: 'MessageSquare',
    color: 'from-violet-500 to-purple-500',
  },
]

export function getModeConfig(modeId: string): ModeConfig | undefined {
  return MARS_MODES.find(m => m.id === modeId)
}

export function getModeDisplayName(modeId: string): string {
  return getModeConfig(modeId)?.displayName || modeId
}
```

**Verification:**
- [ ] All 8 backend mode IDs are preserved
- [ ] Display names are unique and descriptive
- [ ] `getModeConfig()` returns correct config for each mode ID

### Task 2: Create ModeCard Component
**Objective:** Visual card for each execution mode

**Files to Create:**
- `components/modes/ModeCard.tsx`

**Implementation:**

```tsx
'use client'

import { ModeConfig } from '@/lib/modes'
import { Badge, Tag } from '@/components/core'
import * as LucideIcons from 'lucide-react'

interface ModeCardProps {
  mode: ModeConfig
  onLaunch: (modeId: string) => void
  onConfigure?: (modeId: string) => void
}

export default function ModeCard({ mode, onLaunch, onConfigure }: ModeCardProps) {
  // Dynamically get icon component
  const Icon = (LucideIcons as any)[mode.icon] || LucideIcons.Box

  return (
    <div
      className="group relative overflow-hidden rounded-mars-lg border transition-all duration-mars-normal
        hover:shadow-mars-lg hover:scale-[1.02] hover:border-[var(--mars-color-border-strong)]
        cursor-pointer"
      style={{
        backgroundColor: 'var(--mars-color-surface-raised)',
        borderColor: 'var(--mars-color-border)',
      }}
      onClick={() => onLaunch(mode.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onLaunch(mode.id)
        }
      }}
      aria-label={`Launch ${mode.displayName}`}
    >
      {/* Gradient overlay on hover */}
      <div
        className={`absolute inset-0 bg-gradient-to-br ${mode.color} opacity-0 group-hover:opacity-5 transition-opacity duration-mars-normal`}
      />

      <div className="relative p-6">
        {/* Icon */}
        <div
          className={`w-12 h-12 rounded-mars-md bg-gradient-to-br ${mode.color} flex items-center justify-center mb-4
            group-hover:scale-110 transition-transform duration-mars-normal`}
        >
          <Icon className="w-6 h-6 text-white" />
        </div>

        {/* Title */}
        <h3
          className="text-lg font-semibold mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          {mode.displayName}
        </h3>

        {/* Description */}
        <p
          className="text-sm mb-4 line-clamp-2"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          {mode.description}
        </p>

        {/* Tags */}
        <div className="flex flex-wrap gap-2 mb-4">
          {mode.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 text-xs rounded-mars-sm"
              style={{
                backgroundColor: 'var(--mars-color-primary-subtle)',
                color: 'var(--mars-color-primary-text)',
              }}
            >
              {tag}
            </span>
          ))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <button
            className="text-sm font-medium px-4 py-2 rounded-mars-md transition-colors duration-mars-fast"
            style={{
              backgroundColor: 'var(--mars-color-primary)',
              color: 'white',
            }}
            onClick={(e) => {
              e.stopPropagation()
              onLaunch(mode.id)
            }}
          >
            Launch
          </button>
          {onConfigure && (
            <button
              className="text-sm px-3 py-2 rounded-mars-md transition-colors duration-mars-fast
                hover:bg-[var(--mars-color-bg-hover)]"
              style={{ color: 'var(--mars-color-text-secondary)' }}
              onClick={(e) => {
                e.stopPropagation()
                onConfigure(mode.id)
              }}
            >
              Configure
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
```

### Task 3: Create ModeGallery Component
**Objective:** Grid container for ModeCards with search/filter

**Files to Create:**
- `components/modes/ModeGallery.tsx`
- `components/modes/index.ts`

**ModeGallery Implementation:**

```tsx
'use client'

import { useState, useMemo } from 'react'
import { Search } from 'lucide-react'
import { MARS_MODES, ModeConfig } from '@/lib/modes'
import ModeCard from './ModeCard'
import { EmptyState } from '@/components/core'

interface ModeGalleryProps {
  onLaunchMode: (modeId: string) => void
  onConfigureMode?: (modeId: string) => void
}

export default function ModeGallery({ onLaunchMode, onConfigureMode }: ModeGalleryProps) {
  const [searchQuery, setSearchQuery] = useState('')

  const filteredModes = useMemo(() => {
    if (!searchQuery.trim()) return MARS_MODES
    const q = searchQuery.toLowerCase()
    return MARS_MODES.filter(
      (m) =>
        m.displayName.toLowerCase().includes(q) ||
        m.description.toLowerCase().includes(q) ||
        m.tags.some((t) => t.toLowerCase().includes(q))
    )
  }, [searchQuery])

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h2
          className="text-3xl font-bold mb-2"
          style={{ color: 'var(--mars-color-text)' }}
        >
          Modes
        </h2>
        <p
          className="text-base mb-6"
          style={{ color: 'var(--mars-color-text-secondary)' }}
        >
          Select an execution mode to start a new workflow
        </p>

        {/* Search */}
        <div className="relative max-w-md">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          />
          <input
            type="text"
            placeholder="Search modes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-mars-md border text-sm
              focus:outline-none focus:ring-2 focus:ring-[var(--mars-color-primary)]"
            style={{
              backgroundColor: 'var(--mars-color-surface-raised)',
              borderColor: 'var(--mars-color-border)',
              color: 'var(--mars-color-text)',
            }}
          />
        </div>
      </div>

      {/* Grid */}
      {filteredModes.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredModes.map((mode) => (
            <ModeCard
              key={mode.id}
              mode={mode}
              onLaunch={onLaunchMode}
              onConfigure={onConfigureMode}
            />
          ))}
        </div>
      ) : (
        <EmptyState
          title="No modes found"
          description={`No modes match "${searchQuery}". Try a different search term.`}
          action={{
            label: 'Clear search',
            onClick: () => setSearchQuery(''),
          }}
        />
      )}
    </div>
  )
}
```

### Task 4: Restructure `app/page.tsx`
**Objective:** Add ModeGallery as the default view; show run view when a mode is selected

**Files to Modify:**
- `app/page.tsx`

**Strategy:**

The current `page.tsx` is a monolithic 940-line component. The restructuring approach:

1. Add a `selectedMode` state. When `null`, show ModeGallery. When set, show the run view.
2. The run view retains ALL existing functionality (TaskInput, Console, Workflow, Sessions tabs, copilot mode, approval handling).
3. Remove the "Results" tab from the right panel tab bar. ResultDisplay can be accessed via the workflow view or as needed.
4. Add a "Back to Modes" button in the run view.
5. **Pre-set the mode in TaskInput** when launched from ModeCard.

**Changes (conceptual):**

```tsx
// Add state
const [selectedMode, setSelectedMode] = useState<string | null>(null)

// In the return:
{selectedMode === null ? (
  <ModeGallery
    onLaunchMode={(modeId) => setSelectedMode(modeId)}
    onConfigureMode={(modeId) => setSelectedMode(modeId)}
  />
) : (
  <div className="h-full flex flex-col">
    {/* Back button */}
    <div className="px-4 py-2 border-b" style={{ borderColor: 'var(--mars-color-border)' }}>
      <button onClick={() => setSelectedMode(null)}>
        ← Back to Modes
      </button>
      <span>{getModeDisplayName(selectedMode)}</span>
    </div>

    {/* Existing run view (TaskInput + Console/Workflow/Sessions) */}
    {/* ... all existing JSX ... */}
  </div>
)}
```

**Important preservations:**
- All `handle*` functions remain unchanged
- All state variables remain unchanged
- TaskInput receives `defaultMode={selectedMode}` prop
- Console, Workflow, Sessions tabs remain (Results tab removed)
- Copilot mode layout remains unchanged
- Approval and branch handlers remain unchanged

**Tab changes:**
- Remove the `results` option from `rightPanelTab`
- Remove the Results tab button from the tab bar
- Remove the Results tab content rendering
- The ResultDisplay component stays importable for use in WorkflowModal (Stage 8)

**Verification:**
- [ ] Default view shows ModeGallery with 8 mode cards
- [ ] Clicking a ModeCard switches to run view with that mode pre-selected
- [ ] Back button returns to ModeGallery
- [ ] All task submission functionality works in run view
- [ ] Console tab works
- [ ] Workflow tab works
- [ ] Sessions tab works
- [ ] Results tab is removed
- [ ] Copilot mode (chat interface) still works
- [ ] Approval flow still works
- [ ] Session resume from list still works

### Task 5: Update TaskInput to Accept Default Mode
**Objective:** Allow TaskInput to receive a pre-selected mode

**Files to Modify:**
- `components/TaskInput.tsx`

**Changes:**

Add a `defaultMode` prop:

```typescript
interface TaskInputProps {
  onSubmit: (task: string, config: any) => void
  onStop: () => void
  isRunning: boolean
  isConnecting?: boolean
  onOpenDirectory?: (path: string) => void
  defaultMode?: string  // NEW: Pre-select mode from ModeGallery
}
```

When `defaultMode` is provided, set the initial mode state to this value. The user can still change it.

**Verification:**
- [ ] TaskInput respects `defaultMode` prop
- [ ] Mode can still be changed by user within TaskInput
- [ ] Task submission sends the correct mode ID to backend

## Files to Create (Summary)

```
cmbagent-ui/
├── lib/
│   └── modes.ts                    # Mode configuration map
└── components/
    └── modes/
        ├── ModeGallery.tsx         # Gallery grid container
        ├── ModeCard.tsx            # Individual mode card
        └── index.ts                # Barrel export
```

## Files to Modify

- `app/page.tsx` - Add ModeGallery as default view, remove Results tab
- `components/TaskInput.tsx` - Add `defaultMode` prop

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] Default view shows ModeCard gallery with 8 modes
- [ ] Clicking a mode transitions to run view
- [ ] Task submission works with correct backend mode IDs
- [ ] Console output streams correctly
- [ ] Workflow visualization renders
- [ ] Sessions tab functions
- [ ] Results tab is removed from UI
- [ ] Copilot mode works
- [ ] WebSocket events still fire correctly
- [ ] Approval flow is intact

### Should Pass
- [ ] Search/filter in ModeGallery works
- [ ] ModeCard hover effects (scale, glow) are smooth
- [ ] Empty state shows when search has no results
- [ ] Mode display names describe execution capabilities, not domain tasks
- [ ] Tags display correctly on cards
- [ ] Back to Modes navigation works cleanly

## Common Issues and Solutions

### Issue 1: State Reset on Mode Switch
**Symptom:** Console output or workflow data persists when returning to modes
**Solution:** Clear relevant state when going back to ModeGallery, or keep it (user preference). The brief suggests preserving state so users can switch back and forth.

### Issue 2: TaskInput Mode Desync
**Symptom:** TaskInput shows a different mode than what was clicked
**Solution:** Use `useEffect` in TaskInput to sync `defaultMode` prop with internal mode state when it changes. Only sync on initial mount or when `defaultMode` changes.

### Issue 3: Backend Mode ID Changes
**Symptom:** Backend rejects task with wrong mode
**Solution:** NEVER send display names to backend. Always use the `id` field from `ModeConfig`. Verify by checking the config payload in WebSocket messages.

## Rollback Procedure

If Stage 5 causes issues:
1. Revert `app/page.tsx` to the pre-Stage-5 state
2. Revert `components/TaskInput.tsx` changes
3. Delete `components/modes/` directory
4. Delete `lib/modes.ts`
5. Run `npm run build` to confirm

## Success Criteria

Stage 5 is complete when:
1. Default view is a ModeCard gallery
2. All 8 modes are displayed with capability-focused names (not task names)
3. Clicking a mode opens the run view
4. Results tab is removed
5. All backend communication uses original mode IDs
6. All existing functionality is preserved
7. Build passes with no errors

## Next Stage

Once Stage 5 is verified complete, proceed to:
**Stage 6: Tasks Dedicated Screen** (can be parallel with Stage 7)

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
