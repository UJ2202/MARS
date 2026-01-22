# Stage 7: Session & Workflow Table Views

**Phase:** 2 - Advanced Features
**Dependencies:** Stage 6 complete, Backend database models
**Risk Level:** Low

## Objectives

1. Create comprehensive session table with filtering/sorting
2. Create workflow runs table
3. Create steps table for individual workflows
4. Implement reusable DataTable component
5. Add pagination and search functionality

## Current State Analysis

### What We Have
- Database models for sessions, workflows, steps
- Backend API endpoints
- Basic result display

### What We Need
- Sortable/filterable tables
- Pagination for large datasets
- Search functionality
- Row actions (view, delete, resume)
- Responsive table design

## Implementation Tasks

### Task 1: Create Table Types
**Files to Create:**
- `cmbagent-ui/types/tables.ts`

```typescript
// types/tables.ts

export interface Column<T> {
  id: string;
  header: string;
  accessor: keyof T | ((row: T) => React.ReactNode);
  sortable?: boolean;
  width?: string;
  align?: 'left' | 'center' | 'right';
}

export interface TableState {
  page: number;
  pageSize: number;
  sortColumn: string | null;
  sortDirection: 'asc' | 'desc';
  searchQuery: string;
  filters: Record<string, any>;
}

export interface PaginationInfo {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

export interface SessionRow {
  id: string;
  name: string;
  created_at: string;
  last_active_at?: string;
  status: string;
  workflow_count: number;
  total_cost: number;
}

export interface WorkflowRow {
  id: string;
  session_id: string;
  task_description: string;
  status: string;
  agent: string;
  model: string;
  started_at?: string;
  completed_at?: string;
  total_cost: number;
  step_count: number;
}

export interface StepRow {
  id: string;
  run_id: string;
  step_number: number;
  description: string;
  agent: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  cost: number;
  retry_count: number;
}
```

### Task 2: Create Reusable DataTable Component
**Files to Create:**
- `cmbagent-ui/components/tables/DataTable.tsx`

```typescript
// components/tables/DataTable.tsx

'use client';

import { useState, useMemo } from 'react';
import {
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  Search,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import { Column, TableState, PaginationInfo } from '@/types/tables';

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  pagination?: PaginationInfo;
  isLoading?: boolean;
  onStateChange?: (state: TableState) => void;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  searchPlaceholder?: string;
  actions?: (row: T) => React.ReactNode;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  pagination,
  isLoading = false,
  onStateChange,
  onRowClick,
  emptyMessage = 'No data available',
  searchPlaceholder = 'Search...',
  actions,
}: DataTableProps<T>) {
  const [tableState, setTableState] = useState<TableState>({
    page: 1,
    pageSize: 10,
    sortColumn: null,
    sortDirection: 'asc',
    searchQuery: '',
    filters: {},
  });

  const updateState = (updates: Partial<TableState>) => {
    const newState = { ...tableState, ...updates };
    setTableState(newState);
    onStateChange?.(newState);
  };

  const handleSort = (columnId: string) => {
    if (tableState.sortColumn === columnId) {
      updateState({
        sortDirection: tableState.sortDirection === 'asc' ? 'desc' : 'asc',
      });
    } else {
      updateState({
        sortColumn: columnId,
        sortDirection: 'asc',
      });
    }
  };

  const getSortIcon = (columnId: string) => {
    if (tableState.sortColumn !== columnId) {
      return <ChevronsUpDown className="w-4 h-4 text-gray-500" />;
    }
    return tableState.sortDirection === 'asc' ? (
      <ChevronUp className="w-4 h-4 text-blue-400" />
    ) : (
      <ChevronDown className="w-4 h-4 text-blue-400" />
    );
  };

  const getCellValue = (row: T, column: Column<T>) => {
    if (typeof column.accessor === 'function') {
      return column.accessor(row);
    }
    return row[column.accessor] as React.ReactNode;
  };

  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-700 overflow-hidden">
      {/* Search Bar */}
      <div className="px-4 py-3 border-b border-gray-700">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={tableState.searchQuery}
            onChange={(e) => updateState({ searchQuery: e.target.value, page: 1 })}
            placeholder={searchPlaceholder}
            className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-800/50">
              {columns.map((column) => (
                <th
                  key={column.id}
                  className={`px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider ${
                    column.width || ''
                  }`}
                  style={{ textAlign: column.align || 'left' }}
                >
                  {column.sortable !== false ? (
                    <button
                      onClick={() => handleSort(column.id)}
                      className="flex items-center space-x-1 hover:text-white transition-colors"
                    >
                      <span>{column.header}</span>
                      {getSortIcon(column.id)}
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              ))}
              {actions && (
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {isLoading ? (
              <tr>
                <td
                  colSpan={columns.length + (actions ? 1 : 0)}
                  className="px-4 py-12 text-center"
                >
                  <Loader2 className="w-8 h-8 text-blue-400 animate-spin mx-auto" />
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (actions ? 1 : 0)}
                  className="px-4 py-12 text-center text-gray-400"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row) => (
                <tr
                  key={keyExtractor(row)}
                  onClick={() => onRowClick?.(row)}
                  className={`hover:bg-gray-800/50 transition-colors ${
                    onRowClick ? 'cursor-pointer' : ''
                  }`}
                >
                  {columns.map((column) => (
                    <td
                      key={column.id}
                      className="px-4 py-3 text-sm text-gray-300"
                      style={{ textAlign: column.align || 'left' }}
                    >
                      {getCellValue(row, column)}
                    </td>
                  ))}
                  {actions && (
                    <td className="px-4 py-3 text-right">
                      {actions(row)}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pagination && (
        <div className="px-4 py-3 border-t border-gray-700 flex items-center justify-between">
          <div className="text-sm text-gray-400">
            Showing {((pagination.page - 1) * pagination.pageSize) + 1} to{' '}
            {Math.min(pagination.page * pagination.pageSize, pagination.totalItems)} of{' '}
            {pagination.totalItems} results
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => updateState({ page: tableState.page - 1 })}
              disabled={pagination.page <= 1}
              className="p-2 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
            >
              <ChevronLeft className="w-4 h-4 text-gray-400" />
            </button>
            <span className="text-sm text-gray-300">
              Page {pagination.page} of {pagination.totalPages}
            </span>
            <button
              onClick={() => updateState({ page: tableState.page + 1 })}
              disabled={pagination.page >= pagination.totalPages}
              className="p-2 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
            >
              <ChevronRight className="w-4 h-4 text-gray-400" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

### Task 3: Create Session Table Component
**Files to Create:**
- `cmbagent-ui/components/tables/SessionTable.tsx`

```typescript
// components/tables/SessionTable.tsx

