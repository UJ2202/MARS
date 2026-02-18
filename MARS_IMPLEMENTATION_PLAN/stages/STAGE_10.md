# Stage 10: Accessibility, Responsiveness, Performance & Polish

**Phase:** 3 - Polish
**Dependencies:** All previous stages (1-9)
**Risk Level:** Low

## Objectives

1. WCAG 2.2 AA audit and fixes across all components
2. Responsive design for breakpoints: sm (<=640px), md (<=960px), lg (<=1280px), xl (<=1536px)
3. Code-split modals and heavy views for performance
4. Virtualize large lists (sessions, logs)
5. Micro-interactions: 150-200ms ease, reduced-motion friendly
6. Empty states with friendly, action-oriented microcopy
7. Final visual polish and consistency pass
8. Non-regression checklist confirming no backend contract changes

## Implementation Tasks

### Task 1: Accessibility Audit & Fixes

**Color Contrast:**
- [ ] All text meets 4.5:1 contrast ratio (normal text) and 3:1 (large text)
- [ ] Interactive elements have 3:1 contrast against background
- [ ] Verify both dark and light themes
- [ ] Use browser DevTools contrast checker or axe-core

**Keyboard Navigation:**
- [ ] All interactive elements are reachable via Tab
- [ ] Tab order follows visual layout
- [ ] Enter/Space activates buttons and links
- [ ] Arrow keys navigate within Tabs, Dropdown, and SideNav
- [ ] Esc closes modals and dropdowns
- [ ] Focus visible ring (2px solid primary) on all focusable elements
- [ ] No keyboard traps (except intentional modal focus trap)

**ARIA Roles & Labels:**
- [ ] `role="navigation"` on SideNav
- [ ] `role="banner"` on TopBar
- [ ] `role="main"` on content area
- [ ] `role="dialog"` and `aria-modal="true"` on modals
- [ ] `role="tablist"`, `role="tab"`, `aria-selected` on tabs
- [ ] `aria-label` on icon-only buttons
- [ ] `aria-current="page"` on active nav item
- [ ] `aria-live="polite"` on toast region
- [ ] `aria-describedby` on tooltips
- [ ] Form inputs have associated `<label>` or `aria-label`

