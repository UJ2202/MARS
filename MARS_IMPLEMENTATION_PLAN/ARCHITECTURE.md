# MARS Architecture

## Executive Summary
MARS is a UI overhaul of the cmbagent frontend, transforming the presentation and navigation layer while preserving all backend contracts. The architecture follows a layered approach: design tokens → core components → layout shell → screen compositions → global overlays.

## Core Architectural Principles

### 1. Backend Contract Preservation
- All REST API endpoints (`/api/sessions`, `/api/tasks`, `/api/runs/*`, `/api/approvals/*`) remain untouched
- WebSocket connection pattern (`ws://host/ws/{taskId}`) is identical
- All 40+ WebSocket event types in `types/websocket-events.ts` are consumed as-is
- `WebSocketContext.tsx` internals are not modified

### 2. Composition Over Replacement
- Existing components (ConsoleOutput, WorkflowDashboard, TaskInput, etc.) are wrapped and composed, not rewritten
- New layout components (AppShell, TopBar, SideNav) wrap around existing content
- Modals embed existing components rather than duplicating their logic

### 3. Design Token Authority
- All visual properties flow from CSS custom properties in `styles/mars.css`
- Tailwind extends (not replaces) with MARS token references
- Theme switching via `[data-theme]` attribute on `<html>`
- No hardcoded colors, spacing, or typography in component JSX

### 4. Component Purity
- `components/core/` contains zero business logic—pure UI props and callbacks
- State management remains in page-level components and contexts
- Event handling stays in `WebSocketContext` and `page.tsx` handlers

### 5. Progressive Enhancement
- Each stage produces a fully working UI
- Feature flags gate new navigation (SideNav) and modals
- Old components co-exist with new ones during transition

