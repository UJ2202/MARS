# Stage 2: DAG Visualization Component

**Phase:** 0 - Foundation
**Dependencies:** Stage 1 (WebSocket Enhancement) complete
**Risk Level:** Medium-High
**Status:** IN PROGRESS

## Recent Changes (January 2026)

### Callback System Implementation

Added a robust callback architecture to track workflow execution for DAG visualization:

#### Files Modified/Created:
- **`cmbagent/callbacks.py`** - Enhanced with full callback system
- **`cmbagent/cmbagent.py`** - Added callback invocations at key points
- **`cmbagent/__init__.py`** - Exported callback types
- **`backend/main.py`** - Integrated workflow callbacks

#### Callback Types:
```python
@dataclass
class WorkflowCallbacks:
    on_planning_start: Optional[Callable[[str, Dict], None]] = None
    on_planning_complete: Optional[Callable[[PlanInfo], None]] = None
    on_step_start: Optional[Callable[[StepInfo], None]] = None
    on_step_complete: Optional[Callable[[StepInfo], None]] = None
    on_step_failed: Optional[Callable[[StepInfo], None]] = None
    on_workflow_start: Optional[Callable[[str, Dict], None]] = None
    on_workflow_complete: Optional[Callable[[Dict, float], None]] = None
    on_workflow_failed: Optional[Callable[[str, Optional[int]], None]] = None
```

#### WebSocket Callbacks:
`create_websocket_callbacks()` emits DAG events to the UI:
- `dag_node_status_changed` - Node transitions (pending→running→completed)
- `dag_updated` - Full DAG structure after planning completes

#### Callback Invocation Points in `planning_and_control_context_carryover()`:
1. **Line ~1210**: `invoke_workflow_start()` - Workflow begins
2. **Line ~1233**: `invoke_planning_start()` - Planning phase starts
3. **Line ~1300**: `invoke_planning_complete()` - Plan ready with steps
4. **Line ~1491**: `invoke_step_start()` - Each step begins
5. **Line ~1523**: `invoke_step_failed()` - Step failed
6. **Line ~1531**: `invoke_step_complete()` - Step completed

#### Debug Logging Added:
Added debug logging to `record_plan()` and `record_review()` in `functions.py` to trace planning loop issues.

### Known Issue: Infinite Planning Loop (Investigating)

**Problem:** When callbacks are enabled, the planning phase sometimes gets stuck cycling between `plan_recorder` → `plan_reviewer` endlessly.

**Current Status:** Debug logging added to investigate. Testing in progress.

**Workaround:** Callbacks can be disabled by commenting out `callbacks=workflow_callbacks` in main.py.

---

## Objectives

1. Create interactive DAG visualization component using React Flow
2. Display workflow execution as directed acyclic graph
3. Show real-time node status updates
4. Enable node selection for details view
5. Support zoom, pan, and layout controls
6. Handle large DAGs efficiently

## Current State Analysis

### What We Have
- DAG data structure from backend (Stage 4)
- `DAG_CREATED` and `DAG_NODE_STATUS_CHANGED` WebSocket events
- Basic workflow status display
- No visual graph representation

### What We Need
- Interactive graph visualization
- Node components with status badges
- Edge rendering with dependency arrows
- Zoom/pan controls
- Minimap for large graphs
- Node details panel
- Layout options (horizontal/vertical)

## Pre-Stage Verification

### Check Prerequisites
1. Stage 1 complete - WebSocket context working
2. Backend sends `DAG_CREATED` events with nodes/edges
3. Node status changes emit `DAG_NODE_STATUS_CHANGED` events
4. React Flow library compatible with Next.js 14

### Test Current State
```bash
# Start backend and verify DAG events
cd backend && python run.py

# In another terminal, watch WebSocket events
# Start a workflow and check for dag_created event
```

## Implementation Tasks

### Task 1: Install React Flow
**Objective:** Add React Flow library for graph visualization

**Commands:**
```bash
cd cmbagent-ui
npm install @xyflow/react
```

**Note:** React Flow v12+ uses `@xyflow/react` package name.

### Task 2: Create DAG Types
**Objective:** Define TypeScript types for DAG components

**Files to Create:**
- `cmbagent-ui/types/dag.ts`