'use client';

import { Eye, Trash2, MoreHorizontal } from 'lucide-react';
import { DataTable } from './DataTable';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Column, SessionRow, PaginationInfo } from '@/types/tables';

interface SessionTableProps {
  sessions: SessionRow[];
  pagination?: PaginationInfo;
  isLoading?: boolean;
  onViewSession: (session: SessionRow) => void;
  onDeleteSession?: (session: SessionRow) => void;
}

export function SessionTable({
  sessions,
  pagination,
  isLoading,
  onViewSession,
  onDeleteSession,
}: SessionTableProps) {
  const columns: Column<SessionRow>[] = [
    {
      id: 'name',
      header: 'Session Name',
      accessor: 'name',
      sortable: true,
    },
    {
      id: 'status',
      header: 'Status',
      accessor: (row) => <StatusBadge status={row.status} size="sm" />,
      sortable: true,
    },
    {
      id: 'workflow_count',
      header: 'Workflows',
      accessor: 'workflow_count',
      sortable: true,
      align: 'center',
    },
    {
      id: 'total_cost',
      header: 'Total Cost',
      accessor: (row) => `$${row.total_cost.toFixed(4)}`,
      sortable: true,
      align: 'right',
    },
    {
      id: 'created_at',
      header: 'Created',
      accessor: (row) => new Date(row.created_at).toLocaleDateString(),
      sortable: true,
    },
    {
      id: 'last_active_at',
      header: 'Last Active',
      accessor: (row) =>
        row.last_active_at
          ? new Date(row.last_active_at).toLocaleString()
          : 'Never',
      sortable: true,
    },
  ];

  const actions = (row: SessionRow) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        onClick={(e) => {
          e.stopPropagation();
          onViewSession(row);
        }}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="View session"
      >
        <Eye className="w-4 h-4 text-gray-400" />
      </button>
      {onDeleteSession && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDeleteSession(row);
          }}
          className="p-2 hover:bg-red-500/20 rounded transition-colors"
          title="Delete session"
        >
          <Trash2 className="w-4 h-4 text-red-400" />
        </button>
      )}
    </div>
  );

  return (
    <DataTable
      columns={columns}
      data={sessions}
      keyExtractor={(row) => row.id}
      pagination={pagination}
      isLoading={isLoading}
      onRowClick={onViewSession}
      emptyMessage="No sessions found"
      searchPlaceholder="Search sessions..."
      actions={actions}
    />
  );
}
```

### Task 4: Create Workflow Table Component
**Files to Create:**
- `cmbagent-ui/components/tables/WorkflowTable.tsx`

```typescript
// components/tables/WorkflowTable.tsx

