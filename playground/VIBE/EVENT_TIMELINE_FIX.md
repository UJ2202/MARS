# Event Timeline Fix Summary

## Problem Identified

The history timeline tabs in the UI were showing empty data because the backend was returning empty results for node events, even though events were correctly stored in the database.

## Root Cause

The issue was in the **session management logic**:

1. **Flawed Default Session Logic**: The `SessionManager.get_or_create_default_session()` method was returning the "most recently active" session from ALL active sessions in the database, not a fixed default session.

2. **Session Mismatch**: 
   - When a workflow executed, it created DAG nodes and events in whatever session happened to be "most recently active" at that moment
   - Later, when the UI queried for events, it used a DIFFERENT "most recently active" session (especially after test runs created new sessions)
   - The backend query filtered events by `session_id`, so it couldn't find events created in a different session

3. **Over-Filtering**: The `EventRepository.list_events_for_node()` method always filtered by `session_id`, even though `node_id` is already unique and sufficient for querying.

## Solution Applied

### 1. Fixed Session Manager (`cmbagent/database/session_manager.py`)

Changed `get_or_create_default_session()` to use a **fixed session ID** (`"default_session"`):

```python
def get_or_create_default_session(self) -> str:
    """Get or create the default session."""
    DEFAULT_SESSION_ID = "default_session"
    
    # Try to find the default session by ID
    default_session = self.repo.get_session(DEFAULT_SESSION_ID)
    
    if default_session:
        self.repo.update_last_active(DEFAULT_SESSION_ID)
        return DEFAULT_SESSION_ID
    
    # Create the default session with fixed ID
    # ...
```

**Before**: Returned different sessions based on "most recently active"  
**After**: Always returns the same `"default_session"` ID

### 2. Made Session Filtering Optional (`cmbagent/database/repository.py`)

Updated `list_events_for_node()` to accept a `filter_by_session` parameter:

```python
def list_events_for_node(
    self,
    node_id: str,
    event_type: Optional[str] = None,
    filter_by_session: bool = False  # NEW: defaults to False
) -> List[ExecutionEvent]:
    """List events for a DAG node."""
    query = self.db.query(ExecutionEvent).filter(
        ExecutionEvent.node_id == node_id
    )
    
    # Only filter by session if explicitly requested
    if filter_by_session:
        query = query.filter(ExecutionEvent.session_id == self.session_id)
    
    # ...
```

**Rationale**: Since `node_id` is unique, we don't need to filter by session when querying events for a specific node.

### 3. Updated Backend API (`backend/main.py`)

Modified the `/api/nodes/{node_id}/events` endpoint to pass `filter_by_session=False`:

```python
@app.get("/api/nodes/{node_id}/events")
async def get_node_events(node_id: str, ...):
    # ...
    events = event_repo.list_events_for_node(
        node_id, 
        event_type=event_type,
        filter_by_session=False  # Get all events for this node
    )
    # ...
```

## Verification

Tested with existing data and confirmed:
- ✅ Backend API now returns events correctly for all nodes
- ✅ Session manager consistently returns the same default session
- ✅ Events are retrieved regardless of which session they were created in

## Impact

- **Backward Compatible**: Existing events in old sessions are now accessible
- **Forward Compatible**: New workflows will use the fixed "default_session"
- **UI Fixed**: History timeline tabs will now display event data correctly

## Files Modified

1. `/srv/projects/mas/mars/denario/cmbagent/cmbagent/database/session_manager.py`
2. `/srv/projects/mas/mars/denario/cmbagent/cmbagent/database/repository.py`
3. `/srv/projects/mas/mars/denario/cmbagent/backend/main.py`
