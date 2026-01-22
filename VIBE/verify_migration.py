#!/usr/bin/env python3
"""Verify the migration worked correctly."""

from pathlib import Path
from sqlalchemy import create_engine, inspect

def main():
    db_dir = Path.home() / ".cmbagent"
    db_path = db_dir / "cmbagent.db"
    
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    
    # Get workflow_steps columns
    columns = inspector.get_columns('workflow_steps')
    
    print("\n✅ WorkflowStep columns after migration:")
    print("=" * 60)
    for col in columns:
        marker = "  🎯" if col['name'] == 'goal' else "    "
        print(f"{marker} {col['name']:<20} {col['type']}")
    
    has_goal = any(col['name'] == 'goal' for col in columns)
    has_agent = any(col['name'] == 'agent' for col in columns)
    
    print("\n" + "=" * 60)
    if has_goal and not has_agent:
        print("✅ SUCCESS: 'agent' column renamed to 'goal'")
    elif has_agent and not has_goal:
        print("❌ ERROR: Column still named 'agent' (migration not applied)")
    elif has_goal and has_agent:
        print("⚠️  WARNING: Both 'goal' and 'agent' columns exist")
    else:
        print("❌ ERROR: Neither 'goal' nor 'agent' column found")
    print()

if __name__ == "__main__":
    main()
