# Stage 6: Branching & Comparison UI

**Phase:** 2 - Advanced Features
**Dependencies:** Stage 5 complete, Backend Stage 9 (Branching) complete
**Risk Level:** Medium

## Objectives

1. Create branch tree visualization
2. Implement branch comparison view
3. Add create branch dialog
4. Enable play-from-node functionality
5. Display branch metadata and hypothesis

## Current State Analysis

### What We Have
- Backend branching API endpoints
- DAG visualization with nodes
- Basic workflow dashboard

### What We Need
- Branch tree component showing hierarchy
- Side-by-side comparison view
- Create branch workflow
- Switch between branches
- Compare outputs/files between branches

## Implementation Tasks

### Task 1: Create Branching Types
**Files to Create:**
- `cmbagent-ui/types/branching.ts`

```typescript
// types/branching.ts

export interface Branch {
  branch_id: string;
  run_id: string;
  parent_branch_id?: string;
  branch_point_step_id?: string;
  hypothesis?: string;
  name: string;
  created_at: string;
  status: string;
  is_main: boolean;
  children?: Branch[];
}

export interface BranchComparison {
  branch_a: BranchSummary;
  branch_b: BranchSummary;
  differences: BranchDifference[];
  files_comparison?: FileComparison[];
}

export interface BranchSummary {
  branch_id: string;
  name: string;
  hypothesis?: string;
  total_steps: number;
  completed_steps: number;
  failed_steps: number;
  total_cost: number;
  total_time_seconds: number;
  final_status: string;
}

export interface BranchDifference {
  step_number: number;
  step_id_a?: string;
  step_id_b?: string;
  description_a?: string;
  description_b?: string;
  status_a?: string;
  status_b?: string;
  output_differs: boolean;
}

export interface FileComparison {
  file_path: string;
  in_branch_a: boolean;
  in_branch_b: boolean;
  differs: boolean;
  diff_preview?: string;
}

export interface ResumableNode {
  step_id: string;
  step_number: number;
  description: string;
  status: string;
  completed_at?: string;
}
```

### Task 2: Create Branch Tree Component
**Files to Create:**
- `cmbagent-ui/components/branching/BranchTree.tsx`

