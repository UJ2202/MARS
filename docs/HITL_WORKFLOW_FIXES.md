# HITL Workflow Fixes - Complete

## Issues Fixed

### Issue #1: Approval Not Working ("approve" vs "approved")
**Error:** User clicks "approve" but system treats it as "revise" request
**Root Cause:** Frontend sends "approve", backend expects "approved"

**Fixed in:**
- `cmbagent/phases/hitl_planning.py` (lines 312-339)
- `cmbagent/phases/hitl_control.py` (line 605)

**Changes:**
```python
# Before
if resolved.resolution == "approved":
    approved = True

# After
if resolved.resolution in ["approved", "approve"]:
    approved = True
```

**Also fixed:**
- "rejected" vs "reject"
- "modified" vs "modify"

---

### Issue #2: "list index out of range" Error
**Error:** `list index out of range` after MessageHistoryLimiter runs
**Root Cause:** Nested chat summary method tries to access `messages[-1]` but message list is empty after limiter clears all messages

**Fixed in:**
- `cmbagent/handoffs/nested_chats.py` (lines 43-58, 112-127)

**Changes:**
```python
# Before
nested_chats = [{
    "message": lambda recipient, messages, sender, config: (
        f"{messages[-1]['content']}" if messages else ""
    ),
    "summary_method": "last_msg",  # Fails on empty list
}]

# After
def safe_summary(sender, recipient, summary_args):
    """Safely get last message or return empty string."""
    messages = summary_args.get("messages", [])
    if messages and len(messages) > 0:
        return messages[-1].get('content', '')
    return ""

nested_chats = [{
    "message": lambda recipient, messages, sender, config: (
        f"{messages[-1]['content']}" if messages and len(messages) > 0 else ""
    ),
    "summary_method": safe_summary,  # Safe handling
}]
```

**Applied to:**
1. Engineer nested chat (lines 43-58)
2. Idea maker nested chat (lines 112-127)

---

## Files Modified

### 1. `cmbagent/phases/hitl_planning.py`
**Lines changed:** 312-339

**What changed:**
- Line 313: `if resolved.resolution == "approved"` → `if resolved.resolution in ["approved", "approve"]`
- Line 319: `elif resolved.resolution == "rejected"` → `elif resolved.resolution in ["rejected", "reject"]`
- Line 328: `elif resolved.resolution == "modified"` → `elif resolved.resolution in ["modified", "modify"]`
- Line 339: `else:  # revise` → `else:  # revise or any other value`

**Impact:** Approvals now work correctly regardless of frontend sending "approve" or "approved"

---

### 2. `cmbagent/phases/hitl_control.py`
**Lines changed:** 604-613

**What changed:**
- Line 605: `if resolved.resolution == "approved"` → `if resolved.resolution in ["approved", "approve"]`
- Added comment: "Accept both 'approved' and 'approve'"

**Impact:** Step approvals work correctly

---

### 3. `cmbagent/phases/hitl_checkpoint.py`
**Lines changed:** 177-206

**What changed:**
- Line 178: `if resolved.resolution == "rejected"` → `if resolved.resolution in ["rejected", "reject"]`
- Line 194: `elif resolved.resolution == "modified"` → `elif resolved.resolution in ["modified", "modify"]`
- Line 206: `else:  # approved` → `else:  # approved or approve`
- Added comment: "Accept both 'rejected'/'reject' and 'modified'/'modify'"

**Impact:** Checkpoint phase approvals work correctly with both forms

---

### 4. `cmbagent/handoffs/nested_chats.py`
**Lines changed:** 43-58 (engineer), 112-127 (idea maker)

**What changed:**
- Added `safe_summary()` function (lines 44-49, 113-118)
- Updated message lambda: `if messages else ""` → `if messages and len(messages) > 0 else ""`
- Changed summary_method: `"last_msg"` → `safe_summary`

**Impact:** No more "list index out of range" errors when message history limiter runs

---

## Testing

### Test 1: Approval Resolution
```python
# Test that all approval variations work
resolutions_to_test = [
    "approve",   # From frontend
    "approved",  # Expected by backend
    "reject",
    "rejected",
    "modify",
    "modified",
    "revise",
]

# All should now be handled correctly
```

### Test 2: Empty Message List
```python
# Test nested chat with empty messages
messages = []
result = safe_summary(None, None, {"messages": messages})
assert result == ""  # Should not crash

messages = [{"content": "test"}]
result = safe_summary(None, None, {"messages": messages})
assert result == "test"
```

