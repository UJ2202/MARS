# Stage 13: Enhanced Cost Tracking and Session Management

**Phase:** 4 - Advanced Features
**Estimated Time:** 35-45 minutes
**Dependencies:** Stages 1-12 complete
**Risk Level:** Medium

## Objectives

1. Implement real-time cost tracking with WebSocket streaming
2. Add budget limits and quota enforcement
3. Create comprehensive session management APIs
4. Build project/session hierarchy
5. Add cost estimation before execution
6. Implement cost alerts and notifications
7. Create cost analytics and reporting dashboard

## Current State Analysis

### What We Have
- Basic cost tracking in `cost/` directory
- Cost files written post-execution
- Manual cost calculation
- No real-time tracking
- No budget enforcement
- Limited session management

### What We Need
- Real-time cost streaming to UI
- Pre-execution cost estimation
- Budget limits per session/project
- Cost alerts and thresholds
- Comprehensive session APIs
- Cost analytics and trends
- Resource quota management

## Pre-Stage Verification

### Check Prerequisites
1. Stages 1-12 complete and verified
2. Database schema includes cost_records table
3. WebSocket infrastructure operational
4. Sessions table exists

### Expected State
- Cost tracking writes to database
- WebSocket server running
- Session isolation functional
- Ready to enhance cost tracking

## Implementation Tasks

### Task 1: Enhance Cost Tracking Database Schema
**Objective:** Add comprehensive cost and quota tracking

**New/Updated Tables:**

**cost_records table (already exists, verify):**
- id (SERIAL, primary key)
- run_id (UUID, foreign key)
- step_id (UUID, foreign key, nullable)
- session_id (UUID, foreign key)
- project_id (UUID, foreign key, nullable)
- model (VARCHAR 100)
- provider (VARCHAR 50: openai, anthropic, google)
- prompt_tokens (INTEGER)
- completion_tokens (INTEGER)
- total_tokens (INTEGER)
- cost_usd (NUMERIC(10, 6))
- timestamp (TIMESTAMP)
- metadata (JSONB)

**budgets table (new):**
- id (UUID, primary key)
- session_id (UUID, foreign key, nullable)
- project_id (UUID, foreign key, nullable)
- user_id (UUID, foreign key, nullable)
- scope (VARCHAR 50: session, project, user, global)
- limit_usd (NUMERIC(10, 2))
- spent_usd (NUMERIC(10, 6))
- remaining_usd (NUMERIC(10, 6))
- period (VARCHAR 50: daily, weekly, monthly, total)
- period_start (TIMESTAMP)
- period_end (TIMESTAMP, nullable)
- status (VARCHAR 50: active, exceeded, expired)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

**cost_alerts table (new):**
- id (UUID, primary key)
- budget_id (UUID, foreign key)
- alert_type (VARCHAR 50: threshold, exceeded, warning)
- threshold_percentage (INTEGER)
- triggered_at (TIMESTAMP)
- notified (BOOLEAN)
- notification_channels (JSONB)  # email, webhook, ui
- metadata (JSONB)

**resource_quotas table (new):**
- id (UUID, primary key)
- session_id (UUID, foreign key, nullable)
- project_id (UUID, foreign key, nullable)
- quota_type (VARCHAR 50: disk_mb, memory_mb, concurrent_runs, api_calls)
- limit_value (BIGINT)
- used_value (BIGINT)
- remaining_value (BIGINT)
- status (VARCHAR 50: ok, warning, exceeded)
- updated_at (TIMESTAMP)

**cost_estimates table (new):**
- id (UUID, primary key)
- run_id (UUID, foreign key)
- estimated_cost_usd (NUMERIC(10, 6))
- estimated_tokens (INTEGER)
- estimation_method (VARCHAR 100)
- estimated_at (TIMESTAMP)
- actual_cost_usd (NUMERIC(10, 6), nullable)
- accuracy_percentage (NUMERIC(5, 2), nullable)

