# Stage 15: Open Policy Agent Integration

**Phase:** 4 - Advanced Features
**Estimated Time:** 40-50 minutes
**Dependencies:** Stages 1-14 complete
**Risk Level:** Medium-High

## Objectives

1. Integrate Open Policy Agent (OPA) for policy enforcement
2. Implement DEFAULT ALLOW ALL policy stance
3. Create opt-in policy restriction system
4. Add policy decision logging and audit trail
5. Build policy management UI
6. Implement common policy templates
7. Add policy testing and validation tools

## Current State Analysis

### What We Have
- No policy enforcement system
- All operations allowed by default (implicit)
- No audit trail for decisions
- No way to restrict operations
- No compliance framework

### What We Need
- OPA integration
- Policy decision points in code
- DEFAULT ALLOW ALL explicit policy
- Opt-in restriction capabilities
- Audit logging for all policy decisions
- Policy management interface
- Pre-built policy templates
- Policy testing tools

## Pre-Stage Verification

### Check Prerequisites
1. Stages 1-14 complete and verified
2. Observability infrastructure operational
3. Database schema includes audit tables
4. Workflow execution stable

### Expected State
- System running without restrictions
- Ready to add policy layer
- Observability tracking decisions
- Tests passing

## Implementation Tasks

### Task 1: Install OPA and Dependencies
**Objective:** Set up OPA server and Python client

**Install OPA:**
```bash
# Download OPA binary
curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64
chmod +x opa
sudo mv opa /usr/local/bin/
```

**Python Dependencies:**
```toml
# pyproject.toml
dependencies = [
    # Existing dependencies...
    "opa-python-client>=1.3",
    "requests>=2.31"
]
```

**Docker Compose:**
```yaml
# docker-compose.observability.yml (add to existing)
services:
  opa:
    image: openpolicyagent/opa:latest
    ports:
      - "8181:8181"
    command:
      - "run"
      - "--server"
      - "--log-level=debug"
      - "/policies"
    volumes:
      - ./policies:/policies
```

**Files to Modify:**
- `pyproject.toml`
- `docker-compose.observability.yml`

**Verification:**
- OPA installed successfully
- OPA server starts
- Can query OPA API
- Python client can connect

### Task 2: Create Database Schema for Policy Decisions
**Objective:** Track all policy decisions for audit

**New Tables:**

**policy_decisions table:**
- id (UUID, primary key)
- timestamp (TIMESTAMP)
- run_id (UUID, foreign key, nullable)
- step_id (UUID, foreign key, nullable)
- session_id (UUID, foreign key, nullable)
- decision (VARCHAR 50: allow, deny)
- policy_name (VARCHAR 255)
- action (VARCHAR 100: file_write, api_call, etc.)
- resource (VARCHAR 500)
- subject (VARCHAR 255: agent name, user)
- input_data (JSONB)
- policy_result (JSONB)
- decision_reason (TEXT)
- duration_ms (INTEGER)

**policy_rules table:**
- id (UUID, primary key)
- name (VARCHAR 255, unique)
- description (TEXT)
- policy_content (TEXT)  # Rego policy code
- status (VARCHAR 50: active, inactive, draft)
- scope (VARCHAR 50: global, session, project, user)
- scope_id (UUID, nullable)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
- created_by (VARCHAR 255)
- version (INTEGER)

**policy_violations table:**
- id (UUID, primary key)
- decision_id (UUID, foreign key)
- violation_type (VARCHAR 100)
- severity (VARCHAR 50: info, warning, critical)
- action_taken (VARCHAR 100: logged, blocked, alerted)
- notified (BOOLEAN)
- notification_details (JSONB)

**Files to Create:**
- `cmbagent/database/migrations/versions/015_policy_system.py`
- Add models to `cmbagent/database/models.py`

**Verification:**
- Migration runs successfully
- Tables created
- Indexes on timestamp, session_id
- Can record policy decisions

### Task 3: Implement Default ALLOW ALL Policy
**Objective:** Explicit permissive default policy

**Implementation:**

