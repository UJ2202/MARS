# Stage 7: Context-Aware Retry Mechanism

**Phase:** 2 - Human-in-the-Loop and Parallel Execution
**Estimated Time:** 30-40 minutes
**Dependencies:** Stage 6 (Approval System) must be complete
**Risk Level:** Medium

## Objectives

1. Enhance retry logic to inject error context into subsequent attempts
2. Include previous attempt outputs and failure reasons
3. Incorporate user feedback from approval system into retries
4. Track retry history and attempt metadata in database
5. Implement intelligent retry strategies (exponential backoff, adaptive)
6. Generate suggestions for agents based on error patterns

## Current State Analysis

### What We Have
- Basic retry: just re-execute same task
- No error context passed to retry
- No learning from previous failures
- No user feedback in retry loop
- Simple retry count limit
- Same approach attempted multiple times

### What We Need
- Error context injection into retry prompt
- Previous attempt history available to agent
- User feedback from approvals included
- Retry metadata tracked in database
- Smart retry strategies
- Error pattern analysis and suggestions

## Pre-Stage Verification

### Check Prerequisites
1. Stage 6 complete and verified
2. Approval system working
3. User feedback injection functioning
4. State machine tracking step states
5. Database storing error messages

### Expected State
- Can capture errors in workflow_steps
- Approval feedback available in context
- State transitions logged
- Ready to enhance retry logic
- No breaking changes to current retry behavior

## Implementation Tasks

### Task 1: Create Retry Context Structure
**Objective:** Define comprehensive retry context passed to agents

**Implementation:**

Create retry context data model:
```python
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class RetryAttempt(BaseModel):
    """Single retry attempt record"""
    attempt_number: int
    started_at: datetime
    completed_at: Optional[datetime]
    error_type: Optional[str]
    error_message: Optional[str]
    traceback: Optional[str]
    agent_output: Optional[str]
    modifications_tried: List[str] = []

class RetryContext(BaseModel):
    """Context for retry attempts"""
    current_attempt: int
    max_attempts: int
    original_task: str
    modified_task: Optional[str]

    # Previous attempt history
    previous_attempts: List[RetryAttempt] = []

    # Error analysis
    error_pattern: Optional[str]
    error_category: str  # "file_not_found", "api_error", "timeout", etc.
    common_error: bool  # Is this a common known error?

    # User guidance
    user_feedback: Optional[str]
    user_suggestions: List[str] = []

    # System suggestions
    suggested_fixes: List[str] = []
    similar_errors_resolved: List[Dict[str, Any]] = []

    # Retry strategy
    strategy: str  # "immediate", "exponential_backoff", "user_guided"
    backoff_seconds: Optional[int]

    # Success indicators
    success_probability: Optional[float]  # 0.0 to 1.0
```

**Files to Create:**
- `cmbagent/retry/retry_context.py`

**Verification:**
- Retry context structure comprehensive
- Pydantic validation works
- Can serialize to JSON
- Includes all necessary retry information

### Task 2: Implement Error Pattern Analyzer
**Objective:** Categorize errors and suggest fixes

**Implementation:**

