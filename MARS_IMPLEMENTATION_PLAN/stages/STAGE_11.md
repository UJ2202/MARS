# Stage 11: Console Logs Overhaul

**Phase:** 4 - Refinements
**Dependencies:** Stage 8 (Console Modal)
**Risk Level:** Medium

## Objectives

1. Transform raw console output from plain text lines into a structured, polished log viewer
2. Replace emoji prefixes in `useEventHandler.ts` with structured log entry metadata (type, agent, timestamp)
3. Introduce phase-aware activity indicators between log events (e.g., animated "Planning", "Analyzing", "Executing" states)
4. Parse log entries into typed structured objects instead of raw strings
5. Add visual differentiation: collapsible agent sections, syntax-highlighted code blocks, distinct event type rendering
6. All icons from Lucide -- zero emojis in rendered output

## Current State Analysis

### What We Have

**`ConsoleOutput.tsx` (202 lines):**
- Receives `output: string[]` -- flat array of raw text strings
- Renders each line with `formatOutput()` that does string matching:
  - `line.includes('ERROR')` → red text + `❌` emoji
  - `line.includes('WARNING')` → yellow text + `⚠️` emoji
  - `line.includes('SUCCESS')` → green text + `✅` emoji
  - `line.includes('INFO')` → blue text + `ℹ️` emoji
  - `line.startsWith('>>>')` → blue text + `🔧` emoji
  - `line.includes('Code Explanation:')` → yellow text + `📝` emoji
  - `line.includes('Python Code:')` → green text + `🐍` emoji
  - `line.includes('FINAL RESULT:')` → purple text + `🎯` emoji
- Only has a pulsing dot + "Processing..." at the end while running
- No differentiation between agents, steps, or phases
- No collapsible sections, no timestamps, no event grouping
- Footer shows "CMBAgent Console v1.0"

**`useEventHandler.ts` (246 lines):**
- Converts WebSocket events to console output via `handlers.onOutput?.()`
- Formats each event as an emoji-prefixed string:
  - `AGENT_MESSAGE`: `🔄 [agent] message` or `💬 [agent] message`
  - `AGENT_THINKING`: `🤔 [Agent] Thinking...`
  - `AGENT_TOOL_CALL`: `🔧 [Agent] Calling tool: toolName`
  - `CODE_EXECUTION`: `📝 [agent] Code (lang): preview...` + `📤 [agent] Result: ...`
  - `TOOL_CALL`: `🔧 [agent] Tool: name(args)` + `📤 [agent] Result: ...`
  - `ERROR_OCCURRED`: `❌ Error: message`
  - `STATUS`: `📊 message`

**`WebSocketContext.tsx`:**
- `consoleOutput: string[]` -- flat string array state
- `addConsoleOutput()` appends a string to the array
- Connection events: `🔌 WebSocket connected/disconnected/reconnected`

### What We Need
- Structured log entries (typed objects, not raw strings)
- Rich rendering per entry type (agent message, tool call, code execution, status, error)
- Phase/activity indicators between events (animated Lucide icons + status text)
- Collapsible agent sections or step grouping
- Timestamps on entries
- Syntax highlighting for code blocks
- Lucide icons replacing all emojis
- Professional polished look suitable for enterprise demo

## Pre-Stage Verification

### Check Prerequisites
1. Stage 8 complete: ConsoleModal exists
2. Core components available (Stage 4)
3. Build passes

## Implementation Tasks

### Task 1: Define Structured Log Entry Types
**Objective:** Replace `string[]` with typed log entry objects

**Files to Create:**
- `types/console.ts`

**Implementation:**

