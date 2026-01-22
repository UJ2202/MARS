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