**Files to Create:**
- `cmbagent/database/migrations/versions/013_enhanced_cost_tracking.py`
- Add models to `cmbagent/database/models.py`

**Verification:**
- Migration runs successfully
- All tables created
- Foreign key relationships correct
- Indexes on session_id, project_id, timestamp

### Task 2: Implement Real-Time Cost Tracker
**Objective:** Track costs in real-time and stream to UI

**Implementation:**

```python
# cmbagent/cost/realtime_tracker.py
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session

class RealtimeCostTracker:
    """Real-time cost tracking with WebSocket streaming."""

    def __init__(
        self,
        db_session: Session,
        websocket_manager,
        run_id: str,
        session_id: str,
        project_id: Optional[str] = None
    ):
        self.db = db_session
        self.ws = websocket_manager
        self.run_id = run_id
        self.session_id = session_id
        self.project_id = project_id

        # In-memory running totals for fast access
        self._running_total = Decimal("0.00")
        self._total_tokens = 0

    def track_llm_call(
        self,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        step_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Track a single LLM API call."""

        # Calculate cost
        cost_usd = self._calculate_cost(
            model, provider, prompt_tokens, completion_tokens
        )

        # Update running totals
        self._running_total += cost_usd
        self._total_tokens += (prompt_tokens + completion_tokens)

        # Save to database
        from cmbagent.database.models import CostRecords

        record = CostRecords(
            run_id=self.run_id,
            step_id=step_id,
            session_id=self.session_id,
            project_id=self.project_id,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=float(cost_usd),
            timestamp=datetime.utcnow()
        )

        self.db.add(record)
        self.db.commit()

        # Stream update to UI
        cost_update = {
            "type": "cost_update",
            "run_id": self.run_id,
            "step_id": step_id,
            "model": model,
            "cost_usd": float(cost_usd),
            "running_total_usd": float(self._running_total),
            "total_tokens": self._total_tokens,
            "timestamp": datetime.utcnow().isoformat()
        }

        self.ws.broadcast(cost_update, room=self.run_id)

        # Check budget limits
        self._check_budget_limits()

        return cost_update

    def _calculate_cost(
        self,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> Decimal:
        """Calculate cost based on model pricing."""

        # Pricing data (prices per 1M tokens)
        pricing = {
            "openai": {
                "gpt-4o": {"prompt": 2.50, "completion": 10.00},
                "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
                "gpt-4-turbo": {"prompt": 10.00, "completion": 30.00},
                "gpt-3.5-turbo": {"prompt": 0.50, "completion": 1.50}
            },
            "anthropic": {
                "claude-opus-4": {"prompt": 15.00, "completion": 75.00},
                "claude-sonnet-4": {"prompt": 3.00, "completion": 15.00},
                "claude-sonnet-3.5": {"prompt": 3.00, "completion": 15.00},
                "claude-haiku-3": {"prompt": 0.25, "completion": 1.25}
            },
            "google": {
                "gemini-2.0-flash-exp": {"prompt": 0.00, "completion": 0.00},  # Free tier
                "gemini-1.5-pro": {"prompt": 1.25, "completion": 5.00},
                "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30}
            }
        }

        # Get pricing for model
        provider_pricing = pricing.get(provider, {})
        model_pricing = provider_pricing.get(model)

        if not model_pricing:
            # Unknown model, use default estimation
            model_pricing = {"prompt": 1.0, "completion": 3.0}

        # Calculate cost
        prompt_cost = Decimal(str(model_pricing["prompt"])) * prompt_tokens / 1_000_000
        completion_cost = Decimal(str(model_pricing["completion"])) * completion_tokens / 1_000_000

        return prompt_cost + completion_cost

    def _check_budget_limits(self):
        """Check if budget limits exceeded and send alerts."""
        from cmbagent.database.models import Budgets, CostAlerts

        # Get active budgets for this session/project
        budgets = self.db.query(Budgets).filter(
            Budgets.status == "active",
            (Budgets.session_id == self.session_id) |
            (Budgets.project_id == self.project_id)
        ).all()

        for budget in budgets:
            # Calculate spent percentage
            spent_pct = (budget.spent_usd / budget.limit_usd) * 100

            # Check thresholds: 50%, 75%, 90%, 100%
            thresholds = [50, 75, 90, 100]

            for threshold in thresholds:
                if spent_pct >= threshold:
                    # Check if alert already sent
                    existing_alert = self.db.query(CostAlerts).filter(
                        CostAlerts.budget_id == budget.id,
                        CostAlerts.threshold_percentage == threshold
                    ).first()

                    if not existing_alert:
                        # Create alert
                        alert = CostAlerts(
                            budget_id=budget.id,
                            alert_type="threshold" if threshold < 100 else "exceeded",
                            threshold_percentage=threshold,
                            triggered_at=datetime.utcnow(),
                            notified=False
                        )
                        self.db.add(alert)
                        self.db.commit()

                        # Send notification
                        self._send_budget_alert(budget, threshold)

    def _send_budget_alert(self, budget, threshold_pct: int):
        """Send budget alert via WebSocket and other channels."""

        alert_message = {
            "type": "budget_alert",
            "budget_id": str(budget.id),
            "scope": budget.scope,
            "threshold_percentage": threshold_pct,
            "spent_usd": float(budget.spent_usd),
            "limit_usd": float(budget.limit_usd),
            "remaining_usd": float(budget.remaining_usd),
            "severity": "critical" if threshold_pct >= 100 else
                       "warning" if threshold_pct >= 90 else "info"
        }

        self.ws.broadcast(alert_message, room=self.session_id)

    def get_running_total(self) -> Dict[str, Any]:
        """Get current running total."""
        return {
            "run_id": self.run_id,
            "total_cost_usd": float(self._running_total),
            "total_tokens": self._total_tokens
        }

    def finalize(self) -> Dict[str, Any]:
        """Finalize cost tracking for workflow."""
        # Update workflow run with final cost
        from cmbagent.database.models import WorkflowRuns

        run = self.db.query(WorkflowRuns).filter(
            WorkflowRuns.id == self.run_id
        ).first()

        if run:
            run.total_cost_usd = float(self._running_total)
            run.total_tokens = self._total_tokens
            self.db.commit()

        # Send final cost update
        final_update = {
            "type": "cost_final",
            "run_id": self.run_id,
            "total_cost_usd": float(self._running_total),
            "total_tokens": self._total_tokens
        }

        self.ws.broadcast(final_update, room=self.run_id)

        return final_update
```

