# HITL Control Phase — Critical Fixes

## Summary of Issues

The HITL control phase (`cmbagent/phases/hitl_control.py`) has three systemic failures:

1. **Feedback never reaches agents** — Human guidance is collected and stored but never injected into agent prompts
2. **Redo is a no-op** — UI offers "redo" but code does `pass`
3. **Planning approval can't carry feedback** — "approve" exits immediately, feedback only flows through "revise"

---

## Issue 1: Feedback Not Injected Into Agents (CRITICAL)

### Root Cause

When a step executes (line 349), the agents receive:
- `context.task` — the **original** task, never augmented with human feedback
- `step_shared_context['engineer_append_instructions']` — only `self.config.engineer_instructions` (static config, empty by default)
- `step_shared_context['researcher_append_instructions']` — same, static config

The agent YAML templates have placeholders `{engineer_append_instructions}` and `{researcher_append_instructions}` that get filled from `shared_context`. This is the **existing mechanism** to get instructions into agent prompts — but HITL feedback is never placed there.

Meanwhile:
- `self._accumulated_feedback` collects feedback correctly (lines 269-273, 449-453)
- `self._step_feedback` records per-step feedback correctly
- But neither value is ever placed into `engineer_append_instructions` or `researcher_append_instructions`

### The Fix

**File**: `cmbagent/phases/hitl_control.py`

**Location**: Lines 340-346 (step context preparation, just before `cmbagent.solve()`)

**Current code:**
```python
# Prepare step context (matches standard ControlPhase)
step_shared_context = copy.deepcopy(current_context)
step_shared_context['current_plan_step_number'] = step_num
step_shared_context['n_attempts'] = attempt - 1
step_shared_context['agent_for_sub_task'] = agent_for_step
step_shared_context['engineer_append_instructions'] = self.config.engineer_instructions
step_shared_context['researcher_append_instructions'] = self.config.researcher_instructions
```

**Replace with:**
```python
# Prepare step context (matches standard ControlPhase)
step_shared_context = copy.deepcopy(current_context)
step_shared_context['current_plan_step_number'] = step_num
step_shared_context['n_attempts'] = attempt - 1
step_shared_context['agent_for_sub_task'] = agent_for_step

# Build agent instructions: static config + accumulated HITL feedback
engineer_instructions = self.config.engineer_instructions or ""
researcher_instructions = self.config.researcher_instructions or ""

if self._accumulated_feedback:
    hitl_section = (
        "\n\n## Human-in-the-Loop Feedback\n"
        "The human reviewer has provided the following guidance. "
        "You MUST follow these instructions:\n\n"
        f"{self._accumulated_feedback}\n"
    )
    engineer_instructions += hitl_section
    researcher_instructions += hitl_section

# Inject step-specific before-feedback (current step only)
current_step_feedback = [
    f for f in self._step_feedback
    if f['step'] == step_num and f['timing'] == 'before'
]
if current_step_feedback:
    step_guidance = "\n\n## Specific Guidance for This Step\n"
    for fb in current_step_feedback:
        step_guidance += f"- {fb['feedback']}\n"
    engineer_instructions += step_guidance
    researcher_instructions += step_guidance

step_shared_context['engineer_append_instructions'] = engineer_instructions
step_shared_context['researcher_append_instructions'] = researcher_instructions
```

### Why This Works

- Uses the **existing mechanism** (`{engineer_append_instructions}` placeholder in YAML templates)
- No new infrastructure needed
- Static config instructions are preserved (appended to, not replaced)
- Both accumulated feedback (from all previous steps) and step-specific before-feedback are included
- The `MUST follow` phrasing ensures LLM agents treat feedback as high-priority

### Edge Cases Handled

