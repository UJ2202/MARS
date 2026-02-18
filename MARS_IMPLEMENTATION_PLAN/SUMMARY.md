# MARS Implementation Plan Summary

## Overview
Transform cmbagent UI into MARS: modern AppShell layout, rebranded identity, redesigned Modes gallery, dedicated Tasks and Sessions screens, global Console/Workflow modals, parallel session management, and a complete design token system. Zero backend changes.

## Plan Structure

```
MARS_IMPLEMENTATION_PLAN/
├── README.md                  # Master plan (entry point)
├── PROGRESS.md                # Progress tracking
├── ARCHITECTURE.md            # Technical architecture decisions
├── SUMMARY.md                 # This file
├── stages/
│   ├── STAGE_01.md            # Global CSS & Design Tokens
│   ├── STAGE_02.md            # AppShell Layout (TopBar + SideNav)
│   ├── STAGE_03.md            # Branding & Renaming
│   ├── STAGE_04.md            # Core Component Library
│   ├── STAGE_05.md            # Modes Gallery Redesign
│   ├── STAGE_06.md            # Tasks Dedicated Screen
│   ├── STAGE_07.md            # Sessions Screen
│   ├── STAGE_08.md            # Console & Workflow Modals
│   ├── STAGE_09.md            # Parallel Sessions & Progress UX
│   └── STAGE_10.md            # A11y, Responsiveness, Performance & Polish
│   ├── STAGE_11.md            # Console Logs Overhaul
│   └── STAGE_12.md            # File Viewer Overhaul
├── references/
│   ├── api_reference.md       # REST API endpoints
│   ├── event_types.md         # WebSocket event catalog
│   └── data_models.md         # TypeScript interfaces
└── tests/
    └── test_scenarios.md      # Testing & validation guide
```

## Stage Summary

| Stage | Name | Description | Key Deliverables |
|-------|------|-------------|------------------|
| 1 | Global CSS & Design Tokens | CSS custom properties, themes, reset, utilities | `styles/mars.css`, updated `tailwind.config.js` |
| 2 | AppShell Layout | TopBar + SideNav + content area | `components/layout/{AppShell,TopBar,SideNav}.tsx` |
| 3 | Branding & Renaming | CMBAGENT → MARS everywhere | Updated metadata, logos, headers, config |
| 4 | Core Component Library | Reusable UI primitives | `components/core/` (15+ components) |
| 5 | Modes Gallery Redesign | Visual ModeCard grid, updated examples | `components/modes/`, updated `page.tsx` |
| 6 | Tasks Dedicated Screen | Task list with builder and filters | `app/tasks/page.tsx`, `components/tasks/` |
| 7 | Sessions Screen | Grouped sessions with progress | `app/sessions/page.tsx`, `components/sessions/` |
| 8 | Console & Workflow Modals | Global modal overlays | `components/modals/{ConsoleModal,WorkflowModal}.tsx` |
| 9 | Parallel Sessions & Progress | Session switcher, live pills, toasts | TopBar integration, session management |
| 10 | Polish & A11y | WCAG 2.2 AA, responsive, performance | Audit fixes, code-splitting, virtualization |
| 11 | Console Logs Overhaul | Structured log entries, phase indicators, polished rendering | `components/console/`, updated `WebSocketContext`, `useEventHandler` |
| 12 | File Viewer Overhaul | Rich inline preview for PDF, images, Markdown, CSV, code | `components/files/`, updated `DAGFilesView`, `FileBrowser` |

## Files to Create

### Layout (3 files)
```
components/layout/
├── AppShell.tsx
├── TopBar.tsx
└── SideNav.tsx
```

### Core Components (16 files)
```
components/core/
├── Button.tsx
├── IconButton.tsx
├── Dropdown.tsx
├── Tabs.tsx
├── Modal.tsx
├── Toast.tsx
├── InlineAlert.tsx
├── Tooltip.tsx
├── EmptyState.tsx
├── Badge.tsx
├── Tag.tsx
├── Stepper.tsx
├── ProgressIndicator.tsx
├── Skeleton.tsx
├── DataTable.tsx
└── index.ts
```

### Modes (3 files)
```
components/modes/
├── ModeGallery.tsx
├── ModeCard.tsx
└── index.ts
```

### Sessions Additions (3 files)
```
components/sessions/
├── SessionScreen.tsx
├── SessionCard.tsx
└── SessionPill.tsx
```

