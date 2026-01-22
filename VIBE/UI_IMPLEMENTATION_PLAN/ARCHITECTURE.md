# CMBAgent UI Architecture

## Executive Summary

This document outlines the architectural decisions and design principles for the CMBAgent UI enhancement. The UI transforms from a simple task runner interface into a comprehensive workflow management dashboard with real-time visualization, human-in-the-loop controls, and advanced analytics.

## Core Architectural Principles

### 1. Event-Driven UI
- All state updates come from WebSocket events
- No polling - pure real-time communication
- Optimistic updates with server reconciliation
- Event queue for handling missed events during reconnection

### 2. Component-Based Architecture
- Small, focused components with single responsibility
- Reusable UI primitives (StatusBadge, ProgressBar, etc.)
- Feature-based folder organization
- Clear separation between presentational and container components

### 3. Type Safety First
- Full TypeScript coverage
- Strict type checking enabled
- Shared types between frontend and backend event definitions
- Runtime validation for API responses

### 4. Performance by Default
- React 18 concurrent features
- Virtualized lists for large datasets
- Memoization for expensive computations
- Code splitting per feature

### 5. Accessibility & Responsiveness
- WCAG 2.1 AA compliance
- Keyboard navigation support
- Mobile-responsive design
- Dark mode support (existing)

## High-Level Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         App Shell                                │
│  (Header, Navigation, Theme Provider)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Task Panel   │   │ Results Panel │   │ Console Panel │
│               │   │               │   │               │
│ ┌───────────┐ │   │ ┌───────────┐ │   │ ┌───────────┐ │
│ │TaskInput  │ │   │ │Summary    │ │   │ │ConsoleOut │ │
│ └───────────┘ │   │ └───────────┘ │   │ └───────────┘ │
│ ┌───────────┐ │   │ ┌───────────┐ │   └───────────────┘
│ │ModelSelect│ │   │ │DAG View   │ │
│ └───────────┘ │   │ └───────────┘ │
│ ┌───────────┐ │   │ ┌───────────┐ │
│ │Credentials│ │   │ │FileBrowse │ │
│ └───────────┘ │   │ └───────────┘ │
│ ┌───────────┐ │   │ ┌───────────┐ │
│ │Workflow   │ │   │ │CostTable  │ │
│ │Controls   │ │   │ └───────────┘ │
│ └───────────┘ │   │ ┌───────────┐ │
└───────────────┘   │ │BranchView │ │
                    │ └───────────┘ │
                    └───────────────┘
```

## State Management Architecture

### Global State (React Context)

```typescript
// WebSocket Connection State
interface WebSocketState {
  connected: boolean;
  reconnectAttempt: number;
  lastError: string | null;
  lastMessageTimestamp: number;
}

// Workflow State
interface WorkflowState {
  currentRunId: string | null;
  status: WorkflowStatus;
  startedAt: Date | null;
  completedAt: Date | null;
  error: string | null;
}

// DAG State
interface DAGState {
  nodes: DAGNode[];
  edges: DAGEdge[];
  selectedNodeId: string | null;
  layout: 'horizontal' | 'vertical';
}

// Approval State
interface ApprovalState {
  pendingApprovals: ApprovalRequest[];
  currentApproval: ApprovalRequest | null;
  history: ApprovalResolution[];
}

// Metrics State
interface MetricsState {
  totalCost: number;
  costByStep: Map<string, number>;
  tokenUsage: TokenUsage;
  executionTime: number;
}
```

### Context Providers

```
<AppProvider>
  <WebSocketProvider>
    <WorkflowProvider>
      <DAGProvider>
        <ApprovalProvider>
          <MetricsProvider>
            <App />
          </MetricsProvider>
        </ApprovalProvider>
      </DAGProvider>
    </WorkflowProvider>
  </WebSocketProvider>
</AppProvider>
```

## Data Flow Architecture

### WebSocket Event Flow

```
Backend State Change
       │
       ▼
WebSocket Event Emitted
       │
       ▼
┌──────────────────────┐
│ useResilientWebSocket│
│ (Connection Handler) │
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│  useEventHandler     │
│  (Event Router)      │
└──────────────────────┘
       │
       ├───────────────────────────────────────┐
       │                                       │
       ▼                                       ▼
