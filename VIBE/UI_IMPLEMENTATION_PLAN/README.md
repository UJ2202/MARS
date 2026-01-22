# CMBAgent UI Enhancement Implementation Plan

## Overview
This document provides a comprehensive, stage-by-stage implementation plan for enhancing the CMBAgent React UI to integrate all backend features from Stages 1-9, including real-time WebSocket events, DAG visualization, HITL approvals, retry UI, branching, and comprehensive table views.

**Total Stages:** 9 stages organized into 4 phases
**Current Stage:** 0 (Not Started)
**Backend Dependency:** Requires backend Stages 1-9 complete

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
- This README file location
- Claude will cross-verify previous stages and continue

## Stage Overview

### Phase 0: Foundation (Stages 1-2)
**Goal:** Establish robust WebSocket communication and core visualization

- **Stage 1:** WebSocket Enhancement & Event Protocol Integration
- **Stage 2:** DAG Visualization Component

### Phase 1: Workflow Control (Stages 3-5)
**Goal:** Implement workflow state management and user interaction features

- **Stage 3:** Workflow State Dashboard & Controls
- **Stage 4:** HITL Approval System UI
- **Stage 5:** Retry UI with Context Display

### Phase 2: Advanced Features (Stages 6-7)
**Goal:** Branching, comparison, and comprehensive data views

- **Stage 6:** Branching & Comparison UI
- **Stage 7:** Session & Workflow Table Views

### Phase 3: Observability (Stages 8-9)
**Goal:** Cost tracking and real-time metrics visualization

- **Stage 8:** Cost Tracking Dashboard
- **Stage 9:** Real-time Metrics & Observability UI

## Directory Structure

```
UI_IMPLEMENTATION_PLAN/
├── README.md                    # This file - master plan
├── PROGRESS.md                  # Track completion status
├── ARCHITECTURE.md              # UI architecture decisions
├── stages/
│   ├── STAGE_01.md             # WebSocket enhancement
│   ├── STAGE_02.md             # DAG visualization
│   ├── STAGE_03.md             # Workflow state dashboard
│   ├── STAGE_04.md             # HITL approval UI
│   ├── STAGE_05.md             # Retry UI
│   ├── STAGE_06.md             # Branching UI
│   ├── STAGE_07.md             # Table views
│   ├── STAGE_08.md             # Cost dashboard
│   └── STAGE_09.md             # Metrics UI
├── references/
│   ├── current_ui_analysis.md  # Current UI component analysis
│   ├── backend_api_reference.md # Backend API endpoints
│   └── websocket_events.md     # WebSocket event types
└── tests/
    ├── test_scenarios.md       # Test scenarios per stage
    └── component_tests.md      # Component testing guide
```

## Current UI Analysis

### Existing Components (`cmbagent-ui/`)
```
components/
├── ApprovalDialog.tsx          # Basic approval dialog (needs enhancement)
├── ConsoleOutput.tsx           # Console output display
├── CredentialsKeyIcon.tsx      # Credentials icon
├── CredentialsModal.tsx        # Credentials modal
├── CredentialsStatus.tsx       # Credentials status display
├── FileBrowser.tsx             # File browser component
├── Header.tsx                  # App header
├── ModelSelector.tsx           # Model selection dropdown
├── ResultDisplay.tsx           # Results display with cost tables
└── TaskInput.tsx               # Task input form

hooks/
├── useCredentials.ts           # Credentials management hook
├── useResilientWebSocket.ts    # Auto-reconnecting WebSocket (NEW)
└── useWebSocket.ts             # Basic WebSocket hook

app/
├── layout.tsx                  # App layout
└── page.tsx                    # Main page component
```

### Backend Features to Integrate (Stages 1-9)

| Backend Stage | Feature | UI Component Needed |
|---------------|---------|---------------------|
| Stage 2 | Database models | Session/Workflow tables |
| Stage 3 | State machine | Workflow state display |
| Stage 4 | DAG system | DAG visualization |
| Stage 5 | WebSocket events | Event handling system |
| Stage 6 | HITL approvals | Enhanced approval dialog |
| Stage 7 | Context-aware retry | Retry status UI |
| Stage 8 | Parallel execution | Parallel progress display |
| Stage 9 | Branching | Branch tree & comparison UI |

