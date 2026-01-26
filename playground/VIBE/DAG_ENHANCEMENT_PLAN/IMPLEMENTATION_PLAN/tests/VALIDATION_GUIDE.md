# CMBAgent Stages 1-9 Validation Guide

## Overview

This guide helps you validate all functionality implemented in Stages 1-9 before proceeding to Stages 10-15.

**What's Been Implemented:**
- ✓ Stage 1: AG2 Upgrade
- ✓ Stage 2: Database Schema
- ✓ Stage 3: State Machine
- ✓ Stage 4: DAG Builder
- ✓ Stage 5: WebSocket Protocol
- ✓ Stage 6: HITL Approval System
- ✓ Stage 7: Retry Mechanism
- ✓ Stage 8: Parallel Execution
- ✓ Stage 9: Branching

## Quick Validation (5 minutes)

Run the research validation suite with short, realistic tasks:

```bash
cd /srv/projects/mas/mars/denario/cmbagent

# Ensure environment is ready
export OPENAI_API_KEY="your-key-here"
export CMBAGENT_USE_DATABASE=true

# Run research validation
python IMPLEMENTATION_PLAN/tests/research_validation.py
```

**What This Tests:**
- ✓ One-shot mode with simple calculations
- ✓ Plot generation (matplotlib integration)
- ✓ Multi-step workflows
- ✓ Scientific calculations
- ✓ File operations
- ✓ Error handling and recovery
- ✓ Database integration
- ✓ State tracking

**Expected Results:**
- 9-11 tests total
- All tests should pass
- Outputs created in `~/.cmbagent/validation/run_*/`
- Duration: 3-5 minutes depending on API speed

## Comprehensive Validation (15 minutes)

Run the full validation suite testing all components:

```bash
python IMPLEMENTATION_PLAN/tests/comprehensive_validation.py
```

**What This Tests:**
- ✓ All execution modes (one-shot, planning, control)
- ✓ Parallel execution with dependencies
- ✓ Branching and play-from-node
- ✓ HITL approval workflows
- ✓ Retry mechanisms with error analysis
- ✓ Database lifecycle and state history
- ✓ DAG visualization
- ✓ WebSocket events
- ✓ End-to-end integration

**Expected Results:**
- 25+ tests total
- All tests should pass
- Comprehensive component validation

## Mode-Specific Testing

### Test Mode 1: One-Shot Execution

Simple autonomous execution without planning:

```bash
cmbagent run --task "Generate a sine wave plot" --agent engineer --model gpt-4o-mini
```

**What to verify:**
- Task completes successfully
- Plot created in `data/` directory
- Database record created
- State transitions tracked

### Test Mode 2: Planning Mode (with review)

Multi-step workflow with planning:

```bash
# This would require HITL approval if enabled
cmbagent run --task "Create data pipeline: generate, analyze, plot" \
    --agent engineer \
    --model gpt-4o-mini \
    --max-round 15
```

**What to verify:**
- Multi-step execution
- Steps tracked in database
- DAG structure created
- Results in organized directories

### Test Mode 3: Parallel Execution

Tasks with independent steps:

```python
from cmbagent import one_shot
from cmbagent.execution.config import ExecutionConfig, ExecutionMode

config = ExecutionConfig(mode=ExecutionMode.PARALLEL, max_workers=4)

result = one_shot(
    task="Create 3 independent plots: sine, cosine, and tangent waves",
    agent='engineer',
    model='gpt-4o-mini',
    execution_config=config
)
```

**What to verify:**
- Parallel execution detected
- Multiple plots created
- Faster than sequential
- Resource management working

### Test Mode 4: Branching

Create experimental branches:

```bash
# Create a branch from an existing workflow
cmbagent branch <workflow_id> --name "alternative_analysis" \
    --hypothesis "Testing different parameters" \
    --step 3

# Play from a specific node
cmbagent play-from <workflow_id> --node 2 --modifications '{"param": "value"}'

# Compare branches
cmbagent compare <workflow_id_1> <workflow_id_2>
```

