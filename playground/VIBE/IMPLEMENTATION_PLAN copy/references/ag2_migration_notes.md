# AG2 Migration Notes

**Migration Date:** 2026-01-14
**From:** cmbagent_autogen 0.0.91post11 (custom fork)
**To:** ag2[openai] 0.10.3 (official release)

---

## Quick Reference

### Old Import Patterns → New Import Patterns

```python
# OLD (Custom Fork)
from autogen.cmbagent_utils import cmbagent_debug
from autogen.cmbagent_utils import LOGO, IMG_WIDTH
from autogen import cmbagent_debug
cmbagent_debug = autogen.cmbagent_debug

# NEW (Official AG2 + Local Utils)
from cmbagent.cmbagent_utils import cmbagent_debug
from cmbagent.cmbagent_utils import LOGO, IMG_WIDTH, cmbagent_disable_display
```

### AG2 Imports (Unchanged)

These imports work the same way in both versions:

```python
import autogen
from autogen.agentchat.group import ContextVariables
from autogen.agentchat.group.patterns import AutoPattern
from autogen.agentchat import ConversableAgent, UserProxyAgent
from autogen import GroupChatManager, GroupChat, register_function
from autogen.coding import LocalCommandLineCodeExecutor
from autogen.agentchat.contrib.gpt_assistant_agent import GPTAssistantAgent
from autogen.agentchat.group import AgentTarget, ReplyResult, TerminateTarget
from autogen.agentchat.group import OnCondition, StringLLMCondition
from autogen.agentchat.contrib.capabilities.transform_messages import TransformMessages
from autogen.agentchat.contrib.capabilities.transforms import MessageHistoryLimiter
from autogen.agentchat import initiate_group_chat
```

---

## Custom Fork Features → Local Implementation

### 1. `cmbagent_utils` Module

**Location:** `cmbagent/cmbagent_utils.py`

**Contents:**

| Feature | Type | Default Value | Description |
|---------|------|---------------|-------------|
| `cmbagent_debug` | bool | `False` | Debug mode flag |
| `file_search_max_num_results` | int | `10` | Max results for file search |
| `cmbagent_color_dict` | dict | `{"admin": "green", "control": "red"}` | Agent color mapping |
| `cmbagent_default_color` | str | `"yellow"` | Default agent color |
| `LOGO` | str | ASCII art | CMBAgent logo |
| `IMG_WIDTH` | int | Calculated | Image width for display |
| `cmbagent_disable_display` | bool | From env var | Disable display in headless mode |

**Usage:**

```python
from cmbagent.cmbagent_utils import (
    cmbagent_debug,
    file_search_max_num_results,
    LOGO,
    IMG_WIDTH,
    cmbagent_disable_display
)

# Check if debug mode
if cmbagent_debug:
    print("Debug info here")

# Use in display logic
if not cmbagent_disable_display:
    display(Image(filename=path, width=IMG_WIDTH))
```

### 2. Debug Messages in AG2 Core

**Custom Fork Had:**
- Debug printing in `autogen/messages/agent_messages.py`
- Conditional messages for specific CMBAgent agents
- "Forwarding content for formatting..." messages

**Migration Strategy:**
- **Not ported** - These were internal AG2 modifications
- **Impact:** Debug messages don't appear, but functionality unchanged
- **Alternative:** Add debug logging at application level if needed

**Example (if needed):**

```python
# In your agent code
if cmbagent_debug:
    print(f"[DEBUG] Agent {agent_name} forwarding to {target_agent}")
```

---

## Breaking Changes Analysis

### API Changes from Custom Fork → AG2 0.10.3

**None identified.** All APIs used by CMBAgent are compatible.

### Deprecation Warnings

**None observed** in basic testing.

### Behavioral Changes

**None identified** that affect CMBAgent functionality.

---

## Testing Checklist

Use this checklist when testing the migration:

### Basic Functionality
- [ ] Import `cmbagent` package
- [ ] Import `one_shot` function
- [ ] Import all AG2 classes used
- [ ] Logo displays correctly
- [ ] Debug flags accessible

### Agent System
- [ ] Create ConversableAgent instances
- [ ] Initialize GroupChat
- [ ] Set up hand-off chains
- [ ] Use ContextVariables
- [ ] Execute nested chats