## New Components to Create

### Core Components
```
components/
├── dag/
│   ├── DAGVisualization.tsx    # Interactive DAG graph
│   ├── DAGNode.tsx             # Individual DAG node
│   ├── DAGEdge.tsx             # DAG edge connector
│   └── DAGControls.tsx         # DAG zoom/pan controls
├── workflow/
│   ├── WorkflowDashboard.tsx   # Main workflow view
│   ├── WorkflowStateBar.tsx    # State indicator bar
│   ├── WorkflowControls.tsx    # Pause/Resume/Cancel buttons
│   └── WorkflowTimeline.tsx    # Execution timeline
├── approval/
│   ├── ApprovalDialog.tsx      # Enhanced approval dialog
│   ├── ApprovalQueue.tsx       # Pending approvals list
│   └── ApprovalHistory.tsx     # Past approvals
├── retry/
│   ├── RetryStatus.tsx         # Retry progress display
│   ├── RetryContext.tsx        # Error context viewer
│   └── RetryControls.tsx       # Manual retry controls
├── branching/
│   ├── BranchTree.tsx          # Branch hierarchy tree
│   ├── BranchComparison.tsx    # Side-by-side comparison
│   └── BranchControls.tsx      # Create/switch branch
├── tables/
│   ├── SessionTable.tsx        # Sessions list table
│   ├── WorkflowTable.tsx       # Workflows list table
│   ├── StepTable.tsx           # Steps list table
│   └── DataTable.tsx           # Reusable data table
├── metrics/
│   ├── CostDashboard.tsx       # Cost tracking view
│   ├── CostChart.tsx           # Cost over time chart
│   ├── MetricsPanel.tsx        # Real-time metrics
│   └── ResourceMonitor.tsx     # Resource usage display
└── common/
    ├── StatusBadge.tsx         # State status badges
    ├── ProgressBar.tsx         # Progress indicators
    ├── TimeDisplay.tsx         # Time/duration display
    └── LoadingSpinner.tsx      # Loading states
```

### New Hooks
```
hooks/
├── useWorkflowState.ts         # Workflow state management
├── useDAGVisualization.ts      # DAG rendering logic
├── useApprovals.ts             # Approval management
├── useRetryStatus.ts           # Retry state tracking
├── useBranching.ts             # Branching operations
├── useMetrics.ts               # Metrics & cost data
└── useEventHandler.ts          # WebSocket event routing
```

## Stage Dependencies

```
Stage 1 (WebSocket Enhancement)
  ↓
Stage 2 (DAG Visualization)
  ↓
Stage 3 (Workflow Dashboard) ←────┐
  ↓                               │
Stage 4 (HITL Approval UI)        │
  ↓                               │
Stage 5 (Retry UI)                │
  ↓                               │
Stage 6 (Branching UI)            │
  ↓                               │
Stage 7 (Table Views)             │
  ↓                               │
Stage 8 (Cost Dashboard)          │
  ↓                               │
Stage 9 (Metrics UI) ←────────────┘
```

## Critical Success Factors

### 1. Real-Time Updates
- All state changes reflected immediately
- No polling - pure WebSocket events
- Graceful handling of connection loss
- Event queue for missed events

### 2. User Experience
- Intuitive navigation
- Clear status indicators
- Responsive design
- Accessible controls

### 3. Data Consistency
- UI state matches backend database
- Optimistic updates with rollback
- Clear loading/error states
- Proper error handling

### 4. Performance
- Efficient re-rendering
- Virtualized lists for large datasets
- Lazy loading of components
- Memoized expensive computations

### 5. Backward Compatibility
- Existing workflows still work
- Graceful degradation if features disabled
- Progressive enhancement

## Technology Stack

### Frontend
- **Next.js 14+** - React framework
- **React 18+** - UI library
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Lucide Icons** - Icon library