**Files to Create:**
- `cmbagent/cost/__init__.py`
- `cmbagent/cost/realtime_tracker.py`
- `cmbagent/cost/pricing.py` (pricing data module)

**Verification:**
- Cost tracked per LLM call
- WebSocket updates sent in real-time
- Database records created
- Running totals accurate

### Task 3: Implement Cost Estimation
**Objective:** Estimate costs before workflow execution

**Implementation:**

```python
# cmbagent/cost/estimator.py
from typing import Dict, Any, Optional
from decimal import Decimal

class CostEstimator:
    """Estimate workflow costs before execution."""

    def __init__(self, db_session):
        self.db = db_session

    def estimate_workflow(
        self,
        task: str,
        mode: str,
        agent: str,
        model: str
    ) -> Dict[str, Any]:
        """Estimate cost for entire workflow."""

        # Token estimation based on task complexity
        task_length = len(task)
        estimated_tokens = self._estimate_tokens(task_length, mode)

        # Cost calculation
        provider = self._get_provider(model)
        estimated_cost = self._estimate_cost(model, provider, estimated_tokens)

        # Get historical accuracy
        accuracy = self._get_estimation_accuracy(agent, model)

        estimate = {
            "estimated_cost_usd": float(estimated_cost),
            "estimated_tokens": estimated_tokens,
            "model": model,
            "provider": provider,
            "estimation_method": "historical_average",
            "confidence_level": accuracy,
            "breakdown": self._get_cost_breakdown(mode, estimated_tokens, model)
        }

        return estimate

    def _estimate_tokens(self, task_length: int, mode: str) -> int:
        """Estimate tokens based on task and mode."""

        # Base estimation
        base_tokens = task_length * 2  # Rough approximation

        # Mode multipliers
        mode_multipliers = {
            "one_shot": 1.5,
            "planning_control": 3.0,
            "deep_research": 5.0
        }

        multiplier = mode_multipliers.get(mode, 2.0)

        return int(base_tokens * multiplier)

    def _estimate_cost(
        self,
        model: str,
        provider: str,
        total_tokens: int
    ) -> Decimal:
        """Estimate cost for given tokens."""

        # Use pricing data from realtime_tracker
        from cmbagent.cost.realtime_tracker import RealtimeCostTracker

        # Assume 70% prompt, 30% completion distribution
        prompt_tokens = int(total_tokens * 0.7)
        completion_tokens = int(total_tokens * 0.3)

        tracker = RealtimeCostTracker(self.db, None, "estimate", "estimate")
        cost = tracker._calculate_cost(model, provider, prompt_tokens, completion_tokens)

        return cost

    def _get_estimation_accuracy(self, agent: str, model: str) -> float:
        """Get historical estimation accuracy."""

        from cmbagent.database.models import CostEstimates

        # Query recent estimates
        estimates = self.db.query(CostEstimates).filter(
            CostEstimates.accuracy_percentage.isnot(None)
        ).order_by(CostEstimates.estimated_at.desc()).limit(100).all()

        if not estimates:
            return 0.75  # Default 75% confidence

        # Calculate average accuracy
        accuracies = [e.accuracy_percentage for e in estimates]
        avg_accuracy = sum(accuracies) / len(accuracies)

        return float(avg_accuracy) / 100

    def _get_cost_breakdown(
        self,
        mode: str,
        total_tokens: int,
        model: str
    ) -> Dict[str, Any]:
        """Break down cost by workflow phase."""

        if mode == "planning_control":
            return {
                "planning": {"tokens": int(total_tokens * 0.3), "percentage": 30},
                "control": {"tokens": int(total_tokens * 0.2), "percentage": 20},
                "execution": {"tokens": int(total_tokens * 0.5), "percentage": 50}
            }
        else:
            return {
                "execution": {"tokens": total_tokens, "percentage": 100}
            }

    def save_estimate(self, run_id: str, estimate: Dict[str, Any]):
        """Save estimate to database."""

        from cmbagent.database.models import CostEstimates

        record = CostEstimates(
            run_id=run_id,
            estimated_cost_usd=estimate["estimated_cost_usd"],
            estimated_tokens=estimate["estimated_tokens"],
            estimation_method=estimate["estimation_method"],
            estimated_at=datetime.utcnow()
        )

        self.db.add(record)
        self.db.commit()

        return record

    def update_with_actual(self, run_id: str, actual_cost: Decimal):
        """Update estimate with actual cost for accuracy tracking."""

        from cmbagent.database.models import CostEstimates

        estimate = self.db.query(CostEstimates).filter(
            CostEstimates.run_id == run_id
        ).first()

        if estimate:
            estimate.actual_cost_usd = float(actual_cost)

            # Calculate accuracy
            if estimate.estimated_cost_usd > 0:
                accuracy = (
                    1 - abs(actual_cost - Decimal(str(estimate.estimated_cost_usd))) /
                    Decimal(str(estimate.estimated_cost_usd))
                ) * 100
                estimate.accuracy_percentage = float(max(0, min(100, accuracy)))

            self.db.commit()
```

