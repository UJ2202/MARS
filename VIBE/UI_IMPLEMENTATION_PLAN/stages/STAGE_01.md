# Stage 1: WebSocket Enhancement & Event Protocol Integration

**Phase:** 0 - Foundation
**Dependencies:** Backend Stage 5 complete
**Risk Level:** Medium

## Objectives

1. Replace basic `useWebSocket` hook with enhanced `useResilientWebSocket`
2. Implement comprehensive event handler for all WebSocket event types
3. Create event-driven state management system
4. Add connection status indicators and reconnection UI
5. Implement event queue for handling missed events

## Current State Analysis

### What We Have
- Basic `useWebSocket.ts` hook with simple message handling
- `useResilientWebSocket.ts` hook (created in backend Stage 5) with auto-reconnection
- Simple message types: output, status, result, error, complete, heartbeat
- No typed event protocol
- No event routing system

### What We Need
- Full integration of 25+ WebSocket event types from backend
- Event router that dispatches to appropriate handlers
- Context providers for different state domains
- Connection status UI with reconnection feedback
- Event queue for replay on reconnection

## Pre-Stage Verification

### Check Prerequisites
1. Backend running with enhanced WebSocket protocol
2. `useResilientWebSocket.ts` hook exists
3. `backend/websocket_events.py` defines all event types
4. WebSocket endpoint working at `ws://localhost:8000/ws/{run_id}`

### Test Current State
```bash
# Start backend
cd backend && python run.py

# Start frontend
cd cmbagent-ui && npm run dev

# Verify WebSocket connects
# Check browser console for connection logs
```

## Implementation Tasks

### Task 1: Create TypeScript Event Types
**Objective:** Define TypeScript types matching backend event protocol

**Files to Create:**
- `cmbagent-ui/types/websocket-events.ts`