**Implementation:**
```typescript
// types/dag.ts

import { Node, Edge, NodeProps } from '@xyflow/react';

export type NodeStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'paused'
  | 'waiting_approval'
  | 'retrying'
  | 'skipped';

export type NodeType =
  | 'planning'
  | 'control'
  | 'agent'
  | 'approval'
  | 'parallel'
  | 'terminator';

export interface DAGNodeData {
  id: string;
  label: string;
  type: NodeType;
  status: NodeStatus;
  agent?: string;
  stepNumber?: number;
  description?: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  retryInfo?: {
    attemptNumber: number;
    maxAttempts: number;
  };
}

export type DAGNode = Node<DAGNodeData, 'dagNode'>;
export type DAGEdge = Edge;

export interface DAGState {
  nodes: DAGNode[];
  edges: DAGEdge[];
  selectedNodeId: string | null;
  layout: 'horizontal' | 'vertical';
}

export interface DAGLayoutOptions {
  direction: 'TB' | 'LR';  // Top-Bottom or Left-Right
  nodeSpacing: number;
  levelSpacing: number;
}

// Status colors for nodes
export const statusColors: Record<NodeStatus, string> = {
  pending: '#6B7280',      // gray-500
  running: '#3B82F6',      // blue-500
  completed: '#10B981',    // green-500
  failed: '#EF4444',       // red-500
  paused: '#F59E0B',       // yellow-500
  waiting_approval: '#8B5CF6', // purple-500
  retrying: '#F97316',     // orange-500
  skipped: '#9CA3AF',      // gray-400
};

// Node type icons (Lucide icon names)
export const nodeTypeIcons: Record<NodeType, string> = {
  planning: 'ClipboardList',
  control: 'Settings2',
  agent: 'Bot',
  approval: 'UserCheck',
  parallel: 'GitBranch',
  terminator: 'CheckCircle',
};
```

### Task 3: Create Custom Node Component
**Objective:** Build the visual representation of DAG nodes

**Files to Create:**
- `cmbagent-ui/components/dag/DAGNode.tsx`

**Implementation:**
```typescript
// components/dag/DAGNode.tsx

'use client';

import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import {
  ClipboardList,
  Settings2,
  Bot,
  UserCheck,
  GitBranch,
  CheckCircle,
  Play,
  Pause,
  AlertCircle,
  RotateCw,
  Clock,
} from 'lucide-react';
import { DAGNodeData, NodeStatus, NodeType, statusColors } from '@/types/dag';

const nodeIcons: Record<NodeType, React.ReactNode> = {
  planning: <ClipboardList className="w-4 h-4" />,
  control: <Settings2 className="w-4 h-4" />,
  agent: <Bot className="w-4 h-4" />,
  approval: <UserCheck className="w-4 h-4" />,
  parallel: <GitBranch className="w-4 h-4" />,
  terminator: <CheckCircle className="w-4 h-4" />,
};

const statusIcons: Record<NodeStatus, React.ReactNode> = {
  pending: <Clock className="w-3 h-3" />,
  running: <Play className="w-3 h-3 animate-pulse" />,
  completed: <CheckCircle className="w-3 h-3" />,
  failed: <AlertCircle className="w-3 h-3" />,
  paused: <Pause className="w-3 h-3" />,
  waiting_approval: <UserCheck className="w-3 h-3 animate-pulse" />,
  retrying: <RotateCw className="w-3 h-3 animate-spin" />,
  skipped: <Clock className="w-3 h-3 opacity-50" />,
};

interface DAGNodeComponentProps extends NodeProps {
  data: DAGNodeData;
  selected: boolean;
}

function DAGNodeComponent({ data, selected }: DAGNodeComponentProps) {
  const statusColor = statusColors[data.status];
  const isActive = data.status === 'running' || data.status === 'retrying';

  return (
    <div
      className={`
        relative px-4 py-3 rounded-lg border-2 bg-gray-900/90 backdrop-blur
        transition-all duration-200 min-w-[180px] max-w-[250px]
        ${selected ? 'ring-2 ring-blue-400 ring-offset-2 ring-offset-gray-900' : ''}
        ${isActive ? 'shadow-lg shadow-blue-500/20' : ''}
      `}
      style={{ borderColor: statusColor }}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-gray-600 !border-2 !border-gray-400"
      />

      {/* Node Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <div
            className="p-1.5 rounded"
            style={{ backgroundColor: `${statusColor}20` }}
          >
            {nodeIcons[data.type]}
          </div>
          <span className="text-xs text-gray-400 uppercase">
            {data.type}
          </span>
        </div>
        <div
          className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs"
          style={{
            backgroundColor: `${statusColor}20`,
            color: statusColor,
          }}
        >
          {statusIcons[data.status]}
          <span>{data.status}</span>
        </div>
      </div>

      {/* Node Label */}
      <div className="text-sm font-medium text-white truncate" title={data.label}>
        {data.stepNumber !== undefined && (
          <span className="text-gray-400 mr-1">#{data.stepNumber}</span>
        )}
        {data.label}
      </div>

      {/* Agent Info */}
      {data.agent && (
        <div className="mt-1 text-xs text-gray-400 flex items-center space-x-1">
          <Bot className="w-3 h-3" />
          <span>{data.agent}</span>
        </div>
      )}

      {/* Retry Info */}
      {data.retryInfo && (
        <div className="mt-1 text-xs text-orange-400 flex items-center space-x-1">
          <RotateCw className="w-3 h-3" />
          <span>
            Attempt {data.retryInfo.attemptNumber}/{data.retryInfo.maxAttempts}
          </span>
        </div>
      )}

      {/* Error Preview */}
      {data.error && (
        <div className="mt-2 text-xs text-red-400 truncate" title={data.error}>
          {data.error}
        </div>
      )}

      {/* Running Animation */}
      {isActive && (
        <div
          className="absolute inset-0 rounded-lg border-2 animate-pulse pointer-events-none"
          style={{ borderColor: statusColor, opacity: 0.3 }}
        />
      )}

      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-gray-600 !border-2 !border-gray-400"
      />
    </div>
  );
}

export default memo(DAGNodeComponent);
```