**What to verify:**
- Branch created with metadata
- Hypothesis tracked
- Modifications applied
- Comparison shows differences

### Test Mode 5: HITL Approval

Run with approval checkpoints:

```python
from cmbagent import CMBAgent
from cmbagent.hitl.approval import ApprovalMode

agent = CMBAgent(
    task="Multi-step analysis task",
    agent='engineer',
    model='gpt-4o-mini',
    approval_mode=ApprovalMode.AFTER_PLANNING  # Request approval after planning
)

# Workflow will pause for approval
# Check WebSocket events for approval_requested
```

**What to verify:**
- Workflow pauses at checkpoint
- Approval request created in database
- WebSocket event emitted
- Can approve/reject via API

### Test Mode 6: Retry with Context

Test error recovery:

```python
# Force an error scenario (simulate)
result = one_shot(
    task="Use a non-existent library to analyze data",
    agent='engineer',
    model='gpt-4o-mini',
    max_round=10
)

# Should automatically retry with context
```

**What to verify:**
- Error detected and analyzed
- Retry context created
- Suggestions generated
- Retry attempts tracked

## Validation Checklist

Before proceeding to Stages 10-15, verify:

### Database & Persistence
- [ ] SQLite database exists at `~/.cmbagent/cmbagent.db`
- [ ] All 13+ tables created (sessions, workflows, steps, DAG, approvals, etc.)
- [ ] State transitions recorded in state_history
- [ ] Workflow runs tracked with timestamps
- [ ] Branching metadata stored correctly

### State Management
- [ ] State machine validates transitions
- [ ] Invalid transitions are blocked
- [ ] Terminal states (completed, failed, cancelled) enforced
- [ ] Pause/resume functionality works
- [ ] State history audit trail complete

### DAG System
- [ ] DAG built from plan JSON
- [ ] Topological sort produces correct order
- [ ] Cycle detection works
- [ ] Parallel execution levels identified
- [ ] DAG exports (JSON, Mermaid, DOT) generate correctly

### WebSocket Protocol
- [ ] Event types properly defined
- [ ] Events serialized correctly
- [ ] Event queue retains messages
- [ ] Reconnection handling works
- [ ] Heartbeat keeps connection alive

### HITL Approval
- [ ] Approval modes configurable
- [ ] Approval requests created
- [ ] Workflow pauses on approval
- [ ] User feedback captured
- [ ] Approval history tracked

### Retry Mechanism
- [ ] Error patterns recognized (12 categories)
- [ ] Retry context includes history
- [ ] Suggestions generated appropriately
- [ ] Backoff strategies applied
- [ ] Metrics tracked

### Parallel Execution
- [ ] Dependency graph built correctly
- [ ] Independent tasks identified
- [ ] Parallel executor creates workers
- [ ] Work directories isolated
- [ ] Resource management active
- [ ] Results merged correctly

### Branching
- [ ] Branches created from workflows
- [ ] Hypothesis tracked
- [ ] Context modifications applied
- [ ] Play-from-node restores state
- [ ] Branch comparison works
- [ ] Branch tree visualization generated

### Integration
- [ ] One-shot mode works end-to-end
- [ ] Database records created for workflows
- [ ] File outputs organized correctly
- [ ] Error handling graceful
- [ ] Backward compatibility maintained

## Common Issues & Solutions

### Issue: Database Locked

**Symptom:** `database is locked` error

**Solution:**
```bash
# Close all Python processes
pkill -f python

# Or remove and recreate
rm ~/.cmbagent/cmbagent.db
alembic upgrade head
```

### Issue: Import Errors

**Symptom:** `ModuleNotFoundError`

**Solution:**
```bash
pip install -e . --force-reinstall
```

### Issue: API Key Not Found

**Symptom:** API authentication errors

**Solution:**
```bash
# Check .env file
cat .env

# Or set in environment
export OPENAI_API_KEY="sk-..."
```

### Issue: Alembic Migration Failed