**Implementation:**
```typescript
// types/websocket-events.ts

export enum WebSocketEventType {
  // Connection events
  CONNECTED = 'connected',
  DISCONNECTED = 'disconnected',
  RECONNECTED = 'reconnected',

  // Workflow lifecycle events
  WORKFLOW_STARTED = 'workflow_started',
  WORKFLOW_STATE_CHANGED = 'workflow_state_changed',
  WORKFLOW_PAUSED = 'workflow_paused',
  WORKFLOW_RESUMED = 'workflow_resumed',
  WORKFLOW_COMPLETED = 'workflow_completed',
  WORKFLOW_FAILED = 'workflow_failed',

  // Step execution events
  STEP_STARTED = 'step_started',
  STEP_PROGRESS = 'step_progress',
  STEP_COMPLETED = 'step_completed',
  STEP_FAILED = 'step_failed',

  // Retry events
  STEP_RETRY_STARTED = 'step_retry_started',
  STEP_RETRY_BACKOFF = 'step_retry_backoff',
  STEP_RETRY_SUCCEEDED = 'step_retry_succeeded',
  STEP_RETRY_EXHAUSTED = 'step_retry_exhausted',

  // DAG events
  DAG_CREATED = 'dag_created',
  DAG_UPDATED = 'dag_updated',
  DAG_NODE_STATUS_CHANGED = 'dag_node_status_changed',

  // Agent events
  AGENT_MESSAGE = 'agent_message',
  AGENT_THINKING = 'agent_thinking',
  AGENT_TOOL_CALL = 'agent_tool_call',

  // Approval events
  APPROVAL_REQUESTED = 'approval_requested',
  APPROVAL_RECEIVED = 'approval_received',

  // Cost and metrics
  COST_UPDATE = 'cost_update',
  METRIC_UPDATE = 'metric_update',

  // File events
  FILE_CREATED = 'file_created',
  FILE_UPDATED = 'file_updated',

  // Error events
  ERROR_OCCURRED = 'error_occurred',

  // Heartbeat
  HEARTBEAT = 'heartbeat',
  PONG = 'pong',

  // Legacy (backward compatibility)
  OUTPUT = 'output',
  STATUS = 'status',
  RESULT = 'result',
  COMPLETE = 'complete',
}

export interface WebSocketEvent {
  event_type: WebSocketEventType | string;
  timestamp: string;
  run_id?: string;
  session_id?: string;
  data: Record<string, any>;
}

// Specific event data types
export interface WorkflowStartedData {
  run_id: string;
  task_description: string;
  agent: string;
  model: string;
  work_dir?: string;
}

export interface WorkflowStateChangedData {
  status: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

export interface StepStartedData {
  step_id: string;
  step_number: number;
  step_description: string;
  agent: string;
}

export interface StepProgressData {
  step_id: string;
  step_number: number;
  progress_percentage: number;
  message: string;
}

export interface StepCompletedData {
  step_id: string;
  step_number: number;
  result?: string;
  output?: string;
}

export interface StepFailedData {
  step_id: string;
  step_number: number;
  error: string;
  traceback?: string;
}

export interface StepRetryStartedData {
  step_id: string;
  step_number: number;
  attempt_number: number;
  max_attempts: number;
  error_category: string;
  error_pattern?: string;
  success_probability?: number;
  strategy: string;
  suggestions: string[];
  has_user_feedback: boolean;
}

export interface DAGCreatedData {
  run_id: string;
  nodes: DAGNodeData[];
  edges: DAGEdgeData[];
  levels: number;
}

export interface DAGNodeData {
  id: string;
  label: string;
  type: string;
  status: string;
  agent?: string;
  step_number?: number;
  metadata?: Record<string, any>;
}

export interface DAGEdgeData {
  source: string;
  target: string;
  type?: string;
}

export interface DAGNodeStatusChangedData {
  node_id: string;
  old_status: string;
  new_status: string;
  error?: string;
}

export interface AgentMessageData {
  agent: string;
  message: string;
  role: string;
}

export interface ApprovalRequestedData {
  approval_id: string;
  step_id: string;
  action: string;
  description: string;
  context: Record<string, any>;
  options?: string[];
  checkpoint_type?: string;
}

export interface ApprovalReceivedData {
  approval_id: string;
  approved: boolean;
  feedback?: string;
}

export interface CostUpdateData {
  run_id: string;
  step_id?: string;
  model: string;
  tokens: number;
  cost_usd: number;
  total_cost_usd: number;
}

export interface ErrorOccurredData {
  error_type: string;
  message: string;
  step_id?: string;
  traceback?: string;
}
```

**Verification:**
- Types compile without errors
- Types match backend `websocket_events.py` definitions

### Task 2: Create Event Handler Hook
**Objective:** Route WebSocket events to appropriate state handlers

**Files to Create:**
- `cmbagent-ui/hooks/useEventHandler.ts`