┌──────────────────┐                 ┌──────────────────┐
│ WorkflowContext  │                 │   DAGContext     │
│ (State Update)   │                 │ (Node Updates)   │
└──────────────────┘                 └──────────────────┘
       │                                       │
       ▼                                       ▼
┌──────────────────┐                 ┌──────────────────┐
│ WorkflowDashboard│                 │ DAGVisualization │
│ (Re-render)      │                 │ (Re-render)      │
└──────────────────┘                 └──────────────────┘
```

### Event Handler Implementation

```typescript
// hooks/useEventHandler.ts
export function useEventHandler() {
  const { updateWorkflowState } = useWorkflow();
  const { updateDAGNode } = useDAG();
  const { addApproval, resolveApproval } = useApproval();
  const { updateMetrics } = useMetrics();
  const { addConsoleOutput } = useConsole();

  const handleEvent = useCallback((event: WebSocketEvent) => {
    switch (event.event_type) {
      // Workflow events
      case 'workflow_started':
        updateWorkflowState({ status: 'executing', startedAt: new Date() });
        break;
      case 'workflow_state_changed':
        updateWorkflowState(event.data);
        break;
      case 'workflow_completed':
        updateWorkflowState({ status: 'completed', completedAt: new Date() });
        break;
      case 'workflow_failed':
        updateWorkflowState({ status: 'failed', error: event.data.error });
        break;

      // DAG events
      case 'dag_created':
        initializeDAG(event.data.nodes, event.data.edges);
        break;
      case 'dag_node_status_changed':
        updateDAGNode(event.data.node_id, event.data.new_status);
        break;

      // Approval events
      case 'approval_requested':
        addApproval(event.data);
        break;
      case 'approval_received':
        resolveApproval(event.data.approval_id, event.data);
        break;

      // Retry events
      case 'step_retry_started':
        updateDAGNode(event.data.step_id, 'retrying', event.data);
        addConsoleOutput(`⟳ Retrying step: ${event.data.step_id} (attempt ${event.data.attempt_number})`);
        break;

      // Metrics events
      case 'cost_update':
        updateMetrics({ cost: event.data });
        break;

      // Agent events
      case 'agent_message':
        addConsoleOutput(`[${event.data.agent}] ${event.data.message}`);
        break;

      // Error events
      case 'error_occurred':
        addConsoleOutput(`❌ Error: ${event.data.message}`);
        break;

      default:
        console.log('Unhandled event:', event.event_type);
    }
  }, [updateWorkflowState, updateDAGNode, addApproval, updateMetrics, addConsoleOutput]);

  return { handleEvent };
}
```

## Component Hierarchy

### DAG Visualization

```
DAGVisualization
├── DAGControls (zoom, pan, layout toggle)
├── DAGCanvas
│   ├── DAGEdge[] (connections between nodes)
│   └── DAGNode[]
│       ├── NodeIcon (agent type icon)
│       ├── NodeStatus (status badge)
│       ├── NodeLabel (step description)
│       └── NodeProgress (if running)
├── DAGMinimap (optional overview)
└── DAGNodeDetails (selected node panel)
```

### Workflow Dashboard

```
WorkflowDashboard
├── WorkflowHeader
│   ├── WorkflowTitle
│   ├── WorkflowStatus (state badge)
│   └── WorkflowControls (pause/resume/cancel)
├── WorkflowProgress
│   ├── ProgressBar (overall progress)
│   └── StepIndicators (step status dots)
├── WorkflowTabs
│   ├── TabDAG → DAGVisualization
│   ├── TabSteps → StepTable
│   ├── TabCost → CostDashboard
│   └── TabBranches → BranchTree
└── WorkflowTimeline (execution history)
```

### Approval System

```
ApprovalSystem
├── ApprovalNotification (toast/banner when approval needed)
├── ApprovalDialog (modal for approval)
│   ├── ApprovalHeader (checkpoint type, step info)
│   ├── ApprovalMessage (what needs approval)
│   ├── ApprovalContext (collapsible context details)
│   ├── ApprovalOptions (radio buttons)
│   ├── ApprovalFeedback (textarea for user input)
│   └── ApprovalActions (submit/cancel buttons)
└── ApprovalHistory (past approvals list)
```

### Branching UI

```
BranchingPanel
├── BranchTree
│   ├── BranchNode[] (branch nodes)
│   │   ├── BranchIcon
│   │   ├── BranchName
│   │   ├── BranchHypothesis
│   │   └── BranchStatus
│   └── BranchConnector[] (parent-child lines)
├── BranchControls
│   ├── CreateBranchButton
│   ├── SwitchBranchSelect
│   └── CompareBranchesButton
└── BranchComparison
    ├── ComparisonHeader (branch names)
    ├── ComparisonMetrics (cost, time, steps)
    ├── ComparisonSteps (side-by-side step diff)
    └── ComparisonFiles (file diff view)