**Symptom:** Migration errors

**Solution:**
```bash
# Check migration status
alembic current

# Upgrade to latest
alembic upgrade head

# If issues persist, reset
rm ~/.cmbagent/cmbagent.db
alembic upgrade head
```

### Issue: Tests Fail

**Symptom:** Some validation tests fail

**Solution:**
```bash
# Run with verbose output
python research_validation.py --verbose

# Check database state
sqlite3 ~/.cmbagent/cmbagent.db
> .tables
> SELECT * FROM workflow_runs ORDER BY created_at DESC LIMIT 5;
```

## Manual Verification

### 1. Database Inspection

```bash
sqlite3 ~/.cmbagent/cmbagent.db

-- Check sessions
SELECT count(*) FROM sessions;

-- Check workflows
SELECT workflow_id, task, state, workflow_type FROM workflow_runs
ORDER BY created_at DESC LIMIT 5;

-- Check state transitions
SELECT * FROM state_history ORDER BY created_at DESC LIMIT 10;

-- Check branches
SELECT workflow_id, branch_name, hypothesis, is_branch
FROM workflow_runs WHERE is_branch = 1;

.quit
```

### 2. File Outputs

```bash
# List validation runs
ls -la ~/.cmbagent/validation/

# Check outputs from a run
ls -R ~/.cmbagent/validation/run_*/

# View plots
ls ~/.cmbagent/validation/run_*/oneshot_generateplot/data/*.png
```

### 3. Python Imports

```python
# Test all new imports
import autogen
from cmbagent import CMBAgent, one_shot
from cmbagent.database import init_db, get_session
from cmbagent.database.models import *
from cmbagent.database.repository import *
from cmbagent.state_machine.states import WorkflowState, StepState
from cmbagent.dag.builder import DAGBuilder
from cmbagent.dag.executor import DAGExecutor
from cmbagent.websocket.events import EventType, WebSocketEvent
from cmbagent.hitl.approval import ApprovalMode, ApprovalManager
from cmbagent.retry.analyzer import ErrorAnalyzer
from cmbagent.retry.manager import RetryContextManager
from cmbagent.execution.config import ExecutionConfig, ExecutionMode
from cmbagent.execution.executor import ParallelExecutor
from cmbagent.branching.manager import BranchManager
from cmbagent.branching.comparator import BranchComparator

print("✓ All imports successful")
```

## Performance Benchmarks

Expected performance for validation:

| Test Type | Expected Duration | Notes |
|-----------|------------------|-------|
| Research validation | 3-5 minutes | 9-11 tests with API calls |
| Comprehensive validation | 10-15 minutes | 25+ tests, full coverage |
| One-shot simple task | 10-30 seconds | Single API call |
| One-shot with plot | 20-60 seconds | Multiple API calls |
| Complex workflow | 1-3 minutes | 10+ rounds |
| Parallel execution | 50-70% faster | Vs sequential |

## Next Steps

Once validation passes:

1. ✓ Review all test results
2. ✓ Verify database contains expected records
3. ✓ Check file outputs are organized
4. ✓ Confirm no errors in logs
5. ✓ Document any issues found
6. → Proceed to Stage 10 (MCP Server Interface)

## Reporting Issues

If you encounter problems:

1. Check stage summaries in `IMPLEMENTATION_PLAN/STAGE_*_SUMMARY.md`
2. Review test files in `tests/test_stage_*.py`
3. Inspect database with sqlite3
4. Check logs in work directories
5. Verify environment variables

## Support Files

- **Research Validation:** `research_validation.py` - Quick realistic tests
- **Comprehensive Validation:** `comprehensive_validation.py` - Full component tests
- **Stage Summaries:** `../STAGE_*_SUMMARY.md` - Implementation details
- **Test Files:** `../../tests/test_stage_*.py` - Original verification tests

---

**Validation Guide Version:** 1.0
**Last Updated:** 2026-01-15
**Stages Validated:** 1-9
**Status:** Ready for validation