```python
import re
from typing import List, Dict, Optional

class ErrorAnalyzer:
    """Analyzes errors and provides suggestions"""

    # Common error patterns
    ERROR_PATTERNS = {
        "file_not_found": {
            "regex": r"(FileNotFoundError|No such file|cannot find)",
            "category": "file_not_found",
            "suggestions": [
                "Verify the file path is correct",
                "Check if the file exists before accessing",
                "Use absolute path instead of relative path",
                "List directory contents to see available files"
            ]
        },
        "api_error": {
            "regex": r"(APIError|API.*failed|rate limit|quota exceeded)",
            "category": "api_error",
            "suggestions": [
                "Check API credentials are valid",
                "Verify API endpoint is correct",
                "Check if rate limit was exceeded (wait and retry)",
                "Validate request parameters"
            ]
        },
        "timeout": {
            "regex": r"(timeout|timed out|TimeoutError)",
            "category": "timeout",
            "suggestions": [
                "Increase timeout duration",
                "Check network connectivity",
                "Simplify the operation to complete faster",
                "Implement chunking for large operations"
            ]
        },
        "import_error": {
            "regex": r"(ImportError|ModuleNotFoundError|No module named)",
            "category": "import_error",
            "suggestions": [
                "Install missing package: pip install <package>",
                "Check package name spelling",
                "Verify package is in requirements",
                "Use correct import statement"
            ]
        },
        "type_error": {
            "regex": r"TypeError",
            "category": "type_error",
            "suggestions": [
                "Check argument types match function signature",
                "Verify data type conversions",
                "Handle None values properly",
                "Validate input data types"
            ]
        },
        "value_error": {
            "regex": r"ValueError",
            "category": "value_error",
            "suggestions": [
                "Validate input values are in expected range",
                "Check for empty or invalid data",
                "Verify data format is correct",
                "Handle edge cases"
            ]
        }
    }

    def analyze_error(self, error_message: str, traceback: str = None) -> Dict[str, Any]:
        """
        Analyze error and return category and suggestions

        Args:
            error_message: Error message string
            traceback: Full traceback (optional)

        Returns:
            Dictionary with category, suggestions, and pattern info
        """
        # Try to match error patterns
        for pattern_name, pattern_info in self.ERROR_PATTERNS.items():
            if re.search(pattern_info["regex"], error_message, re.IGNORECASE):
                return {
                    "category": pattern_info["category"],
                    "pattern": pattern_name,
                    "suggestions": pattern_info["suggestions"],
                    "common_error": True
                }

        # Unknown error pattern
        return {
            "category": "unknown",
            "pattern": None,
            "suggestions": [
                "Review the full error message and traceback",
                "Check recent code changes",
                "Search for similar errors online",
                "Break down the task into smaller steps"
            ],
            "common_error": False
        }

    def get_similar_resolved_errors(self, db_session, error_category: str, limit: int = 3) -> List[Dict]:
        """
        Find similar errors that were successfully resolved

        Args:
            db_session: Database session
            error_category: Category of current error
            limit: Max number of examples to return

        Returns:
            List of resolved error examples with solutions
        """
        from cmbagent.database.models import WorkflowStep

        # Query successful steps that had previous failures in same category
        # This would require additional metadata tracking
        # Simplified version for now:

        resolved_errors = []

        # TODO: Implement database query for similar resolved errors
        # For now, return empty list
        return resolved_errors

    def estimate_success_probability(
        self,
        attempt_number: int,
        error_category: str,
        has_user_feedback: bool
    ) -> float:
        """
        Estimate probability of success for next retry

        Args:
            attempt_number: Current attempt number
            error_category: Type of error
            has_user_feedback: Whether user provided guidance

        Returns:
            Probability between 0.0 and 1.0
        """
        # Base probability decreases with attempts
        base_prob = 1.0 / (attempt_number + 1)

        # Boost if user provided feedback
        if has_user_feedback:
            base_prob *= 1.5

        # Adjust based on error category
        category_multipliers = {
            "file_not_found": 0.8,  # Often requires external fix
            "api_error": 0.6,       # May be external service issue
            "timeout": 0.7,         # May resolve with retry
            "import_error": 0.9,    # Usually fixable
            "type_error": 0.85,     # Code fix needed
            "value_error": 0.85,    # Code fix needed
            "unknown": 0.5          # Uncertain
        }

        multiplier = category_multipliers.get(error_category, 0.5)
        probability = min(base_prob * multiplier, 1.0)

        return round(probability, 2)
```

**Files to Create:**
- `cmbagent/retry/error_analyzer.py`

**Verification:**
- Error patterns correctly matched
- Suggestions generated for common errors
- Unknown errors handled gracefully
- Success probability calculated
- Can query similar resolved errors