**Implementation:**
```typescript
// hooks/useEventHandler.ts

import { useCallback } from 'react';
import {
  WebSocketEvent,
  WebSocketEventType,
  WorkflowStartedData,
  WorkflowStateChangedData,
  DAGCreatedData,
  DAGNodeStatusChangedData,
  ApprovalRequestedData,
  StepRetryStartedData,
  CostUpdateData,
  AgentMessageData,
  ErrorOccurredData,
} from '@/types/websocket-events';

interface EventHandlers {
  // Workflow handlers
  onWorkflowStarted?: (data: WorkflowStartedData) => void;
  onWorkflowStateChanged?: (data: WorkflowStateChangedData) => void;
  onWorkflowPaused?: () => void;
  onWorkflowResumed?: () => void;
  onWorkflowCompleted?: () => void;
  onWorkflowFailed?: (error: string) => void;

  // Step handlers
  onStepStarted?: (data: any) => void;
  onStepProgress?: (data: any) => void;
  onStepCompleted?: (data: any) => void;
  onStepFailed?: (data: any) => void;

  // Retry handlers
  onRetryStarted?: (data: StepRetryStartedData) => void;
  onRetryBackoff?: (data: any) => void;
  onRetrySucceeded?: (data: any) => void;
  onRetryExhausted?: (data: any) => void;

  // DAG handlers
  onDAGCreated?: (data: DAGCreatedData) => void;
  onDAGUpdated?: (data: any) => void;
  onDAGNodeStatusChanged?: (data: DAGNodeStatusChangedData) => void;

  // Agent handlers
  onAgentMessage?: (data: AgentMessageData) => void;
  onAgentThinking?: (data: any) => void;
  onAgentToolCall?: (data: any) => void;

  // Approval handlers
  onApprovalRequested?: (data: ApprovalRequestedData) => void;
  onApprovalReceived?: (data: any) => void;

  // Metrics handlers
  onCostUpdate?: (data: CostUpdateData) => void;
  onMetricUpdate?: (data: any) => void;

  // File handlers
  onFileCreated?: (data: any) => void;
  onFileUpdated?: (data: any) => void;

  // Error handlers
  onError?: (data: ErrorOccurredData) => void;

  // Legacy handlers (backward compatibility)
  onOutput?: (output: string) => void;
  onStatus?: (status: string) => void;
  onResult?: (result: any) => void;
  onComplete?: () => void;
}

export function useEventHandler(handlers: EventHandlers) {
  const handleEvent = useCallback((event: WebSocketEvent) => {
    const { event_type, data } = event;

    switch (event_type) {
      // Workflow events
      case WebSocketEventType.WORKFLOW_STARTED:
        handlers.onWorkflowStarted?.(data as WorkflowStartedData);
        break;
      case WebSocketEventType.WORKFLOW_STATE_CHANGED:
        handlers.onWorkflowStateChanged?.(data as WorkflowStateChangedData);
        break;
      case WebSocketEventType.WORKFLOW_PAUSED:
        handlers.onWorkflowPaused?.();
        break;
      case WebSocketEventType.WORKFLOW_RESUMED:
        handlers.onWorkflowResumed?.();
        break;
      case WebSocketEventType.WORKFLOW_COMPLETED:
        handlers.onWorkflowCompleted?.();
        break;
      case WebSocketEventType.WORKFLOW_FAILED:
        handlers.onWorkflowFailed?.(data.error || 'Unknown error');
        break;

      // Step events
      case WebSocketEventType.STEP_STARTED:
        handlers.onStepStarted?.(data);
        break;
      case WebSocketEventType.STEP_PROGRESS:
        handlers.onStepProgress?.(data);
        break;
      case WebSocketEventType.STEP_COMPLETED:
        handlers.onStepCompleted?.(data);
        break;
      case WebSocketEventType.STEP_FAILED:
        handlers.onStepFailed?.(data);
        break;

      // Retry events
      case WebSocketEventType.STEP_RETRY_STARTED:
        handlers.onRetryStarted?.(data as StepRetryStartedData);
        break;
      case WebSocketEventType.STEP_RETRY_BACKOFF:
        handlers.onRetryBackoff?.(data);
        break;
      case WebSocketEventType.STEP_RETRY_SUCCEEDED:
        handlers.onRetrySucceeded?.(data);
        break;
      case WebSocketEventType.STEP_RETRY_EXHAUSTED:
        handlers.onRetryExhausted?.(data);
        break;

      // DAG events
      case WebSocketEventType.DAG_CREATED:
        handlers.onDAGCreated?.(data as DAGCreatedData);
        break;
      case WebSocketEventType.DAG_UPDATED:
        handlers.onDAGUpdated?.(data);
        break;
      case WebSocketEventType.DAG_NODE_STATUS_CHANGED:
        handlers.onDAGNodeStatusChanged?.(data as DAGNodeStatusChangedData);
        break;

      // Agent events
      case WebSocketEventType.AGENT_MESSAGE:
        handlers.onAgentMessage?.(data as AgentMessageData);
        // Also send to legacy output handler
        handlers.onOutput?.(`[${data.agent}] ${data.message}`);
        break;
      case WebSocketEventType.AGENT_THINKING:
        handlers.onAgentThinking?.(data);
        break;
      case WebSocketEventType.AGENT_TOOL_CALL:
        handlers.onAgentToolCall?.(data);
        break;

      // Approval events
      case WebSocketEventType.APPROVAL_REQUESTED:
        handlers.onApprovalRequested?.(data as ApprovalRequestedData);
        break;
      case WebSocketEventType.APPROVAL_RECEIVED:
        handlers.onApprovalReceived?.(data);
        break;

      // Metrics events
      case WebSocketEventType.COST_UPDATE:
        handlers.onCostUpdate?.(data as CostUpdateData);
        break;
      case WebSocketEventType.METRIC_UPDATE:
        handlers.onMetricUpdate?.(data);
        break;

      // File events
      case WebSocketEventType.FILE_CREATED:
        handlers.onFileCreated?.(data);
        break;
      case WebSocketEventType.FILE_UPDATED:
        handlers.onFileUpdated?.(data);
        break;

      // Error events
      case WebSocketEventType.ERROR_OCCURRED:
        handlers.onError?.(data as ErrorOccurredData);
        handlers.onOutput?.(`❌ Error: ${data.message}`);
        break;

      // Heartbeat (ignore, just for connection keepalive)
      case WebSocketEventType.HEARTBEAT:
      case WebSocketEventType.PONG:
        break;

      // Legacy event types (backward compatibility)
      case WebSocketEventType.OUTPUT:
      case 'output':
        handlers.onOutput?.(data.data || data.message || String(data));
        break;
      case WebSocketEventType.STATUS:
      case 'status':
        handlers.onStatus?.(data.message || String(data));
        handlers.onOutput?.(`📊 ${data.message}`);
        break;
      case WebSocketEventType.RESULT:
      case 'result':
        handlers.onResult?.(data.data || data);
        break;
      case WebSocketEventType.COMPLETE:
      case 'complete':
        handlers.onComplete?.();
        break;

      default:
        console.log('Unhandled WebSocket event:', event_type, data);
    }
  }, [handlers]);

  return { handleEvent };
}
```

