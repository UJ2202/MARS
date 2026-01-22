# Stage 9: Real-time Metrics & Observability UI

**Phase:** 3 - Observability
**Dependencies:** Stage 8 complete
**Risk Level:** Low

## Objectives

1. Create real-time metrics panel
2. Display execution time tracking
3. Show resource usage indicators
4. Build performance metrics view
5. Add system health indicators

## Current State Analysis

### What We Have
- `METRIC_UPDATE` WebSocket events
- Basic timing in workflow state
- Cost tracking from Stage 8

### What We Need
- Real-time metrics display
- Execution timeline
- Memory/resource indicators
- Performance trends
- Health status panel

## Implementation Tasks

### Task 1: Create Metrics Types
**Files to Create:**
- `cmbagent-ui/types/metrics.ts`

```typescript
// types/metrics.ts

export interface MetricData {
  name: string;
  value: number;
  unit: string;
  timestamp: string;
  tags?: Record<string, string>;
}

export interface ExecutionMetrics {
  total_duration_seconds: number;
  planning_duration_seconds: number;
  execution_duration_seconds: number;
  avg_step_duration_seconds: number;
  slowest_step_seconds: number;
  fastest_step_seconds: number;
}

export interface ResourceMetrics {
  memory_usage_mb: number;
  memory_limit_mb: number;
  cpu_usage_percent?: number;
  open_files?: number;
  active_connections?: number;
}

export interface PerformanceMetrics {
  llm_call_count: number;
  avg_response_time_ms: number;
  cache_hit_rate?: number;
  error_rate: number;
  retry_rate: number;
}

export interface SystemHealth {
  backend_status: 'healthy' | 'degraded' | 'unhealthy';
  websocket_status: 'connected' | 'disconnected' | 'reconnecting';
  database_status?: 'healthy' | 'degraded' | 'unhealthy';
  last_heartbeat?: string;
}
```

### Task 2: Create Metrics Panel Component
**Files to Create:**
- `cmbagent-ui/components/metrics/MetricsPanel.tsx`

```typescript
// components/metrics/MetricsPanel.tsx

'use client';

import {
  Clock,
  Activity,
  Cpu,
  HardDrive,
  Zap,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import { ExecutionMetrics, ResourceMetrics, PerformanceMetrics, SystemHealth } from '@/types/metrics';

interface MetricsPanelProps {
  execution: ExecutionMetrics;
  resources?: ResourceMetrics;
  performance: PerformanceMetrics;
  health: SystemHealth;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
}

function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  color = 'blue',
  trend,
}: {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ElementType;
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'purple';
  trend?: 'up' | 'down' | 'stable';
}) {
  const colorClasses = {
    blue: 'text-blue-400 bg-blue-500/10',
    green: 'text-green-400 bg-green-500/10',
    yellow: 'text-yellow-400 bg-yellow-500/10',
    red: 'text-red-400 bg-red-500/10',
    purple: 'text-purple-400 bg-purple-500/10',
  };

  return (
    <div className="p-4 bg-gray-800/50 rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-400 uppercase">{title}</span>
        <div className={`p-1.5 rounded ${colorClasses[color]}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <div className="text-xl font-bold text-white">{value}</div>
      {subtitle && (
        <div className="text-xs text-gray-400 mt-1">{subtitle}</div>
      )}
    </div>
  );
}

