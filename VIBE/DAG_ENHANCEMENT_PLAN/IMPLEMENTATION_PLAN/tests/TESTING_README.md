# CMBAgent Stages 1-9 Testing Guide

## Overview

This guide provides comprehensive instructions for testing all functionality implemented in Stages 1-9 of the CMBAgent enhancement project.

**Implementation Status:** Stages 1-9 Complete (60% of total project)

## Quick Start

```bash
# 1. Ensure you're in the project directory
cd /srv/projects/mas/mars/denario/cmbagent

# 2. Verify environment variables are set
cat .env  # Check API keys are present

# 3. Run all tests
python test_all_stages.py

# 4. Or run specific stage tests
python test_all_stages.py --stage 1-2
python test_all_stages.py --stage 3-4
python test_all_stages.py --stage 5
python test_all_stages.py --stage 6
python test_all_stages.py --stage 7
python test_all_stages.py --stage 8
python test_all_stages.py --stage 9
```

## What's Implemented

### Stage 1: AG2 Upgrade ✓
- Migrated from custom fork `cmbagent_autogen` to official `ag2` v0.10.3
- Created local `cmbagent_utils.py` module
- All imports working correctly
- **Test Coverage:** AG2 version verification, import tests, utilities validation

### Stage 2: Database Schema and Models ✓
- SQLAlchemy models for 13 entities
- Alembic migrations for schema management
- Repository layer with session isolation
- Dual-persistence (database + pickle files)
- **Test Coverage:** Database initialization, CRUD operations, session isolation, dual-write persistence

### Stage 3: State Machine Implementation ✓
- Workflow and step state enumerations (8 states each)
- State transition rules with validation
- State history tracking for audit trails
- Pause/resume/cancel workflow control
- **Test Coverage:** State transitions, history tracking, workflow controller

