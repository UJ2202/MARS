# Stage 8: Cost Tracking Dashboard

**Phase:** 3 - Observability
**Dependencies:** Stage 7 complete, Backend cost tracking
**Risk Level:** Low

## Objectives

1. Create cost summary cards
2. Build cost breakdown by model/agent
3. Implement cost over time chart
4. Add budget threshold alerts
5. Display token usage statistics

## Current State Analysis

### What We Have
- `COST_UPDATE` WebSocket events
- Basic cost display in ResultDisplay
- Total cost in workflow state

### What We Need
- Detailed cost breakdown component
- Cost trend visualization
- Per-model and per-agent cost views
- Token usage display
- Budget warning system

## Implementation Tasks

### Task 1: Create Cost Types
**Files to Create:**
- `cmbagent-ui/types/cost.ts`

```typescript
// types/cost.ts

export interface CostSummary {
  total_cost: number;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  model_breakdown: ModelCost[];
  agent_breakdown: AgentCost[];
  step_breakdown: StepCost[];
}

export interface ModelCost {
  model: string;
  cost: number;
  tokens: number;
  input_tokens: number;
  output_tokens: number;
  call_count: number;
}

export interface AgentCost {
  agent: string;
  cost: number;
  tokens: number;
  call_count: number;
}

export interface StepCost {
  step_id: string;
  step_number: number;
  description: string;
  cost: number;
  tokens: number;
}

export interface CostTimeSeries {
  timestamp: string;
  cumulative_cost: number;
  step_cost: number;
  step_number?: number;
}

export interface BudgetConfig {
  warning_threshold: number;
  limit_threshold: number;
  current_usage: number;
}
```

### Task 2: Create Cost Summary Cards
**Files to Create:**
- `cmbagent-ui/components/metrics/CostSummaryCards.tsx`

```typescript
// components/metrics/CostSummaryCards.tsx

'use client';

import { DollarSign, Hash, ArrowUpRight, ArrowDownRight, Zap } from 'lucide-react';

interface CostSummaryCardsProps {
  totalCost: number;
  totalTokens: number;
  inputTokens: number;
  outputTokens: number;
  previousCost?: number;
  budgetLimit?: number;
}

export function CostSummaryCards({
  totalCost,
  totalTokens,
  inputTokens,
  outputTokens,
  previousCost,
  budgetLimit,
}: CostSummaryCardsProps) {
  const costChange = previousCost
    ? ((totalCost - previousCost) / previousCost) * 100
    : 0;
  const budgetUsage = budgetLimit ? (totalCost / budgetLimit) * 100 : 0;

  const cards = [
    {
      title: 'Total Cost',
      value: `$${totalCost.toFixed(4)}`,
      icon: DollarSign,
      color: 'blue',
      change: costChange,
      subtitle: previousCost ? 'vs. previous run' : undefined,
    },
    {
      title: 'Total Tokens',
      value: totalTokens.toLocaleString(),
      icon: Hash,
      color: 'purple',
      subtitle: `${inputTokens.toLocaleString()} in / ${outputTokens.toLocaleString()} out`,
    },
    {
      title: 'Avg Cost/Token',
      value: totalTokens > 0 ? `$${(totalCost / totalTokens * 1000).toFixed(4)}` : '$0',
      icon: Zap,
      color: 'green',
      subtitle: 'per 1K tokens',
    },
    {
      title: 'Budget Usage',
      value: budgetLimit ? `${budgetUsage.toFixed(1)}%` : 'N/A',
      icon: DollarSign,
      color: budgetUsage > 80 ? 'red' : budgetUsage > 50 ? 'yellow' : 'green',
      subtitle: budgetLimit ? `of $${budgetLimit.toFixed(2)} limit` : 'No limit set',
    },
  ];

  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    purple: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    green: 'bg-green-500/20 text-green-400 border-green-500/30',
    yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    red: 'bg-red-500/20 text-red-400 border-red-500/30',
  };

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div
          key={card.title}
          className={`p-4 rounded-xl border ${colorClasses[card.color]}`}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase tracking-wider opacity-70">
              {card.title}
            </span>
            <card.icon className="w-4 h-4" />
          </div>
          <div className="flex items-end justify-between">
            <span className="text-2xl font-bold text-white">{card.value}</span>
            {card.change !== undefined && card.change !== 0 && (
              <div className={`flex items-center text-xs ${
                card.change > 0 ? 'text-red-400' : 'text-green-400'
              }`}>
                {card.change > 0 ? (
                  <ArrowUpRight className="w-3 h-3" />
                ) : (
                  <ArrowDownRight className="w-3 h-3" />
                )}
                <span>{Math.abs(card.change).toFixed(1)}%</span>
              </div>
            )}
          </div>
          {card.subtitle && (
            <span className="text-xs text-gray-400 mt-1 block">
              {card.subtitle}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
```