### Task 3: Build Retry Context Manager
**Objective:** Manage retry context creation and updates

**Implementation:**

```python
from typing import Optional, List
from cmbagent.retry.retry_context import RetryContext, RetryAttempt
from cmbagent.retry.error_analyzer import ErrorAnalyzer
from cmbagent.database.models import WorkflowStep
from datetime import datetime

class RetryContextManager:
    """Manages retry context for workflow steps"""

    def __init__(self, db_session, session_id):
        self.db = db_session
        self.session_id = session_id
        self.error_analyzer = ErrorAnalyzer()

    def create_retry_context(
        self,
        step: WorkflowStep,
        attempt_number: int,
        max_attempts: int,
        user_feedback: Optional[str] = None
    ) -> RetryContext:
        """
        Create retry context for step

        Args:
            step: WorkflowStep being retried
            attempt_number: Current attempt number
            max_attempts: Maximum retry attempts
            user_feedback: Optional user guidance

        Returns:
            RetryContext with all retry information
        """
        # Load previous attempts
        previous_attempts = self._load_previous_attempts(step)

        # Analyze latest error
        latest_error = step.error_message or "Unknown error"
        error_analysis = self.error_analyzer.analyze_error(latest_error)

        # Get user suggestions from feedback
        user_suggestions = []
        if user_feedback:
            user_suggestions = self._parse_user_suggestions(user_feedback)

        # Get similar resolved errors
        similar_errors = self.error_analyzer.get_similar_resolved_errors(
            self.db,
            error_analysis["category"]
        )

        # Estimate success probability
        success_prob = self.error_analyzer.estimate_success_probability(
            attempt_number=attempt_number,
            error_category=error_analysis["category"],
            has_user_feedback=bool(user_feedback)
        )

        # Determine retry strategy
        if user_feedback:
            strategy = "user_guided"
            backoff_seconds = 0  # Immediate retry with guidance
        elif attempt_number > 2:
            strategy = "exponential_backoff"
            backoff_seconds = min(2 ** attempt_number, 60)
        else:
            strategy = "immediate"
            backoff_seconds = 0

        return RetryContext(
            current_attempt=attempt_number,
            max_attempts=max_attempts,
            original_task=step.inputs.get("task", ""),
            modified_task=None,
            previous_attempts=previous_attempts,
            error_pattern=error_analysis.get("pattern"),
            error_category=error_analysis["category"],
            common_error=error_analysis["common_error"],
            user_feedback=user_feedback,
            user_suggestions=user_suggestions,
            suggested_fixes=error_analysis["suggestions"],
            similar_errors_resolved=similar_errors,
            strategy=strategy,
            backoff_seconds=backoff_seconds,
            success_probability=success_prob
        )

    def _load_previous_attempts(self, step: WorkflowStep) -> List[RetryAttempt]:
        """Load previous retry attempts from step metadata"""
        attempts_data = step.metadata.get("retry_attempts", [])

        return [
            RetryAttempt(**attempt_data)
            for attempt_data in attempts_data
        ]

    def _parse_user_suggestions(self, feedback: str) -> List[str]:
        """Parse user feedback into actionable suggestions"""
        # Simple parsing: split by newlines/bullets
        suggestions = []

        for line in feedback.split('\n'):
            line = line.strip()
            # Remove bullet points
            line = re.sub(r'^[-*•]\s*', '', line)
            if line:
                suggestions.append(line)

        return suggestions

    def record_attempt(
        self,
        step: WorkflowStep,
        attempt_number: int,
        error_type: Optional[str],
        error_message: Optional[str],
        traceback: Optional[str],
        agent_output: Optional[str]
    ):
        """Record retry attempt in step metadata"""
        attempt = RetryAttempt(
            attempt_number=attempt_number,
            started_at=step.started_at or datetime.utcnow(),
            completed_at=datetime.utcnow(),
            error_type=error_type,
            error_message=error_message,
            traceback=traceback,
            agent_output=agent_output
        )

        # Add to step metadata
        if "retry_attempts" not in step.metadata:
            step.metadata["retry_attempts"] = []

        step.metadata["retry_attempts"].append(attempt.dict())
        self.db.commit()

    def format_retry_prompt(self, retry_context: RetryContext) -> str:
        """
        Format retry context into agent prompt

        Args:
            retry_context: Retry context

        Returns:
            Formatted prompt string for agent
        """
        prompt_parts = []

        # Header
        prompt_parts.append(f"RETRY ATTEMPT {retry_context.current_attempt}/{retry_context.max_attempts}")
        prompt_parts.append("=" * 60)
        prompt_parts.append("")

        # Original task
        prompt_parts.append("ORIGINAL TASK:")
        prompt_parts.append(retry_context.original_task)
        prompt_parts.append("")

        # Previous attempts summary
        if retry_context.previous_attempts:
            prompt_parts.append("PREVIOUS ATTEMPTS:")
            for attempt in retry_context.previous_attempts:
                prompt_parts.append(f"\nAttempt {attempt.attempt_number}:")
                prompt_parts.append(f"  Error: {attempt.error_message}")
                if attempt.modifications_tried:
                    prompt_parts.append(f"  Tried: {', '.join(attempt.modifications_tried)}")
            prompt_parts.append("")

        # Error analysis
        prompt_parts.append("ERROR ANALYSIS:")
        prompt_parts.append(f"  Category: {retry_context.error_category}")
        if retry_context.error_pattern:
            prompt_parts.append(f"  Pattern: {retry_context.error_pattern}")
        prompt_parts.append(f"  Common error: {retry_context.common_error}")
        prompt_parts.append("")

        # User feedback
        if retry_context.user_feedback:
            prompt_parts.append("USER GUIDANCE:")
            prompt_parts.append(retry_context.user_feedback)
            prompt_parts.append("")

        # Suggestions
        all_suggestions = retry_context.suggested_fixes + retry_context.user_suggestions
        if all_suggestions:
            prompt_parts.append("SUGGESTIONS TO TRY:")
            for idx, suggestion in enumerate(all_suggestions, 1):
                prompt_parts.append(f"  {idx}. {suggestion}")
            prompt_parts.append("")

        # Similar resolved errors
        if retry_context.similar_errors_resolved:
            prompt_parts.append("SIMILAR ERRORS SUCCESSFULLY RESOLVED:")
            for example in retry_context.similar_errors_resolved:
                prompt_parts.append(f"  - {example['description']}")
                prompt_parts.append(f"    Solution: {example['solution']}")
            prompt_parts.append("")

        # Success probability
        prompt_parts.append(f"ESTIMATED SUCCESS PROBABILITY: {retry_context.success_probability * 100:.0f}%")
        prompt_parts.append("")

        # Instructions
        prompt_parts.append("INSTRUCTIONS:")
        prompt_parts.append("Please retry the task taking into account:")
        prompt_parts.append("1. Why previous attempts failed")
        prompt_parts.append("2. User guidance provided")
        prompt_parts.append("3. Suggested fixes")
        prompt_parts.append("4. Different approaches that might work")
        prompt_parts.append("")
        prompt_parts.append("If you determine the task cannot be completed, explain why clearly.")

        return "\n".join(prompt_parts)
```