```typescript
// components/branching/BranchTree.tsx

'use client';

import { useState } from 'react';
import {
  GitBranch,
  GitCommit,
  ChevronRight,
  ChevronDown,
  Play,
  Eye,
  MoreHorizontal,
} from 'lucide-react';
import { Branch } from '@/types/branching';
import { StatusBadge } from '@/components/common/StatusBadge';

interface BranchTreeProps {
  branches: Branch[];
  currentBranchId?: string;
  onSelectBranch: (branchId: string) => void;
  onViewBranch: (branchId: string) => void;
  onCompareBranches: (branchIdA: string, branchIdB: string) => void;
}

function BranchNode({
  branch,
  level,
  currentBranchId,
  selectedForCompare,
  onSelect,
  onView,
  onToggleCompare,
}: {
  branch: Branch;
  level: number;
  currentBranchId?: string;
  selectedForCompare?: string;
  onSelect: (id: string) => void;
  onView: (id: string) => void;
  onToggleCompare: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = branch.children && branch.children.length > 0;
  const isCurrent = branch.branch_id === currentBranchId;
  const isSelectedForCompare = branch.branch_id === selectedForCompare;

  return (
    <div>
      <div
        className={`
          flex items-center p-2 rounded-lg transition-all cursor-pointer
          ${isCurrent ? 'bg-blue-500/20 border border-blue-500/30' : 'hover:bg-gray-700/50'}
          ${isSelectedForCompare ? 'ring-2 ring-purple-500' : ''}
        `}
        style={{ marginLeft: `${level * 24}px` }}
        onClick={() => onSelect(branch.branch_id)}
      >
        {/* Expand/Collapse */}
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
            className="p-1 hover:bg-gray-600 rounded mr-1"
          >
            {expanded ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )}
          </button>
        ) : (
          <div className="w-6 mr-1" />
        )}

        {/* Branch Icon */}
        {branch.is_main ? (
          <GitCommit className="w-4 h-4 text-blue-400 mr-2" />
        ) : (
          <GitBranch className="w-4 h-4 text-purple-400 mr-2" />
        )}

        {/* Branch Info */}
        <div className="flex-grow min-w-0">
          <div className="flex items-center space-x-2">
            <span className={`text-sm font-medium truncate ${isCurrent ? 'text-blue-400' : 'text-white'}`}>
              {branch.name}
            </span>
            {isCurrent && (
              <span className="px-1.5 py-0.5 text-xs bg-blue-500/30 text-blue-300 rounded">
                current
              </span>
            )}
          </div>
          {branch.hypothesis && (
            <p className="text-xs text-gray-400 truncate mt-0.5">
              {branch.hypothesis}
            </p>
          )}
        </div>

        {/* Status */}
        <StatusBadge status={branch.status} size="sm" showLabel={false} />

        {/* Actions */}
        <div className="flex items-center space-x-1 ml-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onView(branch.branch_id);
            }}
            className="p-1.5 hover:bg-gray-600 rounded transition-colors"
            title="View branch"
          >
            <Eye className="w-4 h-4 text-gray-400" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleCompare(branch.branch_id);
            }}
            className={`p-1.5 rounded transition-colors ${
              isSelectedForCompare ? 'bg-purple-500/30 text-purple-400' : 'hover:bg-gray-600 text-gray-400'
            }`}
            title="Select for comparison"
          >
            <GitBranch className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Children */}
      {hasChildren && expanded && (
        <div>
          {branch.children!.map((child) => (
            <BranchNode
              key={child.branch_id}
              branch={child}
              level={level + 1}
              currentBranchId={currentBranchId}
              selectedForCompare={selectedForCompare}
              onSelect={onSelect}
              onView={onView}
              onToggleCompare={onToggleCompare}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function BranchTree({
  branches,
  currentBranchId,
  onSelectBranch,
  onViewBranch,
  onCompareBranches,
}: BranchTreeProps) {
  const [selectedForCompare, setSelectedForCompare] = useState<string | null>(null);

  const handleToggleCompare = (branchId: string) => {
    if (selectedForCompare === null) {
      setSelectedForCompare(branchId);
    } else if (selectedForCompare === branchId) {
      setSelectedForCompare(null);
    } else {
      // Compare the two branches
      onCompareBranches(selectedForCompare, branchId);
      setSelectedForCompare(null);
    }
  };

  if (branches.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-400">
        <div className="text-center">
          <GitBranch className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No branches yet</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {selectedForCompare && (
        <div className="mb-4 p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
          <p className="text-sm text-purple-300">
            Select another branch to compare
          </p>
          <button
            onClick={() => setSelectedForCompare(null)}
            className="mt-2 text-xs text-purple-400 hover:text-purple-300"
          >
            Cancel
          </button>
        </div>
      )}
      {branches.map((branch) => (
        <BranchNode
          key={branch.branch_id}
          branch={branch}
          level={0}
          currentBranchId={currentBranchId}
          selectedForCompare={selectedForCompare || undefined}
          onSelect={onSelectBranch}
          onView={onViewBranch}
          onToggleCompare={handleToggleCompare}
        />
      ))}
    </div>
  );
}
```

### Task 3: Create Branch Comparison Component
**Files to Create:**
- `cmbagent-ui/components/branching/BranchComparison.tsx`

