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