**Files to Create:**
- `cmbagent/retry/retry_context_manager.py`

**Verification:**
- Retry context created correctly
- Previous attempts loaded from metadata
- User feedback parsed into suggestions
- Retry prompt formatted properly
- Attempt metadata recorded

### Task 4: Integrate Context-Aware Retry into Workflow
**Objective:** Use retry context in step execution

**Implementation:**

Update step execution with context-aware retry:
```python
# In cmbagent.py

from cmbagent.retry.retry_context_manager import RetryContextManager
import time

class CMBAgent:
    def __init__(self, max_retries: int = 3, **kwargs):
        # ... existing init ...
        self.max_retries = max_retries
        self.retry_manager = RetryContextManager(self.db_session, self.session_id)

    def _execute_step_with_retry(
        self,
        step: WorkflowStep,
        agent_name: str,
        task: str
    ):
        """Execute step with context-aware retry logic"""

        for attempt in range(1, self.max_retries + 1):
            try:
                # Create retry context (if retry)
                if attempt > 1:
                    # Get user feedback if available
                    user_feedback = shared_context.get(f"retry_guidance_{step.step_number}")

                    # Create retry context
                    retry_context = self.retry_manager.create_retry_context(
                        step=step,
                        attempt_number=attempt,
                        max_attempts=self.max_retries,
                        user_feedback=user_feedback
                    )

                    # Apply backoff strategy
                    if retry_context.backoff_seconds > 0:
                        print(f"Backing off for {retry_context.backoff_seconds}s before retry...")
                        time.sleep(retry_context.backoff_seconds)

                    # Format retry prompt
                    retry_prompt = self.retry_manager.format_retry_prompt(retry_context)

                    # Augment task with retry context
                    augmented_task = f"{retry_prompt}\n\nORIGINAL TASK:\n{task}"
                else:
                    # First attempt - use original task
                    augmented_task = task

                # Execute agent
                result = self._execute_agent(agent_name, augmented_task)

                # Success - record attempt
                self.retry_manager.record_attempt(
                    step=step,
                    attempt_number=attempt,
                    error_type=None,
                    error_message=None,
                    traceback=None,
                    agent_output=result
                )

                return result

            except Exception as e:
                # Record failed attempt
                import traceback as tb
                self.retry_manager.record_attempt(
                    step=step,
                    attempt_number=attempt,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    traceback=tb.format_exc(),
                    agent_output=None
                )

                # Update step error
                step.error_message = str(e)
                self.db.commit()

                # Last attempt - raise error
                if attempt >= self.max_retries:
                    raise

                # Otherwise, continue to next retry
                print(f"Attempt {attempt} failed: {str(e)}")
                print(f"Retrying... ({attempt + 1}/{self.max_retries})")

        # Should not reach here
        raise RuntimeError("Retry loop exited unexpectedly")
```