```typescript
// components/branching/BranchComparison.tsx

'use client';

import { useState } from 'react';
import {
  X,
  GitBranch,
  Clock,
  DollarSign,
  Layers,
  FileText,
  ArrowRight,
  CheckCircle,
  XCircle,
  Minus,
} from 'lucide-react';
import { BranchComparison, BranchDifference } from '@/types/branching';

interface BranchComparisonProps {
  comparison: BranchComparison;
  onClose: () => void;
  onSwitchToBranch?: (branchId: string) => void;
}

export function BranchComparisonView({
  comparison,
  onClose,
  onSwitchToBranch,
}: BranchComparisonProps) {
  const [activeTab, setActiveTab] = useState<'summary' | 'steps' | 'files'>('summary');

  const { branch_a, branch_b, differences, files_comparison } = comparison;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-4xl max-h-[90vh] overflow-hidden bg-gray-900 rounded-xl border border-gray-700 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div className="flex items-center space-x-4">
            <GitBranch className="w-6 h-6 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Branch Comparison</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Branch Headers */}
        <div className="grid grid-cols-2 gap-4 px-6 py-4 bg-gray-800/50">
          {/* Branch A */}
          <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-blue-400">{branch_a.name}</span>
              {onSwitchToBranch && (
                <button
                  onClick={() => onSwitchToBranch(branch_a.branch_id)}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  Switch
                </button>
              )}
            </div>
            {branch_a.hypothesis && (
              <p className="text-xs text-gray-400 truncate">{branch_a.hypothesis}</p>
            )}
          </div>

          {/* Branch B */}
          <div className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-purple-400">{branch_b.name}</span>
              {onSwitchToBranch && (
                <button
                  onClick={() => onSwitchToBranch(branch_b.branch_id)}
                  className="text-xs text-purple-400 hover:text-purple-300"
                >
                  Switch
                </button>
              )}
            </div>
            {branch_b.hypothesis && (
              <p className="text-xs text-gray-400 truncate">{branch_b.hypothesis}</p>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex space-x-2 px-6 py-2 border-b border-gray-700">
          {['summary', 'steps', 'files'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as any)}
              className={`px-4 py-2 text-sm rounded-lg transition-colors capitalize ${
                activeTab === tab
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="px-6 py-4 overflow-y-auto max-h-[50vh]">
          {activeTab === 'summary' && (
            <div className="grid grid-cols-2 gap-6">
              {/* Metrics Comparison */}
              {[
                { label: 'Total Steps', icon: Layers, a: branch_a.total_steps, b: branch_b.total_steps },
                { label: 'Completed', icon: CheckCircle, a: branch_a.completed_steps, b: branch_b.completed_steps },
                { label: 'Failed', icon: XCircle, a: branch_a.failed_steps, b: branch_b.failed_steps },
                { label: 'Total Cost', icon: DollarSign, a: `$${branch_a.total_cost.toFixed(4)}`, b: `$${branch_b.total_cost.toFixed(4)}` },
                { label: 'Duration', icon: Clock, a: `${Math.round(branch_a.total_time_seconds)}s`, b: `${Math.round(branch_b.total_time_seconds)}s` },
              ].map((metric) => (
                <div
                  key={metric.label}
                  className="flex items-center justify-between p-4 bg-gray-800/50 rounded-lg"
                >
                  <div className="flex items-center space-x-2">
                    <metric.icon className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-300">{metric.label}</span>
                  </div>
                  <div className="flex items-center space-x-4">
                    <span className="text-sm text-blue-400">{metric.a}</span>
                    <ArrowRight className="w-4 h-4 text-gray-600" />
                    <span className="text-sm text-purple-400">{metric.b}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'steps' && (
            <div className="space-y-2">
              {differences.map((diff, index) => (
                <div
                  key={index}
                  className={`grid grid-cols-2 gap-4 p-3 rounded-lg ${
                    diff.output_differs ? 'bg-yellow-500/10' : 'bg-gray-800/30'
                  }`}
                >
                  {/* Branch A Step */}
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-gray-400">#{diff.step_number}</span>
                    {diff.description_a ? (
                      <>
                        <span className={`w-2 h-2 rounded-full ${
                          diff.status_a === 'completed' ? 'bg-green-400' :
                          diff.status_a === 'failed' ? 'bg-red-400' : 'bg-gray-400'
                        }`} />
                        <span className="text-sm text-gray-300 truncate">
                          {diff.description_a}
                        </span>
                      </>
                    ) : (
                      <span className="text-sm text-gray-500 italic">Not present</span>
                    )}
                  </div>

                  {/* Branch B Step */}
                  <div className="flex items-center space-x-2">
                    {diff.description_b ? (
                      <>
                        <span className={`w-2 h-2 rounded-full ${
                          diff.status_b === 'completed' ? 'bg-green-400' :
                          diff.status_b === 'failed' ? 'bg-red-400' : 'bg-gray-400'
                        }`} />
                        <span className="text-sm text-gray-300 truncate">
                          {diff.description_b}
                        </span>
                      </>
                    ) : (
                      <span className="text-sm text-gray-500 italic">Not present</span>
                    )}
                    {diff.output_differs && (
                      <span className="px-1.5 py-0.5 text-xs bg-yellow-500/30 text-yellow-400 rounded">
                        differs
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'files' && files_comparison && (
            <div className="space-y-2">
              {files_comparison.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 bg-gray-800/30 rounded-lg"
                >
                  <div className="flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-gray-400" />
                    <span className="text-sm text-gray-300">{file.file_path}</span>
                  </div>
                  <div className="flex items-center space-x-4">
                    {file.in_branch_a ? (
                      <CheckCircle className="w-4 h-4 text-blue-400" />
                    ) : (
                      <Minus className="w-4 h-4 text-gray-600" />
                    )}
                    {file.in_branch_b ? (
                      <CheckCircle className="w-4 h-4 text-purple-400" />
                    ) : (
                      <Minus className="w-4 h-4 text-gray-600" />
                    )}
                    {file.differs && (
                      <span className="px-1.5 py-0.5 text-xs bg-yellow-500/30 text-yellow-400 rounded">
                        modified
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

### Task 4: Create Branch Dialog
**Files to Create:**
- `cmbagent-ui/components/branching/CreateBranchDialog.tsx`

```typescript
// components/branching/CreateBranchDialog.tsx

'use client';

import { useState } from 'react';
import { X, GitBranch, Lightbulb } from 'lucide-react';
import { ResumableNode } from '@/types/branching';

interface CreateBranchDialogProps {
  resumableNodes: ResumableNode[];
  onCreateBranch: (nodeId: string, name: string, hypothesis?: string) => void;
  onClose: () => void;
}

export function CreateBranchDialog({
  resumableNodes,
  onCreateBranch,
  onClose,
}: CreateBranchDialogProps) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [branchName, setBranchName] = useState('');
  const [hypothesis, setHypothesis] = useState('');

  const handleSubmit = () => {
    if (!selectedNodeId || !branchName.trim()) return;
    onCreateBranch(selectedNodeId, branchName.trim(), hypothesis.trim() || undefined);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-gray-900 rounded-xl border border-gray-700 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div className="flex items-center space-x-3">
            <GitBranch className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Create Branch</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Select Resume Point */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-3">
              Select Resume Point
            </label>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {resumableNodes.map((node) => (
                <button
                  key={node.step_id}
                  onClick={() => setSelectedNodeId(node.step_id)}
                  className={`w-full text-left p-3 rounded-lg border transition-all ${
                    selectedNodeId === node.step_id
                      ? 'border-purple-500 bg-purple-500/20'
                      : 'border-gray-700 hover:border-gray-600'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-white">
                      Step #{node.step_number}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      node.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                      node.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                      'bg-gray-500/20 text-gray-400'
                    }`}>
                      {node.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1 truncate">
                    {node.description}
                  </p>
                </button>
              ))}
            </div>
          </div>

          {/* Branch Name */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Branch Name *
            </label>
            <input
              type="text"
              value={branchName}
              onChange={(e) => setBranchName(e.target.value)}
              placeholder="e.g., experiment-higher-lr"
              className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          {/* Hypothesis */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              <div className="flex items-center space-x-2">
                <Lightbulb className="w-4 h-4 text-yellow-400" />
                <span>Hypothesis (Optional)</span>
              </div>
            </label>
            <textarea
              value={hypothesis}
              onChange={(e) => setHypothesis(e.target.value)}
              placeholder="What do you expect this branch to achieve?"
              className="w-full h-24 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 px-6 py-4 border-t border-gray-700 bg-gray-800/50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!selectedNodeId || !branchName.trim()}
            className="px-6 py-2 bg-purple-500 hover:bg-purple-600 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded-lg transition-colors"
          >
            Create Branch
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Task 5: Create Branching Index Export
**Files to Create:**
- `cmbagent-ui/components/branching/index.ts`

```typescript
// components/branching/index.ts
export { BranchTree } from './BranchTree';
export { BranchComparisonView } from './BranchComparison';
export { CreateBranchDialog } from './CreateBranchDialog';
```

## Files to Create (Summary)

```
cmbagent-ui/
├── types/
│   └── branching.ts
└── components/
    └── branching/
        ├── index.ts
        ├── BranchTree.tsx
        ├── BranchComparison.tsx
        └── CreateBranchDialog.tsx
```

## Verification Criteria

### Must Pass
- [ ] Branch tree displays hierarchy
- [ ] Can expand/collapse branches
- [ ] Comparison view shows differences
- [ ] Create branch dialog works
- [ ] Node selection for branching works

### Should Pass
- [ ] Switch branch functionality
- [ ] File comparison in branches
- [ ] Responsive design

## Success Criteria

Stage 6 is complete when:
1. Branch tree visualization working
2. Comparison view functional
3. Create branch workflow complete
4. Integration with backend API working

## Next Stage

Once Stage 6 is verified complete, proceed to:
**Stage 7: Session & Workflow Table Views**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-16