```typescript
// types/console.ts

export type LogLevel = 'info' | 'success' | 'warning' | 'error' | 'debug'

export type LogEntryType =
  | 'system'           // WebSocket connected/disconnected, system messages
  | 'agent_message'    // Agent speaking (transition, llm_call, etc.)
  | 'agent_thinking'   // Agent is thinking/reasoning
  | 'tool_call'        // Agent calling a tool
  | 'code_execution'   // Code being run
  | 'code_result'      // Result from code execution
  | 'step_started'     // Workflow step began
  | 'step_completed'   // Workflow step finished
  | 'step_failed'      // Workflow step failed
  | 'status'           // Status update from backend
  | 'error'            // Error occurred
  | 'output'           // Generic text output from backend
  | 'phase_indicator'  // UI-only: phase transition indicator (planning, executing, etc.)

export interface LogEntry {
  id: string             // Unique ID (timestamp + counter)
  timestamp: number      // Unix ms
  type: LogEntryType
  level: LogLevel
  agent?: string         // Agent name if applicable
  message: string        // Primary message text
  details?: {
    tool_name?: string
    arguments?: string
    result?: string
    language?: string
    code?: string
    step_number?: number
    step_id?: string
    error_type?: string
    traceback?: string
  }
  collapsed?: boolean    // For collapsible entries (code blocks, long results)
}

export type PhaseStatus =
  | 'idle'
  | 'connecting'
  | 'planning'
  | 'researching'
  | 'analyzing'
  | 'executing'
  | 'generating'
  | 'reviewing'
  | 'completing'

export interface PhaseIndicator {
  phase: PhaseStatus
  label: string
  description?: string
}

// Map event types and step descriptions to phase indicators
export const PHASE_MAP: Record<string, PhaseIndicator> = {
  planning: { phase: 'planning', label: 'Planning', description: 'Building execution plan' },
  researching: { phase: 'researching', label: 'Researching', description: 'Gathering information' },
  analyzing: { phase: 'analyzing', label: 'Analyzing', description: 'Processing data' },
  executing: { phase: 'executing', label: 'Executing', description: 'Running workflow steps' },
  generating: { phase: 'generating', label: 'Generating', description: 'Producing output' },
  reviewing: { phase: 'reviewing', label: 'Reviewing', description: 'Validating results' },
  completing: { phase: 'completing', label: 'Completing', description: 'Finalizing results' },
}
```

### Task 2: Update WebSocketContext to Use Structured Entries
**Objective:** Change `consoleOutput: string[]` to `consoleOutput: LogEntry[]`

**Files to Modify:**
- `contexts/WebSocketContext.tsx`

**Changes:**
```typescript
// Replace
const [consoleOutput, setConsoleOutput] = useState<string[]>([]);
const addConsoleOutput = useCallback((output: string) => {
  setConsoleOutput(prev => [...prev, output]);
}, []);

// With
const [consoleOutput, setConsoleOutput] = useState<LogEntry[]>([]);
let logCounter = useRef(0);

const addLogEntry = useCallback((entry: Omit<LogEntry, 'id' | 'timestamp'>) => {
  const fullEntry: LogEntry = {
    ...entry,
    id: `${Date.now()}-${logCounter.current++}`,
    timestamp: Date.now(),
  };
  setConsoleOutput(prev => [...prev, fullEntry]);
}, []);

// Keep addConsoleOutput as backward-compatible wrapper
const addConsoleOutput = useCallback((output: string) => {
  addLogEntry({ type: 'output', level: 'info', message: output });
}, [addLogEntry]);
```

Replace the connection event emoji strings:
```typescript
// Replace: addConsoleOutput('🔌 WebSocket connected')
// With:    addLogEntry({ type: 'system', level: 'success', message: 'WebSocket connected' })

// Replace: addConsoleOutput('🔌 WebSocket disconnected')
// With:    addLogEntry({ type: 'system', level: 'warning', message: 'WebSocket disconnected' })

// Replace: addConsoleOutput('🔌 WebSocket reconnected')
// With:    addLogEntry({ type: 'system', level: 'success', message: 'WebSocket reconnected' })
```

Also export `addLogEntry` from the context so useEventHandler can use it.

### Task 3: Update useEventHandler to Emit Structured Entries
**Objective:** Replace emoji-prefixed strings with typed LogEntry objects

**Files to Modify:**
- `hooks/useEventHandler.ts`

**Changes:**

Add a new handler callback `onLogEntry` alongside the existing `onOutput`:

```typescript
interface EventHandlers {
  // ... existing handlers ...
  onLogEntry?: (entry: Omit<LogEntry, 'id' | 'timestamp'>) => void;
}
```

Replace all `handlers.onOutput?.(...)` calls with `handlers.onLogEntry?.(...)`:

