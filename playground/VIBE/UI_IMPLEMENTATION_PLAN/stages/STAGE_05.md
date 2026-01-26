# Stage 5: Retry UI with Context Display

**Phase:** 1 - Workflow Control
**Dependencies:** Stage 4 complete, Backend Stage 7 (Retry) complete
**Risk Level:** Low

## Objectives

1. Display retry status in DAG nodes
2. Show retry attempt count and progress
3. Display error context and suggestions
4. Visualize backoff timing
5. Allow manual retry trigger

## Current State Analysis

### What We Have
- `STEP_RETRY_STARTED`, `STEP_RETRY_BACKOFF`, `STEP_RETRY_SUCCEEDED`, `STEP_RETRY_EXHAUSTED` events
- DAG node can show retry status
- Basic error display

### What We Need
- Dedicated retry status component
- Error categorization display
- Retry suggestions viewer
- Backoff countdown timer
- Manual retry button

## Implementation Tasks

### Task 1: Create Retry Types
**Files to Create:**
- `cmbagent-ui/types/retry.ts`

```typescript
// types/retry.ts

export type ErrorCategory =
  | 'NETWORK'
  | 'RATE_LIMIT'
  | 'API_ERROR'
  | 'VALIDATION'
  | 'TIMEOUT'
  | 'RESOURCE'
  | 'UNKNOWN';

export interface RetryInfo {
  step_id: string;
  step_number: number;
  attempt_number: number;
  max_attempts: number;
  error_category: ErrorCategory;
  error_pattern?: string;
  error_message: string;
  traceback?: string;
  success_probability?: number;
  strategy: string;
  suggestions: string[];
  has_user_feedback: boolean;
  backoff_seconds?: number;
  next_attempt_at?: string;
}

export interface RetryStatus {
  is_retrying: boolean;
  current_retry: RetryInfo | null;
  history: RetryHistoryItem[];
}

export interface RetryHistoryItem {
  attempt_number: number;
  error_message: string;
  timestamp: string;
  succeeded: boolean;
}
```

### Task 2: Create Retry Status Component
**Files to Create:**
- `cmbagent-ui/components/retry/RetryStatus.tsx`