### Task 3: Create Cost Breakdown Tables
**Files to Create:**
- `cmbagent-ui/components/metrics/CostBreakdown.tsx`

```typescript
// components/metrics/CostBreakdown.tsx

'use client';

import { useState } from 'react';
import { Bot, Cpu, Layers } from 'lucide-react';
import { ModelCost, AgentCost, StepCost } from '@/types/cost';

interface CostBreakdownProps {
  modelBreakdown: ModelCost[];
  agentBreakdown: AgentCost[];
  stepBreakdown: StepCost[];
  totalCost: number;
}

type BreakdownView = 'model' | 'agent' | 'step';

export function CostBreakdown({
  modelBreakdown,
  agentBreakdown,
  stepBreakdown,
  totalCost,
}: CostBreakdownProps) {
  const [activeView, setActiveView] = useState<BreakdownView>('model');

  const views = [
    { id: 'model' as const, label: 'By Model', icon: Cpu },
    { id: 'agent' as const, label: 'By Agent', icon: Bot },
    { id: 'step' as const, label: 'By Step', icon: Layers },
  ];

  const getPercentage = (cost: number) => {
    return totalCost > 0 ? (cost / totalCost) * 100 : 0;
  };

  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-700 overflow-hidden">
      {/* Tab Navigation */}
      <div className="flex border-b border-gray-700">
        {views.map((view) => (
          <button
            key={view.id}
            onClick={() => setActiveView(view.id)}
            className={`flex-1 flex items-center justify-center space-x-2 px-4 py-3 transition-colors ${
              activeView === view.id
                ? 'bg-gray-800 text-white border-b-2 border-blue-500'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <view.icon className="w-4 h-4" />
            <span className="text-sm">{view.label}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="p-4">
        {activeView === 'model' && (
          <div className="space-y-3">
            {modelBreakdown.map((model) => (
              <div key={model.model} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Cpu className="w-4 h-4 text-blue-400" />
                    <span className="text-sm text-white">{model.model}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-medium text-white">
                      ${model.cost.toFixed(4)}
                    </span>
                    <span className="text-xs text-gray-400 ml-2">
                      ({getPercentage(model.cost).toFixed(1)}%)
                    </span>
                  </div>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all"
                    style={{ width: `${getPercentage(model.cost)}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>{model.tokens.toLocaleString()} tokens</span>
                  <span>{model.call_count} calls</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeView === 'agent' && (
          <div className="space-y-3">
            {agentBreakdown.map((agent) => (
              <div key={agent.agent} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Bot className="w-4 h-4 text-purple-400" />
                    <span className="text-sm text-white">{agent.agent}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-medium text-white">
                      ${agent.cost.toFixed(4)}
                    </span>
                    <span className="text-xs text-gray-400 ml-2">
                      ({getPercentage(agent.cost).toFixed(1)}%)
                    </span>
                  </div>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full transition-all"
                    style={{ width: `${getPercentage(agent.cost)}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-400">
                  <span>{agent.tokens.toLocaleString()} tokens</span>
                  <span>{agent.call_count} calls</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeView === 'step' && (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {stepBreakdown.map((step) => (
              <div
                key={step.step_id}
                className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg"
              >
                <div className="flex items-center space-x-3">
                  <span className="text-xs text-gray-400 w-8">
                    #{step.step_number}
                  </span>
                  <span className="text-sm text-white truncate max-w-[200px]">
                    {step.description}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-sm font-medium text-white">
                    ${step.cost.toFixed(4)}
                  </span>
                  <span className="text-xs text-gray-400 block">
                    {step.tokens.toLocaleString()} tokens
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

### Task 4: Create Cost Chart Component
**Files to Create:**
- `cmbagent-ui/components/metrics/CostChart.tsx`

```typescript
// components/metrics/CostChart.tsx

'use client';

import { useMemo } from 'react';
import { CostTimeSeries } from '@/types/cost';

interface CostChartProps {
  data: CostTimeSeries[];
  height?: number;
}

export function CostChart({ data, height = 200 }: CostChartProps) {
  const chartData = useMemo(() => {
    if (data.length === 0) return null;

    const maxCost = Math.max(...data.map((d) => d.cumulative_cost));
    const padding = 40;
    const chartWidth = 100; // percentage

    const points = data.map((d, i) => {
      const x = (i / (data.length - 1 || 1)) * (chartWidth - padding * 2 / 100) + padding / 100;
      const y = 100 - (d.cumulative_cost / maxCost) * 80 - 10;
      return { x: x * 100, y, data: d };
    });

    const pathD = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x}% ${p.y}%`)
      .join(' ');

    const areaD = `${pathD} L ${points[points.length - 1]?.x || 0}% 90% L ${points[0]?.x || 0}% 90% Z`;

    return { points, pathD, areaD, maxCost };
  }, [data]);

  if (!chartData || data.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-gray-800/50 rounded-xl"
        style={{ height }}
      >
        <span className="text-gray-400">No cost data available</span>
      </div>
    );
  }

  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-700 p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-4">Cost Over Time</h3>
      <div style={{ height }} className="relative">
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="w-full h-full"
        >
          {/* Grid lines */}
          {[0, 25, 50, 75, 100].map((y) => (
            <line
              key={y}
              x1="10%"
              y1={`${10 + y * 0.8}%`}
              x2="98%"
              y2={`${10 + y * 0.8}%`}
              stroke="#374151"
              strokeWidth="0.2"
            />
          ))}

          {/* Area fill */}
          <path
            d={chartData.areaD}
            fill="url(#costGradient)"
            opacity="0.3"
          />

          {/* Line */}
          <path
            d={chartData.pathD}
            fill="none"
            stroke="#3B82F6"
            strokeWidth="0.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Points */}
          {chartData.points.map((p, i) => (
            <circle
              key={i}
              cx={`${p.x}%`}
              cy={`${p.y}%`}
              r="1"
              fill="#3B82F6"
              className="hover:r-2 transition-all cursor-pointer"
            />
          ))}

          {/* Gradient definition */}
          <defs>
            <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
            </linearGradient>
          </defs>
        </svg>

        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 h-full flex flex-col justify-between text-xs text-gray-500">
          <span>${chartData.maxCost.toFixed(3)}</span>
          <span>${(chartData.maxCost / 2).toFixed(3)}</span>
          <span>$0</span>
        </div>
      </div>
    </div>
  );
}
```

### Task 5: Create Cost Dashboard Component
**Files to Create:**
- `cmbagent-ui/components/metrics/CostDashboard.tsx`

```typescript
// components/metrics/CostDashboard.tsx

'use client';

import { CostSummaryCards } from './CostSummaryCards';
import { CostBreakdown } from './CostBreakdown';
import { CostChart } from './CostChart';
import { CostSummary, CostTimeSeries, BudgetConfig } from '@/types/cost';

interface CostDashboardProps {
  summary: CostSummary;
  timeSeries: CostTimeSeries[];
  budget?: BudgetConfig;
  previousRunCost?: number;
}

export function CostDashboard({
  summary,
  timeSeries,
  budget,
  previousRunCost,
}: CostDashboardProps) {
  return (
    <div className="space-y-6">
      {/* Budget Warning */}
      {budget && budget.current_usage > budget.warning_threshold && (
        <div className={`p-4 rounded-lg border ${
          budget.current_usage > budget.limit_threshold
            ? 'bg-red-500/10 border-red-500/30 text-red-400'
            : 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
        }`}>
          <span className="font-medium">
            {budget.current_usage > budget.limit_threshold
              ? 'Budget limit exceeded!'
              : 'Approaching budget limit'}
          </span>
          <span className="ml-2 text-sm">
            ${budget.current_usage.toFixed(4)} / ${budget.limit_threshold.toFixed(2)}
          </span>
        </div>
      )}

      {/* Summary Cards */}
      <CostSummaryCards
        totalCost={summary.total_cost}
        totalTokens={summary.total_tokens}
        inputTokens={summary.input_tokens}
        outputTokens={summary.output_tokens}
        previousCost={previousRunCost}
        budgetLimit={budget?.limit_threshold}
      />

      {/* Chart */}
      <CostChart data={timeSeries} height={200} />

      {/* Breakdown */}
      <CostBreakdown
        modelBreakdown={summary.model_breakdown}
        agentBreakdown={summary.agent_breakdown}
        stepBreakdown={summary.step_breakdown}
        totalCost={summary.total_cost}
      />
    </div>
  );
}
```

### Task 6: Create Metrics Index Export
**Files to Create:**
- `cmbagent-ui/components/metrics/index.ts`

```typescript
// components/metrics/index.ts
export { CostSummaryCards } from './CostSummaryCards';
export { CostBreakdown } from './CostBreakdown';
export { CostChart } from './CostChart';
export { CostDashboard } from './CostDashboard';
```

## Files to Create (Summary)

```
cmbagent-ui/
├── types/
│   └── cost.ts
└── components/
    └── metrics/
        ├── index.ts
        ├── CostSummaryCards.tsx
        ├── CostBreakdown.tsx
        ├── CostChart.tsx
        └── CostDashboard.tsx
```

## Verification Criteria

### Must Pass
- [ ] Summary cards display correct values
- [ ] Cost breakdown shows model/agent/step views
- [ ] Chart renders with data points
- [ ] Budget warnings appear at thresholds

### Should Pass
- [ ] Responsive design works
- [ ] Chart interactive with tooltips
- [ ] Empty states handled

## Success Criteria

Stage 8 is complete when:
1. All cost components working
2. Real-time updates from COST_UPDATE events
3. Breakdown views functional
4. Budget alerts working

## Next Stage

Once Stage 8 is verified complete, proceed to:
**Stage 9: Real-time Metrics & Observability UI**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-16