### Stage 4: DAG Builder and Storage System ✓
- DAG construction from planning output
- Topological sorting (Kahn's algorithm)
- Cycle detection
- Parallel execution levels
- DAG visualization (JSON, Mermaid, DOT formats)
- **Test Coverage:** DAG building, topological sort, cycle detection, visualization

### Stage 5: Enhanced WebSocket Protocol ✓
- Structured event protocol (20+ event types)
- Thread-safe event queue with retention
- Stateless WebSocket manager
- Auto-reconnecting UI hook with exponential backoff
- Real-time state and DAG updates
- **Test Coverage:** Event types, event queue, serialization, emission

### Stage 6: Human-in-the-Loop (HITL) Approval System ✓
- 6 approval modes (NONE, AFTER_PLANNING, BEFORE_EACH_STEP, ON_ERROR, MANUAL, CUSTOM)
- Approval request management
- Workflow pause/resume on approvals
- User feedback injection
- Approval history tracking
- **Test Coverage:** Approval modes, request creation, resolution, feedback injection

### Stage 7: Context-Aware Retry Mechanism ✓
- Error pattern analyzer (12 error categories)
- Retry context with previous attempts
- Success probability estimation
- Intelligent retry suggestions
- Exponential backoff strategies
- Retry metrics and reporting
- **Test Coverage:** Error analysis, retry context, backoff, metrics

### Stage 8: Dependency Analysis and Parallel Execution ✓
- LLM-based dependency analysis (optional, with fallback)
- Dependency graph with topological sort
- Parallel executor (ThreadPoolExecutor/ProcessPoolExecutor)
- Work directory isolation for parallel tasks
- Resource management (memory, CPU)
- Configurable execution modes
- **Test Coverage:** Dependency graph, parallel execution, work directories, resource management

### Stage 9: Branching and Play-from-Node ✓
- Branch creation from workflow steps
- Hypothesis tracking for scientific experiments
- Context modifications (parameter overrides)
- Play-from-node execution resumption
- Branch comparison (step-by-step, files, metrics)
- Branch tree visualization
- **Test Coverage:** Branch creation, comparison, play-from-node, tree visualization

## Test Structure

### Test Script: `test_all_stages.py`

Comprehensive Python test script that validates all implemented functionality. Each test is self-contained and provides clear pass/fail output.

**Features:**
- Automated test execution
- Clear pass/fail reporting
- Stage-specific test selection
- Detailed error messages
- Test summary statistics

**Test Categories:**
1. **Foundation Tests** (Stages 1-2): 7 tests
2. **State Machine & DAG Tests** (Stages 3-4): 7 tests
3. **WebSocket Tests** (Stage 5): 3 tests
4. **HITL Approval Tests** (Stage 6): 3 tests
5. **Retry Mechanism Tests** (Stage 7): 4 tests
6. **Parallel Execution Tests** (Stage 8): 4 tests
7. **Branching Tests** (Stage 9): 3 tests

**Total: 31+ Tests**

### Jupyter Notebooks (Alternative)

For interactive exploration and demonstration:

- `notebooks/01_foundation_tests.ipynb` - Stages 1-2
- `notebooks/02_state_machine_dag_tests.ipynb` - Stages 3-4
- `notebooks/03_websocket_protocol_tests.ipynb` - Stage 5
- `notebooks/04_hitl_approval_tests.ipynb` - Stage 6
- `notebooks/05_retry_mechanism_tests.ipynb` - Stage 7
- `notebooks/06_parallel_execution_tests.ipynb` - Stage 8
- `notebooks/07_branching_tests.ipynb` - Stage 9
- `notebooks/08_end_to_end_integration.ipynb` - Full workflow demo

## Prerequisites

### 1. Environment Setup

```bash
# Install CMBAgent in development mode
pip install -e .

# Install testing dependencies (if needed)
pip install pytest jupyter ipykernel
```

### 2. API Keys

Ensure `.env` file contains:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
GEMINI_API_KEY=...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp_account.json
```

### 3. Database Migration

```bash
# Run Alembic migrations to latest version
alembic upgrade head

# Verify database exists
ls ~/.cmbagent/cmbagent.db
```

### 4. Enable Database

```bash
# Ensure database is enabled (default)
export CMBAGENT_USE_DATABASE=true
```

## Running Tests

### Option 1: Run All Tests

```bash
python test_all_stages.py
```

**Expected Output:**
```
===============================================================================
  CMBAGENT STAGES 1-9 COMPREHENSIVE TEST SUITE
===============================================================================

Start Time: 2026-01-15T10:30:00
Database: /home/user/.cmbagent/cmbagent.db

===============================================================================
  STAGE 1-2: FOUNDATION (AG2 Upgrade + Database)
===============================================================================

  Testing: AG2 Import and Version... ✓ PASS
  Testing: CMBAgent Utils Import... ✓ PASS
  Testing: Database Initialization... ✓ PASS
  ...

===============================================================================
  TEST EXECUTION SUMMARY
===============================================================================

Total Tests: 31
Passed: 31 ✓
Failed: 0 ✗
Skipped: 0

Pass Rate: 100.0%

✓ ALL TESTS PASSED!
```

### Option 2: Run Specific Stage Tests

```bash
# Test foundation (Stages 1-2)
python test_all_stages.py --stage 1-2

# Test state machine and DAG (Stages 3-4)
python test_all_stages.py --stage 3-4

# Test WebSocket protocol (Stage 5)
python test_all_stages.py --stage 5

# Test HITL approval system (Stage 6)
python test_all_stages.py --stage 6

# Test retry mechanism (Stage 7)
python test_all_stages.py --stage 7

# Test parallel execution (Stage 8)
python test_all_stages.py --stage 8

# Test branching (Stage 9)
python test_all_stages.py --stage 9
```

### Option 3: Use Existing Test Files

```bash
# Run original stage-specific test files
python tests/test_database_integration.py  # Stage 2
python tests/test_state_machine.py         # Stage 3
python tests/test_stage_04_dag.py          # Stage 4
python tests/test_stage_05.py              # Stage 5
python tests/test_stage_06_approval.py     # Stage 6
python tests/test_stage_07_retry.py        # Stage 7
python tests/test_stage_08_parallel_execution.py  # Stage 8
python tests/test_stage_09_branching.py    # Stage 9
```

### Option 4: Run Jupyter Notebooks

```bash
cd notebooks
jupyter notebook

# Then open and run each notebook interactively
```

## Test Details

### Stage 1-2 Tests (Foundation)

**Test 1: AG2 Import and Version**
- Verifies AG2 v0.10.3+ installed
- Confirms not using custom fork
- Tests core AG2 classes import

**Test 2: CMBAgent Utils**
- Tests local cmbagent_utils module
- Verifies LOGO, colors, config variables
- Ensures utilities migrated correctly

**Test 3-4: Database Initialization**
- Creates SQLite database at `~/.cmbagent/cmbagent.db`
- Initializes all 13 tables
- Verifies schema via Alembic

**Test 5-7: Repository Layer**
- SessionRepository CRUD operations
- WorkflowRepository CRUD operations
- Session isolation verification

**Test 8-11: Advanced Features**
- DAG repository (nodes and edges)
- Checkpoint repository
- Cost tracking repository
- Dual-persistence manager

### Stage 3-4 Tests (State Machine & DAG)

**Test 1-4: State Machine**
- State enumeration definitions
- State transitions with validation
- State history tracking
- Workflow pause/resume/cancel

**Test 5-7: DAG System**
- DAG construction from plan JSON
- Topological sorting for execution order
- Cycle detection
- DAG visualization exports

### Stage 5 Tests (WebSocket)

**Test 1-3: Event System**
- Event type definitions (20+ types)
- Event queue with retention
- Event serialization/deserialization

### Stage 6 Tests (HITL)

**Test 1-3: Approval System**
- Approval modes and configurations
- Approval request creation
- Approval resolution with feedback

### Stage 7 Tests (Retry)

**Test 1-4: Retry Mechanism**
- Error pattern recognition (12 categories)
- Retry context creation
- Retry context manager
- Retry metrics and statistics

### Stage 8 Tests (Parallel Execution)

**Test 1-4: Parallel Execution**
- Dependency graph construction
- Work directory isolation
- Resource management
- Execution configuration

### Stage 9 Tests (Branching)

**Test 1-3: Branching**
- Branch creation from steps
- Branch comparison
- Play-from-node execution

## Expected Performance

### Test Execution Time

- **Stage 1-2:** ~5-10 seconds
- **Stage 3-4:** ~10-15 seconds
- **Stage 5:** ~3-5 seconds
- **Stage 6:** ~5-10 seconds
- **Stage 7:** ~5-10 seconds
- **Stage 8:** ~10-15 seconds (includes parallel execution demos)
- **Stage 9:** ~5-10 seconds

**Total: ~50-80 seconds for all tests**

### Database Size After Tests

- Initial: ~20 KB
- After all tests: ~100-200 KB
- Test data includes: sessions, workflows, steps, DAG nodes, checkpoints, approvals, branches

## Troubleshooting

### Issue: Database Locked

**Symptom:** `database is locked` error

**Solution:**
```bash
# Close all Python processes accessing the database
pkill -f python

# Or remove and recreate database
rm ~/.cmbagent/cmbagent.db
alembic upgrade head
```

### Issue: Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'cmbagent'`

**Solution:**
```bash
# Reinstall in development mode
pip install -e . --force-reinstall
```

### Issue: API Key Errors

**Symptom:** `OPENAI_API_KEY not found`

**Solution:**
```bash
# Verify .env file exists and is loaded
cat .env
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('OPENAI_API_KEY')[:20])"
```

### Issue: Alembic Migration Errors

**Symptom:** `alembic.util.exc.CommandError: Can't locate revision identified by`

**Solution:**
```bash
# Check current migration status
alembic current

# Upgrade to latest
alembic upgrade head

# If issues persist, reset database
rm ~/.cmbagent/cmbagent.db
alembic upgrade head
```

### Issue: Test Failures

**Symptom:** Some tests fail unexpectedly

**Solution:**
```bash
# Run tests with verbose output to see detailed errors
python test_all_stages.py --verbose

# Run specific failing stage
python test_all_stages.py --stage <stage-number>

# Check database state
sqlite3 ~/.cmbagent/cmbagent.db
> .tables
> .quit
```

## Validating Functionality

### Manual Validation

After running automated tests, you can manually verify functionality:

#### 1. Database Inspection

```bash
# Open database
sqlite3 ~/.cmbagent/cmbagent.db

# View sessions
SELECT * FROM sessions;

# View workflow runs
SELECT * FROM workflow_runs;

# View state history
SELECT * FROM state_history ORDER BY created_at DESC LIMIT 10;

# Exit
.quit
```

#### 2. Check Files Created

```bash
# List work directories
ls ~/.cmbagent/

# Check database size
du -h ~/.cmbagent/cmbagent.db
```

#### 3. Verify Imports

```python
# Test imports in Python REPL
python3
>>> import autogen
>>> from cmbagent import CMBAgent
>>> from cmbagent.database import *
>>> from cmbagent.branching import *
>>> from cmbagent.retry import *
>>> from cmbagent.execution import *
```

## Test Data Cleanup

After testing, you may want to clean up test data:

```bash
# Remove test database
rm ~/.cmbagent/cmbagent.db

# Recreate fresh database
alembic upgrade head

# Or keep test data for inspection
# (database is automatically cleaned up on next run)
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Test Stages 1-9

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -e .
          alembic upgrade head
      - name: Run tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          CMBAGENT_USE_DATABASE: true
        run: python test_all_stages.py
```

## Next Steps

After validating Stages 1-9:

1. **Review Test Results** - Ensure all tests pass
2. **Performance Benchmarking** - Measure execution times
3. **Integration Testing** - Test full workflows end-to-end
4. **Documentation** - Update user documentation with new features
5. **Prepare for Stages 10-15** - MCP integration, policy enforcement, observability

## Reporting Issues

If you encounter issues:

1. **Check Logs** - Review test output for error messages
2. **Database State** - Inspect database with `sqlite3`
3. **Environment** - Verify API keys and environment variables
4. **Stage Summaries** - Review `IMPLEMENTATION_PLAN/STAGE_*_SUMMARY.md` files
5. **Original Tests** - Compare with `tests/test_stage_*.py` files

## Support

For questions or issues:
- Check stage summary documents in `IMPLEMENTATION_PLAN/`
- Review original test files in `tests/`
- Inspect database schema in `cmbagent/database/models.py`
- Check migration files in `cmbagent/database/migrations/versions/`

---

**Testing Guide Version:** 1.0
**Last Updated:** 2026-01-15
**Stages Covered:** 1-9 (Complete)
**Total Tests:** 31+
**Expected Duration:** 50-80 seconds