```

### Table Views

```
DataTables
├── SessionTable
│   ├── TableHeader (sortable columns)
│   ├── TableBody (virtualized rows)
│   │   └── SessionRow[]
│   │       ├── SessionName
│   │       ├── SessionStatus
│   │       ├── SessionRunsCount
│   │       ├── SessionCost
│   │       └── SessionActions
│   ├── TablePagination
│   └── TableFilters
├── WorkflowTable (similar structure)
└── StepTable (similar structure)
```

## UI State Machines

### Workflow UI States

```
┌─────────┐
│  IDLE   │ ← Initial state, no workflow
└────┬────┘
     │ Start workflow
     ▼
┌─────────┐
│CONNECTING│ ← WebSocket connecting
└────┬────┘
     │ Connected
     ▼
┌─────────┐
│ RUNNING │ ← Workflow executing
└────┬────┘
     │
     ├──────────────────┬──────────────────┐
     │ Pause clicked    │ Approval needed  │ Error
     ▼                  ▼                  ▼
┌─────────┐      ┌───────────┐      ┌─────────┐
│ PAUSED  │      │ APPROVING │      │ ERRORED │
└────┬────┘      └─────┬─────┘      └────┬────┘
     │ Resume          │ Submit          │ Retry/Abort
     └────────────────►│◄────────────────┘
                       ▼
                ┌─────────┐
                │ RUNNING │
                └────┬────┘
                     │ Complete
                     ▼
                ┌─────────┐
                │COMPLETED│
                └─────────┘
```

### DAG Node UI States

```
┌─────────┐
│ PENDING │ ← Not yet started
└────┬────┘
     │ Node starts
     ▼
┌─────────┐
│ RUNNING │ ← Currently executing
└────┬────┘
     │
     ├─────────────────┬─────────────────┐
     │ Success         │ Error           │ Waiting
     ▼                 ▼                 ▼
┌─────────┐      ┌─────────┐      ┌───────────┐
│COMPLETED│      │ FAILED  │      │ RETRYING  │
└─────────┘      └────┬────┘      └─────┬─────┘
                      │                 │
                      │ Retry           │ Max retries
                      ▼                 ▼
                ┌─────────┐       ┌─────────┐
                │ RUNNING │       │ FAILED  │
                └─────────┘       └─────────┘
```

## Styling Architecture

### Theme Structure

```typescript
// Tailwind CSS config extension
const theme = {
  extend: {
    colors: {
      // Workflow states
      'state-pending': '#6B7280',    // gray-500
      'state-running': '#3B82F6',    // blue-500
      'state-completed': '#10B981',  // green-500
      'state-failed': '#EF4444',     // red-500
      'state-paused': '#F59E0B',     // yellow-500
      'state-waiting': '#8B5CF6',    // purple-500
      'state-retrying': '#F97316',   // orange-500

      // DAG node types
      'node-planning': '#06B6D4',    // cyan-500
      'node-agent': '#3B82F6',       // blue-500
      'node-approval': '#8B5CF6',    // purple-500
      'node-parallel': '#10B981',    // green-500

      // Console colors
      'console-bg': '#0D1117',
      'console-text': '#E6EDF3',
      'console-error': '#F85149',
      'console-warning': '#D29922',
      'console-success': '#3FB950',
      'console-info': '#58A6FF',
    },
  },
};
```

### Component Styling Pattern

```typescript
// Consistent styling pattern for components
const statusStyles: Record<WorkflowStatus, string> = {
  pending: 'bg-state-pending/20 text-state-pending border-state-pending/30',
  running: 'bg-state-running/20 text-state-running border-state-running/30',
  completed: 'bg-state-completed/20 text-state-completed border-state-completed/30',
  failed: 'bg-state-failed/20 text-state-failed border-state-failed/30',
  paused: 'bg-state-paused/20 text-state-paused border-state-paused/30',
  waiting: 'bg-state-waiting/20 text-state-waiting border-state-waiting/30',
};