## High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        html[data-theme]                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     Providers                             │  │
│  │  ┌─────────────────┐  ┌────────────────────────────────┐  │  │
│  │  │ WebSocketProvider│  │ ThemeProvider (NEW)            │  │  │
│  │  └─────────────────┘  └────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌───────────────────────────────────────────────────┐    │  │
│  │  │               AppShell (NEW)                       │    │  │
│  │  │  ┌─────────────────────────────────────────────┐   │    │  │
│  │  │  │  TopBar                                      │   │    │  │
│  │  │  │  [Logo] [Search] [SessionPills] [Console]    │   │    │  │
│  │  │  │  [Workflow] [Settings] [Theme] [User]        │   │    │  │
│  │  │  └─────────────────────────────────────────────┘   │    │  │
│  │  │                                                     │    │  │
│  │  │  ┌──────────┐  ┌──────────────────────────────┐    │    │  │
│  │  │  │ SideNav  │  │ Content Area                  │    │    │  │
│  │  │  │          │  │                                │    │    │  │
│  │  │  │ [Modes]  │  │  Page content rendered by     │    │    │  │
│  │  │  │ [Tasks]  │  │  Next.js App Router:          │    │    │  │
│  │  │  │ [Sessions│  │  - / → ModeGallery            │    │    │  │
│  │  │  │          │  │  - /tasks → TasksScreen       │    │    │  │
│  │  │  │          │  │  - /sessions → SessionsScreen │    │    │  │
│  │  │  │          │  │                                │    │    │  │
│  │  │  └──────────┘  └──────────────────────────────┘    │    │  │
│  │  └─────────────────────────────────────────────────────┘    │  │
│  │                                                           │  │
│  │  ┌──────────────────────────┐  ┌────────────────────┐     │  │
│  │  │  ConsoleModal (Global)   │  │ WorkflowModal      │     │  │
│  │  │  (Overlay, any screen)   │  │ (Overlay, any scr) │     │  │
│  │  └──────────────────────────┘  └────────────────────┘     │  │
│  │  ┌──────────────────────────┐                             │  │
│  │  │  Toast Container         │                             │  │
│  │  └──────────────────────────┘                             │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow Architecture

### Task Submission Flow (Unchanged)

```
User fills TaskInput
  ↓
handleTaskSubmit(task, config)
  ↓
connect(taskId, task, config)  [WebSocketContext]
  ↓
POST /api/tasks  →  Backend creates task
  ↓
WebSocket /ws/{taskId}  →  Backend streams events
  ↓
Event dispatchers update state:
  • consoleOutput[]
  • dagData { nodes, edges }
  • workflowStatus
  • costSummary / costTimeSeries
  • pendingApproval
  • results
  ↓
Components re-render with new state
```

### Modal Data Flow (New)

```
ConsoleModal
  ├── Subscribes to: consoleOutput[] from WebSocketContext
  ├── Actions: clearConsole(), copy, download, filter
  └── No new data required—reads existing state

WorkflowModal
  ├── Subscribes to: dagData, workflowStatus, branches, costSummary
  ├── Embeds: WorkflowDashboard (existing component)
  └── Actions: onPause, onResume, onCancel (existing handlers)
```

### Session Data Flow (Unchanged)

```
SessionsScreen
  ├── GET /api/sessions  →  SessionList renders
  ├── Click session  →  SessionDetailPanel
  │   └── GET /api/sessions/{id}  →  Tabs (Overview, DAG, Console, etc.)
  ├── Resume  →  handleResumeSessionFromList()
  │   └── POST /api/sessions/{id}/resume  →  WebSocket connect
  └── View Logs  →  handleViewSessionLogs()
      └── GET /api/sessions/{id}/history  →  ConsoleModal opens
```

## Component Hierarchy

### Layout Components (New)
```
AppShell
├── TopBar
│   ├── Logo ("MARS")
│   ├── SearchInput (future)
│   ├── SessionPillBar
│   │   └── SessionPill (per active session)
│   ├── IconButton (Console toggle)
│   ├── IconButton (Workflow toggle)
│   ├── ThemeToggle
│   └── ConnectionStatus (existing)
└── SideNav
    ├── NavItem (Modes) → /
    ├── NavItem (Tasks) → /tasks
    ├── NavItem (Sessions) → /sessions
    └── CollapseToggle
```

### Page Components
```
ModesPage (/)
└── ModeGallery
    ├── SearchFilter
    └── ModeCard[] (grid)
        ├── Title, Description, Tags
        ├── Button (Launch)
        └── Button (Configure)

TasksPage (/tasks)
├── TaskList (filterable)
│   └── TaskCard[] (list/grid)
└── TaskBuilder (on create/edit)
    ├── FormField[]
    └── TaskInput (existing, embedded)

SessionsPage (/sessions)
├── SessionGroupHeader (Active/Queued/Paused/Completed/Failed)
├── SessionCard[] (per group)
│   ├── ProgressIndicator
│   ├── StatusBadge
│   └── ActionMenu
└── SessionDetailPanel (existing, in drawer or inline)
```

### Modal Components (New)
```
Modal (base)
├── ModalHeader (title, close, drag handle)
├── ModalBody (scrollable content)
└── ModalFooter (optional actions)

ConsoleModal extends Modal
├── FilterBar (level: Info/Warn/Error, search)
├── ConsoleLogViewer (NEW - replaces ConsoleOutput)
└── ActionBar (copy, download, clear, auto-scroll toggle)

WorkflowModal extends Modal
├── WorkflowDashboard (existing component)
└── WorkflowControls (Pause/Resume/Cancel)
```

### Console Components (New - Stage 11)
```
ConsoleLogViewer
├── ConsoleFilterBar (level, agent, search filters)
├── ConsoleEntry[] (structured log entries)
│   ├── LevelIcon (Lucide icon per log level)
│   ├── Timestamp
│   ├── AgentBadge
│   ├── Message
│   └── ExpandableDetails (collapsible JSON/code)
├── PhaseIndicator (animated transition markers)
│   ├── PhaseIcon (Lucide: Map, Search, Cog, etc.)
│   ├── PhaseLabel
│   └── LoadingDots animation
└── VirtualScroll (windowed rendering for 500+ entries)
```

### File Viewer Components (New - Stage 12)
```
FilePreview (unified type-detection router)
├── PDFViewer (iframe/embed for .pdf)
├── ImageViewer (inline <img> with zoom)
├── MarkdownRenderer (formatted HTML from .md)
├── CSVTableViewer (DataTable from .csv)
├── CodeViewer (react-syntax-highlighter for .py/.js/.ts/.json/.yaml)
├── TextViewer (monospace <pre> with line numbers)
└── BinaryFallback (file info card + download)

fileIcons (Lucide icon map per file extension)
```

## State Management

### Global State (WebSocketContext - Modified in Stage 11)
```typescript
interface WebSocketContextValue {
  // Connection
  connected: boolean;
  reconnectAttempt: number;
  lastError: string | null;
  isConnecting: boolean;

  // Actions
  connect: (taskId, task, config) => Promise<void>;
  sendMessage: (message) => void;
  disconnect: () => void;
  reconnect: () => void;

  // Run state
  currentRunId: string | null;
  workflowStatus: string | null;
  dagData: { nodes, edges } | null;
  pendingApproval: ApprovalRequestedData | null;
  consoleOutput: LogEntry[];      // CHANGED: was string[], now structured LogEntry[]
  results: any | null;
  isRunning: boolean;
  costSummary: CostSummary;
  costTimeSeries: CostTimeSeries[];
  filesUpdatedCounter: number;
  agentMessages: AgentMessageData[];

  // Session
  copilotSessionId: string | null;
  resumeSession: (sessionId, context?) => Promise<void>;
  loadSessionHistory: (sessionId) => Promise<any>;
}

// NEW: Structured log entry (Stage 11)
interface LogEntry {
  id: string;
  timestamp: string;
  type: 'agent_message' | 'tool_call' | 'tool_result' | 'thinking' | 'code' | 'status' | 'error' | 'system' | 'phase_change';
  level: 'info' | 'warning' | 'error' | 'success' | 'debug';
  agent?: string;
  message: string;
  details?: Record<string, unknown>;
  phase?: string;
}
```

### New UI State (Page-level, not context)
```typescript
// ThemeContext (new)
interface ThemeContextValue {
  theme: 'dark' | 'light';
  toggleTheme: () => void;
}

// Modal state (lifted to AppShell or page)
interface ModalState {
  consoleOpen: boolean;
  workflowOpen: boolean;
}

// SideNav state
interface SideNavState {
  collapsed: boolean;
  activeItem: 'modes' | 'tasks' | 'sessions';
}
```

## Technology Stack

### Core (Unchanged)
- **Next.js 14.0.4** - App Router, SSR, API rewrites
- **React 18** - Component framework
- **TypeScript 5** - Type safety
- **Socket.io-client 4.7.4** - WebSocket communication
- **@xyflow/react 12.10.0** - DAG visualization

### Styling (Enhanced)
- **Tailwind CSS 3.3.0** - Utility classes (extended with MARS tokens)
- **mars.css** - CSS custom properties, themes, reset, utilities (NEW)
- **Inter font** - Primary typography (already loaded via `next/font/google`)
- **JetBrains Mono** - Monospace/code (already loaded)

### Icons (Unchanged)
- **Lucide-react 0.294.0** - Icon library
- **No emojis anywhere in the UI.** All status indicators, prefixes, and visual cues must use Lucide icon components. Existing emoji usage in ConsoleOutput (e.g., status prefixes) must be replaced with Lucide icons during Stage 11 (Console Logs Overhaul).

### New Dependencies (Minimal)
- None required. All new functionality is built with existing stack.
- Optional: `@floating-ui/react` for tooltip positioning (if Tooltip component needs advanced placement)

## Security Considerations
- No new API endpoints or data exposure
- Modal content is scoped to existing authenticated context
- No client-side storage of sensitive data beyond what exists today
- CSP headers remain unchanged (no new external resources)

## Performance Considerations
- **Code Splitting:** Modals (`ConsoleModal`, `WorkflowModal`) are dynamically imported via `next/dynamic`
- **Virtualization:** Session and log lists use windowing for 1000+ items
- **CSS:** `mars.css` is < 10KB; critical tokens are inline; no FOUC
- **Animations:** All use `transform`/`opacity` (GPU-composited); `prefers-reduced-motion` respected
- **Bundle Impact:** Estimated +15KB gzipped for all new components (no new heavy dependencies)

---

**Version:** 1.0
**Last Updated:** 2026-02-18