```rego
# policies/default.rego
package cmbagent.default

# DEFAULT POLICY: ALLOW ALL
# This is the default stance for scientific discovery workflows.
# CMBAgent is designed for research and experimentation, which requires
# maximum flexibility. Users can opt-in to stricter policies when needed.

import future.keywords.if
import future.keywords.in

# Default decision: ALLOW
default allow := true

# Default deny reasons (empty by default)
default deny_reasons := []

# Audit all decisions (even allows)
log_decision := {
    "decision": allow,
    "policy": "default_allow_all",
    "timestamp": time.now_ns(),
    "reason": "Default permissive policy"
}

# Optional: Warnings for sensitive operations
warnings[msg] {
    input.action == "file_delete"
    msg := "Warning: File deletion operation (allowed by default)"
}

warnings[msg] {
    input.action == "external_api_call"
    input.resource.url
    not startswith(input.resource.url, "https://")
    msg := "Warning: Non-HTTPS API call detected (allowed by default)"
}

# Cost warning (does not block)
warnings[msg] {
    input.action == "llm_call"
    input.estimated_cost_usd > 1.0
    msg := sprintf("Warning: High cost operation ($%.2f) - allowed by default", [input.estimated_cost_usd])
}
```

**Files to Create:**
- `policies/default.rego`

**Verification:**
- Default policy allows all operations
- Warnings generated but don't block
- Audit logging captures decisions
- Policy evaluates correctly

### Task 4: Create Opt-In Restriction Policies
**Objective:** Policy templates users can enable

**Cost Control Policy:**
```rego
# policies/cost_control.rego
package cmbagent.cost_control

import future.keywords.if

# OPT-IN POLICY: Cost Control
# Enable this policy to enforce budget limits

default allow := true

# Block if cost exceeds budget
allow := false if {
    input.action == "llm_call"
    input.budget.remaining_usd < input.estimated_cost_usd
}

deny_reasons["budget_exceeded"] if {
    input.action == "llm_call"
    input.budget.remaining_usd < input.estimated_cost_usd
}

# Block expensive models for low-priority tasks
allow := false if {
    input.action == "llm_call"
    input.model in ["gpt-4", "claude-opus-4"]
    input.task_priority == "low"
}

deny_reasons["expensive_model_for_low_priority"] if {
    input.action == "llm_call"
    input.model in ["gpt-4", "claude-opus-4"]
    input.task_priority == "low"
}
```

**Data Privacy Policy:**
```rego
# policies/data_privacy.rego
package cmbagent.data_privacy

import future.keywords.if

# OPT-IN POLICY: Data Privacy
# Prevent sensitive data exposure

default allow := true

# Block reading files with sensitive data patterns
allow := false if {
    input.action == "file_read"
    sensitive_file(input.resource.path)
}

sensitive_file(path) if {
    contains(path, ".env")
}

sensitive_file(path) if {
    contains(path, "credentials")
}

sensitive_file(path) if {
    contains(path, "secrets")
}

sensitive_file(path) if {
    endswith(path, ".pem")
}

sensitive_file(path) if {
    endswith(path, ".key")
}

deny_reasons["sensitive_file_access"] if {
    input.action == "file_read"
    sensitive_file(input.resource.path)
}
```

**Rate Limiting Policy:**
```rego
# policies/rate_limiting.rego
package cmbagent.rate_limiting

import future.keywords.if

# OPT-IN POLICY: Rate Limiting
# Prevent API abuse

default allow := true

# Check rate limits
allow := false if {
    input.action == "llm_call"
    exceeds_rate_limit(input.agent, input.timewindow_seconds)
}

exceeds_rate_limit(agent, window) if {
    count(input.recent_calls[agent]) > 100
}

deny_reasons["rate_limit_exceeded"] if {
    input.action == "llm_call"
    exceeds_rate_limit(input.agent, input.timewindow_seconds)
}
```

**Files to Create:**
- `policies/cost_control.rego`
- `policies/data_privacy.rego`
- `policies/rate_limiting.rego`
- `policies/time_restrictions.rego` (business hours only)
- `policies/compliance.rego` (regulatory compliance)

**Verification:**
- Policies compile successfully
- Policies block when enabled
- Policies allow when disabled
- Deny reasons clear and actionable

### Task 5: Implement Policy Client
**Objective:** Python client for OPA integration

**Implementation:**