// Usage
<StatusBadge status={workflow.status} />
```

## Error Handling Architecture

### Error Boundaries

```typescript
// Error boundary for feature isolation
<ErrorBoundary
  fallback={<FeatureErrorFallback feature="DAG Visualization" />}
  onError={(error) => logError('DAGVisualization', error)}
>
  <DAGVisualization />
</ErrorBoundary>
```

### Error States by Component

```
Component           Error State Display
─────────────────────────────────────────────────
WebSocket           Banner: "Connection lost, reconnecting..."
DAGVisualization    Inline: "Failed to load DAG" + retry button
ApprovalDialog      Toast: "Failed to submit approval"
CostDashboard       Inline: "Error loading cost data" + retry
BranchComparison    Inline: "Failed to compare branches"
Tables              Inline: "Error loading data" + retry
```

## Performance Optimization Strategies

### 1. Virtualization
```typescript
// For large lists (steps, branches, files)
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={400}
  width="100%"
  itemCount={steps.length}
  itemSize={60}
>
  {({ index, style }) => (
    <StepRow step={steps[index]} style={style} />
  )}
</FixedSizeList>
```

### 2. Memoization
```typescript
// Expensive computations
const dagLayout = useMemo(() =>
  calculateDAGLayout(nodes, edges),
  [nodes, edges]
);

// Component memoization
const DAGNode = memo(({ node, selected }) => {
  // ...
});
```

### 3. Debouncing
```typescript
// For frequent events
const debouncedSearch = useMemo(
  () => debounce(searchSteps, 300),
  [searchSteps]
);
```

### 4. Code Splitting
```typescript
// Lazy load heavy components
const DAGVisualization = lazy(() => import('./components/dag/DAGVisualization'));
const BranchComparison = lazy(() => import('./components/branching/BranchComparison'));
```

## Testing Strategy

### Unit Tests
- Component rendering
- Hook behavior
- Event handler logic
- Utility functions

### Integration Tests
- WebSocket event handling
- State updates from events
- User interactions
- API calls

### E2E Tests (Optional)
- Full workflow execution
- Approval flow
- Branch creation
- Error scenarios

## Accessibility Considerations

### Keyboard Navigation
- Tab order through interactive elements
- Arrow keys for DAG node navigation
- Enter/Space for actions
- Escape to close modals

### Screen Reader Support
- ARIA labels for icons
- Live regions for status updates
- Role attributes for custom components
- Alt text for images

### Visual Accessibility
- Sufficient color contrast
- Status not conveyed by color alone
- Focus indicators
- Reduced motion support

## Mobile Responsiveness

### Breakpoints
```typescript
// Tailwind breakpoints
sm: '640px'   // Tablet portrait
md: '768px'   // Tablet landscape
lg: '1024px'  // Desktop
xl: '1280px'  // Large desktop
```

### Responsive Patterns
- DAG: Horizontal scroll on mobile, vertical layout
- Tables: Card view on mobile, table on desktop
- Console: Full width, collapsible on mobile
- Panels: Stacked on mobile, side-by-side on desktop

## Security Considerations

### Input Validation
- Sanitize user feedback in approvals
- Validate file paths before display
- Escape HTML in console output

### XSS Prevention
- Use React's built-in escaping
- DOMPurify for any raw HTML
- CSP headers in Next.js config

### API Security
- HTTPS only in production
- CORS configuration
- No sensitive data in client state

---

**Version:** 1.0
**Last Updated:** 2026-01-16
**Status:** Design Complete
