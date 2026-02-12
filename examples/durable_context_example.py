"""
Example demonstrating the DurableContext system for copilot sessions.

This example shows:
1. Creating and using durable context
2. Taking snapshots and restoring
3. Phase invocation with isolated context
4. Merging phase results
5. Persistence to disk
6. Session continuation
"""

import asyncio
import json
from pathlib import Path
from cmbagent.orchestrator.durable_context import DurableContext, ContextSnapshot


def example_1_basic_usage():
    """Basic DurableContext usage."""
    print("=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)
    
    # Create context
    ctx = DurableContext(session_id="demo_session_001")
    
    # Store values
    ctx.set('user_name', 'Alice', protected=True)  # Can't be overwritten
    ctx.set('project_root', '/srv/projects/myapp')
    ctx.set('task', 'Build REST API')
    
    # Nested object with deep copy
    config = {
        'database': {'host': 'localhost', 'port': 5432},
        'api': {'version': '1.0'}
    }
    ctx.set('config', config)
    
    # Modify original - stored copy unaffected
    config['database']['host'] = 'changed'
    
    print(f"Original modified: {config['database']['host']}")
    print(f"Stored unchanged: {ctx.get('config')['database']['host']}")
    print(f"Context version: {ctx.version}")
    print()


def example_2_ephemeral_data():
    """Persistent vs ephemeral data."""
    print("=" * 60)
    print("Example 2: Ephemeral Data")
    print("=" * 60)
    
    ctx = DurableContext(session_id="demo_session_002")
    
    # Persistent data
    ctx.set('user_name', 'Bob')
    ctx.set('project_type', 'web_app')
    
    # Ephemeral data (cleared after operations)
    ctx.set_ephemeral('temp_file', '/tmp/processing.json')
    ctx.set_ephemeral('progress_percent', 45)
    
    print(f"Before clear:")
    print(f"  user_name: {ctx.get('user_name')}")
    print(f"  temp_file: {ctx.get('temp_file')}")
    
    # Clear ephemeral
    ctx.clear_ephemeral()
    
    print(f"After clear:")
    print(f"  user_name: {ctx.get('user_name')}")  # Still there
    print(f"  temp_file: {ctx.get('temp_file')}")  # Gone
    print()


def example_3_snapshots():
    """Taking snapshots and restoring."""
    print("=" * 60)
    print("Example 3: Snapshots")
    print("=" * 60)
    
    ctx = DurableContext(session_id="demo_session_003")
    
    # Initial state
    ctx.set('step', 1)
    ctx.set('status', 'starting')
    
    # Take snapshot
    snap1 = ctx.create_snapshot('after_step_1')
    print(f"Snapshot 1: version={snap1.version}, keys={list(snap1.data.keys())}")
    
    # More changes
    ctx.set('step', 2)
    ctx.set('results', ['result1', 'result2'])
    snap2 = ctx.create_snapshot('after_step_2')
    print(f"Snapshot 2: version={snap2.version}, keys={list(snap2.data.keys())}")
    
    # Even more changes
    ctx.set('step', 3)
    ctx.delete('status')
    print(f"Current version: {ctx.version}, step={ctx.get('step')}, status={ctx.get('status')}")
    
    # Restore to snapshot 1
    ctx.restore_snapshot(snap1.version)
    print(f"After restore: version={ctx.version}, step={ctx.get('step')}, status={ctx.get('status')}")
    print(f"  'results' exists: {'results' in ctx}")
    print()


def example_4_phase_isolation():
    """Simulate phase invocation with isolated context."""
    print("=" * 60)
    print("Example 4: Phase Context Isolation")
    print("=" * 60)
    
    # Orchestrator context
    orchestrator_ctx = DurableContext(session_id="demo_session_004")
    orchestrator_ctx.set('task', 'Build e-commerce platform')
    orchestrator_ctx.set('user_prefs', {'language': 'Python', 'framework': 'FastAPI'})
    
    # Before phase: create snapshot
    snap_before = orchestrator_ctx.create_snapshot('before_planning_phase')
    
    # Phase gets independent copy
    phase_ctx_data = orchestrator_ctx.get_phase_context()
    print(f"Phase received: {list(phase_ctx_data.keys())}")
    
    # Simulate phase modifications
    phase_ctx_data['plan_steps'] = [
        {'step': 1, 'action': 'Setup database'},
        {'step': 2, 'action': 'Create API endpoints'},
    ]
    phase_ctx_data['task'] = 'MODIFIED BY PHASE'  # Try to corrupt
    
    # Orchestrator context unchanged
    print(f"Orchestrator task: {orchestrator_ctx.get('task')}")  # Still original
    
    # Merge phase results with 'safe' strategy
    orchestrator_ctx.merge_phase_results(
        {'plan_steps': phase_ctx_data['plan_steps']},
        strategy='safe'
    )
    
    # After merge
    print(f"After merge:")
    print(f"  plan_steps added: {'plan_steps' in orchestrator_ctx}")
    print(f"  task unchanged: {orchestrator_ctx.get('task')}")
    
    # After phase: create snapshot
    snap_after = orchestrator_ctx.create_snapshot('after_planning_phase')
    print(f"Snapshots created: {len(orchestrator_ctx.get_snapshots())}")
    print()


def example_5_merge_strategies():
    """Different merge strategies."""
    print("=" * 60)
    print("Example 5: Merge Strategies")
    print("=" * 60)
    
    # Safe strategy
    ctx1 = DurableContext(session_id="demo_session_005a")
    ctx1.set('existing_key', 'original_value')
    ctx1.merge_phase_results(
        {'existing_key': 'new_value', 'new_key': 'added'},
        strategy='safe'
    )
    print(f"Safe merge:")
    print(f"  existing_key: {ctx1.get('existing_key')}")  # Original kept
    print(f"  new_key: {ctx1.get('new_key')}")  # Added
    
    # Update strategy
    ctx2 = DurableContext(session_id="demo_session_005b")
    ctx2.set('existing_key', 'original_value')
    ctx2.merge_phase_results(
        {'existing_key': 'new_value', 'new_key': 'added'},
        strategy='update'
    )
    print(f"Update merge:")
    print(f"  existing_key: {ctx2.get('existing_key')}")  # Updated
    print(f"  new_key: {ctx2.get('new_key')}")  # Added
    
    # Prefixed strategy
    ctx3 = DurableContext(session_id="demo_session_005c")
    ctx3.merge_phase_results(
        {'steps': [1, 2, 3], 'metadata': {'author': 'planner'}},
        strategy='prefixed',
        prefix='planning_'
    )
    print(f"Prefixed merge:")
    print(f"  Keys: {[k for k in ctx3._persistent.keys()]}")
    print()


def example_6_persistence():
    """Save and load context."""
    print("=" * 60)
    print("Example 6: Persistence")
    print("=" * 60)
    
    # Create context
    ctx = DurableContext(session_id="demo_session_006")
    ctx.set('user_name', 'Charlie', protected=True)
    ctx.set('project', 'Data Pipeline')
    ctx.set('config', {'workers': 4, 'timeout': 30})
    ctx.create_snapshot('checkpoint_1')
    ctx.set('step', 5)
    ctx.create_snapshot('checkpoint_2')
    
    print(f"Original context:")
    print(f"  Version: {ctx.version}")
    print(f"  Keys: {[k for k in ctx._persistent.keys()]}")
    print(f"  Snapshots: {len(ctx.get_snapshots())}")
    
    # Save to disk
    temp_dir = Path('./temp_contexts')
    temp_dir.mkdir(exist_ok=True)
    
    json_path = temp_dir / 'context.json'
    pickle_path = temp_dir / 'context.pkl'
    
    ctx.save_to_disk(str(json_path))
    ctx.save_to_disk_pickle(str(pickle_path))
    
    print(f"Saved to:")
    print(f"  JSON: {json_path} ({json_path.stat().st_size} bytes)")
    print(f"  Pickle: {pickle_path} ({pickle_path.stat().st_size} bytes)")
    
    # Load from disk
    ctx_loaded = DurableContext.load_from_disk(str(json_path))
    
    print(f"Loaded context:")
    print(f"  Version: {ctx_loaded.version}")
    print(f"  Keys: {[k for k in ctx_loaded._persistent.keys()]}")
    print(f"  Snapshots: {len(ctx_loaded.get_snapshots())}")
    print(f"  user_name: {ctx_loaded.get('user_name')}")
    print()
    
    # Cleanup
    json_path.unlink()
    pickle_path.unlink()
    temp_dir.rmdir()


def example_7_change_log():
    """View change log."""
    print("=" * 60)
    print("Example 7: Change Log")
    print("=" * 60)
    
    ctx = DurableContext(session_id="demo_session_007")
    
    ctx.set('key1', 'value1')
    ctx.update({'key2': 'value2', 'key3': 'value3'})
    ctx.set_ephemeral('temp', 'data')
    ctx.delete('key1')
    ctx.merge_phase_results({'key4': 'value4'}, strategy='safe')
    
    # Get change log
    changes = ctx.get_change_log()
    
    print(f"Change log ({len(changes)} entries):")
    for change in changes:
        print(f"  v{change['version']}: {change['operation']}")
        print(f"    Details: {change['details']}")
    print()


def example_8_protected_keys():
    """Protected keys demonstration."""
    print("=" * 60)
    print("Example 8: Protected Keys")
    print("=" * 60)
    
    ctx = DurableContext(session_id="demo_session_008")
    
    # Set protected key
    ctx.set('session_id', 'abc123', protected=True)
    ctx.set('run_id', 'xyz789', protected=True)
    ctx.set('normal_key', 'can_change')
    
    print(f"Initial values:")
    print(f"  session_id: {ctx.get('session_id')}")
    print(f"  run_id: {ctx.get('run_id')}")
    print(f"  normal_key: {ctx.get('normal_key')}")
    
    # Try to set protected key to SAME value (idempotent - no error)
    ctx.set('session_id', 'abc123', protected=True)
    print(f"  Re-setting to same value: OK (idempotent)")
    
    # Try to overwrite protected with DIFFERENT value
    try:
        ctx.set('session_id', 'changed')
        print("  Protected overwrite succeeded (unexpected!)")
    except ValueError as e:
        print(f"  Protected overwrite prevented: Cannot overwrite...")
    
    # Try to delete protected
    try:
        ctx.delete('run_id')
        print("  Protected delete succeeded (unexpected!)")
    except ValueError as e:
        print(f"  Protected delete prevented: Cannot delete...")
    
    # Update with protected keys (silently skipped)
    ctx.update({'session_id': 'ignored', 'normal_key': 'updated'})
    print(f"  After update() with protected key:")
    print(f"    session_id: {ctx.get('session_id')} (unchanged)")
    print(f"    normal_key: {ctx.get('normal_key')} (updated)")
    
    # Normal key can be changed
    ctx.set('normal_key', 'changed_again')
    print(f"  normal_key changed directly: {ctx.get('normal_key')}")
    print()


def example_9_dictionary_interface():
    """Dictionary-like interface."""
    print("=" * 60)
    print("Example 9: Dictionary-like Interface")
    print("=" * 60)
    
    ctx = DurableContext(session_id="demo_session_009")
    
    # Dictionary-like access
    ctx['name'] = 'Dave'
    ctx['age'] = 30
    
    print(f"name: {ctx['name']}")
    print(f"age: {ctx['age']}")
    print(f"'name' in ctx: {'name' in ctx}")
    print(f"'missing' in ctx: {'missing' in ctx}")
    print(f"Context: {ctx}")
    print()


def main():
    """Run all examples."""
    example_1_basic_usage()
    example_2_ephemeral_data()
    example_3_snapshots()
    example_4_phase_isolation()
    example_5_merge_strategies()
    example_6_persistence()
    example_7_change_log()
    example_8_protected_keys()
    example_9_dictionary_interface()
    
    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