**Verification:**
- All event types handled
- Legacy events still work
- Console logs for unhandled events

### Task 3: Create Connection Status Component
**Objective:** Visual indicator for WebSocket connection state

**Files to Create:**
- `cmbagent-ui/components/common/ConnectionStatus.tsx`

**Implementation:**
```typescript
// components/common/ConnectionStatus.tsx

import { Wifi, WifiOff, RefreshCw } from 'lucide-react';

interface ConnectionStatusProps {
  connected: boolean;
  reconnectAttempt: number;
  lastError: string | null;
  onReconnect?: () => void;
}

export function ConnectionStatus({
  connected,
  reconnectAttempt,
  lastError,
  onReconnect,
}: ConnectionStatusProps) {
  if (connected) {
    return (
      <div className="flex items-center space-x-2 text-green-400">
        <Wifi className="w-4 h-4" />
        <span className="text-xs">Connected</span>
      </div>
    );
  }

  if (reconnectAttempt > 0) {
    return (
      <div className="flex items-center space-x-2 text-yellow-400">
        <RefreshCw className="w-4 h-4 animate-spin" />
        <span className="text-xs">
          Reconnecting... (attempt {reconnectAttempt})
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center space-x-2 text-red-400">
      <WifiOff className="w-4 h-4" />
      <span className="text-xs">Disconnected</span>
      {lastError && (
        <span className="text-xs text-gray-400">({lastError})</span>
      )}
      {onReconnect && (
        <button
          onClick={onReconnect}
          className="px-2 py-0.5 text-xs bg-red-500/20 hover:bg-red-500/30 rounded"
        >
          Retry
        </button>
      )}
    </div>
  );
}
```

### Task 4: Create WebSocket Context Provider
**Objective:** Global WebSocket state accessible throughout app

**Files to Create:**
- `cmbagent-ui/contexts/WebSocketContext.tsx`