| Scenario | Behavior |
|----------|----------|
| No feedback given at all | `self._accumulated_feedback` is empty string, no section added |
| Feedback from planning only | Planning feedback loaded into `self._accumulated_feedback` at line 226, flows through |
| Multiple before-step feedbacks for same step | All appended (shouldn't happen in practice, but safe) |
| Very long accumulated feedback | Could hit context limits; see "Feedback Length Guard" below |
| Retry attempt after failure | Feedback persists across attempts (correct — human guidance doesn't expire) |
| Config engineer_instructions is None | `or ""` guard prevents `None + string` TypeError |

### Additional Safeguard: Feedback Length Guard

Add this helper method to `HITLControlPhase`:

```python
def _truncate_feedback(self, feedback: str, max_chars: int = 4000) -> str:
    """Truncate accumulated feedback to prevent context overflow.

    Keeps most recent feedback (end of string) since it's most relevant.
    """
    if not feedback or len(feedback) <= max_chars:
        return feedback

    truncated = feedback[-(max_chars):]
    # Find first complete section boundary
    boundary = truncated.find('\n\n**Step')
    if boundary > 0:
        truncated = truncated[boundary:]

    return f"[Earlier feedback truncated]\n{truncated}"
```

Then use it:
```python
if self._accumulated_feedback:
    safe_feedback = self._truncate_feedback(self._accumulated_feedback)
    hitl_section = (
        "\n\n## Human-in-the-Loop Feedback\n"
        "The human reviewer has provided the following guidance. "
        "You MUST follow these instructions:\n\n"
        f"{safe_feedback}\n"
    )
```

---

## Issue 2: Redo Not Implemented (CRITICAL)

### Root Cause

**File**: `cmbagent/phases/hitl_control.py`, lines 438-440

```python
elif review_result is None:  # Redo
    # Could implement redo logic here
    pass
```

The redo check happens **after** the attempt while-loop has already exited successfully. The step result is already recorded as success. The `pass` falls through to recording the step in `step_results` and moving to the next step.

### Structural Problem

The current flow is:
```
for step_num in steps_to_execute:        # outer: step loop
    while attempt < max_n_attempts:       # inner: attempt loop
        execute step
        if success: break

    # << redo check happens HERE, outside attempt loop
    if review_result is None: pass        # can't re-enter attempt loop

    step_results.append(...)              # step already recorded
```

To support redo, the step execution needs an **outer redo loop** around the entire attempt block.

### The Fix

**Replace the entire step execution block (lines 230-505)** with:

```python
# Execute steps
for step_num in steps_to_execute:
    step = plan_steps[step_num - 1]

    # Check for cancellation
    manager.raise_if_cancelled()

    # Update manager's current step
    manager.current_step = step_num

    print(f"\n{'='*60}")
    print(f"STEP {step_num}/{len(plan_steps)}: {step.get('sub_task', 'Unknown')}")
    print(f"{'='*60}\n")

    # Before-step approval
    if self.config.approval_mode in ["before_step", "both"]:
        approval_result = await self._request_step_approval(
            approval_manager,
            context,
            step,
            step_num,
            "before_step",
            current_context,
            manager
        )

        if approval_result is None:  # Skip
            skipped_steps.append(step_num)
            print(f"-> Step {step_num} skipped by human\n")
            continue
        elif approval_result is False:  # Rejected
            return manager.fail(f"Step {step_num} rejected by human", None)
        elif isinstance(approval_result, dict):  # Approved with feedback
            if 'feedback' in approval_result:
                feedback = approval_result['feedback']
                self._step_feedback.append({
                    'step': step_num,
                    'timing': 'before',
                    'feedback': feedback,
                })
                if self._accumulated_feedback:
                    self._accumulated_feedback += f"\n\n**Step {step_num} guidance:** {feedback}"
                else:
                    self._accumulated_feedback = f"**Step {step_num} guidance:** {feedback}"
                print(f"-> Human feedback for step {step_num}: {feedback}\n")
        # else: True (approved without feedback)

    # Notify callbacks
    step_desc = step.get('sub_task', f'Step {step_num}')
    manager.start_step(step_num, step_desc)

    # ── Redo loop wraps the entire execution + review cycle ──
    max_redos = 3  # Safety limit to prevent infinite redo loops
    redo_count = 0
    step_accepted = False

    while not step_accepted and redo_count <= max_redos:
        if redo_count > 0:
            print(f"\n-> Redoing step {step_num} (redo #{redo_count})...")
            # Collect redo feedback if provided
            redo_feedback_entry = self._step_feedback[-1] if self._step_feedback else None
            if redo_feedback_entry and redo_feedback_entry.get('timing') == 'redo':
                redo_reason = redo_feedback_entry.get('feedback', '')
                if self._accumulated_feedback:
                    self._accumulated_feedback += f"\n\n**Step {step_num} redo reason:** {redo_reason}"
                else:
                    self._accumulated_feedback = f"**Step {step_num} redo reason:** {redo_reason}"

        # Execute step (attempt loop)
        success = False
        attempt = 0
        step_result = None
        step_error = None
        cmbagent = None

        while attempt < self.config.max_n_attempts and not success:
            attempt += 1

            try:
                print(f"Executing step {step_num} (attempt {attempt}/{self.config.max_n_attempts})...")

                clear_work_dir = (step_num == 1 and redo_count == 0)
                starter_agent = "control" if step_num == 1 else "control_starter"

                cmbagent = CMBAgent(
                    cache_seed=42,
                    work_dir=control_dir,
                    clear_work_dir=clear_work_dir,
                    agent_llm_configs=agent_llm_configs,
                    mode="planning_and_control_context_carryover",
                    api_keys=api_keys,
                )

                # Configure AG2 HITL handoffs (if enabled)
                if self.config.use_ag2_handoffs:
                    from cmbagent.handoffs import register_all_hand_offs, enable_websocket_for_hitl
                    hitl_config = {
                        'mandatory_checkpoints': self.config.ag2_mandatory_checkpoints,
                        'smart_approval': self.config.ag2_smart_approval,
                        'smart_criteria': self.config.ag2_smart_criteria,
                    }
                    register_all_hand_offs(cmbagent, hitl_config=hitl_config)
                    if approval_manager:
                        try:
                            enable_websocket_for_hitl(cmbagent, approval_manager, context.run_id)
                        except Exception as e:
                            print(f"Warning: Could not enable WebSocket for AG2 handoffs: {e}")
                    else:
                        print(f"Warning: No approval_manager - AG2 handoffs will use console input")

                # Get agent for this step
                if step_num == 1 and plan_steps:
                    agent_for_step = plan_steps[0].get('sub_task_agent')
                else:
                    agent_for_step = current_context.get('agent_for_sub_task')

                # ── FEEDBACK INJECTION (Issue 1 fix) ──
                step_shared_context = copy.deepcopy(current_context)
                step_shared_context['current_plan_step_number'] = step_num
                step_shared_context['n_attempts'] = attempt - 1
                step_shared_context['agent_for_sub_task'] = agent_for_step

                # Build agent instructions: config + accumulated HITL feedback
                engineer_instructions = self.config.engineer_instructions or ""
                researcher_instructions = self.config.researcher_instructions or ""

                if self._accumulated_feedback:
                    safe_feedback = self._truncate_feedback(self._accumulated_feedback)
                    hitl_section = (
                        "\n\n## Human-in-the-Loop Feedback\n"
                        "The human reviewer has provided the following guidance. "
                        "You MUST follow these instructions:\n\n"
                        f"{safe_feedback}\n"
                    )
                    engineer_instructions += hitl_section
                    researcher_instructions += hitl_section

                # Step-specific before-feedback
                current_step_before = [
                    f for f in self._step_feedback
                    if f['step'] == step_num and f['timing'] == 'before'
                ]
                if current_step_before:
                    step_guidance = "\n\n## Specific Guidance for This Step\n"
                    for fb in current_step_before:
                        step_guidance += f"- {fb['feedback']}\n"
                    engineer_instructions += step_guidance
                    researcher_instructions += step_guidance

                step_shared_context['engineer_append_instructions'] = engineer_instructions
                step_shared_context['researcher_append_instructions'] = researcher_instructions

                # Execute
                cmbagent.solve(
                    task=context.task,
                    initial_agent=starter_agent,
                    max_rounds=self.config.max_rounds,
                    shared_context=step_shared_context,
                    step=step_num,
                )

                # Check for failures
                n_failures = cmbagent.final_context.get('n_attempts', 0)
                if n_failures >= self.config.max_n_attempts:
                    success = False
                    step_error = f"Max attempts ({n_failures}) exceeded"
                else:
                    success = True
                    step_result = cmbagent.final_context

                    # Extract step summary
                    this_step_summary = None
                    for msg in cmbagent.chat_result.chat_history[::-1]:
                        if 'name' in msg and agent_for_step:
                            agent_clean = agent_for_step.removesuffix("_context").removesuffix("_agent")
                            if msg['name'] in [agent_clean, f"{agent_clean}_nest", f"{agent_clean}_response_formatter"]:
                                this_step_summary = msg['content']
                                summary = f"### Step {step_num}\n{this_step_summary.strip()}"
                                # On redo, replace previous summary for this step
                                step_summaries = [
                                    s for s in step_summaries
                                    if not s.startswith(f"### Step {step_num}\n")
                                ]
                                step_summaries.append(summary)
                                cmbagent.final_context['previous_steps_execution_summary'] = "\n\n".join(
                                    s if isinstance(s, str) else str(s) for s in step_summaries
                                )
                                break

                    current_context = copy.deepcopy(cmbagent.final_context)

                if success:
                    print(f"Step {step_num} completed successfully")
                else:
                    print(f"Step {step_num} failed: {step_error}")

            except Exception as e:
                success = False
                step_error = str(e)
                print(f"Step {step_num} error: {step_error}")

            # On error, ask for human intervention if configured
            if not success and self.config.approval_mode in ["on_error", "both"]:
                action = await self._request_error_handling(
                    approval_manager, context, step, step_num,
                    step_error, attempt, manager
                )
                if action == "retry":
                    print(f"-> Retrying step {step_num}...")
                    continue
                elif action == "skip":
                    print(f"-> Skipping step {step_num}")
                    skipped_steps.append(step_num)
                    success = True
                    break
                elif action == "abort":
                    return manager.fail(f"Aborted by human at step {step_num}", None)

        # ── END attempt loop ──

        # Check final success
        if not success:
            manager.fail_step(step_num, step_error or "Max attempts exceeded")
            return manager.fail(
                f"Step {step_num} failed after {self.config.max_n_attempts} attempts",
                step_error
            )

        # After-step approval/review
        if self.config.approval_mode in ["after_step", "both"]:
            if not (self.config.auto_approve_successful_steps and success):
                review_result = await self._request_step_review(
                    approval_manager, context, step, step_num,
                    step_result, manager
                )

                if review_result is False:  # Abort
                    return manager.fail(f"Step {step_num} review rejected by human", None)

                elif review_result is None:  # Redo
                    redo_count += 1
                    if redo_count > max_redos:
                        print(f"-> Max redos ({max_redos}) reached for step {step_num}, continuing")
                        step_accepted = True
                    else:
                        print(f"-> Redo requested for step {step_num}")
                        human_interventions.append({
                            'step': step_num,
                            'action': 'redo',
                            'redo_count': redo_count,
                        })
                        # Continue the redo while-loop (don't set step_accepted)
                        continue

                elif isinstance(review_result, dict):  # Continue with feedback
                    if 'feedback' in review_result:
                        feedback = review_result['feedback']
                        self._step_feedback.append({
                            'step': step_num,
                            'timing': 'after',
                            'feedback': feedback,
                        })
                        if self._accumulated_feedback:
                            self._accumulated_feedback += f"\n\n**Step {step_num} notes:** {feedback}"
                        else:
                            self._accumulated_feedback = f"**Step {step_num} notes:** {feedback}"
                        print(f"-> Human notes for step {step_num}: {feedback}\n")
                    step_accepted = True
                else:
                    step_accepted = True
            else:
                step_accepted = True
        else:
            step_accepted = True

    # ── END redo loop ──

    # Record step result with chat history
    step_chat_history = []
    if cmbagent and hasattr(cmbagent, 'chat_result') and cmbagent.chat_result:
        step_chat_history = cmbagent.chat_result.chat_history or []
        all_chat_history.extend(step_chat_history)

    step_results.append({
        'step': step_num,
        'success': success,
        'result': step_result,
        'attempts': attempt,
        'redos': redo_count,
        'chat_history': step_chat_history,
    })

    # Save step context
    context_path = os.path.join(context_dir, f"context_step_{step_num}.pkl")
    filtered_context = {}
    for key, value in current_context.items():
        if key.startswith('_'):
            continue
        try:
            pickle.dumps(value)
            filtered_context[key] = value
        except (TypeError, pickle.PicklingError, AttributeError):
            print(f"[HITL] Skipping non-picklable context key: {key}")
    with open(context_path, 'wb') as f:
        pickle.dump(filtered_context, f)
    manager.track_file(context_path)

    # Save chat history
    chat_full_path = os.path.join(control_dir, "chats")
    os.makedirs(chat_full_path, exist_ok=True)
    chat_output_path = os.path.join(chat_full_path, f"chat_history_step_{step_num}.json")
    with open(chat_output_path, 'w') as f:
        json.dump(step_chat_history, f, indent=2)
    manager.track_file(chat_output_path)

    # Display cost
    if cmbagent:
        if not hasattr(cmbagent, 'groupchat'):
            Dummy = type('Dummy', (object,), {'new_conversable_agents': []})
            cmbagent.groupchat = Dummy()
        cmbagent.display_cost(name_append=f"step_{step_num}")

    manager.complete_step(step_num, "Step completed")
    print(f"\nStep {step_num} completed in control phase\n")
```

### Redo Edge Cases Handled

| Scenario | Behavior |
|----------|----------|
| Redo with no feedback | Re-executes step cleanly; no extra feedback injected |
| Redo with feedback | Feedback added as "redo reason" to accumulated feedback; agents see it on re-execution |
| Multiple redos | Capped at `max_redos=3` to prevent infinite loops; after limit, step is accepted anyway |
| Redo on step 1 | `clear_work_dir` only on first execution (`redo_count == 0`), not on redo |
| Redo after step summaries recorded | Previous summary for this step is **replaced** (not duplicated) via list filter |
| Redo count in step_results | Recorded in output so downstream can see how many redos occurred |

### Why `max_redos = 3`?

Without a limit, a user could redo indefinitely. Each redo:
- Creates a new `CMBAgent` instance (memory cost)
- Runs a full agent conversation (API cost)
- Could produce identical results if no feedback is given

The limit prevents accidental infinite loops from a stuck UI or automated testing.

---

## Issue 3: Redo with Feedback from `_request_step_review`

### Root Cause

When the user selects "redo", `_request_step_review` returns `None` (line 716). But there's no way to capture **why** the user wants a redo — `user_feedback` is only checked when `resolution == "continue"` (line 712).

### The Fix

**File**: `cmbagent/phases/hitl_control.py`, method `_request_step_review` (lines 710-718)

**Current code:**
```python
if resolved.resolution == "continue":
    if hasattr(resolved, 'user_feedback') and resolved.user_feedback:
        return {'continue': True, 'feedback': resolved.user_feedback}
    return True
elif resolved.resolution == "redo":
    return None
else:
    return False
```

**Replace with:**
```python
if resolved.resolution == "continue":
    if hasattr(resolved, 'user_feedback') and resolved.user_feedback:
        return {'continue': True, 'feedback': resolved.user_feedback}
    return True
elif resolved.resolution == "redo":
    # Capture redo feedback so agents know what to fix on re-execution
    redo_feedback = getattr(resolved, 'user_feedback', None) or ''
    if redo_feedback:
        return {'redo': True, 'feedback': redo_feedback}
    return None  # Redo without specific feedback
else:
    return False
```

Then update the redo handler in the main loop to handle both `None` and `dict` with `redo`:

```python
elif review_result is None or (isinstance(review_result, dict) and review_result.get('redo')):
    redo_count += 1
    # Capture redo feedback if provided
    if isinstance(review_result, dict) and review_result.get('feedback'):
        redo_feedback = review_result['feedback']
        self._step_feedback.append({
            'step': step_num,
            'timing': 'redo',
            'feedback': redo_feedback,
        })
        if self._accumulated_feedback:
            self._accumulated_feedback += f"\n\n**Step {step_num} redo requested:** {redo_feedback}"
        else:
            self._accumulated_feedback = f"**Step {step_num} redo requested:** {redo_feedback}"
        print(f"-> Redo step {step_num} with feedback: {redo_feedback}")

    if redo_count > max_redos:
        print(f"-> Max redos ({max_redos}) reached for step {step_num}, continuing")
        step_accepted = True
    else:
        human_interventions.append({
            'step': step_num,
            'action': 'redo',
            'redo_count': redo_count,
            'feedback': review_result.get('feedback') if isinstance(review_result, dict) else None,
        })
        continue  # Re-enter redo loop
```

---

## Issue 4: Planning "Approve with Feedback" Missing

### Root Cause

**File**: `cmbagent/phases/hitl_planning.py`, lines 312-317

```python
if resolved.resolution in ["approved", "approve"]:
    approved = True
    final_plan = plan
    final_context = planning_context
    print("\n Plan approved by human\n")
```

If a user approves BUT also writes feedback (e.g., "Approved. Make sure step 2 uses pandas"), the feedback is silently discarded. The `resolved.user_feedback` is never checked on the "approve" path.

### The Fix

**File**: `cmbagent/phases/hitl_planning.py`, lines 312-317

**Replace with:**
```python
if resolved.resolution in ["approved", "approve"]:
    approved = True
    final_plan = plan
    final_context = planning_context
    print("\n Plan approved by human\n")

    # Capture approval-time feedback for the control phase
    if hasattr(resolved, 'user_feedback') and resolved.user_feedback:
        human_feedback_history.append({
            'iteration': iteration,
            'plan': plan,
            'feedback': resolved.user_feedback,
            'type': 'approval_note',  # Distinguish from revision feedback
        })
        print(f"-> Approval note: {resolved.user_feedback}")
```

This ensures that even when approving, any feedback text is captured in `human_feedback_history`, which flows to `combined_feedback` (line 408), which becomes `hitl_feedback` in shared state (line 423), which the control phase loads (line 192) and (with Issue 1 fix) injects into agents.

---

## Issue 5: `_request_step_review` — Console Fallback Doesn't Support Redo

### Root Cause

**File**: `cmbagent/phases/hitl_control.py`, lines 671-679

```python
if not approval_manager:
    # Console fallback
    ...
    response = input("\nContinue? (y/n): ").strip().lower()
    return response == 'y' or response == 'yes'
```

Console fallback only offers y/n. No redo option. No feedback capture.

### The Fix

```python
if not approval_manager:
    print(f"\n{'='*60}")
    print(f"STEP {step_num} REVIEW")
    print(f"{'='*60}")
    print("Step completed successfully")
    print(f"{'='*60}")
    response = input("\nAction? (c=continue/r=redo/a=abort/[feedback]): ").strip()

    lower = response.lower()
    if lower in ('c', 'continue', 'y', 'yes'):
        return True
    elif lower in ('r', 'redo'):
        return None
    elif lower in ('a', 'abort', 'n', 'no'):
        return False
    else:
        # Treat any other input as "continue with feedback"
        return {'continue': True, 'feedback': response}
```

---

## Issue 6: `_request_step_approval` — Console Fallback Doesn't Capture Feedback

### Root Cause

**File**: `cmbagent/phases/hitl_control.py`, lines 605-618

```python
if not approval_manager:
    ...
    response = input("\nApprove step? (y/n/s=skip): ").strip().lower()
    if response == 'y' or response == 'yes':
        return True
    elif response == 's' or response == 'skip':
        return None
    else:
        return False
```

No way to approve **with feedback** via console.

### The Fix

```python
if not approval_manager:
    print(f"\n{'='*60}")
    print(f"STEP {step_num} APPROVAL")
    print(f"{'='*60}")
    print(f"Task: {step.get('sub_task')}")
    print(f"{'='*60}")
    response = input("\nAction? (y=approve/n=reject/s=skip/[feedback to approve with]): ").strip()

    lower = response.lower()
    if lower in ('y', 'yes'):
        return True
    elif lower in ('s', 'skip'):
        return None
    elif lower in ('n', 'no'):
        return False
    else:
        # Treat any other text as "approve with feedback"
        return {'approved': True, 'feedback': response}
```

---

## Issue 7: `_build_step_review_message` — No Step Result Details

### Root Cause

The review message (line 807-819) says "Completed successfully" but doesn't show **what** the step produced. The user can't make an informed redo/continue decision.

### The Fix

```python
def _build_step_review_message(self, step: Dict, step_num: int, result: Dict) -> str:
    """Build message for step review with result details."""
    # Extract meaningful result info
    result_summary = ""
    if result and isinstance(result, dict):
        # Show step summary if available
        summary = result.get('previous_steps_execution_summary', '')
        if summary:
            # Get only this step's summary
            lines = summary.split(f"### Step {step_num}\n")
            if len(lines) > 1:
                step_text = lines[-1].split("### Step")[0].strip()
                result_summary = f"\n**Result Summary:**\n{step_text[:1000]}\n"

    return f"""**Step {step_num} Review**

**Task:** {step.get('sub_task', 'Unknown')}

**Status:** Completed successfully
{result_summary}
**Options:**
- **Continue**: Proceed to next step
- **Redo**: Re-execute this step (optionally provide feedback on what to change)
- **Abort**: Cancel the workflow
"""
```

---

## Issue 8: `_build_step_approval_message` — No Feedback From Previous Steps

The before-step approval message just says "Previous steps completed successfully" but doesn't show what was done. Add previous step summaries to give context.

### The Fix

```python
def _build_step_approval_message(self, step: Dict, step_num: int, context: Dict) -> str:
    """Build message for step approval with context."""
    parts = [
        f"**Step {step_num}**",
        "",
        f"**Task:** {step.get('sub_task', 'Unknown')}",
        "",
    ]

    if self.config.show_step_context and step_num > 1:
        prev_summary = context.get('previous_steps_execution_summary', '')
        if prev_summary:
            # Show last 500 chars to keep message reasonable
            summary_text = prev_summary[-500:] if len(prev_summary) > 500 else prev_summary
            parts.extend([
                "**Previous Steps Summary:**",
                summary_text,
                "",
            ])

    if self._accumulated_feedback:
        parts.extend([
            "**Accumulated Human Feedback:**",
            self._accumulated_feedback[-300:] if len(self._accumulated_feedback) > 300 else self._accumulated_feedback,
            "",
        ])

    parts.extend([
        "**Options:**",
        "- **Approve**: Execute this step",
        "- **Skip**: Skip this step and continue",
        "- **Reject**: Cancel the workflow",
        "",
        "You can also provide feedback text that will guide the agent during execution.",
    ])

    return "\n".join(parts)
```

---

## New Helper Method

Add this method to the `HITLControlPhase` class:

```python
def _truncate_feedback(self, feedback: str, max_chars: int = 4000) -> str:
    """Truncate accumulated feedback to prevent context overflow.

    Keeps most recent feedback since it's most relevant to current step.
    """
    if not feedback or len(feedback) <= max_chars:
        return feedback

    truncated = feedback[-(max_chars):]
    # Find first complete section boundary to avoid mid-sentence cut
    boundary = truncated.find('\n\n**Step')
    if boundary > 0:
        truncated = truncated[boundary:]

    return f"[Earlier feedback truncated]\n{truncated}"
```

---

## Complete Change Summary

| File | Method/Location | Change | Lines |
|------|----------------|--------|-------|
| `hitl_control.py` | Step execution block | Wrap in redo loop, inject feedback into agents | 230-505 |
| `hitl_control.py` | `_request_step_review` | Return redo feedback as dict | 710-718 |
| `hitl_control.py` | `_request_step_review` console fallback | Add redo + feedback options | 671-679 |
| `hitl_control.py` | `_request_step_approval` console fallback | Add feedback capture | 605-618 |
| `hitl_control.py` | `_build_step_review_message` | Show step result details | 807-819 |
| `hitl_control.py` | `_build_step_approval_message` | Show prev summaries + feedback | 783-805 |
| `hitl_control.py` | New method | `_truncate_feedback` | New |
| `hitl_planning.py` | Approve resolution handler | Capture approval-time feedback | 312-317 |

---

## Testing Scenarios

After implementing, these scenarios must work:

1. **Feedback flows to agents**: Give before-step feedback "use pandas" → agent's `{engineer_append_instructions}` contains "use pandas"
2. **Accumulated feedback across steps**: Give feedback on step 1 → step 2 agent sees step 1 feedback
3. **Redo without feedback**: Select redo → step re-executes cleanly
4. **Redo with feedback**: Select redo + "fix the bug in line 5" → re-executed agent sees "fix the bug in line 5"
5. **Max redos enforced**: Redo 4 times → after 3rd redo, step is accepted
6. **Planning approval with feedback**: Approve plan + "remember to handle edge cases" → control phase agents see this
7. **Redo doesn't duplicate summaries**: After redo, `step_summaries` has only one entry for that step
8. **Redo resets attempt counter**: After redo, attempts start from 1 again
9. **Console fallback redo**: In console mode, typing "r" triggers redo
10. **Feedback truncation**: With 50+ feedbacks, instructions don't explode beyond 4000 chars