```typescript
// components/retry/RetryStatus.tsx

'use client';

import { useState, useEffect } from 'react';
import {
  RotateCw,
  AlertTriangle,
  Clock,
  Lightbulb,
  TrendingUp,
  Timer,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { RetryInfo, ErrorCategory } from '@/types/retry';

interface RetryStatusProps {
  retryInfo: RetryInfo;
  onManualRetry?: () => void;
  onProvideContext?: (context: string) => void;
}

const categoryColors: Record<ErrorCategory, string> = {
  NETWORK: 'text-yellow-400 bg-yellow-500/20',
  RATE_LIMIT: 'text-orange-400 bg-orange-500/20',
  API_ERROR: 'text-red-400 bg-red-500/20',
  VALIDATION: 'text-purple-400 bg-purple-500/20',
  TIMEOUT: 'text-yellow-400 bg-yellow-500/20',
  RESOURCE: 'text-blue-400 bg-blue-500/20',
  UNKNOWN: 'text-gray-400 bg-gray-500/20',
};

const categoryDescriptions: Record<ErrorCategory, string> = {
  NETWORK: 'Network connectivity issue',
  RATE_LIMIT: 'API rate limit exceeded',
  API_ERROR: 'External API returned error',
  VALIDATION: 'Input validation failed',
  TIMEOUT: 'Operation timed out',
  RESOURCE: 'Resource not found or unavailable',
  UNKNOWN: 'Unexpected error occurred',
};

export function RetryStatus({
  retryInfo,
  onManualRetry,
  onProvideContext,
}: RetryStatusProps) {
  const [backoffRemaining, setBackoffRemaining] = useState(retryInfo.backoff_seconds || 0);
  const [userContext, setUserContext] = useState('');

  // Countdown timer for backoff
  useEffect(() => {
    if (backoffRemaining <= 0) return;

    const interval = setInterval(() => {
      setBackoffRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, [backoffRemaining]);

  // Update backoff when new retry info received
  useEffect(() => {
    setBackoffRemaining(retryInfo.backoff_seconds || 0);
  }, [retryInfo.backoff_seconds]);

  const progressPercentage = (retryInfo.attempt_number / retryInfo.max_attempts) * 100;

  return (
    <div className="bg-orange-500/10 border border-orange-500/30 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-orange-500/20 border-b border-orange-500/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <RotateCw className="w-5 h-5 text-orange-400 animate-spin" />
            <div>
              <h3 className="text-sm font-medium text-orange-300">
                Retry in Progress
              </h3>
              <p className="text-xs text-orange-400/70">
                Step #{retryInfo.step_number}
              </p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-lg font-bold text-orange-300">
              {retryInfo.attempt_number}
            </span>
            <span className="text-sm text-orange-400/70">
              / {retryInfo.max_attempts}
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-3 h-1.5 bg-orange-900/50 rounded-full overflow-hidden">
          <div
            className="h-full bg-orange-500 rounded-full transition-all duration-500"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Error Category */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Error Category</span>
          <span className={`px-2 py-1 rounded text-xs font-medium ${categoryColors[retryInfo.error_category]}`}>
            {retryInfo.error_category}
          </span>
        </div>

        {/* Error Message */}
        <div>
          <div className="flex items-center space-x-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span className="text-xs text-gray-400">Error Message</span>
          </div>
          <p className="text-sm text-red-300 bg-red-500/10 p-3 rounded-lg">
            {retryInfo.error_message}
          </p>
        </div>

        {/* Success Probability */}
        {retryInfo.success_probability !== undefined && (
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-400">Success Probability</span>
            </div>
            <span className={`text-sm font-medium ${
              retryInfo.success_probability > 0.7 ? 'text-green-400' :
              retryInfo.success_probability > 0.4 ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {Math.round(retryInfo.success_probability * 100)}%
            </span>
          </div>
        )}

        {/* Strategy */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Retry Strategy</span>
          <span className="text-sm text-gray-300 capitalize">
            {retryInfo.strategy.replace('_', ' ')}
          </span>
        </div>

        {/* Backoff Timer */}
        {backoffRemaining > 0 && (
          <div className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
            <div className="flex items-center space-x-2">
              <Timer className="w-4 h-4 text-blue-400" />
              <span className="text-sm text-gray-300">Next attempt in</span>
            </div>
            <span className="text-lg font-mono text-blue-400">
              {backoffRemaining}s
            </span>
          </div>
        )}

        {/* Suggestions */}
        {retryInfo.suggestions.length > 0 && (
          <div>
            <div className="flex items-center space-x-2 mb-2">
              <Lightbulb className="w-4 h-4 text-yellow-400" />
              <span className="text-xs text-gray-400">Suggestions</span>
            </div>
            <ul className="space-y-1">
              {retryInfo.suggestions.map((suggestion, index) => (
                <li
                  key={index}
                  className="text-sm text-gray-300 pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-yellow-400"
                >
                  {suggestion}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* User Context Input */}
        {onProvideContext && (
          <div>
            <label className="block text-xs text-gray-400 mb-2">
              Provide Additional Context (Optional)
            </label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={userContext}
                onChange={(e) => setUserContext(e.target.value)}
                placeholder="e.g., 'Try using a different API key'"
                className="flex-grow px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-orange-500"
              />
              <button
                onClick={() => {
                  if (userContext.trim()) {
                    onProvideContext(userContext.trim());
                    setUserContext('');
                  }
                }}
                disabled={!userContext.trim()}
                className="px-4 py-2 bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 rounded-lg transition-colors disabled:opacity-50"
              >
                Send
              </button>
            </div>
          </div>
        )}

        {/* Manual Retry Button */}
        {onManualRetry && backoffRemaining === 0 && (
          <button
            onClick={onManualRetry}
            className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-orange-500 hover:bg-orange-600 text-white font-medium rounded-lg transition-colors"
          >
            <RotateCw className="w-4 h-4" />
            <span>Retry Now</span>
          </button>
        )}
      </div>
    </div>
  );
}
```

### Task 3: Create Retry History Component
**Files to Create:**
- `cmbagent-ui/components/retry/RetryHistory.tsx`

```typescript
// components/retry/RetryHistory.tsx

'use client';

import { CheckCircle, XCircle, Clock } from 'lucide-react';
import { RetryHistoryItem } from '@/types/retry';

interface RetryHistoryProps {
  history: RetryHistoryItem[];
}

export function RetryHistory({ history }: RetryHistoryProps) {
  if (history.length === 0) {
    return null;
  }

  return (
    <div className="mt-4">
      <h4 className="text-xs text-gray-400 mb-2">Retry History</h4>
      <div className="space-y-1">
        {history.map((item, index) => (
          <div
            key={index}
            className={`flex items-center justify-between p-2 rounded text-xs ${
              item.succeeded ? 'bg-green-500/10' : 'bg-red-500/10'
            }`}
          >
            <div className="flex items-center space-x-2">
              {item.succeeded ? (
                <CheckCircle className="w-3 h-3 text-green-400" />
              ) : (
                <XCircle className="w-3 h-3 text-red-400" />
              )}
              <span className="text-gray-300">
                Attempt {item.attempt_number}
              </span>
            </div>
            <div className="flex items-center space-x-2 text-gray-400">
              <Clock className="w-3 h-3" />
              <span>{new Date(item.timestamp).toLocaleTimeString()}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Task 4: Create Retry Context Viewer
**Files to Create:**
- `cmbagent-ui/components/retry/RetryContext.tsx`

```typescript
// components/retry/RetryContext.tsx

'use client';

import { useState } from 'react';
import { Code, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';

interface RetryContextProps {
  errorMessage: string;
  traceback?: string;
  previousAttempts?: {
    attempt: number;
    error: string;
    timestamp: string;
  }[];
}

export function RetryContext({ errorMessage, traceback, previousAttempts }: RetryContextProps) {
  const [showTraceback, setShowTraceback] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyTraceback = () => {
    if (traceback) {
      navigator.clipboard.writeText(traceback);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-3">
      {/* Error Message */}
      <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
        <p className="text-sm text-red-300">{errorMessage}</p>
      </div>

      {/* Traceback */}
      {traceback && (
        <div className="border border-gray-700 rounded-lg overflow-hidden">
          <button
            onClick={() => setShowTraceback(!showTraceback)}
            className="w-full flex items-center justify-between px-4 py-2 bg-gray-800 hover:bg-gray-700 transition-colors"
          >
            <div className="flex items-center space-x-2">
              <Code className="w-4 h-4 text-gray-400" />
              <span className="text-sm text-gray-300">Traceback</span>
            </div>
            <div className="flex items-center space-x-2">
              {showTraceback && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    copyTraceback();
                  }}
                  className="p-1 hover:bg-gray-600 rounded"
                >
                  {copied ? (
                    <Check className="w-4 h-4 text-green-400" />
                  ) : (
                    <Copy className="w-4 h-4 text-gray-400" />
                  )}
                </button>
              )}
              {showTraceback ? (
                <ChevronDown className="w-4 h-4 text-gray-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-400" />
              )}
            </div>
          </button>
          {showTraceback && (
            <pre className="p-4 bg-gray-900 text-xs text-gray-400 overflow-x-auto max-h-64 overflow-y-auto">
              {traceback}
            </pre>
          )}
        </div>
      )}

      {/* Previous Attempts */}
      {previousAttempts && previousAttempts.length > 0 && (
        <div>
          <h4 className="text-xs text-gray-400 mb-2">Previous Attempts</h4>
          <div className="space-y-2">
            {previousAttempts.map((attempt) => (
              <div
                key={attempt.attempt}
                className="p-2 bg-gray-800/50 rounded text-xs"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-gray-400">Attempt {attempt.attempt}</span>
                  <span className="text-gray-500">
                    {new Date(attempt.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-red-400 truncate">{attempt.error}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

### Task 5: Create Retry Index Export
**Files to Create:**
- `cmbagent-ui/components/retry/index.ts`

```typescript
// components/retry/index.ts
export { RetryStatus } from './RetryStatus';
export { RetryHistory } from './RetryHistory';
export { RetryContext } from './RetryContext';
```

## Files to Create (Summary)

```
cmbagent-ui/
├── types/
│   └── retry.ts
└── components/
    └── retry/
        ├── index.ts
        ├── RetryStatus.tsx
        ├── RetryHistory.tsx
        └── RetryContext.tsx
```

## Verification Criteria

### Must Pass
- [ ] RetryStatus displays attempt count
- [ ] Backoff countdown timer works
- [ ] Error category shown correctly
- [ ] Suggestions displayed
- [ ] Manual retry button functional
- [ ] User context input works

### Should Pass
- [ ] Traceback collapsible
- [ ] Copy traceback button works
- [ ] Previous attempts history shown
- [ ] Responsive design

## Success Criteria

Stage 5 is complete when:
1. Retry status component working
2. Real-time updates from WebSocket
3. Backoff timer counting down
4. User can provide context
5. History displayed correctly

## Next Stage

Once Stage 5 is verified complete, proceed to:
**Stage 6: Branching & Comparison UI**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-16
