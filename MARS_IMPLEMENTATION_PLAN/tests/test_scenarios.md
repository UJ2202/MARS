# Test Scenarios

Verification guide for each stage and end-to-end testing of the MARS UI overhaul.

## Stage 1: Global CSS & Design Tokens

### Build Tests
- [ ] `npm run build` succeeds
- [ ] `npx tsc --noEmit` passes

### Manual Tests
1. Open app in browser — UI should look identical to pre-MARS state (dark theme default)
2. Inspect `<html>` element — `data-theme="dark"` should be present
3. Open DevTools → Elements → check `:root` for `--mars-*` custom properties
4. Verify `--mars-color-primary` resolves to `#3B82F6`
5. Test Tailwind class `bg-mars-primary` in a temporary element — should show blue
6. Reload page — theme should persist via localStorage

---

## Stage 2: AppShell Layout

### Build Tests
- [ ] `npm run build` succeeds
- [ ] `npx tsc --noEmit` passes

### Manual Tests
1. Open `/` — AppShell renders with TopBar (56px height) and SideNav (240px width)
2. SideNav shows: Modes (active), Tasks, Sessions
3. Click "Tasks" in SideNav — navigates to `/tasks`, SideNav highlights Tasks
4. Click "Sessions" — navigates to `/sessions`, SideNav highlights Sessions
5. Click "Modes" — navigates to `/`, SideNav highlights Modes
6. Click SideNav collapse button — SideNav shrinks to 64px, only icons visible
7. Click expand — SideNav returns to 240px
8. Verify TopBar shows "MARS" logo and action icons
9. Verify no duplicate Header or TopNavigation components render
10. Tab through SideNav items with keyboard — all items reachable

---

## Stage 3: Branding & Renaming

### Build Tests
- [ ] `npm run build` succeeds

### Manual Tests
1. Browser tab shows "MARS" title
2. Favicon shows "M" icon
3. No visible instance of "CMBAGENT" anywhere in the UI
4. TopBar logo reads "MARS"
5. Search source code: `grep -r "CMBAGENT" --include="*.tsx" app/ components/` returns only technical identifiers (env vars, not UI text)

---

## Stage 4: Core Component Library

### Build Tests
- [ ] `npm run build` succeeds
- [ ] `npx tsc --noEmit` passes
- [ ] `import { Button, Modal, Toast, ... } from '@/components/core'` compiles

### Manual Tests (create a test page or use Storybook)
1. **Button:** All variants (primary, secondary, ghost, danger) render with correct colors
2. **Button:** Loading state shows spinner and disables interaction
3. **Modal:** Opens centered with backdrop overlay
4. **Modal:** Esc closes modal
5. **Modal:** Tab key cycles within modal (focus trap)
6. **Modal:** Clicking backdrop closes modal
7. **Modal:** Draggable by header
8. **Toast:** Appears at top-right, auto-dismisses after 5s
9. **Toast:** Action button fires callback
10. **Tabs:** Arrow keys navigate between tabs
11. **Badge:** All variants (success, warning, danger, info) show correct colors
12. **EmptyState:** Renders icon, title, description, and action button
13. **ProgressIndicator:** Bar variant shows correct width for value
14. **Skeleton:** Pulsing animation visible
15. **Dropdown:** Opens on trigger click, closes on Esc

---

## Stage 5: Modes Gallery Redesign

### Build Tests
- [ ] `npm run build` succeeds

### Manual Tests
1. Default view at `/` shows ModeGallery with 8 ModeCards
2. Cards show: icon, display name, description, tags, Launch button
3. Search "analysis" — filters to relevant modes
4. Search "xyz" — shows empty state "No modes match..."
5. Click "Launch" on a card — transitions to run view with mode pre-selected
6. Verify TaskInput shows the selected mode
7. Click "Back to Modes" — returns to gallery
8. Submit a task — console output streams correctly
9. Workflow tab shows DAG visualization
10. Results tab is NOT present in the tab bar
11. Sessions tab is NOT present in the tab bar (moved to /sessions)
12. Copilot mode still works (select Copilot Chat → chat interface)

### Backend Verification
- [ ] WebSocket message sends original mode ID (e.g., `one-shot`, not `Single-Pass Analysis`)
- [ ] Task completes successfully with backend

---

## Stage 6: Tasks Dedicated Screen

### Build Tests
- [ ] `npm run build` succeeds

### Manual Tests
1. Navigate to `/tasks` via SideNav
2. TaskList shows three tasks: AI Weekly Report, Release Notes, Code Review
3. Click "AI Weekly Report" — opens AIWeeklyTaskEnhanced component
4. Back button returns to task list
5. Repeat for Release Notes and Code Review
6. Verify all three task workflows function correctly
7. Filters (if implemented) show/hide tasks

---

## Stage 7: Sessions Screen

### Build Tests
- [ ] `npm run build` succeeds

### Manual Tests
1. Navigate to `/sessions` via SideNav
2. Session list loads from `GET /api/sessions`
3. Sessions are grouped by status (Active, Completed, Failed, etc.)
4. Click a session — detail panel opens on the right
5. Detail panel shows tabs: Overview, DAG, Console, Events, Costs, Config
6. "Resume" action on an active session works
7. "View Logs" action loads session history
8. Empty state shows when no sessions exist
9. Sessions tab is no longer in the home page right panel