**Files to Create:**
- `cmbagent/cost/estimator.py`

**Verification:**
- Estimates generated before execution
- Estimates saved to database
- Accuracy tracked over time
- Estimates improve with historical data

### Task 4: Implement Budget Management
**Objective:** Budget limits and enforcement

**Implementation:**

```python
# cmbagent/cost/budget_manager.py
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

class BudgetManager:
    """Manage budgets and enforce limits."""

    def __init__(self, db_session):
        self.db = db_session

    def create_budget(
        self,
        limit_usd: Decimal,
        scope: str,
        period: str = "total",
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create new budget."""

        from cmbagent.database.models import Budgets

        # Calculate period dates
        period_start = datetime.utcnow()
        period_end = self._calculate_period_end(period, period_start)

        budget = Budgets(
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
            scope=scope,
            limit_usd=float(limit_usd),
            spent_usd=0.0,
            remaining_usd=float(limit_usd),
            period=period,
            period_start=period_start,
            period_end=period_end,
            status="active"
        )

        self.db.add(budget)
        self.db.commit()

        return self._budget_to_dict(budget)

    def check_budget_available(
        self,
        estimated_cost: Decimal,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check if budget allows for estimated cost."""

        budgets = self._get_applicable_budgets(session_id, project_id)

        for budget in budgets:
            if budget.remaining_usd < float(estimated_cost):
                return {
                    "allowed": False,
                    "reason": "budget_exceeded",
                    "budget_id": str(budget.id),
                    "remaining_usd": float(budget.remaining_usd),
                    "required_usd": float(estimated_cost)
                }

        return {
            "allowed": True,
            "budgets": [self._budget_to_dict(b) for b in budgets]
        }

    def update_budget_spent(
        self,
        cost: Decimal,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ):
        """Update budget spent amount."""

        budgets = self._get_applicable_budgets(session_id, project_id)

        for budget in budgets:
            budget.spent_usd += float(cost)
            budget.remaining_usd = budget.limit_usd - budget.spent_usd

            if budget.remaining_usd <= 0:
                budget.status = "exceeded"

            budget.updated_at = datetime.utcnow()

        self.db.commit()

    def _get_applicable_budgets(
        self,
        session_id: Optional[str],
        project_id: Optional[str]
    ) -> List:
        """Get all applicable budgets for scope."""

        from cmbagent.database.models import Budgets

        query = self.db.query(Budgets).filter(
            Budgets.status == "active"
        )

        # Add scope filters
        filters = []
        if session_id:
            filters.append(Budgets.session_id == session_id)
        if project_id:
            filters.append(Budgets.project_id == project_id)

        if filters:
            from sqlalchemy import or_
            query = query.filter(or_(*filters))

        return query.all()

    def _calculate_period_end(
        self,
        period: str,
        start: datetime
    ) -> Optional[datetime]:
        """Calculate period end date."""

        if period == "total":
            return None
        elif period == "daily":
            return start + timedelta(days=1)
        elif period == "weekly":
            return start + timedelta(weeks=1)
        elif period == "monthly":
            return start + timedelta(days=30)
        else:
            return None

    def _budget_to_dict(self, budget) -> Dict[str, Any]:
        """Convert budget model to dict."""
        return {
            "id": str(budget.id),
            "scope": budget.scope,
            "limit_usd": float(budget.limit_usd),
            "spent_usd": float(budget.spent_usd),
            "remaining_usd": float(budget.remaining_usd),
            "period": budget.period,
            "status": budget.status
        }

    def list_budgets(
        self,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all budgets for scope."""

        budgets = self._get_applicable_budgets(session_id, project_id)
        return [self._budget_to_dict(b) for b in budgets]
```