**Files to Modify:**
- `cmbagent/cmbagent.py` (add context-aware retry)

**Verification:**
- Retry context injected into prompts
- Previous errors passed to agent
- User feedback included in retry
- Exponential backoff applied
- Retry attempts tracked in metadata

### Task 5: Add Retry Metrics and Reporting
**Objective:** Track and report retry statistics

**Implementation:**

```python
class RetryMetrics:
    """Track retry statistics"""

    def __init__(self, db_session):
        self.db = db_session

    def get_retry_stats(self, run_id: str) -> Dict[str, Any]:
        """Get retry statistics for workflow run"""
        from cmbagent.database.models import WorkflowStep

        steps = self.db.query(WorkflowStep).filter(
            WorkflowStep.run_id == run_id
        ).all()

        total_steps = len(steps)
        steps_with_retries = 0
        total_retries = 0
        retry_success_rate = 0
        error_categories = {}

        for step in steps:
            attempts = step.metadata.get("retry_attempts", [])
            if len(attempts) > 1:
                steps_with_retries += 1
                total_retries += len(attempts) - 1

                # Track success after retry
                last_attempt = attempts[-1]
                if last_attempt.get("error_type") is None:
                    retry_success_rate += 1

                # Count error categories
                for attempt in attempts:
                    error_type = attempt.get("error_type")
                    if error_type:
                        error_categories[error_type] = error_categories.get(error_type, 0) + 1

        if steps_with_retries > 0:
            retry_success_rate = (retry_success_rate / steps_with_retries) * 100
        else:
            retry_success_rate = 0

        return {
            "total_steps": total_steps,
            "steps_with_retries": steps_with_retries,
            "total_retry_attempts": total_retries,
            "retry_success_rate": round(retry_success_rate, 1),
            "avg_retries_per_step": round(total_retries / total_steps, 2) if total_steps > 0 else 0,
            "error_categories": error_categories
        }

    def generate_retry_report(self, run_id: str) -> str:
        """Generate human-readable retry report"""
        stats = self.get_retry_stats(run_id)

        report = []
        report.append("RETRY STATISTICS")
        report.append("=" * 60)
        report.append(f"Total steps: {stats['total_steps']}")
        report.append(f"Steps requiring retry: {stats['steps_with_retries']}")
        report.append(f"Total retry attempts: {stats['total_retry_attempts']}")
        report.append(f"Retry success rate: {stats['retry_success_rate']}%")
        report.append(f"Average retries per step: {stats['avg_retries_per_step']}")
        report.append("")

        if stats['error_categories']:
            report.append("ERROR CATEGORIES:")
            for error_type, count in sorted(stats['error_categories'].items(), key=lambda x: x[1], reverse=True):
                report.append(f"  {error_type}: {count}")

        return "\n".join(report)
```