**Reduced Motion:**
- [ ] `@media (prefers-reduced-motion: reduce)` disables all animations
- [ ] mars.css already has this rule (verify it's comprehensive)
- [ ] Transitions fallback to instant changes

**Screen Reader:**
- [ ] Empty states have descriptive text
- [ ] Progress indicators have `aria-valuenow`, `aria-valuemin`, `aria-valuemax`, `aria-label`
- [ ] Status badges have text alternatives
- [ ] Console output has `aria-live` region for new entries (debounced)

### Task 2: Responsive Design

**Breakpoints:**
```css
/* sm: <= 640px (mobile) */
/* md: <= 960px (tablet) */
/* lg: <= 1280px (laptop) */
/* xl: <= 1536px (desktop) */
```

**Layout Adaptations:**

**SideNav:**
- xl/lg: Expanded (240px) by default
- md: Collapsed (64px) by default
- sm: Hidden by default, hamburger menu in TopBar opens as overlay

**TopBar:**
- xl/lg: Full layout with pills
- md: Compact pills (no text, status dot only)
- sm: Logo + hamburger + key actions only; pills in dropdown

**ModeGallery Grid:**
- xl: 4 columns
- lg: 3 columns
- md: 2 columns
- sm: 1 column

**TaskList:**
- xl/lg: Table view
- md/sm: Card view (stacked)

**SessionScreen:**
- xl/lg: Split view (list + detail)
- md/sm: Full-width list; detail opens on navigation

**Modals:**
- xl/lg: Centered with size preset
- md: Full width with margin
- sm: Full screen (sheet-style, slides up from bottom)

### Task 3: Performance Optimizations

**Code Splitting:**
```tsx
// Dynamic imports for modals
const ConsoleModal = dynamic(() => import('@/components/modals/ConsoleModal'), {
  loading: () => null  // No spinner needed; modal opens fast enough
})

const WorkflowModal = dynamic(() => import('@/components/modals/WorkflowModal'), {
  loading: () => null
})
```

Add `next/dynamic` imports in `AppShell.tsx` for both modals.

**Virtualized Lists:**

For `ConsoleOutput`:
- When `consoleOutput.length > 500`, use a virtual window renderer
- Only render visible lines (viewport height / line height)
- Implement using a simple virtual scroll hook (avoid adding `react-window` dependency unless needed)
- Preserve auto-scroll behavior

For `SessionList`:
- When sessions exceed 50, use virtual scrolling
- Each `SessionCard` has fixed height for consistent calculation

**Bundle Analysis:**
```bash
# Run after implementing
npx next build
# Check .next/analyze output sizes
```

**Defer Non-Critical Assets:**
- Lazy load DAG visualization components
- Defer cost charts until tab is visible
- Use `Skeleton` components during lazy loading

### Task 4: Micro-Interactions & Motion

**Hover States:**
- [ ] ModeCard: scale(1.02), shadow elevation, gradient overlay
- [ ] SessionCard: background highlight, border color change
- [ ] Buttons: background color shift
- [ ] NavItems: background highlight
- All transitions: `var(--mars-duration-fast)` (150ms) `var(--mars-ease-standard)`

**Press States:**
- [ ] Buttons: scale(0.98) for 100ms
- [ ] Cards: scale(0.99) for 100ms

**Focus States:**
- [ ] 2px outline `var(--mars-color-primary)`, 2px offset
- [ ] Visible only on `:focus-visible` (not mouse clicks)

**Page Transitions:**
- [ ] Content area uses `mars-fade-in` animation on route change
- [ ] Modal appearance: `mars-scale-in` (scale from 95% to 100%)
- [ ] Toast: `mars-slide-up` (slide from 8px below)
- [ ] SideNav collapse: `transition-all var(--mars-duration-slow)`

**Progress:**
- [ ] ProgressIndicator: smooth width/stroke-dashoffset transitions
- [ ] Session status dots: pulse animation for active
- [ ] No jarring opacity jumps

### Task 5: Empty States & Microcopy

**Modes Gallery:**
- Empty search: "No modes match your search. Try a different term."
- Action: "Clear search"

**Sessions Screen:**
- No sessions: "No active sessions — Launch a new workflow from the Modes screen"
- Action: "Go to Modes"

**Tasks Screen:**
- No tasks: "Create a task or import a preset to get started"
- Action: "Create Task"

**Console Modal (empty):**
- "No console output yet — Start a workflow to see live logs"

**Workflow Modal (no data):**
- "No active workflow — Launch a task from the Modes screen to see the execution graph"

### Task 6: Visual Consistency Pass

- [ ] All borders use `var(--mars-color-border)` (not hardcoded `border-white/10` or `border-gray-700`)
- [ ] All text colors use token hierarchy: text > text-secondary > text-tertiary > text-disabled
- [ ] All backgrounds use token hierarchy: bg > bg-secondary > bg-tertiary
- [ ] All interactive elements use consistent border-radius (`--mars-radius-md` for most, `--mars-radius-sm` for small)
- [ ] All shadows use token scale (`--mars-shadow-sm` to `--mars-shadow-xl`)
- [ ] Consistent spacing using `--mars-space-*` tokens
- [ ] Typography hierarchy consistent (h1=2xl, h2=xl, h3=lg, body=base, caption=sm, label=xs)
- [ ] No remaining hardcoded `bg-black/20`, `bg-gradient-to-br from-slate-900` etc. in migrated components
- [ ] **No emoji characters rendered anywhere in the UI.** All status indicators, log prefixes, and visual cues use Lucide icon components exclusively. Verify with: `grep -rn '[emoji-range]' components/ app/` returns zero matches in rendered output.

### Task 7: Non-Regression Checklist

**API Contracts (Must Not Change):**
- [ ] `POST /api/tasks` payload format unchanged
- [ ] `GET /api/sessions` response consumed correctly
- [ ] `GET /api/sessions/{id}` response consumed correctly
- [ ] `GET /api/sessions/{id}/history` response consumed correctly
- [ ] `POST /api/sessions/{id}/resume` endpoint called correctly
- [ ] `GET /api/runs/{id}/dag` response consumed correctly
- [ ] `GET /api/runs/{id}/files` response consumed correctly
- [ ] `GET /api/runs/{id}/costs` response consumed correctly
- [ ] `POST /api/runs/{id}/branch` payload format unchanged
- [ ] `POST /api/runs/{id}/play-from-node` payload format unchanged
- [ ] `POST /api/approvals/{id}` payload format unchanged

**WebSocket Events (Must Not Change):**
- [ ] Connection to `ws://host/ws/{taskId}` unchanged
- [ ] All 40+ event types in `WebSocketEventType` enum consumed correctly
- [ ] Event data interfaces match backend payloads
- [ ] Heartbeat/pong mechanism works
- [ ] Reconnection logic unchanged

**Workflow Behaviors (Must Not Change):**
- [ ] Task submission creates WebSocket connection and sends config
- [ ] Console output streams in real-time
- [ ] DAG visualization updates on node status changes
- [ ] Approval flow: request → dialog → resolve
- [ ] Copilot chat: message → WebSocket → agent response → chat display
- [ ] Session resume: load history → reconnect → continue
- [ ] Branch creation: POST → WebSocket event → DAG update
- [ ] Play from node: POST → status update → execution
- [ ] Cost tracking: accumulates from cost_update events
- [ ] File tracking: updates from files_updated events

**UI Flows:**
- [ ] Home page → Mode Gallery → Select mode → TaskInput → Submit → Console streams → Workflow updates
- [ ] Tasks page → Task list → Open task → Task executes → Results
- [ ] Sessions page → Session list → Select session → Detail panel → Resume/View Logs
- [ ] Console Modal → Filter → Search → Copy → Download → Clear
- [ ] Workflow Modal → DAG → Timeline → Pause/Resume → Branch
- [ ] Copilot mode → Chat → Send messages → Agent responses → Continue
- [ ] Approval → Pending → Approve/Reject → Continue

## Files to Modify

Multiple files across the entire codebase. Focus areas:
- All `components/core/` components (accessibility attributes)
- `components/layout/AppShell.tsx` (responsive behavior)
- `components/layout/SideNav.tsx` (responsive collapse)
- `components/layout/TopBar.tsx` (responsive compact mode)
- `components/modes/ModeCard.tsx` (micro-interactions)
- `app/page.tsx` (responsive grid)
- `styles/mars.css` (responsive utilities, motion)

## Verification Criteria

### Must Pass
- [ ] `npm run build` succeeds
- [ ] `npx tsc --noEmit` passes
- [ ] All WCAG 2.2 AA checks pass (axe-core or browser audit)
- [ ] All non-regression checks pass (API contracts, WebSocket events, UI flows)
- [ ] UI renders correctly at sm/md/lg/xl breakpoints
- [ ] `prefers-reduced-motion: reduce` disables all animations
- [ ] Keyboard navigation works through entire app (Tab, Enter, Esc, Arrow keys)

### Should Pass
- [ ] Console Modal performance with 1000+ log lines
- [ ] Session list performance with 100+ sessions
- [ ] Modal code-split chunks are < 50KB each
- [ ] Page load doesn't regress (Lighthouse Performance >= 90)
- [ ] All empty states have descriptive text and actions
- [ ] Visual consistency across all screens

### Nice to Have
- [ ] Lighthouse Accessibility score = 100
- [ ] Bundle size increase < 20KB gzipped vs pre-MARS baseline
- [ ] All colors pass AAA contrast ratio (7:1)

## Success Criteria

Stage 10 is complete when:
1. WCAG 2.2 AA compliance verified
2. Responsive behavior works across all breakpoints
3. Performance optimizations implemented (code-split, virtual scroll)
4. Micro-interactions are smooth and reduced-motion friendly
5. All empty states have helpful microcopy
6. Visual consistency pass complete
7. Non-regression checklist fully verified (green)
8. Build and type-check pass

## Final Deliverables Checklist

- [x] Updated IA and navigation (SideNav + TopBar) — Stage 2
- [x] Redesigned Modes gallery with industry-relevant examples — Stage 5
- [x] New Tasks screen with builder and list views — Stage 6
- [x] Sessions screen with parallel session management and progress — Stage 7, 9
- [x] Console and Workflow Execution Workspace as global modals — Stage 8
- [x] Global CSS token file with theming and utilities — Stage 1
- [x] Component library (components/core/) — Stage 4
- [x] Product name updated to MARS — Stage 3
- [x] Results tab removed — Stage 5
- [x] Multiple sessions can run in parallel with visible progress & controls — Stage 9
- [x] Accessibility (WCAG 2.2 AA), responsive behavior, and performance baselines met — Stage 10
- [x] All existing UI↔backend flows continue to function unchanged — Stage 10

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-18