### Visualization
- **React Flow** or **D3.js** - DAG visualization
- **Recharts** or **Chart.js** - Charts and graphs

### State Management
- **React Context** - Global state
- **Custom Hooks** - Feature-specific state
- **WebSocket** - Real-time updates

### Testing
- **Jest** - Unit testing
- **React Testing Library** - Component testing
- **Cypress** - E2E testing (optional)

## API Endpoints Reference

### REST Endpoints (Backend)
```
GET    /api/health                      # Health check
GET    /api/credentials/status          # Credential status
POST   /api/credentials/store           # Store credentials

# Branching (Stage 9)
POST   /api/runs/{run_id}/branch        # Create branch
POST   /api/runs/{run_id}/play-from-node # Resume from node
GET    /api/branches/compare            # Compare branches
GET    /api/runs/{run_id}/branch-tree   # Get branch tree
GET    /api/runs/{run_id}/resumable-nodes # List resumable nodes

# Files
GET    /api/files/list                  # List directory
GET    /api/files/content               # Get file content
DELETE /api/files/clear-directory       # Clear directory
GET    /api/files/images                # Get images
GET    /api/files/serve-image           # Serve image
```

### WebSocket Events (Stage 5)
```typescript
// Connection events
CONNECTED, DISCONNECTED, RECONNECTED

// Workflow lifecycle
WORKFLOW_STARTED, WORKFLOW_STATE_CHANGED, WORKFLOW_PAUSED,
WORKFLOW_RESUMED, WORKFLOW_COMPLETED, WORKFLOW_FAILED

// Step execution
STEP_STARTED, STEP_PROGRESS, STEP_COMPLETED, STEP_FAILED

// Retry events
STEP_RETRY_STARTED, STEP_RETRY_BACKOFF,
STEP_RETRY_SUCCEEDED, STEP_RETRY_EXHAUSTED

// DAG events
DAG_CREATED, DAG_UPDATED, DAG_NODE_STATUS_CHANGED

// Agent events
AGENT_MESSAGE, AGENT_THINKING, AGENT_TOOL_CALL

// Approval events
APPROVAL_REQUESTED, APPROVAL_RECEIVED

// Metrics
COST_UPDATE, METRIC_UPDATE

// Files
FILE_CREATED, FILE_UPDATED

// Errors
ERROR_OCCURRED

// Heartbeat
HEARTBEAT, PONG
```

## Quick Reference Commands

### Development
```bash
cd cmbagent-ui
npm install           # Install dependencies
npm run dev           # Start dev server
npm run build         # Production build
npm run lint          # Run linter
npm run test          # Run tests
```

### Start New Stage
```bash
# Review stage details
cat UI_IMPLEMENTATION_PLAN/stages/STAGE_XX.md

# Update progress
# Edit UI_IMPLEMENTATION_PLAN/PROGRESS.md
```

### Verify Stage Completion
```bash
# Run stage-specific tests
npm run test -- --testPathPattern="stage_XX"

# Check verification criteria in STAGE_XX.md
```

## Risk Management

### High-Risk Areas
- **Stage 1:** WebSocket reconnection edge cases
- **Stage 2:** DAG rendering performance with large graphs
- **Stage 6:** Branch comparison with large diffs
- **Stage 7:** Table performance with many rows

### Mitigation Strategies
- Comprehensive error boundaries
- Virtualization for large lists
- Debouncing for frequent updates
- Feature flags for gradual rollout

## Important Notes

1. **Do Not Skip Stages:** Each stage builds on previous ones
2. **Test WebSocket:** Always test with connection loss scenarios
3. **Mobile Responsive:** Ensure components work on smaller screens
4. **Accessibility:** Follow WCAG guidelines
5. **Performance:** Profile rendering with React DevTools

## Next Steps

1. Review `PROGRESS.md` to check current status
2. Read `ARCHITECTURE.md` for technical overview
3. Start with `stages/STAGE_01.md` if beginning fresh
4. Follow stage-by-stage implementation
5. Update `PROGRESS.md` after each stage

---

**Last Updated:** 2026-01-16
**Plan Version:** 1.0
**Status:** Ready for implementation
