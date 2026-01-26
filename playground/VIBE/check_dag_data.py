#!/usr/bin/env python3
"""
Check what DAG data is available via WebSocket/API
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cmbagent.database import get_db_session
from cmbagent.database.models import WorkflowRun, DAGNode, DAGEdge
from cmbagent.database.session_manager import SessionManager

db = get_db_session()
session_manager = SessionManager(db)
session_id = session_manager.get_or_create_default_session()

print(f"Using session: {session_id}")
print("=" * 80)

# Get recent workflow runs
runs = db.query(WorkflowRun).filter(
    WorkflowRun.session_id == session_id
).limit(5).all()

print(f"\nRecent Workflow Runs in session:")
for run in runs:
    print(f"  - {run.id}: {run.task_description[:60] if run.task_description else 'N/A'}")
    print(f"    Status: {run.status}")
    
    # Get nodes for this run
    nodes = db.query(DAGNode).filter(
        DAGNode.run_id == run.id
    ).all()
    
    print(f"    Nodes: {len(nodes)}")
    for node in nodes[:5]:
        print(f"      - {node.id} ({node.node_type}): {node.status}")
    print()

db.close()