---

## Stage 8: Console & Workflow Modals

### Build Tests
- [ ] `npm run build` succeeds

### Manual Tests
1. Click Console icon in TopBar — ConsoleModal opens
2. ConsoleModal shows current consoleOutput
3. Filter by level (Info/Warning/Error) works
4. Search filter works
5. Copy button copies text to clipboard
6. Download button downloads .txt file
7. Clear button clears console (UI only)
8. Auto-scroll toggle works
9. Close modal with Esc — focus returns to TopBar icon
10. Click Workflow icon in TopBar — WorkflowModal opens
11. WorkflowModal shows DAG visualization (if data exists)
12. Modal is draggable by header
13. Modal is resizable from edges
14. Both modals work from `/tasks` and `/sessions` pages
15. Background app is still interactive when modal is open
16. Start a workflow — console updates in real-time inside the modal

---

## Stage 9: Parallel Sessions & Progress UX

### Build Tests
- [ ] `npm run build` succeeds

### Manual Tests
1. Start a workflow — session pill appears in TopBar
2. Pill shows status dot and session name
3. Start a second workflow (if backend supports) — second pill appears
4. Click a pill — switches active session context
5. Toast notification appears when session status changes
6. Toast for failed session includes "Open Console" action
7. Pin a session — pinned session stays at left of pill bar
8. Rename a session via pill dropdown

---

## Stage 10: Accessibility, Responsiveness, Performance & Polish

### Accessibility Tests
1. Run browser audit: DevTools → Lighthouse → Accessibility → score >= 90
2. Install axe DevTools extension → run full page scan → 0 critical issues
3. Tab through entire app: TopBar → SideNav → Content → no traps
4. Verify all icon-only buttons have aria-label
5. Verify modals have role="dialog" and aria-modal="true"
6. Enable "Reduce Motion" in OS settings → verify no animations play
7. Use screen reader (NVDA/VoiceOver) → verify all content is announced

### Responsive Tests
1. Resize to 640px width (sm) — SideNav hidden, hamburger shows
2. Resize to 960px (md) — SideNav collapsed, grid adjusts
3. Resize to 1280px (lg) — SideNav expanded, 3-column grid
4. Resize to 1536px (xl) — Full layout, 4-column grid
5. Modal on sm — opens as full-screen sheet
6. Test on actual mobile device (if available)

### Performance Tests
1. Run `npm run build` — note bundle sizes
2. Compare total JS bundle to pre-MARS baseline
3. Open Network tab → hard refresh → verify no unnecessary requests
4. Load sessions page with 100+ sessions → verify smooth scrolling
5. Open console modal with 1000+ lines → verify no lag
6. Verify modals are lazy-loaded (check network tab for chunked loading)

---

## Stage 11: Console Logs Overhaul

### Build Tests
- [ ] `npm run build` succeeds
- [ ] `npx tsc --noEmit` passes
- [ ] `import { ConsoleLogViewer, ConsoleEntry, PhaseIndicator } from '@/components/console'` compiles

### Structured Log Entry Tests
1. Start a workflow — console entries render as structured cards, not raw text lines
2. Each entry shows: level icon (Lucide), timestamp, agent badge, message
3. Error entries have red-tinted background and XCircle icon
4. Warning entries have amber-tinted background and AlertTriangle icon
5. Success entries have green-tinted background and CheckCircle icon
6. Info entries have blue-tinted background and Info icon
7. No emoji characters visible anywhere in console output

### Phase Indicator Tests
1. Start a workflow — phase indicators appear between log groups (e.g., "Planning", "Researching", "Executing")
2. Active phase shows animated Lucide icon (pulsing or spinning)
3. Completed phases show static icon with checkmark
4. Phase transitions animate smoothly (fade/slide)
5. Phase indicators respect `prefers-reduced-motion` (no animation when enabled)

### Filter & Search Tests
1. Click level filter chips — only entries of selected level(s) show
2. Agent dropdown filters entries by specific agent
3. Search input filters entries by message text
4. Clear filters restores all entries
5. Filter state persists while console is open

### Expandable Details Tests
1. Log entries with details (tool calls, code blocks) show expand chevron
2. Click expand — reveals formatted details (syntax-highlighted code, JSON tree)
3. Click collapse — hides details
4. Multiple entries can be expanded simultaneously

### Backward Compatibility Tests
1. WebSocket events still flow correctly — no dropped events
2. All 40+ event types render as structured entries
3. Session history loads and renders correctly in structured format
4. Console modal shows the same structured entries
5. Copy button exports readable text (not JSON objects)
6. Download button creates a well-formatted .txt or .log file

### Performance Tests
1. Console with 500+ entries — renders smoothly (virtual scrolling active)
2. Auto-scroll follows new entries without jank
3. Rapid event streams (10+ events/second) render without visual lag

---

## Stage 12: File Viewer Overhaul

