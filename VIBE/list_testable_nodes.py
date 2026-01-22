#!/usr/bin/env python3
"""
List nodes with events for UI testing
"""

from cmbagent.database import get_db_session
from cmbagent.database.models import DAGNode, ExecutionEvent
from sqlalchemy import func

db = get_db_session()

print("=" * 80)
print("Nodes with Events - Ready for UI Testing")
print("=" * 80)

# Get nodes that have events
nodes_with_events = (
    db.query(
        DAGNode.id,
        DAGNode.node_type,
        DAGNode.status,
        DAGNode.session_id,
        func.count(ExecutionEvent.id).label('event_count')
    )
    .join(ExecutionEvent, DAGNode.id == ExecutionEvent.node_id)
    .group_by(DAGNode.id)
    .having(func.count(ExecutionEvent.id) > 0)
    .order_by(func.count(ExecutionEvent.id).desc())
    .limit(10)
    .all()
)

if nodes_with_events:
    print(f"\nFound {len(nodes_with_events)} nodes with events:\n")
    for node in nodes_with_events:
        print(f"Node ID: {node.id}")
        print(f"  Type: {node.node_type}")
        print(f"  Status: {node.status}")
        print(f"  Events: {node.event_count}")
        print(f"  Session: {node.session_id}")
        print(f"  API URL: http://localhost:8000/api/nodes/{node.id}/events")
        print()
else:
    print("\n⚠️  No nodes with events found in database")
    print("Run a workflow first to generate test data")

db.close()
print("=" * 80)