**Files to Create:**
- `cmbagent/cost/budget_manager.py`

**Verification:**
- Budgets created successfully
- Budget checks prevent execution when exceeded
- Spent amounts updated correctly
- Multiple budget scopes supported

### Task 5: Enhance Session Management APIs
**Objective:** Comprehensive session management

**Implementation:**

```python
# backend/api/sessions.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

class SessionCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    resource_limits: Optional[dict] = {}

class BudgetCreate(BaseModel):
    limit_usd: float
    period: str = "total"

@router.post("/")
async def create_session(session: SessionCreate):
    """Create new session."""
    from cmbagent.database.models import Sessions

    new_session = Sessions(
        name=session.name,
        metadata={"description": session.description},
        resource_limits=session.resource_limits,
        status="active"
    )

    db.add(new_session)
    db.commit()

    return {
        "id": str(new_session.id),
        "name": new_session.name,
        "created_at": new_session.created_at.isoformat()
    }

@router.get("/")
async def list_sessions(status: Optional[str] = None):
    """List all sessions."""
    from cmbagent.database.models import Sessions

    query = db.query(Sessions)

    if status:
        query = query.filter(Sessions.status == status)

    sessions = query.order_by(Sessions.last_active_at.desc()).all()

    return [
        {
            "id": str(s.id),
            "name": s.name,
            "status": s.status,
            "created_at": s.created_at.isoformat(),
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None
        }
        for s in sessions
    ]

@router.get("/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed session information."""
    from cmbagent.database.models import Sessions, WorkflowRuns
    from cmbagent.cost.budget_manager import BudgetManager

    session = db.query(Sessions).filter(Sessions.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get runs
    runs = db.query(WorkflowRuns).filter(
        WorkflowRuns.session_id == session_id
    ).all()

    # Get total cost
    total_cost = sum(r.total_cost_usd or 0 for r in runs)

    # Get budgets
    budget_mgr = BudgetManager(db)
    budgets = budget_mgr.list_budgets(session_id=session_id)

    return {
        "id": str(session.id),
        "name": session.name,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "total_runs": len(runs),
        "active_runs": len([r for r in runs if r.status == "executing"]),
        "total_cost_usd": float(total_cost),
        "budgets": budgets,
        "resource_limits": session.resource_limits
    }

@router.post("/{session_id}/budgets")
async def create_session_budget(session_id: str, budget: BudgetCreate):
    """Create budget for session."""
    from cmbagent.cost.budget_manager import BudgetManager
    from decimal import Decimal

    budget_mgr = BudgetManager(db)
    result = budget_mgr.create_budget(
        limit_usd=Decimal(str(budget.limit_usd)),
        scope="session",
        period=budget.period,
        session_id=session_id
    )

    return result

@router.get("/{session_id}/cost-analytics")
async def get_cost_analytics(session_id: str):
    """Get cost analytics for session."""
    from cmbagent.database.models import CostRecords
    from sqlalchemy import func

    # Cost by model
    cost_by_model = db.query(
        CostRecords.model,
        func.sum(CostRecords.cost_usd).label("total_cost"),
        func.sum(CostRecords.total_tokens).label("total_tokens")
    ).filter(
        CostRecords.session_id == session_id
    ).group_by(CostRecords.model).all()

    # Cost over time
    cost_over_time = db.query(
        func.date(CostRecords.timestamp).label("date"),
        func.sum(CostRecords.cost_usd).label("cost")
    ).filter(
        CostRecords.session_id == session_id
    ).group_by(func.date(CostRecords.timestamp)).all()

    return {
        "by_model": [
            {
                "model": row.model,
                "total_cost_usd": float(row.total_cost),
                "total_tokens": row.total_tokens
            }
            for row in cost_by_model
        ],
        "over_time": [
            {
                "date": row.date.isoformat(),
                "cost_usd": float(row.cost)
            }
            for row in cost_over_time
        ]
    }

@router.post("/{session_id}/archive")
async def archive_session(session_id: str):
    """Archive session."""
    from cmbagent.database.models import Sessions

    session = db.query(Sessions).filter(Sessions.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = "archived"
    db.commit()

    return {"status": "archived"}

@router.delete("/{session_id}")
async def delete_session(session_id: str, confirm: bool = False):
    """Delete session and all associated data."""

    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to delete session"
        )

    from cmbagent.database.models import Sessions
    import shutil

    session = db.query(Sessions).filter(Sessions.id == session_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete work directory
    work_dir = f"{BASE_WORK_DIR}/sessions/{session_id}"
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)

    # Delete database records (cascade)
    db.delete(session)
    db.commit()

    return {"status": "deleted"}
```