```python
# cmbagent/policy/client.py
from typing import Dict, Any, Optional, List
import requests
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PolicyClient:
    """Client for Open Policy Agent."""

    def __init__(
        self,
        opa_url: str = "http://localhost:8181",
        enabled: bool = True
    ):
        self.opa_url = opa_url
        self.enabled = enabled

        # Policy package to evaluate (default or custom)
        self.default_package = "cmbagent.default"

    def check_permission(
        self,
        action: str,
        resource: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        package: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check if action is allowed by policy."""

        if not self.enabled:
            # Policy enforcement disabled
            return {
                "allowed": True,
                "decision": "allow",
                "reason": "Policy enforcement disabled"
            }

        # Build input document
        input_doc = {
            "action": action,
            "resource": resource,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        }

        # Add context fields
        if context:
            input_doc.update({
                "agent": context.get("agent"),
                "session_id": context.get("session_id"),
                "run_id": context.get("run_id"),
                "budget": context.get("budget"),
                "user": context.get("user")
            })

        # Determine package to evaluate
        policy_package = package or self.default_package

        # Query OPA
        start_time = time.time()

        try:
            response = requests.post(
                f"{self.opa_url}/v1/data/{policy_package.replace('.', '/')}",
                json={"input": input_doc},
                timeout=1.0  # Fast timeout for policy checks
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if response.status_code != 200:
                logger.error(f"OPA query failed: {response.status_code}")
                # Fail open (allow) if OPA unavailable
                return {
                    "allowed": True,
                    "decision": "allow",
                    "reason": "Policy engine unavailable (fail open)",
                    "error": True
                }

            result = response.json()

            # Extract decision
            allowed = result.get("result", {}).get("allow", True)
            deny_reasons = result.get("result", {}).get("deny_reasons", [])
            warnings = result.get("result", {}).get("warnings", [])

            decision = {
                "allowed": allowed,
                "decision": "allow" if allowed else "deny",
                "policy_package": policy_package,
                "deny_reasons": deny_reasons,
                "warnings": warnings,
                "duration_ms": duration_ms,
                "input": input_doc,
                "policy_result": result.get("result", {})
            }

            # Log decision
            self._log_decision(decision, context)

            return decision

        except requests.exceptions.RequestException as e:
            logger.error(f"OPA connection error: {e}")
            # Fail open
            return {
                "allowed": True,
                "decision": "allow",
                "reason": "Policy engine connection failed (fail open)",
                "error": True
            }

    def _log_decision(
        self,
        decision: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ):
        """Log policy decision to database."""

        try:
            from cmbagent.database import get_db_session
            from cmbagent.database.models import PolicyDecisions

            db = get_db_session()

            record = PolicyDecisions(
                timestamp=datetime.utcnow(),
                run_id=context.get("run_id") if context else None,
                step_id=context.get("step_id") if context else None,
                session_id=context.get("session_id") if context else None,
                decision=decision["decision"],
                policy_name=decision["policy_package"],
                action=decision["input"]["action"],
                resource=str(decision["input"]["resource"]),
                subject=context.get("agent") if context else None,
                input_data=decision["input"],
                policy_result=decision["policy_result"],
                decision_reason=", ".join(decision.get("deny_reasons", [])),
                duration_ms=decision.get("duration_ms")
            )

            db.add(record)
            db.commit()

        except Exception as e:
            logger.error(f"Failed to log policy decision: {e}")

    def evaluate_batch(
        self,
        actions: List[Dict[str, Any]],
        package: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Evaluate multiple policy decisions in batch."""

        results = []

        for action in actions:
            result = self.check_permission(
                action=action["action"],
                resource=action["resource"],
                context=action.get("context"),
                package=package
            )
            results.append(result)

        return results

    def get_active_policies(self) -> List[str]:
        """Get list of active policy packages."""

        try:
            response = requests.get(
                f"{self.opa_url}/v1/policies",
                timeout=1.0
            )

            if response.status_code == 200:
                policies = response.json().get("result", [])
                return [p["id"] for p in policies]

        except Exception as e:
            logger.error(f"Failed to get active policies: {e}")

        return []

    def test_policy(
        self,
        policy_content: str,
        test_inputs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Test policy with sample inputs."""

        # This would use OPA's policy testing features
        # For now, a simplified version

        results = {
            "policy_valid": True,
            "test_results": []
        }

        for test_input in test_inputs:
            result = self.check_permission(
                action=test_input["action"],
                resource=test_input["resource"],
                context=test_input.get("context")
            )

            results["test_results"].append({
                "input": test_input,
                "result": result,
                "expected": test_input.get("expected_decision"),
                "passed": result["decision"] == test_input.get("expected_decision", "allow")
            })

        return results
```