### Task 4: Create DAG Controls Component
**Objective:** Zoom, pan, and layout controls for the DAG

**Files to Create:**
- `cmbagent-ui/components/dag/DAGControls.tsx`

**Implementation:**
```typescript
// components/dag/DAGControls.tsx

'use client';

import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  ArrowDownUp,
  ArrowLeftRight,
  RotateCcw,
} from 'lucide-react';
import { useReactFlow } from '@xyflow/react';

interface DAGControlsProps {
  layout: 'horizontal' | 'vertical';
  onLayoutChange: (layout: 'horizontal' | 'vertical') => void;
}

export function DAGControls({ layout, onLayoutChange }: DAGControlsProps) {
  const { zoomIn, zoomOut, fitView, setViewport } = useReactFlow();

  const handleReset = () => {
    setViewport({ x: 0, y: 0, zoom: 1 });
    setTimeout(() => fitView({ padding: 0.2 }), 50);
  };

  return (
    <div className="absolute bottom-4 left-4 z-10 flex items-center space-x-1 bg-gray-800/90 backdrop-blur rounded-lg p-1 border border-gray-700">
      {/* Zoom Controls */}
      <button
        onClick={() => zoomIn({ duration: 300 })}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="Zoom In"
      >
        <ZoomIn className="w-4 h-4 text-gray-300" />
      </button>
      <button
        onClick={() => zoomOut({ duration: 300 })}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="Zoom Out"
      >
        <ZoomOut className="w-4 h-4 text-gray-300" />
      </button>
      <button
        onClick={() => fitView({ padding: 0.2, duration: 300 })}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="Fit View"
      >
        <Maximize2 className="w-4 h-4 text-gray-300" />
      </button>

      <div className="w-px h-6 bg-gray-600 mx-1" />

      {/* Layout Toggle */}
      <button
        onClick={() => onLayoutChange('vertical')}
        className={`p-2 rounded transition-colors ${
          layout === 'vertical' ? 'bg-blue-500/20 text-blue-400' : 'hover:bg-gray-700 text-gray-300'
        }`}
        title="Vertical Layout"
      >
        <ArrowDownUp className="w-4 h-4" />
      </button>
      <button
        onClick={() => onLayoutChange('horizontal')}
        className={`p-2 rounded transition-colors ${
          layout === 'horizontal' ? 'bg-blue-500/20 text-blue-400' : 'hover:bg-gray-700 text-gray-300'
        }`}
        title="Horizontal Layout"
      >
        <ArrowLeftRight className="w-4 h-4" />
      </button>

      <div className="w-px h-6 bg-gray-600 mx-1" />

      {/* Reset */}
      <button
        onClick={handleReset}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="Reset View"
      >
        <RotateCcw className="w-4 h-4 text-gray-300" />
      </button>
    </div>
  );
}
```

### Task 5: Create Node Details Panel
**Objective:** Show detailed information when a node is selected

**Files to Create:**
- `cmbagent-ui/components/dag/DAGNodeDetails.tsx`