```typescript
// AGENT_MESSAGE
case WebSocketEventType.AGENT_MESSAGE:
  handlers.onAgentMessage?.(data as AgentMessageData);
  handlers.onLogEntry?.({
    type: 'agent_message',
    level: 'info',
    agent: data.agent,
    message: data.message,
    details: { role: data.role },
  });
  break;

// AGENT_THINKING
case WebSocketEventType.AGENT_THINKING:
  handlers.onAgentThinking?.(data);
  handlers.onLogEntry?.({
    type: 'agent_thinking',
    level: 'debug',
    agent: data.agent || 'Agent',
    message: 'Thinking...',
  });
  break;

// AGENT_TOOL_CALL
case WebSocketEventType.AGENT_TOOL_CALL:
  handlers.onAgentToolCall?.(data);
  handlers.onLogEntry?.({
    type: 'tool_call',
    level: 'info',
    agent: data.agent || 'Agent',
    message: `Calling tool: ${data.tool_name || 'unknown'}`,
    details: { tool_name: data.tool_name },
  });
  break;

// CODE_EXECUTION
case WebSocketEventType.CODE_EXECUTION:
  handlers.onCodeExecution?.(data as CodeExecutionData);
  handlers.onLogEntry?.({
    type: 'code_execution',
    level: 'info',
    agent: data.agent,
    message: `Code (${data.language})`,
    details: {
      language: data.language,
      code: data.code,
      result: data.result,
    },
    collapsed: true,
  });
  break;

// TOOL_CALL
case WebSocketEventType.TOOL_CALL:
  handlers.onToolCall?.(data as ToolCallData);
  handlers.onLogEntry?.({
    type: 'tool_call',
    level: 'info',
    agent: data.agent,
    message: `Tool: ${data.tool_name}`,
    details: {
      tool_name: data.tool_name,
      arguments: JSON.stringify(data.arguments).substring(0, 200),
      result: data.result?.substring(0, 300),
    },
    collapsed: true,
  });
  break;

// ERROR
case WebSocketEventType.ERROR_OCCURRED:
case 'error':
  handlers.onError?.({ ... });
  handlers.onLogEntry?.({
    type: 'error',
    level: 'error',
    message: data.message || 'Unknown error',
    details: {
      error_type: data.error_type,
      traceback: data.traceback,
    },
  });
  break;

// STATUS
case WebSocketEventType.STATUS:
case 'status':
  handlers.onStatus?.(data.message || String(data));
  handlers.onLogEntry?.({
    type: 'status',
    level: 'info',
    message: data.message || String(data),
  });
  break;

// OUTPUT (legacy)
case WebSocketEventType.OUTPUT:
case 'output':
  handlers.onOutput?.(data.data || data.message || String(data));
  handlers.onLogEntry?.({
    type: 'output',
    level: 'info',
    message: data.data || data.message || String(data),
  });
  break;
```

### Task 4: Create LogEntryRenderer Component
**Objective:** Rich renderer for individual log entries with Lucide icons, timestamps, collapsible sections

**Files to Create:**
- `components/console/LogEntryRenderer.tsx`

**Implementation overview:**

Each entry type gets a distinct visual treatment:

| Entry Type | Icon (Lucide) | Visual Treatment |
|---|---|---|
| `system` | `Wifi` / `WifiOff` | Muted gray, centered, small text |
| `agent_message` | `MessageSquare` | Agent name badge + message body |
| `agent_thinking` | `Brain` (animated pulse) | Italic, muted, with pulsing icon |
| `tool_call` | `Wrench` | Agent badge + tool name + collapsible args/result |
| `code_execution` | `Code` | Agent badge + collapsible syntax-highlighted code block |
| `code_result` | `CornerDownRight` | Indented result with bg highlight |
| `step_started` | `Play` | Bold section header with step number |
| `step_completed` | `CheckCircle` | Green success indicator |
| `step_failed` | `XCircle` | Red error with expandable traceback |
| `status` | `Info` | Muted status line |
| `error` | `AlertTriangle` | Red bg highlight, expandable traceback |
| `output` | `Terminal` | Monospace text |
| `phase_indicator` | Varies (see below) | Animated activity bar |

**Phase indicators** (animated Lucide icons for in-between-event activity):

| Phase | Icon | Animation |
|---|---|---|
| `connecting` | `Wifi` | Pulse |
| `planning` | `Map` | Slow spin |
| `researching` | `Search` | Pulse |
| `analyzing` | `BarChart3` | Pulse |
| `executing` | `Cog` | Spin |
| `generating` | `FileOutput` | Pulse |
| `reviewing` | `CheckSquare` | Pulse |
| `completing` | `Flag` | Pulse |

Each phase indicator renders as:
```
[Animated Icon] Planning... Building execution plan
```
Full-width, centered, with a subtle background band and the animated icon.

**Collapsible sections:**
- Code blocks: Click to expand/collapse; show first 2 lines by default
- Tool results: Collapsed by default; expand to see full output
- Error tracebacks: Collapsed by default; expand to see stack trace