**Files to Create:**
- `backend/api/sessions.py`
- Update `backend/main.py` to include router

**Verification:**
- Session CRUD operations work
- Budget management per session
- Cost analytics accurate
- Archive and delete functional

### Task 6: Create Cost Dashboard UI
**Objective:** Real-time cost visualization

**Implementation:**

```typescript
// cmbagent-ui/src/components/CostDashboard.tsx
import React, { useEffect, useState } from 'react';
import { Line, Doughnut } from 'react-chartjs-2';

interface CostData {
  running_total_usd: number;
  total_tokens: number;
  by_model: Array<{model: string; cost: number}>;
  over_time: Array<{timestamp: string; cost: number}>;
}

export const CostDashboard: React.FC<{runId: string}> = ({ runId }) => {
  const [costData, setCostData] = useState<CostData>({
    running_total_usd: 0,
    total_tokens: 0,
    by_model: [],
    over_time: []
  });

  const [budget, setBudget] = useState<any>(null);

  useEffect(() => {
    // WebSocket listener for real-time updates
    const ws = new WebSocket(`/ws/${runId}`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'cost_update') {
        setCostData(prev => ({
          ...prev,
          running_total_usd: data.running_total_usd,
          total_tokens: data.total_tokens,
          over_time: [...prev.over_time, {
            timestamp: data.timestamp,
            cost: data.cost_usd
          }]
        }));
      }

      if (data.type === 'budget_alert') {
        // Show alert
        alert(`Budget ${data.severity}: ${data.threshold_percentage}% used`);
      }
    };

    return () => ws.close();
  }, [runId]);

  return (
    <div className="cost-dashboard">
      <div className="cost-summary">
        <h3>Real-Time Cost</h3>
        <div className="cost-value">
          ${costData.running_total_usd.toFixed(4)}
        </div>
        <div className="token-count">
          {costData.total_tokens.toLocaleString()} tokens
        </div>
      </div>

      {budget && (
        <div className="budget-progress">
          <h4>Budget</h4>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{
                width: `${(costData.running_total_usd / budget.limit_usd) * 100}%`
              }}
            />
          </div>
          <div className="budget-text">
            ${costData.running_total_usd.toFixed(2)} / ${budget.limit_usd.toFixed(2)}
          </div>
        </div>
      )}

      <div className="cost-chart">
        <h4>Cost Over Time</h4>
        <Line
          data={{
            labels: costData.over_time.map(d => d.timestamp),
            datasets: [{
              label: 'Cost ($)',
              data: costData.over_time.map(d => d.cost),
              borderColor: 'rgb(75, 192, 192)',
              tension: 0.1
            }]
          }}
        />
      </div>

      <div className="cost-by-model">
        <h4>Cost by Model</h4>
        <Doughnut
          data={{
            labels: costData.by_model.map(d => d.model),
            datasets: [{
              data: costData.by_model.map(d => d.cost),
              backgroundColor: [
                'rgba(255, 99, 132, 0.6)',
                'rgba(54, 162, 235, 0.6)',
                'rgba(255, 206, 86, 0.6)'
              ]
            }]
          }}
        />
      </div>
    </div>
  );
};
```