**Implementation:**
```typescript
// components/dag/DAGNodeDetails.tsx

'use client';

import { X, Clock, Bot, FileText, AlertTriangle, RotateCw } from 'lucide-react';
import { DAGNodeData, statusColors } from '@/types/dag';

interface DAGNodeDetailsProps {
  node: DAGNodeData | null;
  onClose: () => void;
  onPlayFromNode?: (nodeId: string) => void;
}

export function DAGNodeDetails({ node, onClose, onPlayFromNode }: DAGNodeDetailsProps) {
  if (!node) return null;

  const statusColor = statusColors[node.status];

  return (
    <div className="absolute top-4 right-4 z-10 w-80 bg-gray-800/95 backdrop-blur rounded-lg border border-gray-700 shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
        <h3 className="text-sm font-medium text-white">Node Details</h3>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-700 rounded transition-colors"
        >
          <X className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Status Badge */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400 uppercase">Status</span>
          <div
            className="flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium"
            style={{
              backgroundColor: `${statusColor}20`,
              color: statusColor,
            }}
          >
            <span>{node.status}</span>
          </div>
        </div>

        {/* Label */}
        <div>
          <span className="text-xs text-gray-400 uppercase block mb-1">Task</span>
          <span className="text-sm text-white">{node.label}</span>
        </div>

        {/* Type */}
        <div>
          <span className="text-xs text-gray-400 uppercase block mb-1">Type</span>
          <span className="text-sm text-white capitalize">{node.type}</span>
        </div>

        {/* Agent */}
        {node.agent && (
          <div className="flex items-center space-x-2">
            <Bot className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-white">{node.agent}</span>
          </div>
        )}

        {/* Timing */}
        {(node.startedAt || node.completedAt) && (
          <div className="space-y-1">
            {node.startedAt && (
              <div className="flex items-center space-x-2 text-xs">
                <Clock className="w-3 h-3 text-gray-400" />
                <span className="text-gray-400">Started:</span>
                <span className="text-white">
                  {new Date(node.startedAt).toLocaleTimeString()}
                </span>
              </div>
            )}
            {node.completedAt && (
              <div className="flex items-center space-x-2 text-xs">
                <Clock className="w-3 h-3 text-gray-400" />
                <span className="text-gray-400">Completed:</span>
                <span className="text-white">
                  {new Date(node.completedAt).toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Retry Info */}
        {node.retryInfo && (
          <div className="flex items-center space-x-2 text-orange-400">
            <RotateCw className="w-4 h-4" />
            <span className="text-sm">
              Retry attempt {node.retryInfo.attemptNumber} of {node.retryInfo.maxAttempts}
            </span>
          </div>
        )}

        {/* Error */}
        {node.error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <div className="flex items-center space-x-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-red-400" />
              <span className="text-xs text-red-400 uppercase">Error</span>
            </div>
            <p className="text-sm text-red-300">{node.error}</p>
          </div>
        )}

        {/* Description */}
        {node.description && (
          <div className="p-3 bg-gray-700/50 rounded-lg">
            <div className="flex items-center space-x-2 mb-2">
              <FileText className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-400 uppercase">Description</span>
            </div>
            <p className="text-sm text-gray-300">{node.description}</p>
          </div>
        )}
      </div>

      {/* Actions */}
      {onPlayFromNode && node.status !== 'running' && (
        <div className="px-4 py-3 border-t border-gray-700">
          <button
            onClick={() => onPlayFromNode(node.id)}
            className="w-full px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Play from this node
          </button>
        </div>
      )}
    </div>
  );
}
```

### Task 6: Create Main DAG Visualization Component
**Objective:** Combine all DAG components into main visualization

**Files to Create:**
- `cmbagent-ui/components/dag/DAGVisualization.tsx`