**Timestamp rendering:**
- Show relative time ("2s ago", "1m ago") on hover
- Show absolute time in tooltip

### Task 5: Create PhaseIndicatorBar Component
**Objective:** Animated activity indicator that appears between log events during execution

**Files to Create:**
- `components/console/PhaseIndicatorBar.tsx`

**Implementation:**

```tsx
'use client'

import { Wifi, Map, Search, BarChart3, Cog, FileOutput, CheckSquare, Flag } from 'lucide-react'
import type { PhaseStatus } from '@/types/console'

interface PhaseIndicatorBarProps {
  phase: PhaseStatus
  label: string
  description?: string
}

const PHASE_ICONS: Record<PhaseStatus, React.ElementType> = {
  idle: Cog,
  connecting: Wifi,
  planning: Map,
  researching: Search,
  analyzing: BarChart3,
  executing: Cog,
  generating: FileOutput,
  reviewing: CheckSquare,
  completing: Flag,
}

export default function PhaseIndicatorBar({ phase, label, description }: PhaseIndicatorBarProps) {
  if (phase === 'idle') return null

  const Icon = PHASE_ICONS[phase]

  return (
    <div
      className="flex items-center gap-3 px-4 py-2.5 my-2 rounded-mars-md"
      style={{ backgroundColor: 'var(--mars-color-primary-subtle)' }}
    >
      <Icon
        className="w-4 h-4 animate-spin-slow flex-shrink-0"
        style={{ color: 'var(--mars-color-primary)' }}
      />
      <div className="flex items-baseline gap-2">
        <span
          className="text-sm font-medium"
          style={{ color: 'var(--mars-color-primary-text)' }}
        >
          {label}...
        </span>
        {description && (
          <span
            className="text-xs"
            style={{ color: 'var(--mars-color-text-tertiary)' }}
          >
            {description}
          </span>
        )}
      </div>
      <div className="ml-auto flex gap-1">
        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: 'var(--mars-color-primary)', animationDelay: '0s' }} />
        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: 'var(--mars-color-primary)', animationDelay: '0.3s' }} />
        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: 'var(--mars-color-primary)', animationDelay: '0.6s' }} />
      </div>
    </div>
  )
}
```

### Task 6: Create StructuredConsoleOutput Component
**Objective:** Replace the current ConsoleOutput with a structured log viewer

**Files to Create:**
- `components/console/StructuredConsoleOutput.tsx`

**Implementation overview:**

```tsx
interface StructuredConsoleOutputProps {
  entries: LogEntry[]
  isRunning: boolean
  currentPhase?: PhaseStatus
  onClear?: () => void
}
```

Features:
- Renders `LogEntry[]` using `LogEntryRenderer` for each entry
- Shows `PhaseIndicatorBar` at the bottom when `isRunning` and `currentPhase` is set
- Auto-scroll to bottom (same behavior as current)
- Line numbers use entry index
- Empty state with `Terminal` icon: "Console output will appear here..."
- Footer: "MARS Console" (replacing "CMBAgent Console v1.0")
- Header: `Terminal` icon + running indicator (pulsing dot + "Live")

### Task 7: Integrate Phase Detection
**Objective:** Detect the current execution phase from WebSocket events and update console

**Files to Modify:**
- `contexts/WebSocketContext.tsx`

Add a `currentPhase: PhaseStatus` state that updates based on events:

```typescript
const [currentPhase, setCurrentPhase] = useState<PhaseStatus>('idle');

// In event handlers:
// workflow_started → 'executing'
// step_started where step description includes "plan" → 'planning'
// step_started where step description includes "research" → 'researching'
// step_started where step description includes "analyz" → 'analyzing'
// step_started where step description includes "generat" → 'generating'
// step_started where step description includes "review" → 'reviewing'
// step_completed → keep current phase
// workflow_completed → 'idle'
// agent_thinking → 'analyzing'
// output event → keep current phase

// Also inject phase_indicator entries into the log when phase changes:
addLogEntry({
  type: 'phase_indicator',
  level: 'info',
  message: phaseIndicator.label,
  details: { description: phaseIndicator.description },
});
```

### Task 8: Add CSS for Console Animations
**Objective:** Add animation keyframes for console phase indicators

**Files to Modify:**
- `styles/mars.css`

Add:
```css
/* Console phase indicator animations */
@keyframes mars-spin-slow {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.animate-spin-slow {
  animation: mars-spin-slow 2s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .animate-spin-slow {
    animation: none;
  }
}
```

