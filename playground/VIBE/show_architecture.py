#!/usr/bin/env python3
"""Show the complete fixed architecture with example data."""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from cmbagent.database.models import WorkflowStep, ExecutionEvent
import json

def main():
    db_dir = Path.home() / ".cmbagent"
    db_path = db_dir / "cmbagent.db"
    
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    print("\n" + "=" * 80)
    print("✅ FIXED ARCHITECTURE - Steps with Goals + Agent Events")
    print("=" * 80)
    
    # Get a sample step with events
    step = db.query(WorkflowStep).first()
    
    if step:
        print(f"\n📋 WORKFLOW STEP #{step.step_number}")
        print(f"   Goal: {step.goal[:100]}...")
        print(f"   Status: {step.status}")
        print(f"   Step ID: {step.id}")
        
        # Get execution events for this step
        events = db.query(ExecutionEvent).filter(
            ExecutionEvent.step_id == step.id
        ).order_by(ExecutionEvent.execution_order).all()
        
        if events:
            print(f"\n   🤖 AGENT EXECUTION EVENTS ({len(events)} events):")
            for event in events[:5]:  # Show first 5
                print(f"      • {event.event_type} by {event.agent_name or 'N/A'}")
                print(f"        Role: {event.agent_role or 'N/A'}")
                print(f"        Status: {event.status}")
                if event.duration_ms:
                    print(f"        Duration: {event.duration_ms}ms")
                print()
        else:
            print(f"\n   ℹ️  No execution events recorded yet")
    
    print("\n" + "=" * 80)
    print("ARCHITECTURE SUMMARY:")
    print("=" * 80)
    print("""
    WorkflowStep (What to do)
    ├─ goal: "Research CMB papers and identify key findings"
    ├─ status: running/completed/failed
    ├─ inputs/outputs: Step-level data
    └─ execution_events: List of agent actions
    
    ExecutionEvent (Who did what)
    ├─ agent_name: "literature_researcher"
    ├─ agent_role: "primary"
    ├─ event_type: "agent_call"
    └─ duration_ms: 5000
    
    ExecutionEvent
    ├─ agent_name: "data_retriever"
    ├─ agent_role: "helper"
    ├─ event_type: "tool_call"
    └─ duration_ms: 2000
    
    ExecutionEvent
    ├─ agent_name: "validator"
    ├─ agent_role: "validator"
    ├─ event_type: "agent_call"
    └─ duration_ms: 1000
    """)
    
    db.close()

if __name__ == "__main__":
    main()
