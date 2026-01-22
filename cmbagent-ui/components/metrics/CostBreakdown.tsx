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
