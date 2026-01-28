# AI Weekly Workflow with Human-in-the-Loop (HITL) Implementation

## Overview

This document describes the end-to-end implementation of the AI Weekly Report workflow with integrated Human-in-the-Loop (HITL) capabilities. The implementation enables users to have full control over the report generation process through interactive context enrichment, plan review, and post-execution modifications.

## Architecture

### Components

1. **Frontend UI (React/Next.js)**
   - `AIWeeklyTaskEnhanced.tsx` - Enhanced component with 3-tab interface
   - Context enrichment dialogs
   - Approval dialogs
   - Real-time console and DAG visualization

2. **Backend API (FastAPI)**
   - WebSocket handlers for real-time communication
   - Approval request/response handling
   - Task execution with HITL support

3. **CMBAgent Integration**
   - Planning and control workflow
   - Approval configuration
   - Callback system for events

## User Flow

### Step 1: Configuration
User selects:
- Date range for report
- Topics (LLM, CV, RL, Robotics, MLOps, Ethics)
- Sources (ArXiv, GitHub, Tech Blogs)
- Report style (Concise, Detailed, Technical)

### Step 2: Context Enrichment (HITL Stage 1)
System asks user 3 key questions:
1. **Focus Areas**: What specific aspects should be prioritized?
2. **Technical Depth**: Should implementation details be included?
3. **Business Context**: Should business applications be emphasized?

Additional preferences:
- Specific focus areas (optional)
- Topics to exclude (optional)
- Report audience (technical/non-technical/mixed)
- Report tone (professional/casual/academic)

### Step 3: Confirmation
User reviews the enriched context before proceeding with execution.

### Step 4: Execution with Real-time Monitoring

The execution view has two panels:

#### Left Panel (60%): Workflow Workspace
- **Task Progress Bar**: Visual progress indicator
- **Workspace Tabs**:
  - **DAG View**: Visual representation of workflow steps
  - **Console**: Live execution logs

#### Right Panel (40%): 3 Tabs
- **Console Tab**: Real-time execution logs
- **Plan Tab**: Generated execution plan with step-by-step breakdown
- **Results Tab**: Final generated report with download option

### Step 5: Plan Review (HITL Stage 2)
After planning phase, system presents:
- Generated execution plan
- Plan context and metadata
- Options to:
  - **Approve & Continue**: Proceed with execution
  - **Reject**: Stop execution and provide modifications
  - **Modify**: Provide feedback for plan adjustments

### Step 6: Execution
System executes each step of the plan with:
- Real-time progress updates
- DAG node status changes
- Console output streaming
- File tracking

### Step 7: Post-Execution Review (HITL Stage 3)
After completion, user can:
- Review the generated report
- Download the markdown file
- Request modifications
- Restart with adjusted parameters

## Technical Implementation

### Frontend Components

#### AIWeeklyTaskEnhanced.tsx
```typescript
interface ContextEnrichment {
  step: 'initial' | 'questions' | 'confirmation' | 'complete'
  questions: Array<{
    id: string
    question: string
    answer: string
  }>
  enrichedPrompt: string
}
```

Key features:
- Modal dialogs for context enrichment
- Approval request handling via WebSocket
- Three-tab interface for monitoring
- Real-time state synchronization

### Backend Integration

#### WebSocket Event Flow
```
Client -> Server: { type: 'execute', task, config }
Server -> Client: { event_type: 'workflow_started' }
Server -> Client: { event_type: 'dag_created' }
Server -> Client: { event_type: 'approval_requested' }
Client -> Server: { type: 'approval_response', approved, feedback }
Server -> Client: { event_type: 'approval_received' }
Server -> Client: { event_type: 'workflow_completed' }
```

#### Task Executor Configuration
```python
# HITL Approval Configuration
approval_config = None
approval_mode = config.get("approvalMode", "none")

if approval_mode == "after_planning":
    approval_config = ApprovalConfig(
        mode=ApprovalMode.AFTER_PLANNING
    )
```

### CMBAgent Integration

#### Approval Manager
The approval system uses:
- `ApprovalManager` - Handles approval lifecycle
- `ApprovalConfig` - Configures approval checkpoints
- `ApprovalRequest` - Database model for requests

Approval modes:
- `NONE` - Autonomous execution (default)
- `AFTER_PLANNING` - Review plan before execution
- `BEFORE_EACH_STEP` - Approve each step
- `ON_ERROR` - Approval on errors only
- `MANUAL` - User can pause anytime

#### Workflow Callbacks
```python
workflow_callbacks = WorkflowCallbacks(
    on_planning_complete=handle_plan_approval,
    on_step_complete=track_progress,
    on_agent_message=log_message,
    should_continue=check_user_approval
)
```

## File Structure