'use client';

import { Eye, Play, Trash2, GitBranch } from 'lucide-react';
import { DataTable } from './DataTable';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Column, WorkflowRow, PaginationInfo } from '@/types/tables';

interface WorkflowTableProps {
  workflows: WorkflowRow[];
  pagination?: PaginationInfo;
  isLoading?: boolean;
  onViewWorkflow: (workflow: WorkflowRow) => void;
  onResumeWorkflow?: (workflow: WorkflowRow) => void;
  onBranchWorkflow?: (workflow: WorkflowRow) => void;
  onDeleteWorkflow?: (workflow: WorkflowRow) => void;
}

export function WorkflowTable({
  workflows,
  pagination,
  isLoading,
  onViewWorkflow,
  onResumeWorkflow,
  onBranchWorkflow,
  onDeleteWorkflow,
}: WorkflowTableProps) {
  const columns: Column<WorkflowRow>[] = [
    {
      id: 'task_description',
      header: 'Task',
      accessor: (row) => (
        <div className="max-w-xs truncate" title={row.task_description}>
          {row.task_description}
        </div>
      ),
      sortable: true,
    },
    {
      id: 'status',
      header: 'Status',
      accessor: (row) => <StatusBadge status={row.status} size="sm" />,
      sortable: true,
    },
    {
      id: 'agent',
      header: 'Agent',
      accessor: (row) => (
        <span className="px-2 py-0.5 bg-gray-700 rounded text-xs">
          {row.agent}
        </span>
      ),
      sortable: true,
    },
    {
      id: 'model',
      header: 'Model',
      accessor: (row) => (
        <span className="text-xs text-gray-400">{row.model}</span>
      ),
      sortable: true,
    },
    {
      id: 'step_count',
      header: 'Steps',
      accessor: 'step_count',
      sortable: true,
      align: 'center',
    },
    {
      id: 'total_cost',
      header: 'Cost',
      accessor: (row) => `$${row.total_cost.toFixed(4)}`,
      sortable: true,
      align: 'right',
    },
    {
      id: 'started_at',
      header: 'Started',
      accessor: (row) =>
        row.started_at
          ? new Date(row.started_at).toLocaleString()
          : '-',
      sortable: true,
    },
  ];

  const actions = (row: WorkflowRow) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        onClick={(e) => {
          e.stopPropagation();
          onViewWorkflow(row);
        }}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="View workflow"
      >
        <Eye className="w-4 h-4 text-gray-400" />
      </button>
      {onResumeWorkflow && ['paused', 'failed'].includes(row.status) && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onResumeWorkflow(row);
          }}
          className="p-2 hover:bg-green-500/20 rounded transition-colors"
          title="Resume workflow"
        >
          <Play className="w-4 h-4 text-green-400" />
        </button>
      )}
      {onBranchWorkflow && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onBranchWorkflow(row);
          }}
          className="p-2 hover:bg-purple-500/20 rounded transition-colors"
          title="Create branch"
        >
          <GitBranch className="w-4 h-4 text-purple-400" />
        </button>
      )}
      {onDeleteWorkflow && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDeleteWorkflow(row);
          }}
          className="p-2 hover:bg-red-500/20 rounded transition-colors"
          title="Delete workflow"
        >
          <Trash2 className="w-4 h-4 text-red-400" />
        </button>
      )}
    </div>
  );

  return (
    <DataTable
      columns={columns}
      data={workflows}
      keyExtractor={(row) => row.id}
      pagination={pagination}
      isLoading={isLoading}
      onRowClick={onViewWorkflow}
      emptyMessage="No workflows found"
      searchPlaceholder="Search workflows..."
      actions={actions}
    />
  );
}
```

### Task 5: Create Step Table Component
**Files to Create:**
- `cmbagent-ui/components/tables/StepTable.tsx`

```typescript
// components/tables/StepTable.tsx

'use client';

import { Eye, RotateCw, Play } from 'lucide-react';
import { DataTable } from './DataTable';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Column, StepRow, PaginationInfo } from '@/types/tables';