**Files to Create:**
- `cmbagent/policy/__init__.py`
- `cmbagent/policy/client.py`
- `cmbagent/policy/decorators.py`

**Verification:**
- Can connect to OPA
- Policy checks work
- Decisions logged to database
- Fail-open behavior correct

### Task 6: Add Policy Enforcement Points
**Objective:** Integrate policy checks into operations

**Implementation:**

```python
# cmbagent/policy/decorators.py
from functools import wraps
from typing import Callable, Optional, Dict, Any
from cmbagent.policy.client import PolicyClient

policy_client = PolicyClient(
    enabled=os.getenv("POLICY_ENFORCEMENT_ENABLED", "false") == "true"
)

def enforce_policy(
    action: str,
    resource_extractor: Optional[Callable] = None
):
    """Decorator to enforce policy on function."""

    def decorator(func: Callable) -> Callable:

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract resource info
            if resource_extractor:
                resource = resource_extractor(*args, **kwargs)
            else:
                resource = {"function": func.__name__}

            # Get context
            context = kwargs.get("context", {})

            # Check policy
            decision = policy_client.check_permission(
                action=action,
                resource=resource,
                context=context
            )

            # Log warnings
            if decision.get("warnings"):
                for warning in decision["warnings"]:
                    logger.warning(f"Policy warning: {warning}")

            # Enforce decision
            if not decision["allowed"]:
                from cmbagent.policy.exceptions import PolicyDeniedError

                raise PolicyDeniedError(
                    action=action,
                    resource=resource,
                    reasons=decision.get("deny_reasons", []),
                    policy=decision.get("policy_package")
                )

            # Execute function
            return func(*args, **kwargs)

        return wrapper

    return decorator

# Example usage:
"""
@enforce_policy(
    action="file_write",
    resource_extractor=lambda file_path, content: {"path": file_path, "size": len(content)}
)
def write_file(file_path: str, content: str, context: dict = None):
    with open(file_path, 'w') as f:
        f.write(content)
"""
```

**Add to Key Operations:**
```python
# cmbagent/agents/base_agent.py
from cmbagent.policy.decorators import enforce_policy

class BaseAgent:

    @enforce_policy(
        action="llm_call",
        resource_extractor=lambda self, model, messages, context: {
            "model": model,
            "prompt_length": sum(len(m.get("content", "")) for m in messages),
            "estimated_cost": context.get("estimated_cost", 0)
        }
    )
    def call_llm(self, model: str, messages: List, context: dict = None):
        # Make LLM call
        pass

    @enforce_policy(
        action="file_write",
        resource_extractor=lambda self, path, context: {"path": path}
    )
    def write_file(self, path: str, content: str, context: dict = None):
        # Write file
        pass
```

**Files to Modify:**
- `cmbagent/agents/base_agent.py`
- `cmbagent/functions.py`
- Key operation functions

**Verification:**
- Policy checks execute before operations
- Denied operations raise exceptions
- Warnings logged
- Context passed correctly

### Task 7: Create Policy Management UI
**Objective:** Web interface for policy management

**Implementation:**

```typescript
// cmbagent-ui/src/components/PolicyManagement.tsx
import React, { useState, useEffect } from 'react';

interface Policy {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'inactive' | 'draft';
  content: string;
}

export const PolicyManagement: React.FC = () => {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);

  useEffect(() => {
    fetchPolicies();
  }, []);

  const fetchPolicies = async () => {
    const response = await fetch('/api/policies');
    const data = await response.json();
    setPolicies(data.policies);
  };

  const togglePolicy = async (policyId: string, enabled: boolean) => {
    await fetch(`/api/policies/${policyId}`, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: enabled ? 'active' : 'inactive'})
    });

    fetchPolicies();
  };

  return (
    <div className="policy-management">
      <h2>Policy Management</h2>

      <div className="policy-notice">
        <strong>Default Policy: ALLOW ALL</strong>
        <p>
          All operations are allowed by default. Enable policies below to add restrictions.
        </p>
      </div>

      <div className="policy-list">
        {policies.map(policy => (
          <div key={policy.id} className="policy-card">
            <div className="policy-header">
              <h3>{policy.name}</h3>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={policy.status === 'active'}
                  onChange={(e) => togglePolicy(policy.id, e.target.checked)}
                />
                <span className="slider"></span>
              </label>
            </div>

            <p className="policy-description">{policy.description}</p>

            {policy.status === 'active' && (
              <div className="policy-status active">
                <span>✓ Enabled</span>
              </div>
            )}

            <button onClick={() => setSelectedPolicy(policy)}>
              View Policy
            </button>
          </div>
        ))}
      </div>

      {selectedPolicy && (
        <PolicyViewer
          policy={selectedPolicy}
          onClose={() => setSelectedPolicy(null)}
        />
      )}
    </div>
  );
};

const PolicyViewer: React.FC<{policy: Policy; onClose: () => void}> = ({policy, onClose}) => {
  return (
    <div className="modal">
      <div className="modal-content">
        <h2>{policy.name}</h2>
        <pre className="policy-code">
          {policy.content}
        </pre>
        <button onClick={onClose}>Close</button>
      </div>
    </div>
  );
};
```

