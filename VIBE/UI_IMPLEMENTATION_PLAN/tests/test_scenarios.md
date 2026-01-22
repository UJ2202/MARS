# UI Test Scenarios

This document outlines test scenarios for each stage of the UI implementation.

---

## Stage 1: WebSocket Enhancement

### Unit Tests
- [ ] TypeScript types compile without errors
- [ ] Event handler routes all event types correctly
- [ ] Legacy event types still work
- [ ] WebSocket context provides all expected values

### Integration Tests
- [ ] WebSocket connects to backend
- [ ] Events received and handled correctly
- [ ] Connection status updates in UI
- [ ] Auto-reconnection triggers on disconnect
- [ ] Exponential backoff works correctly
- [ ] Missed events delivered after reconnection

### Manual Tests
1. Start backend, start UI, verify connection
2. Kill backend, verify reconnection attempts
3. Restart backend, verify reconnection
4. Submit task, verify events in console

---

## Stage 2: DAG Visualization

### Unit Tests
- [ ] DAG layout calculation correct
- [ ] Node positions calculated properly
- [ ] Edge connections valid
- [ ] Node component renders correctly

### Integration Tests
- [ ] DAG renders from backend data
- [ ] Node status updates in real-time
- [ ] Node selection shows details
- [ ] Layout toggle works

### Manual Tests
1. Start workflow, verify DAG appears
2. Watch nodes change status (pending → running → completed)
3. Click nodes, verify details panel
4. Test zoom, pan, fit view
5. Toggle vertical/horizontal layout
6. Check MiniMap functionality

---

## Stage 3: Workflow Dashboard

### Unit Tests
- [ ] StatusBadge shows correct colors
- [ ] ProgressBar calculates width correctly
- [ ] WorkflowControls shows correct buttons per state

### Integration Tests
- [ ] State bar updates from WebSocket events
- [ ] Controls trigger correct actions
- [ ] Timeline populates with steps
- [ ] Tabs switch correctly

### Manual Tests
1. Start workflow, verify state bar shows "Executing"
2. Check progress bar updates
3. Click Pause, verify state changes
4. Click Resume, verify workflow continues
5. Check timeline shows all steps
6. Test Cancel with confirmation

---

## Stage 4: HITL Approval

### Unit Tests
- [ ] ApprovalDialog renders all sections
- [ ] Action selection works
- [ ] Feedback input captures text
- [ ] Timeout countdown works

### Integration Tests
- [ ] Dialog appears on APPROVAL_REQUESTED event
- [ ] Submit sends correct response
- [ ] Workflow resumes after approval
- [ ] Queue shows multiple approvals

### Manual Tests
1. Configure workflow to require approval
2. Start workflow, wait for approval dialog
3. Test each action option
4. Test with feedback text
5. Test Cancel button
6. Test timeout behavior

---

## Stage 5: Retry UI

### Unit Tests
- [ ] RetryStatus displays attempt count
- [ ] Backoff countdown decrements
- [ ] Suggestions render correctly

### Integration Tests
- [ ] Retry events update UI
- [ ] Backoff timer syncs with backend
- [ ] User context submission works

### Manual Tests
1. Create workflow that will fail
2. Verify retry UI appears
3. Watch attempt counter increment
4. Check suggestions displayed
5. Test manual retry button
6. Test user context input

---

## Stage 6: Branching UI

### Unit Tests
- [ ] BranchTree renders hierarchy
- [ ] Expand/collapse works
- [ ] Comparison calculates differences

### Integration Tests
- [ ] Branch tree loads from API
- [ ] Create branch works
- [ ] Comparison loads correctly

### Manual Tests
1. Complete a workflow
2. Create branch from completed step
3. Verify branch appears in tree
4. Run new branch
5. Compare two branches
6. Switch between branches

---

## Stage 7: Table Views

### Unit Tests
- [ ] DataTable sorts correctly
- [ ] Search filters results
- [ ] Pagination calculates correctly

### Integration Tests
- [ ] Tables load from API
- [ ] Actions trigger correctly
- [ ] Empty state displays

### Manual Tests
1. Load session table with multiple sessions
2. Test sorting each column
3. Test search filtering
4. Test pagination navigation
5. Test row actions (view, delete)
6. Test empty state

---

## Stage 8: Cost Dashboard

### Unit Tests
- [ ] Summary cards calculate correctly
- [ ] Breakdown percentages correct
- [ ] Chart renders data points

### Integration Tests
- [ ] Cost updates from WebSocket
- [ ] Breakdown tabs switch
- [ ] Budget warnings appear

### Manual Tests
1. Start workflow
2. Watch cost update in real-time
3. Check model breakdown accurate
4. Check agent breakdown accurate
5. Check step breakdown accurate
6. Test budget threshold warning

---

## Stage 9: Metrics UI

### Unit Tests
- [ ] MetricsPanel renders all sections
- [ ] Health indicators show correct status
- [ ] Progress rings calculate correctly

### Integration Tests
- [ ] Metrics update from WebSocket
- [ ] Health status reflects actual state
- [ ] Timeline populates correctly

### Manual Tests
1. Start workflow
2. Watch metrics update
3. Check health indicators
4. Check resource usage
5. View execution timeline
6. Test with degraded backend (simulate errors)

---

## End-to-End Tests

### Full Workflow Test
1. Start fresh (clear all data)
2. Submit task
3. Watch DAG render
4. Monitor console output
5. Handle approval if configured
6. Handle retry if errors occur
7. View final results
8. Check cost breakdown
9. Create branch
10. Run branch
11. Compare branches

### Connection Resilience Test
1. Start workflow
2. Kill backend mid-execution
3. Verify UI shows disconnected
4. Verify reconnection attempts
5. Restart backend
6. Verify state syncs
7. Verify workflow can resume

### Long-Running Workflow Test
1. Start long workflow (10+ steps)
2. Leave running for several minutes
3. Verify no memory leaks (check browser memory)
4. Verify UI stays responsive
5. Verify all steps tracked
6. Verify cost accumulates correctly

---

## Browser Compatibility

Test all features in:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

## Responsive Design

Test all features at:
- [ ] Desktop (1920x1080)
- [ ] Laptop (1366x768)
- [ ] Tablet landscape (1024x768)
- [ ] Tablet portrait (768x1024)
- [ ] Mobile (375x667)

---

**Last Updated:** 2026-01-16