**Files to Create:**
- `cmbagent-ui/src/components/CostDashboard.tsx`
- `cmbagent-ui/src/components/BudgetAlert.tsx`

**Verification:**
- Real-time cost updates displayed
- Charts render correctly
- Budget progress visible
- Alerts shown when thresholds exceeded

## Files to Create (Summary)

### New Files
```
cmbagent/cost/
├── __init__.py
├── realtime_tracker.py
├── estimator.py
├── budget_manager.py
└── pricing.py

backend/api/
└── sessions.py

cmbagent-ui/src/components/
├── CostDashboard.tsx
└── BudgetAlert.tsx
```

### Modified Files
- `cmbagent/database/models.py` - Add cost/budget models
- `cmbagent/database/migrations/versions/013_enhanced_cost_tracking.py` - Migration
- `cmbagent/cmbagent.py` - Integrate cost tracking
- `backend/main.py` - Add sessions router

## Verification Criteria

### Must Pass
- [ ] Cost tracking tables created
- [ ] Real-time cost tracker functional
- [ ] WebSocket cost updates streaming
- [ ] Cost estimation accurate
- [ ] Budget creation and enforcement working
- [ ] Session management APIs operational
- [ ] Cost dashboard displays real-time data
- [ ] Budget alerts triggered correctly