---

## How to Verify Fixes

### Verification Step 1: Approval Works
1. Start HITL workflow
2. Wait for plan approval request
3. Click "Approve" in UI
4. **Expected:** Plan is approved and workflow continues
5. **Before fix:** Plan treated as "revise" request, max iterations reached

### Verification Step 2: No Crash on Message History Limit
1. Start HITL control phase
2. Let step execute with many messages
3. Wait for MessageHistoryLimiter to clear messages
4. **Expected:** Workflow continues without error
5. **Before fix:** "list index out of range" crash

---

## Root Cause Analysis

### Why Approval Didn't Work

**Frontend (UI):**
```javascript
// Sends action without "-ed" suffix
sendApproval({ action: "approve" })  // "approve", "reject", "modify"
```

**Backend (WebSocket Handler):**
```python
# Receives and passes through as-is
WebSocketApprovalManager.resolve(
    approval_id=approval_id,
    resolution=resolution,  # "approve" (no transformation)
)
```

**Phase (HITL Planning):**
```python
# Expected "-ed" suffix
if resolved.resolution == "approved":  # Fails! Got "approve"
    approved = True
else:  # Falls through to here
    # Treats as "revise"
```

**Fix:** Accept both forms in phases

---

### Why Message List Was Empty

**Flow:**
1. Agent conversation runs, accumulates messages
2. Engineer hands off to nested chat for execution
3. **MessageHistoryLimiter runs** (configured in `message_limiting.py`)
   ```python
   MessageHistoryLimiter(max_messages=1)
   # Removes all but 1 message
   # In some cases, removes ALL messages
   ```
4. Nested chat tries to summarize: `summary_method="last_msg"`
5. Summary method accesses: `messages[-1]`  # IndexError!

**Fix:** Custom summary function with empty list handling

---

## Prevention

### For Future Approval Fields

**Pattern to use:**
```python
# Always accept multiple forms
if resolved.resolution in ["approved", "approve"]:
    # Handle approval

elif resolved.resolution in ["rejected", "reject"]:
    # Handle rejection
```

### For Message List Access

**Pattern to use:**
```python
# Always check length before indexing
def safe_access(messages):
    if messages and len(messages) > 0:
        return messages[-1]['content']
    return default_value
```

**Or use custom summary:**
```python
def safe_summary(sender, recipient, summary_args):
    messages = summary_args.get("messages", [])
    if messages and len(messages) > 0:
        return messages[-1].get('content', '')
    return ""

nested_chats = [{
    "summary_method": safe_summary,
}]
```

---

## Additional Improvements Made

### 1. Better Error Messages
Added comments explaining what each resolution means:
```python
# Accept both "approved" and "approve"
if resolved.resolution in ["approved", "approve"]:
```

### 2. More Robust Lambda Functions
```python
# Before
lambda recipient, messages, sender, config: f"{messages[-1]['content']}" if messages else ""

# After
lambda recipient, messages, sender, config: (
    f"{messages[-1]['content']}" if messages and len(messages) > 0 else ""
)
```

---

## Compatibility

### Backward Compatible?
**Yes!** All changes are backward compatible:
- Old code sending "approved" still works
- New code sending "approve" now works
- Empty message lists handled gracefully

### Breaking Changes?
**None!**

---

## Summary

**Fixed 2 critical bugs:**
1. ✅ Approval not working (resolution string mismatch)
2. ✅ "list index out of range" crash (MessageHistoryLimiter + nested chats)

**Files modified:**
- ✏️ `cmbagent/phases/hitl_planning.py`
- ✏️ `cmbagent/phases/hitl_control.py`
- ✏️ `cmbagent/phases/hitl_checkpoint.py` (additional fix)
- ✏️ `cmbagent/handoffs/nested_chats.py`

**Impact:**
- Approvals now work correctly across ALL HITL phases
- No more crashes from empty message lists
- More robust error handling

**Status:** ✅ Fixed and ready to test!

---

## Next Steps

1. **Test approval flow:** Create HITL workflow, click "Approve", verify it works
2. **Test message limiting:** Run long conversation, verify no crashes
3. **Test error recovery:** Try "reject", "skip", "modify" options
4. **Monitor logs:** Watch for any remaining edge cases

---

**Date:** 2026-02-10
**Tested:** Pending user verification
**Status:** ✅ Complete
