# MARS UI Overhaul - Implementation Plan

## Overview
Transform the existing **cmbagent** UI into **MARS** with a modern, production-grade interface. This plan preserves all current UI-backend functionality (events, endpoints, payloads, and workflows) while overhauling visual design, information architecture, interaction patterns, and the component system.

**Total Stages:** 12 stages organized into 5 phases
**Current Stage:** 0 (Not Started)
**Dependencies:** Next.js 14, React 18, Tailwind CSS 3, TypeScript 5, XYFlow, Socket.io-client, Lucide-react

## How to Use This Plan

### For Each Stage:
1. Read `STAGE_XX.md` in the `stages/` directory
2. Review the stage objectives and verification criteria
3. Implement the stage following the guidelines
4. Run verification tests listed in the stage document
5. Mark stage as complete in `PROGRESS.md`
6. Move to next stage only after all verifications pass

### Resuming Implementation:
When resuming, provide:
- Current stage number (from `PROGRESS.md`)
- This README file location: `/srv/projects/mas/mars/denario/cmbagent/MARS_IMPLEMENTATION_PLAN/README.md`
- Any blockers encountered

## Non-Negotiable Constraints

1. **No backend changes** - All API contracts, event names, WebSocket message formats, and data flows remain intact
2. **No behavior changes** - Workflows, task submission, approval flows, copilot chat, session management all function identically
3. **Console & Workflow modals** must work from any screen, respecting existing triggers and streams
4. **Existing WebSocket events** are subscribed to exactly as today - no new socket events required

## Stage Overview

### Phase 0: Foundation (Stages 1-3)
**Goal:** Establish design system, layout shell, and branding

- **Stage 1: Global CSS & Design Tokens** - Create `mars.css` with CSS custom properties, theming (dark/light), typography, spacing, shadows, z-index, motion tokens, CSS reset, and utility classes
- **Stage 2: AppShell Layout (TopBar + SideNav)** - Replace current TopNavigation + Header with a persistent AppShell containing a collapsible SideNav and TopBar; restructure routing for Modes (default), Tasks, Sessions as SideNav items
- **Stage 3: Branding & Renaming** - Rename CMBAGENT to MARS everywhere: metadata, layout title, header, TopNavigation logo, config descriptions, page titles, favicon, environment banners

### Phase 1: Core Components (Stage 4)
**Goal:** Build the reusable component library

- **Stage 4: Core Component Library** - Build all shared UI components: Button, IconButton, Dropdown, Tabs, Toast/InlineAlert, Tooltip, EmptyState, DataTable, Badge, Tag, Stepper, ProgressIndicator, Skeleton loaders, Modal base; document props and states

### Phase 2: Screen Overhauls (Stages 5-8)
**Goal:** Redesign each screen and create modal experiences

- **Stage 5: Modes Gallery Redesign** - Convert current home page into a visual ModeCard gallery with title, description, tags, CTAs, hover micro-interactions; update mode examples to IT/product workflow names; remove Results tab
- **Stage 6: Tasks Dedicated Screen** - New `/tasks` screen in SideNav with task list view (status, last run, owner), Create/Duplicate/Edit/Archive actions, filters (Mode, Status, Updated), and TaskBuilder components
- **Stage 7: Sessions Screen** - Move Sessions from in-page tab to dedicated SideNav screen; group by Active/Queued/Paused/Completed/Failed; show progress stepper, duration, owner, quick actions
- **Stage 8: Console & Workflow Modals** - Extract ConsoleOutput and WorkflowDashboard into global modal overlays; accessible from TopBar icons and contextual triggers; draggable, resizable, keyboard-accessible, non-blocking

### Phase 3: Parallel Sessions & Polish (Stages 9-10)
**Goal:** Add parallel session UX and final polish

- **Stage 9: Parallel Sessions & Progress UX** - Global Session Switcher in TopBar with live progress pills; per-session menu (Pause/Resume/Cancel/View Logs/Rename/Pin); toast notifications on state changes; inline error surfaces
- **Stage 10: Accessibility, Responsiveness, Performance & Polish** - WCAG 2.2 AA audit and fixes; responsive breakpoints (sm/md/lg/xl); code-split modals; virtualized lists; micro-interactions (150-200ms ease); empty states with microcopy; reduced-motion support

### Phase 4: Refinements (Stages 11-12)
**Goal:** Polish console experience and file viewer capabilities

- **Stage 11: Console Logs Overhaul** - Transform raw text console into structured log viewer; replace emoji prefixes with Lucide icons and typed log entries; add animated phase indicators between events (Planning/Analyzing/Executing); collapsible code blocks and tool results; agent name badges; timestamps
- **Stage 12: File Viewer Overhaul** - Unified FilePreview component supporting PDF, images, Markdown, CSV, JSON, code files with syntax highlighting; update DAGFilesView and FileBrowser to use new viewer; consistent Lucide file type icons; MARS token styling