### Should Pass
- [ ] Multiple budget scopes supported
- [ ] Cost analytics calculated correctly
- [ ] Estimation accuracy improves over time
- [ ] Session isolation maintained
- [ ] Archive/delete operations work

### Nice to Have
- [ ] Cost predictions based on trends
- [ ] Budget recommendations
- [ ] Cost optimization suggestions
- [ ] Export cost reports

## Testing Checklist

### Unit Tests
```python
def test_realtime_cost_tracking():
    tracker = RealtimeCostTracker(db, ws, run_id, session_id)
    tracker.track_llm_call("gpt-4o", "openai", 1000, 500)
    assert tracker.get_running_total()["total_cost_usd"] > 0

def test_cost_estimation():
    estimator = CostEstimator(db)
    estimate = estimator.estimate_workflow("Test task", "one_shot", "engineer", "gpt-4o")
    assert estimate["estimated_cost_usd"] > 0

def test_budget_enforcement():
    budget_mgr = BudgetManager(db)
    budget_mgr.create_budget(Decimal("10.00"), "session", session_id=session_id)
    result = budget_mgr.check_budget_available(Decimal("15.00"), session_id=session_id)
    assert result["allowed"] == False
```

## Common Issues and Solutions

### Issue 1: Cost Calculation Inaccurate
**Symptom:** Costs don't match actual API charges
**Solution:** Update pricing data, verify token counts, check provider pricing changes

### Issue 2: Budget Alerts Not Triggering
**Symptom:** No alerts when budget exceeded
**Solution:** Verify WebSocket connection, check alert threshold logic, ensure budget active

### Issue 3: Real-Time Updates Delayed
**Symptom:** UI cost display lags
**Solution:** Optimize WebSocket broadcasting, reduce update frequency, check network latency

### Issue 4: Session Cost Aggregation Wrong
**Symptom:** Total costs don't sum correctly
**Solution:** Verify session_id in cost records, check SQL aggregation queries, validate isolation

## Rollback Procedure

If cost tracking enhancements cause issues:

1. **Disable real-time tracking:**
   ```python
   USE_REALTIME_COST = os.getenv("CMBAGENT_REALTIME_COST", "false") == "true"
   ```

2. **Revert to file-based cost tracking:**
   - Keep database records for history
   - Fall back to cost files

3. **Disable budget enforcement:**
   - Allow workflows to run without budget checks
   - Keep tracking but don't block

## Post-Stage Actions

### Documentation
- Document cost tracking API
- Create budget management guide
- Add cost optimization tips
- Update architecture documentation

### Update Progress
- Mark Stage 13 complete in PROGRESS.md
- Note any deviations from plan
- Document time spent

### Prepare for Stage 14
- Cost tracking operational
- Session management comprehensive
- Ready to add observability
- Stage 14 can proceed

## Success Criteria

Stage 13 is complete when:
1. Real-time cost tracking functional
2. Cost estimation accurate
3. Budget management working
4. Session APIs comprehensive
5. Cost dashboard displays real-time data
6. Budget alerts functioning
7. All tests passing
8. Verification checklist 100% complete

## Estimated Time Breakdown

- Database schema enhancement: 5 min
- Real-time cost tracker: 10 min
- Cost estimation: 8 min
- Budget management: 10 min
- Session management APIs: 8 min
- Cost dashboard UI: 10 min
- Testing and verification: 10 min
- Documentation: 5 min

**Total: 35-45 minutes**

## Next Stage

Once Stage 13 is verified complete, proceed to:
**Stage 14: Observability and Metrics**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