**Implementation:**
```typescript
// components/dag/DAGVisualization.tsx

'use client';

import { useCallback, useMemo, useState, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  MiniMap,
  useNodesState,
  useEdgesState,
  Node,
  Edge,
  ConnectionMode,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import DAGNodeComponent from './DAGNode';
import { DAGControls } from './DAGControls';
import { DAGNodeDetails } from './DAGNodeDetails';
import { DAGNodeData, statusColors } from '@/types/dag';

const nodeTypes = {
  dagNode: DAGNodeComponent,
};

interface DAGVisualizationProps {
  dagData: { nodes: any[]; edges: any[] } | null;
  onNodeSelect?: (nodeId: string | null) => void;
  onPlayFromNode?: (nodeId: string) => void;
}

// Layout calculation
function calculateLayout(
  rawNodes: any[],
  rawEdges: any[],
  direction: 'TB' | 'LR' = 'TB'
): { nodes: Node<DAGNodeData>[]; edges: Edge[] } {
  if (!rawNodes.length) return { nodes: [], edges: [] };

  // Build adjacency map
  const adjacency: Map<string, string[]> = new Map();
  const inDegree: Map<string, number> = new Map();

  rawNodes.forEach((n) => {
    adjacency.set(n.id, []);
    inDegree.set(n.id, 0);
  });

  rawEdges.forEach((e) => {
    adjacency.get(e.source)?.push(e.target);
    inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1);
  });

  // Topological sort to get levels
  const levels: string[][] = [];
  const visited = new Set<string>();
  const queue = rawNodes.filter((n) => inDegree.get(n.id) === 0).map((n) => n.id);

  while (queue.length > 0) {
    const currentLevel: string[] = [];
    const nextQueue: string[] = [];

    for (const nodeId of queue) {
      if (visited.has(nodeId)) continue;
      visited.add(nodeId);
      currentLevel.push(nodeId);

      for (const child of adjacency.get(nodeId) || []) {
        inDegree.set(child, (inDegree.get(child) || 0) - 1);
        if (inDegree.get(child) === 0) {
          nextQueue.push(child);
        }
      }
    }

    if (currentLevel.length > 0) {
      levels.push(currentLevel);
    }
    queue.length = 0;
    queue.push(...nextQueue);
  }

  // Calculate positions
  const nodeSpacing = 250;
  const levelSpacing = 150;
  const nodes: Node<DAGNodeData>[] = [];

  levels.forEach((level, levelIndex) => {
    const levelWidth = level.length * nodeSpacing;
    const startOffset = -levelWidth / 2 + nodeSpacing / 2;

    level.forEach((nodeId, nodeIndex) => {
      const rawNode = rawNodes.find((n) => n.id === nodeId);
      if (!rawNode) return;

      const x = direction === 'LR'
        ? levelIndex * levelSpacing
        : startOffset + nodeIndex * nodeSpacing;
      const y = direction === 'LR'
        ? startOffset + nodeIndex * nodeSpacing
        : levelIndex * levelSpacing;

      nodes.push({
        id: nodeId,
        type: 'dagNode',
        position: { x, y },
        data: {
          id: rawNode.id,
          label: rawNode.label || rawNode.id,
          type: rawNode.type || 'agent',
          status: rawNode.status || 'pending',
          agent: rawNode.agent,
          stepNumber: rawNode.step_number,
          description: rawNode.description,
          startedAt: rawNode.started_at,
          completedAt: rawNode.completed_at,
          error: rawNode.error,
          retryInfo: rawNode.retry_info,
        },
      });
    });
  });

  // Create edges with styling
  const edges: Edge[] = rawEdges.map((e) => ({
    id: `${e.source}-${e.target}`,
    source: e.source,
    target: e.target,
    type: 'smoothstep',
    animated: false,
    style: { stroke: '#4B5563', strokeWidth: 2 },
  }));

  return { nodes, edges };
}

export function DAGVisualization({
  dagData,
  onNodeSelect,
  onPlayFromNode,
}: DAGVisualizationProps) {
  const [layout, setLayout] = useState<'horizontal' | 'vertical'>('vertical');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Calculate layout
  const { nodes: layoutNodes, edges: layoutEdges } = useMemo(() => {
    if (!dagData) return { nodes: [], edges: [] };
    return calculateLayout(
      dagData.nodes,
      dagData.edges,
      layout === 'horizontal' ? 'LR' : 'TB'
    );
  }, [dagData, layout]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges);

  // Update nodes when layout changes
  useEffect(() => {
    setNodes(layoutNodes);
    setEdges(layoutEdges);
  }, [layoutNodes, layoutEdges, setNodes, setEdges]);

  // Update node statuses when dagData changes
  useEffect(() => {
    if (!dagData) return;

    setNodes((nds) =>
      nds.map((node) => {
        const rawNode = dagData.nodes.find((n) => n.id === node.id);
        if (rawNode) {
          return {
            ...node,
            data: {
              ...node.data,
              status: rawNode.status || node.data.status,
              error: rawNode.error,
              startedAt: rawNode.started_at,
              completedAt: rawNode.completed_at,
              retryInfo: rawNode.retry_info,
            },
          };
        }
        return node;
      })
    );
  }, [dagData, setNodes]);

  // Handle node click
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNodeId(node.id);
      onNodeSelect?.(node.id);
    },
    [onNodeSelect]
  );

  // Handle pane click (deselect)
  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  // Get selected node data
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    const node = nodes.find((n) => n.id === selectedNodeId);
    return node?.data || null;
  }, [selectedNodeId, nodes]);

  // MiniMap node color
  const minimapNodeColor = useCallback((node: Node<DAGNodeData>) => {
    return statusColors[node.data.status] || '#6B7280';
  }, []);

  if (!dagData || dagData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center">
          <p className="text-lg mb-2">No DAG data available</p>
          <p className="text-sm">Start a workflow to see the execution graph</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        connectionMode={ConnectionMode.Loose}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        attributionPosition="bottom-right"
        className="bg-gray-900"
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#374151"
        />
        <MiniMap
          nodeColor={minimapNodeColor}
          maskColor="rgba(0, 0, 0, 0.8)"
          className="!bg-gray-800 !border-gray-700"
        />
      </ReactFlow>

      <DAGControls layout={layout} onLayoutChange={setLayout} />

      <DAGNodeDetails
        node={selectedNode}
        onClose={() => {
          setSelectedNodeId(null);
          onNodeSelect?.(null);
        }}
        onPlayFromNode={onPlayFromNode}
      />
    </div>
  );
}
```

