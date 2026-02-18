# Stage 6: Tasks Dedicated Screen

**Phase:** 2 - Screen Overhauls
**Dependencies:** Stage 4 (Core Components), Stage 5 (Modes Gallery)
**Risk Level:** Medium

## Objectives

1. Redesign the `/tasks` page as a dedicated screen in the SideNav
2. Create TaskList view with status, last run, owner, and filters
3. Create TaskCard component for the list
4. Create TaskBuilder component for creating/editing tasks
5. Preserve existing AI Weekly, Release Notes, and Code Review task implementations
6. Add actions: Create, Duplicate, Edit, Archive
7. Add filters: Mode, Status (Draft/Active/Archived), Updated

## Current State Analysis

### What We Have
- `app/tasks/page.tsx` (~115KB): ToolsPage with three hardcoded cards
  - AI Weekly Report → `AIWeeklyTaskEnhanced`
  - Release Notes → `ReleaseNotesTask`
  - Code Review → `CodeReviewTask`
- Each task component is self-contained with its own UI, state, and backend communication
- Simple card-based selection with gradient backgrounds and icons
- `TopNavigation` and inline header (to be removed since AppShell provides navigation)

### What We Need
- TaskList component showing tasks in a list/grid view with metadata
- TaskCard showing task name, status, last run, mode, and actions
- TaskBuilder for creating new tasks or editing existing ones
- Filters for Mode, Status, and Updated date
- Actions: Create, Duplicate, Edit, Archive
- Existing task components preserved and accessible

## Pre-Stage Verification

### Check Prerequisites
1. Stage 4 complete: Core components (Button, Badge, DataTable, EmptyState, etc.) available
2. AppShell with SideNav is rendering, `/tasks` route exists
3. Build passes

## Implementation Tasks

### Task 1: Create TaskCard Component
**Objective:** Compact card for task list

**Files to Create:**
- `components/tasks/TaskCard.tsx`

**Props:**
```typescript
interface TaskCardProps {
  id: string
  name: string
  description: string
  mode: string
  status: 'draft' | 'active' | 'archived'
  lastRun?: string  // ISO date
  icon: React.ReactNode
  color: string
  onOpen: (id: string) => void
  onDuplicate?: (id: string) => void
  onArchive?: (id: string) => void
}
```

Renders as a row (list mode) or card (grid mode) with:
- Icon + Name + Description
- Mode badge
- Status badge (Draft=gray, Active=green, Archived=gray)
- Last run timestamp
- Action dropdown (Open, Duplicate, Archive)

### Task 2: Create TaskList Component
**Objective:** Filterable list of configured tasks

**Files to Create:**
- `components/tasks/TaskList.tsx`

**Props:**
```typescript
interface TaskListProps {
  onSelectTask: (taskId: string) => void
}
```

Features:
- Filter bar: Mode dropdown, Status toggle (Draft/Active/Archived), Sort by updated
- Search input
- Grid/List view toggle
- TaskCard for each task
- EmptyState when no tasks match filters

Tasks data source: For now, hardcoded from the existing three tasks (AI Weekly, Release Notes, Code Review). In the future, this would come from an API. Use a local data array.

### Task 3: Create TaskBuilder Component
**Objective:** Form for creating/editing task configurations

**Files to Create:**
- `components/tasks/TaskBuilder.tsx`

**Props:**
```typescript
interface TaskBuilderProps {
  taskId?: string  // If provided, edit mode; if undefined, create mode
  onBack: () => void
  onSave?: (config: any) => void
}
```

Features:
- Task name input
- Mode selection (from MARS_MODES)
- Configuration fields (model, max rounds, approval mode, etc.)
- Preset selection
- Save, Cancel buttons
- Validation states on fields

**Note:** This is a UI wrapper. For existing tasks (AI Weekly, Release Notes, Code Review), the TaskBuilder simply opens the existing task component. For new task creation, it provides a generic configuration form that feeds into TaskInput.

### Task 4: Redesign `app/tasks/page.tsx`
**Objective:** Replace the current card selection with TaskList + TaskBuilder

**Files to Modify:**
- `app/tasks/page.tsx`

**Changes:**

```tsx
'use client'

import { useState } from 'react'
import TaskList from '@/components/tasks/TaskList'
import AIWeeklyTaskEnhanced from '@/components/tasks/AIWeeklyTaskEnhanced'
import ReleaseNotesTask from '@/components/tasks/ReleaseNotesTask'
import CodeReviewTask from '@/components/tasks/CodeReviewTask'

type ActiveTask = 'ai-weekly' | 'release-notes' | 'code-review' | null

export default function TasksPage() {
  const [activeTask, setActiveTask] = useState<ActiveTask>(null)

  // When a task is opened, render its component
  if (activeTask === 'ai-weekly') {
    return <AIWeeklyTaskEnhanced onBack={() => setActiveTask(null)} />
  }
  if (activeTask === 'release-notes') {
    return <ReleaseNotesTask onBack={() => setActiveTask(null)} />
  }
  if (activeTask === 'code-review') {
    return <CodeReviewTask onBack={() => setActiveTask(null)} />
  }

  // Default: show task list
  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold" style={{ color: 'var(--mars-color-text)' }}>
          Tasks
        </h2>
        <p className="text-sm mt-1" style={{ color: 'var(--mars-color-text-secondary)' }}>
          Manage and run configured automation tasks
        </p>
      </div>

      <TaskList onSelectTask={(id) => setActiveTask(id as ActiveTask)} />
    </div>
  )
}
```

**Important:** Remove the old `TopNavigation` import and inline header from the page since AppShell provides these.

### Task 5: Barrel Export
**Files to Create:**
- `components/tasks/index.ts` (update if exists)

Add exports for TaskList, TaskCard, TaskBuilder.

## Files to Create (Summary)

```
components/tasks/
├── TaskCard.tsx
├── TaskList.tsx
├── TaskBuilder.tsx
└── index.ts (update)
```

## Files to Modify

- `app/tasks/page.tsx` - Replace card selection with TaskList

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] `/tasks` route shows TaskList with three tasks
- [ ] Clicking a task opens its component (AI Weekly, Release Notes, Code Review)
- [ ] Back navigation returns to TaskList
- [ ] All three existing task workflows still function correctly
- [ ] No TopNavigation or duplicate header renders

### Should Pass
- [ ] Filters (Status, Mode) work
- [ ] Search filters task list
- [ ] Task cards show appropriate icons and status badges
- [ ] Empty state shows when filters match no tasks
- [ ] Action dropdown (Open, Duplicate, Archive) is present

## Rollback Procedure

If Stage 6 causes issues:
1. Revert `app/tasks/page.tsx`
2. Delete new task components (TaskCard, TaskList, TaskBuilder)
3. Run `npm run build`

## Success Criteria

Stage 6 is complete when:
1. Tasks page shows a proper list view with metadata
2. Existing tasks are accessible and functional
3. Filters and search work
4. Build passes

## Next Stage

Proceed to **Stage 7: Sessions Screen** (can be parallel)

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