**Files to Create:**
- `cmbagent/retry/retry_metrics.py`

**Verification:**
- Retry statistics calculated correctly
- Success rate computed
- Error categories tracked
- Report formatted properly

### Task 6: Add Retry Events to WebSocket
**Objective:** Stream retry information to UI

**Implementation:**

Update retry manager to emit events:
```python
# In retry_context_manager.py

def create_retry_context(self, ...):
    # ... existing code ...

    retry_context = RetryContext(...)

    # Emit retry event
    from backend.websocket_events import WebSocketEvent, WebSocketEventType
    from backend.event_queue import event_queue

    event = WebSocketEvent(
        event_type=WebSocketEventType.STEP_STARTED,  # Or create STEP_RETRY event
        timestamp=datetime.utcnow(),
        run_id=str(step.run_id),
        data={
            "step_id": str(step.id),
            "retry_attempt": attempt_number,
            "max_attempts": max_attempts,
            "error_category": retry_context.error_category,
            "success_probability": retry_context.success_probability,
            "strategy": retry_context.strategy
        }
    )

    event_queue.push(str(step.run_id), event)

    return retry_context
```

**Files to Modify:**
- `cmbagent/retry/retry_context_manager.py` (add event emission)

**Verification:**
- Retry events emitted to WebSocket
- UI receives retry notifications
- Retry metadata visible in UI

## Files to Create (Summary)

### New Files
```
cmbagent/retry/
├── __init__.py
├── retry_context.py            # Retry context data models
├── error_analyzer.py           # Error pattern analysis
├── retry_context_manager.py    # Retry context management
└── retry_metrics.py            # Retry statistics
```

### Modified Files
- `cmbagent/cmbagent.py` - Integrate context-aware retry

## Verification Criteria

### Must Pass
- [ ] Retry context structure defined
- [ ] Error patterns analyzed correctly
- [ ] Suggestions generated for common errors
- [ ] Retry context created with all information
- [ ] Previous attempts loaded from metadata
- [ ] User feedback included in retry prompt
- [ ] Retry prompt formatted correctly
- [ ] Exponential backoff applied
- [ ] Retry attempts tracked in database
- [ ] Retry statistics calculated
- [ ] WebSocket events for retries

### Should Pass
- [ ] Similar errors queried from history
- [ ] Success probability estimated
- [ ] Retry report generated
- [ ] Error categories tracked
- [ ] Multiple retry strategies supported