**Implementation:**
```typescript
// contexts/WebSocketContext.tsx

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { useResilientWebSocket } from '@/hooks/useResilientWebSocket';
import { useEventHandler } from '@/hooks/useEventHandler';
import { WebSocketEvent, DAGCreatedData, DAGNodeStatusChangedData, ApprovalRequestedData } from '@/types/websocket-events';

interface WebSocketContextValue {
  // Connection state
  connected: boolean;
  reconnectAttempt: number;
  lastError: string | null;

  // Actions
  sendMessage: (message: any) => void;
  disconnect: () => void;
  reconnect: () => void;

  // Current run
  currentRunId: string | null;
  setCurrentRunId: (runId: string | null) => void;

  // Workflow state
  workflowStatus: string | null;
  setWorkflowStatus: (status: string | null) => void;

  // DAG state
  dagData: { nodes: any[]; edges: any[] } | null;
  updateDAGNode: (nodeId: string, status: string) => void;

  // Approval state
  pendingApproval: ApprovalRequestedData | null;
  clearApproval: () => void;

  // Console output
  consoleOutput: string[];
  addConsoleOutput: (output: string) => void;
  clearConsole: () => void;

  // Results
  results: any | null;
  setResults: (results: any) => void;
}

const WebSocketContext = createContext<WebSocketContextValue | undefined>(undefined);

interface WebSocketProviderProps {
  children: ReactNode;
}

export function WebSocketProvider({ children }: WebSocketProviderProps) {
  // Local state
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<string | null>(null);
  const [dagData, setDAGData] = useState<{ nodes: any[]; edges: any[] } | null>(null);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequestedData | null>(null);
  const [consoleOutput, setConsoleOutput] = useState<string[]>([]);
  const [results, setResults] = useState<any | null>(null);

  // Console helpers
  const addConsoleOutput = useCallback((output: string) => {
    setConsoleOutput(prev => [...prev, output]);
  }, []);

  const clearConsole = useCallback(() => {
    setConsoleOutput([]);
  }, []);

  // DAG helpers
  const updateDAGNode = useCallback((nodeId: string, status: string) => {
    setDAGData(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        nodes: prev.nodes.map(node =>
          node.id === nodeId ? { ...node, status } : node
        ),
      };
    });
  }, []);

  // Approval helpers
  const clearApproval = useCallback(() => {
    setPendingApproval(null);
  }, []);

  // Event handler
  const { handleEvent } = useEventHandler({
    onWorkflowStarted: (data) => {
      setWorkflowStatus('executing');
      addConsoleOutput(`🚀 Workflow started: ${data.task_description}`);
    },
    onWorkflowStateChanged: (data) => {
      setWorkflowStatus(data.status);
    },
    onWorkflowCompleted: () => {
      setWorkflowStatus('completed');
      addConsoleOutput('✅ Workflow completed');
    },
    onWorkflowFailed: (error) => {
      setWorkflowStatus('failed');
      addConsoleOutput(`❌ Workflow failed: ${error}`);
    },
    onDAGCreated: (data: DAGCreatedData) => {
      setDAGData({ nodes: data.nodes, edges: data.edges });
      addConsoleOutput(`📊 DAG created with ${data.nodes.length} nodes`);
    },
    onDAGNodeStatusChanged: (data: DAGNodeStatusChangedData) => {
      updateDAGNode(data.node_id, data.new_status);
    },
    onApprovalRequested: (data: ApprovalRequestedData) => {
      setPendingApproval(data);
      addConsoleOutput(`⏸️ Approval requested: ${data.description}`);
    },
    onApprovalReceived: () => {
      clearApproval();
    },
    onOutput: addConsoleOutput,
    onResult: setResults,
    onComplete: () => {
      setWorkflowStatus('completed');
    },
    onError: (data) => {
      addConsoleOutput(`❌ ${data.error_type}: ${data.message}`);
    },
  });

  // WebSocket message handler
  const onMessage = useCallback((event: WebSocketEvent) => {
    handleEvent(event);
  }, [handleEvent]);

  // WebSocket connection
  const {
    connected,
    reconnectAttempt,
    lastError,
    sendMessage,
    disconnect,
    reconnect,
  } = useResilientWebSocket({
    runId: currentRunId || 'default',
    onMessage,
    onConnectionChange: (isConnected) => {
      if (isConnected) {
        addConsoleOutput('🔌 WebSocket connected');
      } else {
        addConsoleOutput('🔌 WebSocket disconnected');
      }
    },
  });

  const value: WebSocketContextValue = {
    connected,
    reconnectAttempt,
    lastError,
    sendMessage,
    disconnect,
    reconnect,
    currentRunId,
    setCurrentRunId,
    workflowStatus,
    setWorkflowStatus,
    dagData,
    updateDAGNode,
    pendingApproval,
    clearApproval,
    consoleOutput,
    addConsoleOutput,
    clearConsole,
    results,
    setResults,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext);
  if (context === undefined) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
}
```

