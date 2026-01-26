# Stage 1: AG2 Upgrade and Compatibility Testing

**Phase:** 0 - Foundation
**Estimated Time:** 15-20 minutes
**Dependencies:** None (first stage)
**Risk Level:** High

## Objectives

1. Upgrade from custom fork `cmbagent_autogen>=0.0.91post11` to latest official AG2
2. Identify and fix breaking changes in codebase
3. Ensure all existing functionality works with new AG2 version
4. Document migration issues and solutions

## Current State Analysis

### What We Have
- Custom AG2 fork: `cmbagent_autogen>=0.0.91post11`
- Usage patterns: SwarmAgent, GroupChat, ContextVariables
- 50+ agents using AG2 patterns
- Hand-off chains defined in hand_offs.py
- Nested chat capabilities

### What Needs Investigation
- Latest stable AG2 version
- Breaking API changes from 0.0.91 to latest
- Deprecated patterns and their replacements
- New features we can leverage

## Pre-Stage Verification

### Check Current Setup
1. Verify current AG2 version installed
2. Document current import patterns
3. List all files importing from AG2/AutoGen
4. Run existing tests to establish baseline

### Expected Baseline
- All existing tests pass with current version
- `python tests/test_one_shot.py` succeeds
- `python tests/test_engineer.py` succeeds
- No import errors in current code

## Implementation Tasks

### Task 1: Research Latest AG2 Version
**Objective:** Identify target version and changes

**Actions:**
- Check PyPI for latest ag2 version
- Review AG2 changelog/release notes
- Identify breaking changes relevant to CMBAgent
- Document new features worth adopting

**Verification:**
- Target version identified and documented
- Breaking changes list created
- Migration strategy defined

### Task 2: Update Dependencies
**Objective:** Modify pyproject.toml with new AG2 version

**Files to Modify:**
- `pyproject.toml` line 24

**Changes:**
- Replace `cmbagent_autogen>=0.0.91post11` with `ag2>=X.Y.Z`
- Add any new required dependencies for AG2

**Verification:**
- pyproject.toml syntax valid
- Dependency resolver accepts changes
- No circular dependencies

### Task 3: Install New AG2 Version
**Objective:** Update environment with new AG2

**Actions:**
- Backup current environment (requirements freeze)
- Install new AG2: `pip install --upgrade ag2`
- Verify installation: `pip show ag2`
- Check for dependency conflicts

**Verification:**
- AG2 installed successfully
- No dependency conflicts
- Correct version confirmed

### Task 4: Fix Import Statements
**Objective:** Update all AG2 imports to new package structure

**Files Likely to Modify:**
- `cmbagent/cmbagent.py`
- `cmbagent/agents/base_agent.py`
- `cmbagent/hand_offs.py`
- `cmbagent/functions.py`
- All agent files in `cmbagent/agents/`

**Common Changes:**
- Package names: `autogen` → `ag2`
- Class renames: Check for deprecated classes
- Module restructuring: Check import paths

**Verification:**
- No import errors when loading modules
- All AG2 classes importable
- Type hints still valid

### Task 5: Fix Breaking API Changes
**Objective:** Update code to use new AG2 API

**Common Areas to Check:**
- ConversableAgent initialization
- SwarmAgent patterns
- GroupChat configuration
- ContextVariables usage
- Function registration
- Hand-off mechanisms
- Message handling

**Verification:**
- Code runs without AttributeError
- No deprecated warnings
- API usage matches new AG2 patterns

### Task 6: Test Core Functionality
**Objective:** Verify existing workflows still work

**Test Scenarios:**
1. One-shot execution with engineer
2. Planning and control workflow
3. Context carryover between steps
4. Agent hand-offs
5. Nested chats
6. RAG agent queries

**Verification:**
- All test scenarios complete successfully
- Output quality unchanged
- No regressions in functionality

## Files to Review and Potentially Modify

### High Priority (Directly use AG2)
- `cmbagent/cmbagent.py` - Core CMBAgent class
- `cmbagent/agents/base_agent.py` - Agent base class
- `cmbagent/hand_offs.py` - Hand-off definitions
- `cmbagent/functions.py` - Routing functions

### Medium Priority (Import AG2 types)
- `cmbagent/agents/engineer/engineer.py`
- `cmbagent/agents/planner/planner.py`
- `cmbagent/agents/control/control.py`
- All other agent implementations

### Low Priority (Indirect usage)
- Test files
- CLI interface
- Backend WebSocket handler

## Verification Criteria

### Must Pass
- [ ] New AG2 version installed successfully
- [ ] All import statements work without errors
- [ ] `python tests/test_one_shot.py` passes
- [ ] `python tests/test_engineer.py` passes
- [ ] No deprecation warnings in console
- [ ] Context carryover still works (pickle files loadable)
- [ ] Hand-off chains execute correctly
- [ ] Agent nested chats work

### Should Pass
- [ ] All existing test files pass
- [ ] CLI `cmbagent run` works
- [ ] WebSocket backend starts without errors
- [ ] Cost tracking still accurate

### Nice to Have
- [ ] Performance similar or better
- [ ] New AG2 features identified for future use
- [ ] Documentation updated with migration notes

## Common Issues and Solutions

### Issue 1: Package Not Found
**Symptom:** `ModuleNotFoundError: No module named 'autogen'`
**Solution:** Update all `import autogen` to `import ag2`

### Issue 2: Class Renamed
**Symptom:** `AttributeError: module 'ag2' has no attribute 'ConversableAgent'`
**Solution:** Check AG2 docs for new class name, update imports

### Issue 3: API Signature Changed
**Symptom:** `TypeError: __init__() got an unexpected keyword argument`
**Solution:** Review AG2 changelog, update initialization parameters

### Issue 4: Deprecated Warning
**Symptom:** `DeprecationWarning: X is deprecated, use Y instead`
**Solution:** Update code to use new recommended API

### Issue 5: Breaking Changes in Hand-offs
**Symptom:** Hand-off chains don't work as expected
**Solution:** Review new AG2 hand-off mechanism, update hand_offs.py

## Rollback Procedure

If upgrade fails and cannot be fixed quickly:

1. Revert `pyproject.toml` changes
2. Reinstall old version: `pip install cmbagent_autogen==0.0.91post11`
3. Document specific blocking issues
4. Create compatibility plan for gradual migration

## Post-Stage Actions

### Documentation
- Document all code changes made
- Note any new patterns to adopt
- List remaining deprecated code (to fix later)

### Update Progress
- Mark Stage 1 complete in PROGRESS.md
- Add notes about any issues encountered
- Document time spent

### Prepare for Stage 2
- AG2 now stable and working
- Can safely add new database layer
- Stage 2 can proceed

## Success Criteria

Stage 1 is complete when:
1. Latest AG2 installed and working
2. All existing tests pass
3. No breaking issues in core functionality
4. Migration documented
5. Verification checklist 100% complete

## Estimated Time Breakdown

- Research and planning: 5 min
- Dependency update and install: 3 min
- Import fixes: 5 min
- API change fixes: 10 min
- Testing and verification: 7 min
- Documentation: 5 min

**Total: 15-20 minutes**

## Next Stage

Once Stage 1 is verified complete, proceed to:
**Stage 2: Database Schema and Models**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