### Retry Testing
```python
# Test retry context creation
def test_create_retry_context():
    manager = RetryContextManager(db_session, session_id)
    step = create_test_step(error_message="FileNotFoundError: test.txt")
    context = manager.create_retry_context(step, attempt_number=2, max_attempts=3)
    assert context.error_category == "file_not_found"
    assert len(context.suggested_fixes) > 0

# Test error analysis
def test_error_analysis():
    analyzer = ErrorAnalyzer()
    result = analyzer.analyze_error("FileNotFoundError: data.csv not found")
    assert result["category"] == "file_not_found"
    assert len(result["suggestions"]) > 0

# Test retry prompt
def test_retry_prompt():
    context = create_test_retry_context()
    prompt = manager.format_retry_prompt(context)
    assert "RETRY ATTEMPT" in prompt
    assert "SUGGESTIONS" in prompt

# Test attempt recording
def test_record_attempt():
    manager.record_attempt(step, 1, "ValueError", "Invalid input", None, "output")
    assert len(step.metadata["retry_attempts"]) == 1
```

## Testing Checklist

### Unit Tests
```python
# Test error pattern matching
def test_error_patterns():
    analyzer = ErrorAnalyzer()
    for error_msg, expected_category in test_cases:
        result = analyzer.analyze_error(error_msg)
        assert result["category"] == expected_category

# Test retry metrics
def test_retry_metrics():
    metrics = RetryMetrics(db_session)
    stats = metrics.get_retry_stats(run_id)
    assert "total_steps" in stats
    assert "retry_success_rate" in stats
```

### Integration Tests
```python
# Test full retry workflow
def test_context_aware_retry():
    agent = CMBAgent(max_retries=3)

    # Force error on first attempt
    # Provide user feedback
    # Verify retry includes context

# Test retry with user feedback
def test_retry_with_feedback():
    # Create step that fails
    # Get approval with feedback
    # Retry with feedback injected
    # Verify feedback in retry prompt
```

## Common Issues and Solutions

### Issue 1: Retry Loop Infinite
**Symptom:** Retries never stop
**Solution:** Enforce max_retries limit, add timeout

### Issue 2: Context Too Large
**Symptom:** Retry prompt exceeds token limit
**Solution:** Summarize previous attempts, truncate old context

### Issue 3: User Feedback Not Applied
**Symptom:** Retry ignores user guidance
**Solution:** Verify feedback in context, check prompt formatting

### Issue 4: Same Error Repeatedly
**Symptom:** Same error occurs on every retry
**Solution:** Better error analysis, suggest different approaches

### Issue 5: Retry Metadata Growing
**Symptom:** Step metadata becomes too large
**Solution:** Limit stored attempts, archive old attempts

## Rollback Procedure

If context-aware retry causes issues:

1. **Revert to simple retry:**
   ```python
   # Old way: just retry same task
   for attempt in range(max_retries):
       try:
           return execute_task(task)
       except Exception as e:
           if attempt >= max_retries - 1:
               raise
   ```

2. **Disable retry context:**
   ```python
   USE_RETRY_CONTEXT = False
   ```

3. **Keep retry metadata** - Useful for analysis

4. **Document issues** for future resolution

## Post-Stage Actions

### Documentation
- Document retry context structure
- Add error pattern reference
- Create retry strategy guide
- Document retry metrics API

### Update Progress
- Mark Stage 7 complete in PROGRESS.md
- Note any deviations from plan
- Document time spent
- Update retry lessons learned

### Prepare for Next Phase
- Phase 2 complete (HITL and Parallel Execution)
- Ready to proceed to Phase 3 (MCP Integration)
- All foundation and enhancement stages done

## Success Criteria

Stage 7 is complete when:
1. Retry context includes error analysis
2. Previous attempts passed to agent
3. User feedback injected into retries
4. Error patterns analyzed and suggestions generated
5. Retry attempts tracked in database
6. Exponential backoff working
7. Retry metrics calculated
8. Verification checklist 100% complete

## Estimated Time Breakdown

- Retry context structure: 5 min
- Error analyzer implementation: 10 min
- Retry context manager: 10 min
- Workflow integration: 8 min
- Retry metrics: 5 min
- WebSocket events: 2 min
- Testing and verification: 8 min
- Documentation: 2 min

**Total: 30-40 minutes**

## Next Stage

Once Stage 7 is verified complete, proceed to:
**Stage 8: MCP Server Implementation** (Phase 3)

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