### Tasks Additions (3 files)
```
components/tasks/
├── TaskList.tsx
├── TaskCard.tsx
└── TaskBuilder.tsx
```

### Modals (2 files)
```
components/modals/
├── ConsoleModal.tsx
└── WorkflowModal.tsx
```

### Console (5 files)
```
components/console/
├── ConsoleEntry.tsx
├── PhaseIndicator.tsx
├── ConsoleFilterBar.tsx
├── ConsoleLogViewer.tsx
└── index.ts
```

### Files (7 files)
```
components/files/
├── FilePreview.tsx
├── MarkdownRenderer.tsx
├── CSVTableViewer.tsx
├── PDFViewer.tsx
├── CodeViewer.tsx
├── fileIcons.ts
└── index.ts
```

### Styles (1 file)
```
styles/
└── mars.css
```

### Types (1 file)
```
types/
└── mars-ui.ts
```

### Pages (1 new file)
```
app/sessions/
└── page.tsx
```

### Assets (2 files)
```
public/
├── favicon.ico
└── mars-logo.svg
```

**Total new files: ~47**

## Files to Modify

| File | Change |
|------|--------|
| `app/layout.tsx` | Import mars.css, update metadata to MARS, add ThemeProvider |
| `app/globals.css` | Import mars.css tokens |
| `app/page.tsx` | Replace with ModeGallery, remove Results tab, lift modal state |
| `app/tasks/page.tsx` | Redesign with TaskList/TaskBuilder components |
| `components/Header.tsx` | Rename to MARS, integrate into TopBar |
| `components/TopNavigation.tsx` | Replace with SideNav routing |
| `tailwind.config.js` | Extend with MARS design token references |
| `package.json` | Update name to "mars-ui" |
| `components/ConsoleOutput.tsx` | Replace with ConsoleLogViewer using structured LogEntry[] |
| `hooks/useEventHandler.ts` | Emit structured LogEntry objects instead of emoji strings |
| `contexts/WebSocketContext.tsx` | Change consoleOutput from string[] to LogEntry[] |
| `components/dag/DAGFilesView.tsx` | Use FilePreview component, shared file icons, MARS tokens |
| `components/FileBrowser.tsx` | Use FilePreview component, shared file icons, MARS tokens |

## Dependencies to Add

```bash
# No new npm dependencies required
# All functionality built on existing stack
```

## Implementation Order

```
Stage 1 ──→ Stage 2 ──→ Stage 3
                          ↓
                     Stage 4
                          ↓
              ┌───── Stage 5
              ├───── Stage 6  (parallel)
              └───── Stage 7
                          ↓
                     Stage 8
                          ↓
                     Stage 9
                          ↓
                     Stage 10
                          ↓
              ┌───── Stage 11  (parallel)
              └───── Stage 12
```

## Key Integration Points

| Feature | Component | Event/API |
|---------|-----------|-----------|
| Task Submission | TaskInput → WebSocketContext | `POST /api/tasks` → `ws://.../ws/{taskId}` |
| Console Streaming | ConsoleModal ← WebSocketContext | `consoleOutput: LogEntry[]` state |
| Workflow Viz | WorkflowModal ← WebSocketContext | `dagData`, `workflowStatus` |
| Session List | SessionScreen | `GET /api/sessions` |
| Session Detail | SessionDetailPanel | `GET /api/sessions/{id}` |
| Session Resume | handleResumeSessionFromList | `POST /api/sessions/{id}/resume` |
| Approval Flow | ApprovalChatPanel | `pendingApproval` state, `sendMessage()` |
| Cost Tracking | CostDashboard | `costSummary`, `costTimeSeries` |
| Branching | BranchTree | `POST /api/runs/{id}/branch` |

## Getting Started

1. **Read:** Start with `README.md` for full context
2. **Review:** Check `ARCHITECTURE.md` for technical decisions
3. **Implement:** Open `stages/STAGE_01.md` and follow tasks
4. **Track:** Update `PROGRESS.md` after each stage
5. **Verify:** Run verification criteria before moving to next stage

## Quick Commands

```bash
# Navigate to project
cd /srv/projects/mas/mars/denario/cmbagent/cmbagent-ui

# Start dev server
npm run dev

# Build check (run after each stage)
npm run build

# Type check
npx tsc --noEmit

# Lint
npm run lint
```

---

**Created:** 2026-02-18
**Total Stages:** 12
**Status:** Ready for Implementation
