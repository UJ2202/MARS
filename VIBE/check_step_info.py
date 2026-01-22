#!/usr/bin/env python3
"""Check what information is stored for each workflow step."""

import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from cmbagent.database.models import WorkflowStep, WorkflowRun, Session
import json


def main():
    # Get database path from the same location as the app uses
    db_dir = Path.home() / ".cmbagent"
    db_path = db_dir / "cmbagent.db"
    
    if not db_path.exists():
        print(f"\n❌ Database not found at: {db_path}")
        print("   Make sure the backend has been run at least once.\n")
        return
    
    print(f"✅ Using database: {db_path}\n")
    
    # Create database connection
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Get all workflow steps
        steps = db.query(WorkflowStep).order_by(
            WorkflowStep.session_id, 
            WorkflowStep.run_id, 
            WorkflowStep.step_number
        ).all()
        
        print(f"\n{'='*80}")
        print(f"TOTAL WORKFLOW STEPS IN DATABASE: {len(steps)}")
        print(f"{'='*80}\n")
        
        if not steps:
            print("No workflow steps found in database.\n")
            return
        
        # Group by session for better organization
        current_session = None
        current_run = None
        
        for step in steps:
            # Print session header
            if step.session_id != current_session:
                current_session = step.session_id
                session = db.query(Session).filter(Session.id == step.session_id).first()
                print(f"\n{'='*80}")
                print(f"SESSION: {step.session_id[:8]}...")
                if session:
                    print(f"  Name: {session.name}")
                    print(f"  Status: {session.status}")
                    print(f"  Created: {session.created_at}")
                print(f"{'='*80}\n")
            
            # Print run header
            if step.run_id != current_run:
                current_run = step.run_id
                run = db.query(WorkflowRun).filter(WorkflowRun.id == step.run_id).first()
                print(f"\n  RUN: {step.run_id[:8]}... (Run #{run.run_number if run and hasattr(run, 'run_number') else 'N/A'})")
                if run and run.task_description:
                    print(f"  Task: {run.task_description[:150]}...")
                if run:
                    print(f"  Mode: {run.mode}, Agent: {run.agent}, Model: {run.model}")
                    print(f"  Status: {run.status}")
                print(f"  {'─'*76}\n")
            
            # Print step details
            print(f"  📍 STEP {step.step_number}: {step.goal}")
            print(f"     ID: {step.id}")
            print(f"     Status: {step.status}")
            print(f"     Progress: {step.progress_percentage}%")
            print(f"     Started: {step.started_at or 'Not started'}")
            print(f"     Completed: {step.completed_at or 'Not completed'}")
            
            # Show inputs
            if step.inputs:
                print(f"     Inputs: {json.dumps(step.inputs, indent=8)[:200]}...")
            else:
                print(f"     Inputs: None")
            
            # Show outputs
            if step.outputs:
                print(f"     Outputs: {json.dumps(step.outputs, indent=8)[:200]}...")
            else:
                print(f"     Outputs: None")
            
            # Show error if any
            if step.error_message:
                print(f"     Error: {step.error_message[:150]}...")
            
            # Show meta data
            if step.meta:
                print(f"     Meta: {json.dumps(step.meta, indent=8)[:200]}...")
            else:
                print(f"     Meta: None")
            
            print()
        
        # Summary of fields available
        print(f"\n{'='*80}")
        print("FIELDS AVAILABLE FOR EACH WORKFLOW STEP:")
        print(f"{'='*80}")
        print("""
  Core Fields:
    - id (String): Unique identifier
    - run_id (String): Foreign key to workflow_runs
    - session_id (String): Foreign key to sessions
    - step_number (Integer): Sequential step number in run
    - agent (String): Agent name executing this step
    - status (String): pending/running/paused/waiting_approval/completed/failed/skipped
    - started_at (Timestamp): When step execution started
    - completed_at (Timestamp): When step execution completed
    - progress_percentage (Integer): 0-100 progress indicator
    
  Data Fields:
    - inputs (JSON): Input parameters for the step
    - outputs (JSON): Output/results from the step
    - error_message (Text): Error message if step failed
    - meta (JSON): Additional metadata (flexible key-value storage)
    
  Relationships (accessible via joins):
    - run: WorkflowRun parent
    - session: Session parent
    - checkpoints: List of checkpoints
    - messages: List of messages
    - cost_records: List of cost records
    - approval_requests: List of approval requests
    - parent_branches: Branches created from this step
    - workflow_metrics: Metrics associated with this step
    - files: Files associated with this step
    - execution_events: Events related to this step
        """)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