### Task 5: Integrate into Main Page
**Objective:** Update main page to use new WebSocket system

**Files to Modify:**
- `cmbagent-ui/app/page.tsx`
- `cmbagent-ui/app/layout.tsx`

**Changes:**

```typescript
// app/layout.tsx - Add WebSocketProvider
import { WebSocketProvider } from '@/contexts/WebSocketContext';

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <WebSocketProvider>
          {children}
        </WebSocketProvider>
      </body>
    </html>
  );
}
```

```typescript
// app/page.tsx - Use context instead of local state
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { ConnectionStatus } from '@/components/common/ConnectionStatus';

export default function Home() {
  const {
    connected,
    reconnectAttempt,
    lastError,
    reconnect,
    workflowStatus,
    consoleOutput,
    addConsoleOutput,
    clearConsole,
    results,
    pendingApproval,
  } = useWebSocketContext();

  // ... rest of component using context values
}
```

## Files to Create (Summary)

```
cmbagent-ui/
├── types/
│   └── websocket-events.ts        # TypeScript event types
├── hooks/
│   └── useEventHandler.ts         # Event routing hook
├── contexts/
│   └── WebSocketContext.tsx       # Global WebSocket state
└── components/
    └── common/
        └── ConnectionStatus.tsx   # Connection indicator
```

## Files to Modify

- `cmbagent-ui/app/layout.tsx` - Add WebSocketProvider
- `cmbagent-ui/app/page.tsx` - Use WebSocket context
- `cmbagent-ui/components/Header.tsx` - Add ConnectionStatus

## Verification Criteria

### Must Pass
- [ ] TypeScript types compile without errors
- [ ] WebSocket connects successfully
- [ ] Auto-reconnection works (test by killing backend)
- [ ] All legacy event types still work
- [ ] New event types handled correctly
- [ ] Console output shows events
- [ ] Connection status indicator works

### Should Pass
- [ ] Exponential backoff on reconnection
- [ ] Event queue delivers missed events
- [ ] Context values update correctly
- [ ] No memory leaks on unmount

### Testing Commands
```bash
# Type checking
cd cmbagent-ui && npm run build

# Start app
npm run dev

# Test WebSocket
# 1. Start backend: cd backend && python run.py
# 2. Open browser to localhost:3000
# 3. Submit a task
# 4. Kill backend, verify reconnection attempts
# 5. Restart backend, verify reconnection
```

## Common Issues and Solutions

### Issue 1: WebSocket Won't Connect
**Symptom:** Connection never establishes
**Solution:** Check backend is running, CORS config, port matches

### Issue 2: Events Not Handled
**Symptom:** Console logs "Unhandled event"
**Solution:** Add handler for that event type in useEventHandler

### Issue 3: Context Not Available
**Symptom:** "useWebSocketContext must be used within WebSocketProvider"
**Solution:** Ensure WebSocketProvider wraps the component tree

### Issue 4: TypeScript Errors
**Symptom:** Type mismatch errors
**Solution:** Update types to match actual backend event structure

## Rollback Procedure

If Stage 1 causes issues:
1. Revert to using original `useWebSocket.ts` hook
2. Remove WebSocketProvider from layout
3. Restore original page.tsx state management
4. Document what went wrong

## Success Criteria

Stage 1 is complete when:
1. All TypeScript types defined and compiling
2. Event handler routing all event types
3. WebSocket context available app-wide
4. Connection status visible in header
5. Auto-reconnection working
6. Legacy functionality preserved
7. All verification criteria pass

## Next Stage

Once Stage 1 is verified complete, proceed to:
**Stage 2: DAG Visualization Component**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-16