interface StepTableProps {
  steps: StepRow[];
  pagination?: PaginationInfo;
  isLoading?: boolean;
  onViewStep: (step: StepRow) => void;
  onRetryStep?: (step: StepRow) => void;
  onPlayFromStep?: (step: StepRow) => void;
}

export function StepTable({
  steps,
  pagination,
  isLoading,
  onViewStep,
  onRetryStep,
  onPlayFromStep,
}: StepTableProps) {
  const columns: Column<StepRow>[] = [
    {
      id: 'step_number',
      header: '#',
      accessor: 'step_number',
      sortable: true,
      width: 'w-16',
      align: 'center',
    },
    {
      id: 'description',
      header: 'Description',
      accessor: (row) => (
        <div className="max-w-sm truncate" title={row.description}>
          {row.description}
        </div>
      ),
      sortable: true,
    },
    {
      id: 'agent',
      header: 'Agent',
      accessor: (row) => (
        <span className="px-2 py-0.5 bg-gray-700 rounded text-xs">
          {row.agent}
        </span>
      ),
      sortable: true,
    },
    {
      id: 'status',
      header: 'Status',
      accessor: (row) => <StatusBadge status={row.status} size="sm" />,
      sortable: true,
    },
    {
      id: 'cost',
      header: 'Cost',
      accessor: (row) => `$${row.cost.toFixed(4)}`,
      sortable: true,
      align: 'right',
    },
    {
      id: 'retry_count',
      header: 'Retries',
      accessor: (row) =>
        row.retry_count > 0 ? (
          <span className="text-orange-400">{row.retry_count}</span>
        ) : (
          <span className="text-gray-500">0</span>
        ),
      sortable: true,
      align: 'center',
    },
    {
      id: 'started_at',
      header: 'Started',
      accessor: (row) =>
        row.started_at
          ? new Date(row.started_at).toLocaleTimeString()
          : '-',
      sortable: true,
    },
  ];

  const actions = (row: StepRow) => (
    <div className="flex items-center justify-end space-x-1">
      <button
        onClick={(e) => {
          e.stopPropagation();
          onViewStep(row);
        }}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="View step details"
      >
        <Eye className="w-4 h-4 text-gray-400" />
      </button>
      {onRetryStep && row.status === 'failed' && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRetryStep(row);
          }}
          className="p-2 hover:bg-orange-500/20 rounded transition-colors"
          title="Retry step"
        >
          <RotateCw className="w-4 h-4 text-orange-400" />
        </button>
      )}
      {onPlayFromStep && ['completed', 'failed'].includes(row.status) && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPlayFromStep(row);
          }}
          className="p-2 hover:bg-blue-500/20 rounded transition-colors"
          title="Play from this step"
        >
          <Play className="w-4 h-4 text-blue-400" />
        </button>
      )}
    </div>
  );

  return (
    <DataTable
      columns={columns}
      data={steps}
      keyExtractor={(row) => row.id}
      pagination={pagination}
      isLoading={isLoading}
      onRowClick={onViewStep}
      emptyMessage="No steps found"
      searchPlaceholder="Search steps..."
      actions={actions}
    />
  );
}
```

### Task 6: Create Tables Index Export
**Files to Create:**
- `cmbagent-ui/components/tables/index.ts`

```typescript
// components/tables/index.ts
export { DataTable } from './DataTable';
export { SessionTable } from './SessionTable';
export { WorkflowTable } from './WorkflowTable';
export { StepTable } from './StepTable';
```

## Files to Create (Summary)

```
cmbagent-ui/
├── types/
│   └── tables.ts
└── components/
    └── tables/
        ├── index.ts
        ├── DataTable.tsx
        ├── SessionTable.tsx
        ├── WorkflowTable.tsx
        └── StepTable.tsx
```

## Verification Criteria

### Must Pass
- [ ] DataTable renders with data
- [ ] Sorting works on all columns
- [ ] Search filters results
- [ ] Pagination works correctly
- [ ] Row click triggers callback
- [ ] Actions render and work

### Should Pass
- [ ] Empty state displays correctly
- [ ] Loading state shows spinner
- [ ] Responsive on mobile
- [ ] Keyboard navigation works

## Success Criteria

Stage 7 is complete when:
1. Reusable DataTable working
2. All three specialized tables working
3. Sorting, filtering, pagination functional
4. Row actions working correctly

## Next Stage

Once Stage 7 is verified complete, proceed to:
**Stage 8: Cost Tracking Dashboard**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-16
