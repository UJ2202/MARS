#!/usr/bin/env python3
"""Check ExecutionEvent structure to show agent tracking."""

from pathlib import Path
from sqlalchemy import create_engine, inspect

def main():
    db_dir = Path.home() / ".cmbagent"
    db_path = db_dir / "cmbagent.db"
    
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    
    print("\n✅ ExecutionEvent columns (tracks individual agent actions):")
    print("=" * 60)
    
    columns = inspector.get_columns('execution_events')
    for col in columns:
        marker = "  🤖" if col['name'] in ['agent_name', 'agent_role', 'event_type'] else "    "
        print(f"{marker} {col['name']:<20} {col['type']}")
    
    print("\n" + "=" * 60)
    print("✅ Each workflow step can have multiple ExecutionEvents")
    print("   showing different agents working on that step:")
    print("   - agent_name: Which agent performed the action")
    print("   - agent_role: primary, helper, validator")
    print("   - event_type: agent_call, tool_call, code_exec, etc.")
    print()

if __name__ == "__main__":
    main()
