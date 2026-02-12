"""
Durable context management for copilot sessions.

Provides enhanced context persistence, deep copying, versioning,
and serialization support to ensure context survives across:
- Multiple copilot rounds
- Phase invocations
- Session continuations
- Orchestrator restarts
"""

import copy
import json
import time
import pickle
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ContextSnapshot:
    """A point-in-time snapshot of context."""
    version: int
    timestamp: float
    reason: str  # Why snapshot was taken: "phase_start", "phase_end", "checkpoint", etc.
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'version': self.version,
            'timestamp': self.timestamp,
            'reason': self.reason,
            'data': self.data,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextSnapshot':
        """Create from dictionary."""
        return cls(
            version=data['version'],
            timestamp=data['timestamp'],
            reason=data['reason'],
            data=data['data'],
            metadata=data.get('metadata', {}),
        )


class DurableContext:
    """
    Enhanced context manager with durability features.
    
    Features:
    - Deep copying to prevent reference issues
    - Context snapshots for rollback
    - Versioning for tracking changes
    - Serialization for persistence
    - Separation of persistent vs ephemeral data
    - Smart merging strategies
    
    Usage:
        ctx = DurableContext(session_id="abc123")
        ctx.set("key", value)
        ctx.set_ephemeral("temp_key", temp_value)
        
        # Before phase invocation
        snapshot = ctx.create_snapshot("phase_start")
        phase_context = ctx.get_phase_context()
        
        # After phase completion
        ctx.merge_phase_results(phase_results, strategy="safe")
        
        # Persistence
        ctx.save_to_disk("./context.json")
        ctx2 = DurableContext.load_from_disk("./context.json")
    """

    def __init__(
        self,
        session_id: str,
        initial_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize durable context.
        
        Args:
            session_id: Unique session identifier
            initial_data: Initial context data
        """
        self.session_id = session_id
        self.version = 0
        self.created_at = time.time()
        self.updated_at = time.time()
        
        # Persistent data - survives phase invocations
        self._persistent: Dict[str, Any] = {}
        
        # Ephemeral data - cleared after each round or phase
        self._ephemeral: Dict[str, Any] = {}
        
        # Keys that should never be overwritten
        self._protected_keys: Set[str] = {
            'session_id', 'run_id', 'workflow_id', 'initial_task',
        }
        
        # Snapshot history
        self._snapshots: List[ContextSnapshot] = []
        self._max_snapshots = 50  # Keep last 50 snapshots
        
        # Change log
        self._change_log: List[Dict[str, Any]] = []
        self._max_changes = 200  # Keep last 200 changes
        
        # Initialize with data
        if initial_data:
            self._persistent.update(initial_data)
            self._log_change("initialize", {"keys": list(initial_data.keys())})
    
    def set(
        self,
        key: str,
        value: Any,
        protected: bool = False,
        deep_copy: bool = True,
    ) -> None:
        """
        Set a persistent value in context.
        
        Args:
            key: Context key
            value: Value to store
            protected: If True, key cannot be overwritten
            deep_copy: If True, deep copy the value
        """
        # Allow re-setting protected keys to the same value (idempotent)
        if key in self._protected_keys and key in self._persistent:
            old_value = self._persistent[key]
            if old_value == value:
                # Same value, silently succeed (idempotent)
                return
            else:
                raise ValueError(f"Cannot overwrite protected key: {key} (old={old_value}, new={value})")
        
        # Deep copy to prevent reference issues
        stored_value = copy.deepcopy(value) if deep_copy else value
        
        old_value = self._persistent.get(key)
        self._persistent[key] = stored_value
        
        if protected:
            self._protected_keys.add(key)
        
        self.version += 1
        self.updated_at = time.time()
        
        self._log_change("set", {
            "key": key,
            "had_previous": old_value is not None,
            "protected": protected,
        })
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from context.
        
        Checks persistent then ephemeral storage.
        
        Args:
            key: Context key
            default: Default value if not found
            
        Returns:
            Stored value or default
        """
        if key in self._persistent:
            return self._persistent[key]
        if key in self._ephemeral:
            return self._ephemeral[key]
        return default
    
    def set_ephemeral(self, key: str, value: Any, deep_copy: bool = True) -> None:
        """
        Set an ephemeral value (cleared after rounds/phases).
        
        Args:
            key: Context key
            value: Value to store
            deep_copy: If True, deep copy the value
        """
        stored_value = copy.deepcopy(value) if deep_copy else value
        self._ephemeral[key] = stored_value
        self.updated_at = time.time()
        
        self._log_change("set_ephemeral", {"key": key})
    
    def update(self, data: Dict[str, Any], deep_copy: bool = True) -> None:
        """
        Update multiple persistent values.
        
        Args:
            data: Dictionary of key-value pairs
            deep_copy: If True, deep copy the data
        """
        if deep_copy:
            data = copy.deepcopy(data)
        
        updated_keys = []
        for key, value in data.items():
            # Skip protected keys entirely (don't overwrite, don't error)
            if key in self._protected_keys:
                continue
            
            self._persistent[key] = value
            updated_keys.append(key)
        
        if updated_keys:
            self.version += 1
            self.updated_at = time.time()
            
            self._log_change("update", {
                "keys": updated_keys,
                "count": len(updated_keys),
                "skipped_protected": len(data) - len(updated_keys),
            })
    
    def delete(self, key: str) -> bool:
        """
        Delete a key from context.
        
        Args:
            key: Context key
            
        Returns:
            True if key existed, False otherwise
        """
        if key in self._protected_keys:
            raise ValueError(f"Cannot delete protected key: {key}")
        
        existed = False
        if key in self._persistent:
            del self._persistent[key]
            existed = True
        if key in self._ephemeral:
            del self._ephemeral[key]
            existed = True
        
        if existed:
            self.version += 1
            self.updated_at = time.time()
            self._log_change("delete", {"key": key})
        
        return existed
    
    def clear_ephemeral(self) -> None:
        """Clear all ephemeral data."""
        cleared_keys = list(self._ephemeral.keys())
        self._ephemeral.clear()
        self._log_change("clear_ephemeral", {"keys_cleared": cleared_keys})
    
    def create_snapshot(self, reason: str, metadata: Optional[Dict[str, Any]] = None) -> ContextSnapshot:
        """
        Create a snapshot of current context state.
        
        Args:
            reason: Why snapshot is being taken
            metadata: Additional snapshot metadata
            
        Returns:
            ContextSnapshot object
        """
        snapshot = ContextSnapshot(
            version=self.version,
            timestamp=time.time(),
            reason=reason,
            data=copy.deepcopy(self._get_all_data()),
            metadata=metadata or {},
        )
        
        self._snapshots.append(snapshot)
        
        # Limit snapshot history
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]
        
        return snapshot
    
    def restore_snapshot(self, version: Optional[int] = None) -> bool:
        """
        Restore context from a snapshot.
        
        Args:
            version: Snapshot version to restore (None = latest)
            
        Returns:
            True if restored, False if snapshot not found
        """
        if not self._snapshots:
            return False
        
        if version is None:
            snapshot = self._snapshots[-1]
        else:
            snapshot = next((s for s in self._snapshots if s.version == version), None)
            if not snapshot:
                return False
        
        # Restore data
        self._persistent = copy.deepcopy(snapshot.data)
        self.version = snapshot.version
        self.updated_at = time.time()
        
        self._log_change("restore_snapshot", {
            "version": snapshot.version,
            "reason": snapshot.reason,
        })
        
        return True
    
    def get_phase_context(self) -> Dict[str, Any]:
        """
        Get a deep copy of context for phase invocation.
        
        This creates a complete independent copy that phases
        can modify without affecting the orchestrator's context.
        
        Returns:
            Deep copied context dictionary
        """
        # Create snapshot before phase
        self.create_snapshot("phase_start")
        
        # Return deep copy of all data
        return copy.deepcopy(self._get_all_data())
    
    def merge_phase_results(
        self,
        phase_results: Dict[str, Any],
        strategy: str = "safe",
        prefix: Optional[str] = None,
    ) -> None:
        """
        Merge results from phase execution back into context.
        
        Strategies:
        - "safe": Only add new keys, never overwrite existing
        - "update": Update existing keys, add new ones
        - "replace": Completely replace with phase results
        - "prefixed": Add all keys with a prefix
        
        Args:
            phase_results: Results from phase execution
            strategy: Merge strategy to use
            prefix: Optional prefix for keys (e.g., "phase_planning_")
        """
        if not phase_results:
            return
        
        if strategy == "replace":
            self._persistent = copy.deepcopy(phase_results)
        
        elif strategy == "update":
            results_copy = copy.deepcopy(phase_results)
            for key, value in results_copy.items():
                if key not in self._protected_keys or key not in self._persistent:
                    self._persistent[key] = value
        
        elif strategy == "safe":
            results_copy = copy.deepcopy(phase_results)
            for key, value in results_copy.items():
                if key not in self._persistent and key not in self._protected_keys:
                    self._persistent[key] = value
        
        elif strategy == "prefixed":
            if not prefix:
                raise ValueError("Prefix required for 'prefixed' strategy")
            results_copy = copy.deepcopy(phase_results)
            for key, value in results_copy.items():
                prefixed_key = f"{prefix}{key}"
                self._persistent[prefixed_key] = value
        
        else:
            raise ValueError(f"Unknown merge strategy: {strategy}")
        
        self.version += 1
        self.updated_at = time.time()
        
        self._log_change("merge_phase_results", {
            "strategy": strategy,
            "prefix": prefix,
            "keys_merged": len(phase_results),
        })
    
    def get_snapshots(self) -> List[ContextSnapshot]:
        """Get all snapshots."""
        return self._snapshots.copy()
    
    def get_change_log(self) -> List[Dict[str, Any]]:
        """Get change log."""
        return self._change_log.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert entire context to dictionary.
        
        Returns:
            Dictionary with all context data and metadata
        """
        return {
            'session_id': self.session_id,
            'version': self.version,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'persistent': copy.deepcopy(self._persistent),
            'ephemeral': copy.deepcopy(self._ephemeral),
            'protected_keys': list(self._protected_keys),
            'snapshots': [s.to_dict() for s in self._snapshots[-10:]],  # Last 10
            'change_log': self._change_log[-50:],  # Last 50 changes
        }
    
    def save_to_disk(self, filepath: str) -> None:
        """
        Save context to disk as JSON.
        
        Args:
            filepath: Path to save file
        """
        data = self.to_dict()
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def save_to_disk_pickle(self, filepath: str) -> None:
        """
        Save context to disk as pickle (preserves complex objects).
        
        Args:
            filepath: Path to save file
        """
        data = {
            'session_id': self.session_id,
            'version': self.version,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'persistent': self._persistent,
            'ephemeral': self._ephemeral,
            'protected_keys': self._protected_keys,
            'snapshots': self._snapshots[-10:],
            'change_log': self._change_log[-50:],
        }
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
    
    @classmethod
    def load_from_disk(cls, filepath: str) -> 'DurableContext':
        """
        Load context from JSON file.
        
        Args:
            filepath: Path to load file
            
        Returns:
            DurableContext instance
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        ctx = cls(session_id=data['session_id'])
        ctx.version = data['version']
        ctx.created_at = data['created_at']
        ctx.updated_at = data['updated_at']
        ctx._persistent = data['persistent']
        ctx._ephemeral = data.get('ephemeral', {})
        ctx._protected_keys = set(data.get('protected_keys', []))
        
        # Restore snapshots
        if 'snapshots' in data:
            ctx._snapshots = [
                ContextSnapshot.from_dict(s) for s in data['snapshots']
            ]
        
        # Restore change log
        if 'change_log' in data:
            ctx._change_log = data['change_log']
        
        return ctx
    
    @classmethod
    def load_from_disk_pickle(cls, filepath: str) -> 'DurableContext':
        """
        Load context from pickle file.
        
        Args:
            filepath: Path to load file
            
        Returns:
            DurableContext instance
        """
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        ctx = cls(session_id=data['session_id'])
        ctx.version = data['version']
        ctx.created_at = data['created_at']
        ctx.updated_at = data['updated_at']
        ctx._persistent = data['persistent']
        ctx._ephemeral = data.get('ephemeral', {})
        ctx._protected_keys = data.get('protected_keys', set())
        ctx._snapshots = data.get('snapshots', [])
        ctx._change_log = data.get('change_log', [])
        
        return ctx
    
    def _get_all_data(self) -> Dict[str, Any]:
        """Get combined persistent and ephemeral data."""
        return {**self._persistent, **self._ephemeral}
    
    def _log_change(self, operation: str, details: Dict[str, Any]) -> None:
        """Log a change to the change log."""
        entry = {
            'timestamp': time.time(),
            'operation': operation,
            'version': self.version,
            'details': details,
        }
        
        self._change_log.append(entry)
        
        # Limit change log size
        if len(self._change_log) > self._max_changes:
            self._change_log = self._change_log[-self._max_changes:]
    
    def __getitem__(self, key: str) -> Any:
        """Dictionary-like access."""
        return self.get(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Dictionary-like assignment."""
        self.set(key, value)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._persistent or key in self._ephemeral
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"DurableContext(session={self.session_id}, "
            f"version={self.version}, "
            f"keys={len(self._persistent)}, "
            f"snapshots={len(self._snapshots)})"
        )