### CMBAgent Workflows
- [ ] Run `one_shot()` execution
- [ ] Test planning and control
- [ ] Verify context carryover
- [ ] Check RAG agent queries
- [ ] Test code execution

### Edge Cases
- [ ] Headless mode (CMBAGENT_DISABLE_DISPLAY=true)
- [ ] Debug mode enabled
- [ ] Large context windows
- [ ] Multiple concurrent sessions

---

## Common Issues & Solutions

### Issue 1: ModuleNotFoundError: No module named 'autogen.cmbagent_utils'

**Symptom:**
```
ImportError: cannot import name 'cmbagent_utils' from 'autogen'
```

**Solution:**
```python
# Change this:
from autogen.cmbagent_utils import cmbagent_debug

# To this:
from cmbagent.cmbagent_utils import cmbagent_debug
```

### Issue 2: AttributeError: module 'autogen' has no attribute 'cmbagent_debug'

**Symptom:**
```
AttributeError: module 'autogen' has no attribute 'cmbagent_debug'
```

**Solution:**
```python
# Change this:
cmbagent_debug = autogen.cmbagent_debug

# To this:
from cmbagent.cmbagent_utils import cmbagent_debug
```

### Issue 3: AttributeError: module 'autogen' has no attribute 'file_search_max_num_results'

**Symptom:**
```
AttributeError: module 'autogen' has no attribute 'file_search_max_num_results'
```

**Solution:**
```python
# Change this:
file_search_max_num_results = autogen.file_search_max_num_results

# To this:
from cmbagent.cmbagent_utils import file_search_max_num_results
```

---

## AG2 Version History

### AG2 0.10.3 (Current - Latest Stable)
- Released: December 2025
- Status: **Stable - Recommended**
- Python: 3.10+, <3.14
- Key Features:
  - Mature agent orchestration
  - Group chat patterns
  - Context management
  - Tool/function calling
  - OpenAI integration

### Earlier Versions
- 0.9.x: Previous stable series
- 0.8.x: Earlier stable release
- 0.7.x: Beta releases
- 0.6.x and below: Early development

### Custom Fork (cmbagent_autogen 0.0.91post11)
- Based on: AutoGen ~0.2.34
- Custom modifications:
  - Added `cmbagent_utils` module
  - Debug logging in agent messages
  - CMBAgent-specific utilities
- Status: **Deprecated** ❌

---

## Future Upgrade Path

### When to Upgrade

Consider upgrading AG2 when:
1. Security patches are released
2. Critical bug fixes are available
3. New features align with roadmap needs
4. After 3-6 months of stability testing by community

### Upgrade Process

1. **Check Release Notes**
   - Visit: https://github.com/ag2ai/ag2/releases
   - Review breaking changes
   - Note deprecated APIs

2. **Test in Development**
   ```bash
   # Create test environment
   python -m venv test_env
   source test_env/bin/activate
   pip install cmbagent
   pip install --upgrade ag2[openai]

   # Run tests
   python tests/test_one_shot.py
   ```

3. **Update pyproject.toml**
   ```toml
   "ag2[openai]>=0.11.0",  # or whatever version
   ```

4. **Verify Compatibility**
   - Run all tests
   - Check for deprecation warnings
   - Test key workflows

5. **Deploy**
   - Update in production
   - Monitor for issues
   - Roll back if needed

---

## Resources

### Official AG2 Documentation
- Homepage: https://ag2.ai/
- Docs: https://docs.ag2.ai/
- GitHub: https://github.com/ag2ai/ag2
- Discord: https://discord.gg/sNGSwQME3x

### CMBAgent Documentation
- Project: https://github.com/CMBAgents/cmbagent
- Implementation Plan: `IMPLEMENTATION_PLAN/README.md`
- Progress Tracker: `IMPLEMENTATION_PLAN/PROGRESS.md`

### Migration Support
- Stage 1 Summary: `IMPLEMENTATION_PLAN/STAGE_01_SUMMARY.md`
- This Document: `IMPLEMENTATION_PLAN/references/ag2_migration_notes.md`

---

## Changelog

### 2026-01-14: Initial Migration
- Upgraded from `cmbagent_autogen 0.0.91post11` to `ag2[openai] 0.10.3`
- Created `cmbagent/cmbagent_utils.py` module
- Updated 9 files with import changes
- All tests passing
- No breaking changes detected

---

**Last Updated:** 2026-01-14
**Maintained By:** CMBAgent Development Team