**API Endpoints:**
```python
# backend/api/policies.py
from fastapi import APIRouter, HTTPException
from typing import List

router = APIRouter(prefix="/api/policies", tags=["policies"])

@router.get("/")
async def list_policies():
    """List all policies."""
    from cmbagent.database.models import PolicyRules

    policies = db.query(PolicyRules).all()

    return {
        "policies": [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "scope": p.scope
            }
            for p in policies
        ]
    }

@router.get("/{policy_id}")
async def get_policy(policy_id: str):
    """Get policy details."""
    from cmbagent.database.models import PolicyRules

    policy = db.query(PolicyRules).filter(PolicyRules.id == policy_id).first()

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    return {
        "id": str(policy.id),
        "name": policy.name,
        "description": policy.description,
        "content": policy.policy_content,
        "status": policy.status,
        "scope": policy.scope
    }

@router.patch("/{policy_id}")
async def update_policy(policy_id: str, update: dict):
    """Update policy status."""
    from cmbagent.database.models import PolicyRules

    policy = db.query(PolicyRules).filter(PolicyRules.id == policy_id).first()

    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if "status" in update:
        policy.status = update["status"]

    db.commit()

    return {"status": "updated"}

@router.get("/decisions/audit")
async def get_policy_audit(
    session_id: Optional[str] = None,
    limit: int = 100
):
    """Get policy decision audit log."""
    from cmbagent.database.models import PolicyDecisions

    query = db.query(PolicyDecisions).order_by(PolicyDecisions.timestamp.desc())

    if session_id:
        query = query.filter(PolicyDecisions.session_id == session_id)

    decisions = query.limit(limit).all()

    return {
        "decisions": [
            {
                "timestamp": d.timestamp.isoformat(),
                "decision": d.decision,
                "action": d.action,
                "resource": d.resource,
                "policy": d.policy_name,
                "reason": d.decision_reason
            }
            for d in decisions
        ]
    }
```

**Files to Create:**
- `cmbagent-ui/src/components/PolicyManagement.tsx`
- `cmbagent-ui/src/components/PolicyAudit.tsx`
- `backend/api/policies.py`

**Verification:**
- Policy list displays correctly
- Can enable/disable policies
- Policy content viewable
- Audit log accessible

### Task 8: Create Policy Testing Tools
**Objective:** Test policies before deployment

**Implementation:**

```python
# cmbagent/policy/testing.py
from typing import List, Dict, Any
import yaml

class PolicyTester:
    """Test policies with sample inputs."""

    def __init__(self, policy_client):
        self.client = policy_client

    def run_test_suite(self, test_file: str) -> Dict[str, Any]:
        """Run policy test suite from YAML file."""

        with open(test_file) as f:
            test_suite = yaml.safe_load(f)

        results = {
            "policy": test_suite["policy"],
            "total_tests": len(test_suite["tests"]),
            "passed": 0,
            "failed": 0,
            "test_results": []
        }

        for test in test_suite["tests"]:
            result = self.client.check_permission(
                action=test["action"],
                resource=test["resource"],
                context=test.get("context"),
                package=test_suite["policy"]
            )

            expected = test["expected"]
            passed = result["decision"] == expected["decision"]

            if passed:
                results["passed"] += 1
            else:
                results["failed"] += 1

            results["test_results"].append({
                "name": test["name"],
                "passed": passed,
                "expected": expected,
                "actual": result,
                "description": test.get("description")
            })

        return results

# Example test file:
"""
# policy_tests.yaml
policy: cmbagent.cost_control
tests:
  - name: "Block expensive call when budget exceeded"
    description: "Should deny LLM call when budget is insufficient"
    action: "llm_call"
    resource:
      model: "gpt-4"
    context:
      estimated_cost: 0.50
      budget:
        remaining_usd: 0.10
    expected:
      decision: "deny"
      deny_reasons: ["budget_exceeded"]

  - name: "Allow call with sufficient budget"
    action: "llm_call"
    resource:
      model: "gpt-4"
    context:
      estimated_cost: 0.10
      budget:
        remaining_usd: 1.00
    expected:
      decision: "allow"
"""
```