### Task 9: Update ConsoleModal to Use StructuredConsoleOutput
**Objective:** Wire the new structured output component into the console modal

**Files to Modify:**
- `components/modals/ConsoleModal.tsx`

**Changes:**
- Import `StructuredConsoleOutput` instead of `ConsoleOutput`
- Update filter logic to work with `LogEntry[]` instead of `string[]`:
  - Level filter: match `entry.level` directly (no string parsing needed)
  - Search filter: match `entry.message`, `entry.agent`, `entry.details.*`
- Pass `currentPhase` from WebSocketContext

### Task 10: Backward Compatibility
**Objective:** Ensure existing ConsoleOutput usages still work

**Strategy:**
- Keep the original `ConsoleOutput.tsx` as-is for backward compatibility
- `StructuredConsoleOutput` is the new default used in ConsoleModal
- Any place still using `string[]` output can use the old component
- `WebSocketContext` now stores `LogEntry[]` but provides a `consoleOutputText` getter for legacy access:

```typescript
const consoleOutputText = useMemo(
  () => consoleOutput.map(entry => entry.message),
  [consoleOutput]
);
```

## Files to Create (Summary)

```
types/
└── console.ts

components/console/
├── LogEntryRenderer.tsx
├── PhaseIndicatorBar.tsx
├── StructuredConsoleOutput.tsx
└── index.ts
```

## Files to Modify

- `contexts/WebSocketContext.tsx` - `LogEntry[]` state, `addLogEntry()`, `currentPhase`, remove emoji strings
- `hooks/useEventHandler.ts` - Replace `onOutput` emoji strings with `onLogEntry` structured entries
- `components/modals/ConsoleModal.tsx` - Use StructuredConsoleOutput
- `styles/mars.css` - Add console animation keyframes

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] `npx tsc --noEmit` passes
- [ ] Console renders structured log entries (not raw text)
- [ ] Zero emoji characters in rendered console output
- [ ] All log entry types render with Lucide icons
- [ ] Phase indicator shows animated state during execution
- [ ] Console filter (level + search) works with structured entries
- [ ] Copy and download produce readable text output
- [ ] Auto-scroll behavior preserved
- [ ] All WebSocket events still captured and displayed

### Should Pass
- [ ] Code blocks are syntax-highlighted and collapsible
- [ ] Tool call results are collapsible
- [ ] Error tracebacks are collapsible
- [ ] Agent names displayed as colored badges
- [ ] Timestamps show on hover
- [ ] Phase transitions between events are smooth (no jarring jumps)
- [ ] "Planning..." / "Analyzing..." / "Executing..." indicators appear at appropriate times
- [ ] Existing pages using ConsoleOutput still work (backward compat)

### Nice to Have
- [ ] Log entries grouped by step/agent with collapsible sections
- [ ] Phase indicator shows elapsed time in phase
- [ ] Different agent names get consistent color assignments

## Common Issues and Solutions

### Issue 1: Type Mismatch After Changing consoleOutput Type
**Symptom:** Build errors from components expecting `string[]`
**Solution:** Provide `consoleOutputText` (string array getter) from context for backward compatibility. Update imports gradually.

### Issue 2: Phase Detection Too Aggressive
**Symptom:** Phase indicator changes too rapidly, feels noisy
**Solution:** Debounce phase changes with a 500ms delay. Only show phase indicator if the phase lasts > 1 second.

### Issue 3: Performance With Many Log Entries
**Symptom:** Console slows down with 1000+ structured entries
**Solution:** The structured entries are slightly heavier than strings. Use virtualization (from Stage 10) and limit object depth. Keep `details` minimal.

## Rollback Procedure

If Stage 11 causes issues:
1. Revert `WebSocketContext.tsx` to `string[]` consoleOutput
2. Revert `useEventHandler.ts` to emoji-prefixed `onOutput` calls
3. Revert `ConsoleModal.tsx` to use `ConsoleOutput` component
4. Delete `types/console.ts` and `components/console/` directory
5. Run `npm run build`

## Success Criteria

Stage 11 is complete when:
1. Console renders structured, polished log entries
2. Each event type has a distinct Lucide icon and visual treatment
3. Phase indicators (animated icons + status text) appear between events
4. Code blocks and results are collapsible
5. Zero emojis in rendered output
6. All existing WebSocket events are captured and displayed
7. Build passes with no errors

## Next Stage

Proceed to **Stage 12: File Viewer Overhaul**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