```
cmbagent/
├── cmbagent-ui/
│   ├── app/tasks/page.tsx                          # Updated to use enhanced component
│   └── components/tasks/
│       ├── AIWeeklyTask.tsx                        # Original component
│       ├── AIWeeklyTaskEnhanced.tsx                # New HITL-enabled component
│       └── TaskWorkspaceView.tsx                   # Workspace visualization
│
├── backend/
│   ├── execution/
│   │   └── task_executor.py                        # Updated with HITL support
│   ├── websocket/
│   │   └── handlers.py                             # Updated approval handlers
│   └── routers/
│       └── tasks.py                                # Task submission endpoints
│
└── cmbagent/
    ├── workflows/
    │   └── planning_control.py                     # Planning workflow with HITL
    └── database/
        ├── approval_types.py                        # Approval configuration
        └── approval_manager.py                      # Approval lifecycle management
```

## Configuration Options

### Frontend Config
```typescript
const taskConfig = {
  mode: 'planning-control',
  model: 'gpt-4o',
  plannerModel: 'gpt-4o',
  researcherModel: 'gpt-4.1-2025-04-14',
  engineerModel: 'gpt-4o',
  planReviewerModel: 'o3-mini-2025-01-31',
  defaultModel: 'gpt-4.1-2025-04-14',
  defaultFormatterModel: 'o3-mini-2025-01-31',
  maxRounds: 25,
  maxAttempts: 6,
  maxPlanSteps: 3,
  nPlanReviews: 1,
  planInstructions: 'Use researcher to gather information...',
  agent: 'planner',
  workDir: '~/cmbagent_workdir',
  // HITL Configuration
  approvalMode: 'after_planning',
  enableManualControl: true
}
```

### Backend Config
```python
# Approval configuration in task_executor.py
approval_mode = config.get("approvalMode", "none")
if approval_mode != "none":
    from cmbagent.database.approval_types import ApprovalConfig
    approval_config = ApprovalConfig(
        mode=ApprovalMode.AFTER_PLANNING,
        timeout_seconds=None,  # Wait indefinitely
        require_feedback_on_reject=True
    )
```

## Report Structure

The generated report includes:

1. **Executive Summary** - High-level overview
2. **Key Highlights** - Top 5 impactful stories
3. **Research & Innovation** - 5 significant papers from ArXiv
4. **Product Launches & Tools** - 5 major releases
5. **Technical Breakthroughs** - 5 items per topic category
6. **Industry & Business News** - 5 major developments
7. **Trends & Strategic Implications** - Key insights
8. **Quick Reference Table** - All items in tabular format

Each section includes:
- Comprehensive summaries (3-4 sentences)
- Working source links (no placeholders)
- Publication dates
- Business and technical context
- Impact analysis

## Error Handling

### Approval Timeout
- Configurable timeout (default: no timeout)
- Default action on timeout (approve/reject/skip)

### Connection Loss
- Approval state persisted in database
- Can resume after reconnection
- Event queue ensures no lost messages

### Execution Errors
- Error-specific approval requests
- Retry strategies presented to user
- Option to skip failed steps

## Testing

### Manual Testing Steps
1. Navigate to `/tasks` page
2. Select "AI Weekly Report"
3. Configure date range, topics, sources
4. Click "Generate Weekly Report"
5. Answer context enrichment questions
6. Review and confirm enriched context
7. Approve or modify the generated plan
8. Monitor execution in real-time
9. Review and download final report

### Automated Testing
```bash
# Run frontend tests
cd cmbagent-ui
npm test

# Run backend tests
cd backend
pytest tests/test_hitl_workflow.py
```

## Performance Considerations

- **WebSocket Connection**: Maintains single connection throughout workflow
- **Event Queue**: Buffers events during disconnection
- **Database Persistence**: All approval states saved
- **Async Execution**: Non-blocking approval requests
- **Stream Capture**: Real-time output without buffering

## Security

- Approval requests tied to authenticated sessions
- User feedback sanitized before storage
- Work directory isolated per task
- API keys secured in environment

## Future Enhancements

1. **Multi-user Collaboration**: Multiple reviewers for approvals
2. **Approval Templates**: Pre-configured approval workflows
3. **Version Control**: Track plan modifications over time
4. **Approval Analytics**: Metrics on approval patterns
5. **AI-Assisted Decisions**: Suggest approval/rejection based on context
6. **Approval Escalation**: Auto-escalate to senior reviewers
7. **Audit Trail**: Complete history of all approvals

## Troubleshooting

### Issue: Approval dialog not appearing
- Check WebSocket connection status
- Verify `approvalMode` is set in config
- Check browser console for errors
- Verify database connection

### Issue: Plan not showing in Plan tab
- Wait for planning phase to complete
- Check DAG data is being received
- Verify `dagData.nodes` is populated

### Issue: Report not generated
- Check console output for errors
- Verify work directory permissions
- Check API keys are configured
- Verify file tracking in backend

## References

- [CMBAgent Documentation](./README.md)
- [WebSocket Protocol](./playground/docs/WEBSOCKET_PROTOCOL.md)
- [State Machine Design](./playground/docs/STATE_MACHINE.md)
- [Approval System](./cmbagent/database/approval_types.py)
- [Denario Integration](../denario/README.md)

## Support

For issues or questions:
1. Check this documentation
2. Review console logs
3. Check WebSocket events in browser DevTools
4. Review backend logs
5. Create an issue with reproduction steps