**CLI Command:**
```python
# cmbagent/cli.py
@click.command()
@click.argument("test_file")
def test_policy(test_file):
    """Test policy with test file."""
    from cmbagent.policy.testing import PolicyTester
    from cmbagent.policy.client import PolicyClient

    client = PolicyClient()
    tester = PolicyTester(client)

    results = tester.run_test_suite(test_file)

    click.echo(f"Policy: {results['policy']}")
    click.echo(f"Tests: {results['total_tests']}")
    click.echo(f"Passed: {results['passed']}")
    click.echo(f"Failed: {results['failed']}")

    for test in results["test_results"]:
        status = "✓" if test["passed"] else "✗"
        click.echo(f"{status} {test['name']}")

        if not test["passed"]:
            click.echo(f"  Expected: {test['expected']}")
            click.echo(f"  Actual: {test['actual']['decision']}")
```

**Files to Create:**
- `cmbagent/policy/testing.py`
- `tests/policy_tests/` (directory for test files)
- Update `cmbagent/cli.py`

**Verification:**
- Can run policy tests
- Test results accurate
- Test file format validated
- CLI command works

## Files to Create (Summary)

### New Files
```
policies/
├── default.rego
├── cost_control.rego
├── data_privacy.rego
├── rate_limiting.rego
├── time_restrictions.rego
└── compliance.rego

cmbagent/policy/
├── __init__.py
├── client.py
├── decorators.py
├── exceptions.py
└── testing.py

backend/api/
└── policies.py

cmbagent-ui/src/components/
├── PolicyManagement.tsx
└── PolicyAudit.tsx

tests/policy_tests/
├── cost_control_tests.yaml
├── data_privacy_tests.yaml
└── rate_limiting_tests.yaml
```

### Modified Files
- `pyproject.toml` - Add OPA dependencies
- `docker-compose.observability.yml` - Add OPA service
- `cmbagent/database/models.py` - Add policy models
- `cmbagent/database/migrations/versions/015_policy_system.py` - Migration
- `cmbagent/agents/base_agent.py` - Add policy enforcement
- `cmbagent/cli.py` - Add policy testing command
- `backend/main.py` - Add policies router

## Verification Criteria

### Must Pass
- [ ] OPA installed and running
- [ ] Policy database tables created
- [ ] Default ALLOW ALL policy working
- [ ] Opt-in policies can be enabled
- [ ] Policy client connects to OPA
- [ ] Policy decisions logged to database
- [ ] Fail-open behavior correct (allow on error)
- [ ] Policy enforcement doesn't break workflows

### Should Pass
- [ ] Policy management UI functional
- [ ] Can enable/disable policies via UI
- [ ] Policy audit log accessible
- [ ] Policy testing tools work
- [ ] Multiple policies can be active
- [ ] Policy context passed correctly

### Nice to Have
- [ ] Policy recommendations based on usage
- [ ] Policy impact analysis
- [ ] Custom policy editor
- [ ] Policy versioning

## Testing Checklist

### Unit Tests
```python
def test_default_allow_all():
    client = PolicyClient()
    result = client.check_permission("any_action", {"resource": "test"})
    assert result["allowed"] == True

def test_cost_control_policy():
    client = PolicyClient()
    result = client.check_permission(
        action="llm_call",
        resource={"model": "gpt-4"},
        context={"estimated_cost": 1.0, "budget": {"remaining_usd": 0.5}},
        package="cmbagent.cost_control"
    )
    assert result["allowed"] == False
    assert "budget_exceeded" in result["deny_reasons"]

def test_policy_fail_open():
    # Stop OPA server
    client = PolicyClient(opa_url="http://localhost:9999")  # Wrong port
    result = client.check_permission("test", {"resource": "test"})
    # Should allow (fail open)
    assert result["allowed"] == True
```