### Task 7: Export and Integrate
**Objective:** Create index export and integrate into main app

**Files to Create:**
- `cmbagent-ui/components/dag/index.ts`

**Implementation:**
```typescript
// components/dag/index.ts
export { DAGVisualization } from './DAGVisualization';
export { DAGControls } from './DAGControls';
export { DAGNodeDetails } from './DAGNodeDetails';
export { default as DAGNodeComponent } from './DAGNode';
```

**Modify `app/page.tsx` to include DAG:**
```typescript
import { DAGVisualization } from '@/components/dag';

// In the component, add a tab or section for DAG:
{dagData && (
  <div className="h-[500px] bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
    <DAGVisualization
      dagData={dagData}
      onNodeSelect={(nodeId) => console.log('Selected:', nodeId)}
      onPlayFromNode={(nodeId) => handlePlayFromNode(nodeId)}
    />
  </div>
)}
```

## Files to Create (Summary)

```
cmbagent-ui/
├── types/
│   └── dag.ts                     # DAG TypeScript types
└── components/
    └── dag/
        ├── index.ts               # Exports
        ├── DAGVisualization.tsx   # Main component
        ├── DAGNode.tsx            # Node component
        ├── DAGControls.tsx        # Zoom/pan controls
        └── DAGNodeDetails.tsx     # Node details panel
```

## Verification Criteria

### Must Pass
- [ ] React Flow installed and working
- [ ] DAG renders with nodes and edges
- [ ] Node status colors correct
- [ ] Node selection shows details panel
- [ ] Zoom and pan controls work
- [ ] Layout toggle (horizontal/vertical) works
- [ ] MiniMap shows overview
- [ ] Real-time node status updates work

### Should Pass
- [ ] Performance acceptable with 20+ nodes
- [ ] Responsive on different screen sizes
- [ ] Animations smooth
- [ ] No console errors

### Testing Steps
```bash
# Install dependencies
cd cmbagent-ui && npm install @xyflow/react

# Build to check types
npm run build

# Start dev server
npm run dev

# Test with mock data first, then real backend
```

## Common Issues and Solutions

### Issue 1: React Flow Styles Not Loading
**Symptom:** Nodes render but look wrong
**Solution:** Ensure `@xyflow/react/dist/style.css` is imported

### Issue 2: Layout Calculation Wrong
**Symptom:** Nodes overlap or off-screen
**Solution:** Check topological sort logic, adjust spacing

### Issue 3: Node Status Not Updating
**Symptom:** Status changes but UI doesn't reflect
**Solution:** Ensure setNodes is called with new status

### Issue 4: Performance Issues
**Symptom:** Laggy with many nodes
**Solution:** Use memo on DAGNode, reduce re-renders

## Rollback Procedure

If Stage 2 causes issues:
1. Remove React Flow import
2. Show simple list of steps instead
3. Keep backend DAG functionality
4. Document what went wrong

## Success Criteria

Stage 2 is complete when:
1. DAG visualization renders correctly
2. Real-time updates work
3. Node selection and details work
4. Controls (zoom, pan, layout) work
5. Performance acceptable
6. All verification criteria pass

## Next Stage

Once Stage 2 is verified complete, proceed to:
**Stage 3: Workflow State Dashboard & Controls**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-16
