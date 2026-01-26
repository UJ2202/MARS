#!/usr/bin/env python3
"""Verify summary field is working correctly."""

from pathlib import Path
from sqlalchemy import create_engine, inspect

def main():
    db_dir = Path.home() / ".cmbagent"
    db_path = db_dir / "cmbagent.db"
    
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    
    print("\n✅ WorkflowStep columns with summary field:")
    print("=" * 70)
    
    columns = inspector.get_columns('workflow_steps')
    for col in columns:
        marker = "  📝" if col['name'] == 'summary' else "  🎯" if col['name'] == 'goal' else "    "
        print(f"{marker} {col['name']:<25} {col['type']}")
    
    has_summary = any(col['name'] == 'summary' for col in columns)
    has_goal = any(col['name'] == 'goal' for col in columns)
    
    print("\n" + "=" * 70)
    if has_summary and has_goal:
        print("✅ SUCCESS: WorkflowStep has both 'goal' and 'summary' fields")
        print("\nProduction-Grade Architecture:")
        print("  🎯 goal    - What the step aims to accomplish")
        print("  📝 summary - What was actually accomplished (from agent)")
        print("  🤖 ExecutionEvent.agent_name - Which agents worked on it")
    else:
        print(f"❌ Missing fields: goal={has_goal}, summary={has_summary}")
    print()

if __name__ == "__main__":
    main()