### Build Tests
- [ ] `npm run build` succeeds
- [ ] `npx tsc --noEmit` passes
- [ ] `import { FilePreview, CodeViewer, MarkdownRenderer } from '@/components/files'` compiles

### PDF Preview Tests
1. Select a .pdf file in DAGFilesView — renders inline via iframe
2. PDF is scrollable and zoomable within the viewer
3. If browser doesn't support inline PDF — fallback shows download button
4. PDF viewer has proper MARS-styled container (border, radius)

### Image Preview Tests
1. Select a .png file — renders inline with proper sizing
2. Select a .jpg file — renders inline
3. Select a .svg file — renders inline
4. Images use MARS-styled container (border, radius, max-width)

### Markdown Preview Tests
1. Select a .md file — renders with formatted HTML
2. Headers (#, ##, ###) render with correct sizes and MARS typography
3. Bold, italic, inline code render correctly
4. Code blocks render with syntax highlighting
5. Lists (ordered and unordered) render correctly
6. Tables render with MARS-styled borders and spacing
7. Blockquotes render with left border accent
8. Links are clickable
9. No XSS — script tags and event handlers are sanitized

### CSV Preview Tests
1. Select a .csv file — renders as a formatted data table
2. First row is used as column headers
3. Columns are sortable (click header)
4. Quoted fields with commas parse correctly
5. Large CSV (>100 rows) shows "Showing first 100 of N rows"
6. Cell content is truncated with tooltip for full text

### Code Preview Tests
1. Select a .py file — renders with Python syntax highlighting
2. Select a .js/.ts file — renders with JavaScript/TypeScript highlighting
3. Select a .json file — renders with JSON highlighting
4. Select a .yaml file — renders with YAML highlighting
5. Line numbers are visible
6. Copy button copies file content to clipboard
7. File name and language badge visible in header
8. Large files (>500 lines) show truncation warning

### Binary/Fallback Tests
1. Select a .docx file — shows file info card with size and download button
2. Select an unknown binary file — shows generic file info with download
3. Download button triggers file download

### Integration Tests (DAGFilesView)
1. DAGFilesView renders file list with Lucide file type icons (no emojis)
2. Click a file — FilePreview component renders appropriate viewer
3. File type filter dropdown works for all supported types
4. Search filter works across file names
5. All hardcoded `bg-gray-900`/`border-gray-700` replaced with MARS tokens

### Integration Tests (FileBrowser)
1. FileBrowser directory listing uses Lucide icons for all file types
2. Click a text file — CodeViewer renders with syntax highlighting
3. Click an image — ImageViewer renders inline
4. Click a PDF — PDFViewer renders inline (or download fallback)
5. All hardcoded colors replaced with MARS tokens

---

## End-to-End Full Flow Tests

### Flow 1: Complete Task Execution
1. Open app → Modes gallery displayed
2. Click "Single-Pass Analysis" → run view opens
3. Enter task description → Click Start
4. Console output streams in real-time as structured log entries with phase indicators
5. Open ConsoleModal from TopBar → same structured output visible
6. Switch to Workflow tab → DAG renders
7. Open WorkflowModal from TopBar → same DAG visible
8. Task completes → results available; files render with FilePreview (PDF, images, code)
9. Navigate to Sessions → completed session visible
10. Click session → detail panel shows overview, DAG, costs, files with inline preview

### Flow 2: Copilot Mode
1. Select "Copilot Chat" mode
2. Chat interface opens
3. Type message → send
4. Agent response appears in chat
5. Send follow-up message → conversation continues
6. Console modal shows execution logs

### Flow 3: Human-in-the-Loop
1. Select "Human-in-the-Loop" mode
2. Submit task
3. Approval request appears
4. Approve/reject → execution continues
5. Verify approval response sent via WebSocket

### Flow 4: Session Resume
1. Navigate to Sessions page
2. Click an active/suspended session
3. Click Resume
4. Execution resumes via WebSocket
5. Console updates with new output

### Flow 5: Branch Creation
1. Run a planning-control workflow
2. Open Workflow modal
3. Right-click a completed node → "Create Branch"
4. Enter branch name and hypothesis
5. Branch created via POST /api/runs/{id}/branch
6. Branch appears in DAG

---

## Non-Regression Verification

### API Contract Verification
```bash
# Start a task and capture WebSocket messages
# Verify these match pre-MARS format:

# 1. Initial WebSocket message format
# 2. Pause/Resume message format
# 3. Approval resolution format

# Verify REST calls:
# 1. GET /api/sessions returns expected format
# 2. GET /api/sessions/{id} returns expected format
# 3. POST /api/sessions/{id}/resume works
# 4. POST /api/runs/{id}/branch works
# 5. POST /api/runs/{id}/play-from-node works
```

### Quick Smoke Test Checklist
- [ ] Task submission works
- [ ] Console output streams
- [ ] DAG visualization renders
- [ ] Approval flow works
- [ ] Session list loads
- [ ] Session resume works
- [ ] Copilot chat works
- [ ] Cost tracking updates
- [ ] File tracking updates
- [ ] Branch creation works
- [ ] Play from node works

---

**Last Updated:** 2026-02-18