## Current File Structure (Pre-MARS)

```
cmbagent-ui/
├── app/
│   ├── page.tsx              # Main page (Research mode) - 940 lines
│   ├── layout.tsx            # Root layout with providers
│   ├── globals.css           # Tailwind directives + custom styles
│   ├── providers.tsx         # WebSocket provider wrapper
│   ├── not-found.tsx         # 404 page
│   └── tasks/
│       └── page.tsx          # Tasks mode page - 115KB
├── components/               # 78 component files
│   ├── Header.tsx            # Logo + connection status
│   ├── TopNavigation.tsx     # Research/Tasks mode switcher
│   ├── TaskInput.tsx         # Main task form (~1400 lines)
│   ├── ConsoleOutput.tsx     # Console output panel
│   ├── ResultDisplay.tsx     # Results tab
│   ├── CopilotView.tsx       # Copilot chat interface
│   ├── ApprovalDialog.tsx    # Approval modal
│   ├── ApprovalChatPanel.tsx # Chat-based approval
│   ├── CredentialsModal.tsx  # API key management
│   ├── ModelSelector.tsx     # Model selection
│   ├── FileBrowser.tsx       # File tree browser
│   ├── dag/                  # 11 DAG visualization components
│   ├── workflow/             # 4 workflow components
│   ├── SessionManager/       # 8 session components
│   ├── branching/            # 4 branching components
│   ├── metrics/              # 5 cost tracking components
│   ├── tables/               # 4 data table components
│   ├── tasks/                # 3 specialized task components
│   ├── retry/                # 3 retry handling components
│   └── common/               # 3 shared components
├── contexts/
│   └── WebSocketContext.tsx   # Global WebSocket management
├── hooks/                     # 7 custom React hooks
├── lib/
│   └── config.ts             # API/WS URL configuration
├── types/                     # 7 TypeScript type files
├── tailwind.config.js
├── next.config.js
└── package.json
```

## Target File Structure (Post-MARS)