function HealthIndicator({ status }: { status: 'healthy' | 'degraded' | 'unhealthy' }) {
  const config = {
    healthy: { icon: CheckCircle, color: 'text-green-400', label: 'Healthy' },
    degraded: { icon: AlertTriangle, color: 'text-yellow-400', label: 'Degraded' },
    unhealthy: { icon: XCircle, color: 'text-red-400', label: 'Unhealthy' },
  };

  const { icon: Icon, color, label } = config[status];

  return (
    <div className={`flex items-center space-x-2 ${color}`}>
      <Icon className="w-4 h-4" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function MetricsPanel({
  execution,
  resources,
  performance,
  health,
}: MetricsPanelProps) {
  return (
    <div className="space-y-6">
      {/* System Health */}
      <div className="p-4 bg-gray-900/50 rounded-xl border border-gray-700">
        <h3 className="text-sm font-medium text-gray-300 mb-4">System Health</h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <span className="text-xs text-gray-400 block mb-1">Backend</span>
            <HealthIndicator status={health.backend_status} />
          </div>
          <div>
            <span className="text-xs text-gray-400 block mb-1">WebSocket</span>
            <div className={`flex items-center space-x-2 ${
              health.websocket_status === 'connected' ? 'text-green-400' :
              health.websocket_status === 'reconnecting' ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {health.websocket_status === 'connected' ? (
                <CheckCircle className="w-4 h-4" />
              ) : health.websocket_status === 'reconnecting' ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <XCircle className="w-4 h-4" />
              )}
              <span className="text-sm capitalize">{health.websocket_status}</span>
            </div>
          </div>
          <div>
            <span className="text-xs text-gray-400 block mb-1">Database</span>
            <HealthIndicator status={health.database_status || 'healthy'} />
          </div>
        </div>
      </div>

      {/* Execution Metrics */}
      <div>
        <h3 className="text-sm font-medium text-gray-300 mb-3">Execution Timing</h3>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          <MetricCard
            title="Total Duration"
            value={formatDuration(execution.total_duration_seconds)}
            icon={Clock}
            color="blue"
          />
          <MetricCard
            title="Planning"
            value={formatDuration(execution.planning_duration_seconds)}
            icon={Activity}
            color="purple"
          />
          <MetricCard
            title="Execution"
            value={formatDuration(execution.execution_duration_seconds)}
            icon={Zap}
            color="green"
          />
          <MetricCard
            title="Avg Step"
            value={formatDuration(execution.avg_step_duration_seconds)}
            subtitle="per step"
            icon={Clock}
            color="blue"
          />
          <MetricCard
            title="Slowest Step"
            value={formatDuration(execution.slowest_step_seconds)}
            icon={Clock}
            color="red"
          />
          <MetricCard
            title="Fastest Step"
            value={formatDuration(execution.fastest_step_seconds)}
            icon={Clock}
            color="green"
          />
        </div>
      </div>

      {/* Resource Metrics */}
      {resources && (
        <div>
          <h3 className="text-sm font-medium text-gray-300 mb-3">Resources</h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <MetricCard
              title="Memory"
              value={`${resources.memory_usage_mb.toFixed(0)} MB`}
              subtitle={`of ${resources.memory_limit_mb} MB`}
              icon={HardDrive}
              color={resources.memory_usage_mb / resources.memory_limit_mb > 0.8 ? 'red' : 'blue'}
            />
            {resources.cpu_usage_percent !== undefined && (
              <MetricCard
                title="CPU"
                value={`${resources.cpu_usage_percent.toFixed(1)}%`}
                icon={Cpu}
                color={resources.cpu_usage_percent > 80 ? 'red' : 'blue'}
              />
            )}
            {resources.open_files !== undefined && (
              <MetricCard
                title="Open Files"
                value={resources.open_files.toString()}
                icon={HardDrive}
              />
            )}
            {resources.active_connections !== undefined && (
              <MetricCard
                title="Connections"
                value={resources.active_connections.toString()}
                icon={Activity}
              />
            )}
          </div>
        </div>
      )}

      {/* Performance Metrics */}
      <div>
        <h3 className="text-sm font-medium text-gray-300 mb-3">Performance</h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <MetricCard
            title="LLM Calls"
            value={performance.llm_call_count.toString()}
            icon={Zap}
            color="purple"
          />
          <MetricCard
            title="Avg Response"
            value={`${performance.avg_response_time_ms.toFixed(0)} ms`}
            icon={Clock}
            color={performance.avg_response_time_ms > 5000 ? 'yellow' : 'green'}
          />
          <MetricCard
            title="Error Rate"
            value={`${(performance.error_rate * 100).toFixed(1)}%`}
            icon={AlertTriangle}
            color={performance.error_rate > 0.1 ? 'red' : 'green'}
          />
          <MetricCard
            title="Retry Rate"
            value={`${(performance.retry_rate * 100).toFixed(1)}%`}
            icon={RefreshCw}
            color={performance.retry_rate > 0.2 ? 'yellow' : 'green'}
          />
        </div>
      </div>
    </div>
  );
}
```

### Task 3: Create Resource Monitor Component
**Files to Create:**
- `cmbagent-ui/components/metrics/ResourceMonitor.tsx`

```typescript
// components/metrics/ResourceMonitor.tsx

'use client';

import { useEffect, useState } from 'react';
import { HardDrive, Cpu, Activity } from 'lucide-react';
import { ResourceMetrics } from '@/types/metrics';

interface ResourceMonitorProps {
  resources: ResourceMetrics;
  compact?: boolean;
}

function ProgressRing({
  progress,
  size = 60,
  strokeWidth = 4,
  color = 'blue',
}: {
  progress: number;
  size?: number;
  strokeWidth?: number;
  color?: 'blue' | 'green' | 'yellow' | 'red';
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;

  const colors = {
    blue: '#3B82F6',
    green: '#10B981',
    yellow: '#F59E0B',
    red: '#EF4444',
  };

  return (
    <svg width={size} height={size} className="transform -rotate-90">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="transparent"
        stroke="#374151"
        strokeWidth={strokeWidth}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="transparent"
        stroke={colors[color]}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="transition-all duration-500"
      />
    </svg>
  );
}

export function ResourceMonitor({ resources, compact = false }: ResourceMonitorProps) {
  const memoryPercent = (resources.memory_usage_mb / resources.memory_limit_mb) * 100;
  const cpuPercent = resources.cpu_usage_percent || 0;

  const getColor = (percent: number) => {
    if (percent > 80) return 'red';
    if (percent > 60) return 'yellow';
    return 'green';
  };

  if (compact) {
    return (
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <HardDrive className="w-4 h-4 text-gray-400" />
          <span className={`text-sm ${
            memoryPercent > 80 ? 'text-red-400' : 'text-gray-300'
          }`}>
            {resources.memory_usage_mb.toFixed(0)} MB
          </span>
        </div>
        {resources.cpu_usage_percent !== undefined && (
          <div className="flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-gray-400" />
            <span className={`text-sm ${
              cpuPercent > 80 ? 'text-red-400' : 'text-gray-300'
            }`}>
              {cpuPercent.toFixed(0)}%
            </span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="p-4 bg-gray-900/50 rounded-xl border border-gray-700">
      <h3 className="text-sm font-medium text-gray-300 mb-4">Resource Usage</h3>
      <div className="flex items-center justify-around">
        {/* Memory */}
        <div className="flex flex-col items-center">
          <div className="relative">
            <ProgressRing progress={memoryPercent} color={getColor(memoryPercent)} />
            <div className="absolute inset-0 flex items-center justify-center">
              <HardDrive className="w-5 h-5 text-gray-400" />
            </div>
          </div>
          <span className="text-sm text-white mt-2">
            {resources.memory_usage_mb.toFixed(0)} MB
          </span>
          <span className="text-xs text-gray-400">Memory</span>
        </div>

        {/* CPU */}
        {resources.cpu_usage_percent !== undefined && (
          <div className="flex flex-col items-center">
            <div className="relative">
              <ProgressRing progress={cpuPercent} color={getColor(cpuPercent)} />
              <div className="absolute inset-0 flex items-center justify-center">
                <Cpu className="w-5 h-5 text-gray-400" />
              </div>
            </div>
            <span className="text-sm text-white mt-2">
              {cpuPercent.toFixed(0)}%
            </span>
            <span className="text-xs text-gray-400">CPU</span>
          </div>
        )}

        {/* Active Connections */}
        {resources.active_connections !== undefined && (
          <div className="flex flex-col items-center">
            <div className="w-[60px] h-[60px] flex items-center justify-center rounded-full bg-blue-500/20">
              <Activity className="w-6 h-6 text-blue-400" />
            </div>
            <span className="text-sm text-white mt-2">
              {resources.active_connections}
            </span>
            <span className="text-xs text-gray-400">Connections</span>
          </div>
        )}
      </div>
    </div>
  );
}
```

### Task 4: Create Execution Timeline Component
**Files to Create:**
- `cmbagent-ui/components/metrics/ExecutionTimeline.tsx`

```typescript
// components/metrics/ExecutionTimeline.tsx

'use client';

import { Clock, CheckCircle, XCircle, Play, Pause } from 'lucide-react';

interface TimelineEvent {
  id: string;
  type: 'start' | 'step_start' | 'step_complete' | 'step_fail' | 'pause' | 'resume' | 'complete';
  timestamp: string;
  label: string;
  duration_ms?: number;
}

interface ExecutionTimelineProps {
  events: TimelineEvent[];
  startTime?: string;
}

const eventConfig: Record<string, { icon: React.ElementType; color: string }> = {
  start: { icon: Play, color: 'blue' },
  step_start: { icon: Clock, color: 'blue' },
  step_complete: { icon: CheckCircle, color: 'green' },
  step_fail: { icon: XCircle, color: 'red' },
  pause: { icon: Pause, color: 'yellow' },
  resume: { icon: Play, color: 'green' },
  complete: { icon: CheckCircle, color: 'green' },
};

export function ExecutionTimeline({ events, startTime }: ExecutionTimelineProps) {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-500 text-blue-500',
    green: 'bg-green-500 text-green-500',
    red: 'bg-red-500 text-red-500',
    yellow: 'bg-yellow-500 text-yellow-500',
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
  };

  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-700 p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-4">Execution Timeline</h3>
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-3 top-0 bottom-0 w-px bg-gray-700" />

        <div className="space-y-4">
          {events.map((event, index) => {
            const config = eventConfig[event.type] || eventConfig.step_complete;
            const Icon = config.icon;
            const color = config.color;

            return (
              <div key={event.id} className="relative flex items-start ml-1">
                {/* Dot */}
                <div className={`relative z-10 w-5 h-5 rounded-full flex items-center justify-center ${
                  colorClasses[color].split(' ')[0]
                }`}>
                  <Icon className="w-3 h-3 text-white" />
                </div>

                {/* Content */}
                <div className="ml-4 flex-grow">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-white">{event.label}</span>
                    {event.duration_ms && (
                      <span className="text-xs text-gray-400">
                        {formatDuration(event.duration_ms)}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-500">
                    {formatTime(event.timestamp)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
```

### Task 5: Update Metrics Index Export
**Files to Modify:**
- `cmbagent-ui/components/metrics/index.ts`

```typescript
// components/metrics/index.ts
export { CostSummaryCards } from './CostSummaryCards';
export { CostBreakdown } from './CostBreakdown';
export { CostChart } from './CostChart';
export { CostDashboard } from './CostDashboard';
export { MetricsPanel } from './MetricsPanel';
export { ResourceMonitor } from './ResourceMonitor';
export { ExecutionTimeline } from './ExecutionTimeline';
```

## Files to Create (Summary)

```
cmbagent-ui/
├── types/
│   └── metrics.ts
└── components/
    └── metrics/
        ├── index.ts (updated)
        ├── MetricsPanel.tsx
        ├── ResourceMonitor.tsx
        └── ExecutionTimeline.tsx
```

## Verification Criteria

### Must Pass
- [ ] MetricsPanel displays all metric categories
- [ ] Health indicators show correct status
- [ ] ResourceMonitor progress rings work
- [ ] ExecutionTimeline renders events in order
- [ ] Real-time updates from WebSocket

### Should Pass
- [ ] Compact mode for ResourceMonitor
- [ ] Responsive design
- [ ] Smooth animations

## Success Criteria

Stage 9 is complete when:
1. All metrics components working
2. Real-time updates functional
3. Health monitoring operational
4. Timeline displays correctly

## Post-Implementation

After completing all 9 stages:
1. Update PROGRESS.md marking all stages complete
2. Create integration test scenarios
3. Document any API changes needed
4. Create demo/walkthrough documentation

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-16