### Integration Tests
```python
def test_policy_enforcement_in_workflow():
    # Enable cost control policy
    enable_policy("cost_control")

    # Try to run workflow that exceeds budget
    with pytest.raises(PolicyDeniedError):
        agent = CMBAgent()
        agent.one_shot("expensive task", budget={"limit_usd": 0.01})
```

## Common Issues and Solutions

### Issue 1: OPA Not Starting
**Symptom:** Cannot connect to OPA
**Solution:** Check OPA logs, verify port 8181 available, restart OPA service

### Issue 2: Policies Not Loading
**Symptom:** Policy decisions always default
**Solution:** Verify policy files in /policies directory, check OPA bundle loading

### Issue 3: Policy Blocking Legitimate Operations
**Symptom:** Workflows fail with policy denials
**Solution:** Review policy rules, adjust thresholds, or disable overly restrictive policies

### Issue 4: Audit Log Growing Too Large
**Symptom:** Database size increasing rapidly
**Solution:** Implement log rotation, archive old decisions, add retention policy

### Issue 5: Performance Impact
**Symptom:** Policy checks slow down operations
**Solution:** Optimize policy rules, add caching, increase OPA timeout

## Rollback Procedure

If policy system causes issues:

1. **Disable policy enforcement:**
   ```bash
   export POLICY_ENFORCEMENT_ENABLED=false
   ```

2. **Revert to default allow:**
   - Policy enforcement disabled by default
   - System returns to original behavior

3. **Stop OPA service:**
   ```bash
   docker-compose -f docker-compose.observability.yml stop opa
   ```

4. **Keep audit logs** - Useful for analysis

## Post-Stage Actions

### Documentation
- Document policy system architecture
- Create policy writing guide
- Add example policies
- Update security documentation

### Update Progress
- Mark Stage 15 complete in PROGRESS.md
- Note any deviations from plan
- Document time spent

### Project Complete
- All 15 stages complete
- CMBAgent fully enhanced
- Ready for production use
- Begin user acceptance testing

## Success Criteria

Stage 15 is complete when:
1. OPA integrated successfully
2. Default ALLOW ALL policy explicit
3. Opt-in policies available
4. Policy decisions logged
5. Policy management UI functional
6. Policy testing tools working
7. No disruption to existing workflows
8. All tests passing
9. Verification checklist 100% complete

## Estimated Time Breakdown

- OPA installation and setup: 8 min
- Database schema: 5 min
- Default policy implementation: 7 min
- Opt-in policies: 10 min
- Policy client: 10 min
- Enforcement integration: 8 min
- Policy management UI: 8 min
- Testing tools: 7 min
- Testing and verification: 10 min
- Documentation: 5 min

**Total: 40-50 minutes**

## Next Steps

Once Stage 15 is verified complete:
1. **System Integration Testing** - Test all components together
2. **Performance Testing** - Verify no degradation
3. **User Acceptance Testing** - Get feedback from researchers
4. **Documentation Finalization** - Complete all documentation
5. **Deployment Planning** - Plan production rollout
6. **Training Materials** - Create user guides and tutorials

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14

## Notes on Policy Philosophy

**Why DEFAULT ALLOW ALL?**

CMBAgent is designed for scientific discovery and research workflows. These use cases require:

1. **Flexibility**: Researchers need to experiment without bureaucratic barriers
2. **Rapid Iteration**: Scientific discovery is exploratory by nature
3. **Trust**: Scientists are professionals who understand their work
4. **Opt-In Control**: When restrictions are needed (compliance, budget), they can be explicitly enabled

**This is NOT a bug, it's a feature.** The policy system is:
- Ready to enforce rules when needed
- Auditing all decisions by default
- Providing opt-in control mechanisms
- Defaulting to enabling research, not blocking it

Traditional "secure by default, deny everything" approaches are appropriate for:
- Production web applications
- Financial systems
- Healthcare systems
- Multi-tenant SaaS platforms

But CMBAgent is a research tool, more analogous to:
- Jupyter notebooks (allow arbitrary code execution)
- Data science environments
- Research computing clusters
- Development environments

The policy framework provides the **capability** for restriction without imposing it by **default**.