```
cmbagent-ui/
├── app/
│   ├── page.tsx              # Modes gallery (default view)
│   ├── layout.tsx            # Root layout with MARS branding
│   ├── globals.css           # Imports mars.css + Tailwind
│   ├── providers.tsx         # WebSocket + Theme providers
│   ├── not-found.tsx         # 404 page (MARS branded)
│   ├── tasks/
│   │   └── page.tsx          # Tasks dedicated screen
│   └── sessions/
│       └── page.tsx          # Sessions dedicated screen
├── components/
│   ├── layout/               # NEW: AppShell components
│   │   ├── AppShell.tsx      # TopBar + SideNav + Content wrapper
│   │   ├── TopBar.tsx        # Product name, quick actions, session pills
│   │   └── SideNav.tsx       # Collapsible side navigation
│   ├── core/                 # NEW: Reusable UI components
│   │   ├── Button.tsx
│   │   ├── IconButton.tsx
│   │   ├── Dropdown.tsx
│   │   ├── Tabs.tsx
│   │   ├── Modal.tsx         # Base modal (draggable, resizable)
│   │   ├── Toast.tsx
│   │   ├── InlineAlert.tsx
│   │   ├── Tooltip.tsx
│   │   ├── EmptyState.tsx
│   │   ├── Badge.tsx
│   │   ├── Tag.tsx
│   │   ├── Stepper.tsx
│   │   ├── ProgressIndicator.tsx
│   │   ├── Skeleton.tsx
│   │   ├── DataTable.tsx
│   │   └── index.ts
│   ├── modes/                # NEW: Modes gallery components
│   │   ├── ModeGallery.tsx
│   │   ├── ModeCard.tsx
│   │   └── index.ts
│   ├── tasks/                # Existing + new TaskBuilder
│   │   ├── TaskList.tsx      # NEW
│   │   ├── TaskCard.tsx      # NEW
│   │   ├── TaskBuilder.tsx   # NEW
│   │   ├── AIWeeklyTaskEnhanced.tsx
│   │   ├── ReleaseNotesTask.tsx
│   │   └── CodeReviewTask.tsx
│   ├── sessions/             # Refactored SessionManager
│   │   ├── SessionScreen.tsx # NEW: Full-page sessions view
│   │   ├── SessionList.tsx
│   │   ├── SessionCard.tsx   # NEW
│   │   ├── SessionPill.tsx   # NEW: TopBar session switcher pill
│   │   ├── SessionDetailPanel.tsx
│   │   └── ...existing session components
│   ├── modals/               # NEW: Global modals
│   │   ├── ConsoleModal.tsx
│   │   └── WorkflowModal.tsx
│   ├── console/              # NEW: Structured console components
│   │   ├── LogEntryRenderer.tsx
│   │   ├── PhaseIndicatorBar.tsx
│   │   ├── StructuredConsoleOutput.tsx
│   │   └── index.ts
│   ├── files/                # NEW: File viewer components
│   │   ├── FilePreview.tsx
│   │   ├── MarkdownRenderer.tsx
│   │   ├── CSVTableViewer.tsx
│   │   ├── PDFViewer.tsx
│   │   ├── CodeViewer.tsx
│   │   ├── fileIcons.ts
│   │   └── index.ts
│   ├── dag/                  # Existing (unchanged internals)
│   ├── workflow/             # Existing (unchanged internals)
│   ├── branching/            # Existing (unchanged internals)
│   ├── metrics/              # Existing (unchanged internals)
│   ├── tables/               # Existing (unchanged internals)
│   ├── retry/                # Existing (unchanged internals)
│   ├── common/               # Existing (unchanged internals)
│   ├── TaskInput.tsx         # Existing (preserved)
│   ├── ConsoleOutput.tsx     # Existing (preserved, used inside modal)
│   ├── ResultDisplay.tsx     # Existing (preserved)
│   ├── CopilotView.tsx       # Existing (preserved)
│   ├── ApprovalDialog.tsx    # Existing (unchanged)
│   ├── ApprovalChatPanel.tsx # Existing (unchanged)
│   ├── CredentialsModal.tsx  # Existing (unchanged)
│   ├── ModelSelector.tsx     # Existing (unchanged)
│   └── FileBrowser.tsx       # Existing (unchanged)
├── styles/
│   └── mars.css              # NEW: Global design tokens & themes
├── contexts/
│   ├── WebSocketContext.tsx   # Existing (unchanged)
│   └── ThemeContext.tsx       # NEW: Theme management
├── hooks/                     # Existing hooks (unchanged)
├── lib/
│   └── config.ts             # Existing (unchanged)
├── types/                     # Existing types (unchanged) + new
│   ├── websocket-events.ts
│   ├── dag.ts
│   ├── sessions.ts
│   ├── cost.ts
│   ├── branching.ts
│   ├── tables.ts
│   ├── retry.ts
│   └── mars-ui.ts            # NEW: MARS UI-specific types
│   └── console.ts            # NEW: Structured log entry types
├── public/
│   ├── favicon.ico           # NEW: MARS favicon
│   └── mars-logo.svg         # NEW: MARS logo
├── tailwind.config.js         # Updated with MARS design tokens
├── next.config.js             # Unchanged
└── package.json               # Updated name
```

## Stage Dependencies

```
Stage 1 (CSS & Tokens)
  ↓
Stage 2 (AppShell) ──→ Stage 3 (Branding)
  ↓
Stage 4 (Core Components)
  ↓
Stage 5 (Modes Gallery)
Stage 6 (Tasks Screen)     ← can run in parallel
Stage 7 (Sessions Screen)
  ↓
Stage 8 (Modals)
  ↓
Stage 9 (Parallel Sessions)
  ↓
Stage 10 (A11y, Responsive, Performance)
  ↓
Stage 11 (Console Logs Overhaul)
Stage 12 (File Viewer Overhaul)  ← can run in parallel with 11
```

## Critical Success Factors

1. **Zero Backend Regressions** - All API calls, WebSocket events, and data flows must continue to work unchanged
2. **Incremental Delivery** - Each stage produces a working UI; no stage leaves the app in a broken state
3. **Component Reusability** - All new UI is built from `components/core/` primitives; no business logic in components
4. **Accessibility First** - WCAG 2.2 AA compliance built into every component from Stage 4 onward
5. **Performance** - No perceptible performance regression; modals are code-split; lists are virtualized

## Quick Reference Commands

```bash
# Development
cd /srv/projects/mas/mars/denario/cmbagent/cmbagent-ui
npm run dev

# Build check
npm run build

# Lint
npm run lint

# Type check
npx tsc --noEmit
```

## Risk Management

### High-Risk Stages
- **Stage 2 (AppShell):** Restructures the main layout; affects every page. Must preserve all state management in `page.tsx`
- **Stage 8 (Modals):** Extracting Console and Workflow into modals requires careful state lifting and event stream piping
- **Stage 9 (Parallel Sessions):** Multiple concurrent WebSocket connections may require careful lifecycle management

### Mitigation
- Each stage includes rollback procedures
- Feature flags recommended for Stages 8-9 to enable phased rollout
- All existing component files are preserved (not deleted) during transition
- Non-regression testing after every stage

---

**Last Updated:** 2026-02-18
**Plan Version:** 1.0
**Status:** Ready for implementation
