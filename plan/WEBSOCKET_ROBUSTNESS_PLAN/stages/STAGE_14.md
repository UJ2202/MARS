# Stage 14: Migration & Deployment

**Phase:** 5 - Testing & Deployment
**Dependencies:** All previous stages
**Risk Level:** High
**Estimated Time:** 2-3 days

## Objectives

1. Create deployment checklist
2. Set up staging environment testing
3. Define rollback procedures
4. Execute production deployment

## Pre-Deployment Checklist

### Code Review
- [ ] All PRs merged
- [ ] No TODO comments in critical paths
- [ ] No debug print statements remaining
- [ ] All tests passing

### Database
- [ ] Migration scripts tested on copy of production data
- [ ] Backup created before migration
- [ ] Rollback migration tested

### Configuration
- [ ] Environment variables documented
- [ ] Logging level set appropriately
- [ ] Connection limits configured
- [ ] Timeout values set

### Monitoring
- [ ] Log aggregation configured
- [ ] Error alerting set up
- [ ] Performance metrics dashboard ready

## Implementation Tasks

### Task 1: Create Deployment Script

**File to Create:** `scripts/deploy.sh`

```bash
#!/bin/bash
# Production deployment script

set -e

# Configuration
BACKUP_DIR="/var/backups/cmbagent"
DEPLOY_DIR="/srv/cmbagent"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=== CMBAgent Deployment Script ==="
echo "Timestamp: $TIMESTAMP"
echo ""

# Pre-flight checks
echo "Running pre-flight checks..."

# Check if services are reachable
echo "  Checking database..."
python -c "from cmbagent.database import get_db_session; get_db_session().close()" || {
    echo "ERROR: Database not reachable"
    exit 1
}
echo "  ✓ Database OK"

# Backup current state
echo ""
echo "Creating backup..."
mkdir -p "$BACKUP_DIR"

# Backup database
echo "  Backing up database..."
cp ~/.cmbagent/cmbagent.db "$BACKUP_DIR/cmbagent_$TIMESTAMP.db" 2>/dev/null || true
echo "  ✓ Database backup: $BACKUP_DIR/cmbagent_$TIMESTAMP.db"

# Backup code
echo "  Backing up code..."
tar -czf "$BACKUP_DIR/code_$TIMESTAMP.tar.gz" -C "$DEPLOY_DIR" . --exclude='.venv' --exclude='node_modules' 2>/dev/null || true
echo "  ✓ Code backup: $BACKUP_DIR/code_$TIMESTAMP.tar.gz"

# Run migrations
echo ""
echo "Running database migrations..."
cd "$DEPLOY_DIR"
alembic upgrade head
echo "  ✓ Migrations complete"

# Restart services
echo ""
echo "Restarting services..."

# Backend
echo "  Restarting backend..."
systemctl restart cmbagent-backend || {
    echo "WARNING: Could not restart backend via systemctl"
    echo "  Trying manual restart..."
    pkill -f "uvicorn main:app" || true
    sleep 2
    cd "$DEPLOY_DIR/backend"
    nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /var/log/cmbagent/backend.log 2>&1 &
}
echo "  ✓ Backend restarted"

# Frontend (if applicable)
echo "  Restarting frontend..."
cd "$DEPLOY_DIR/cmbagent-ui"
npm run build
systemctl restart cmbagent-frontend || {
    echo "WARNING: Could not restart frontend via systemctl"
}
echo "  ✓ Frontend restarted"

# Health check
echo ""
echo "Running health checks..."
sleep 5

# Check backend health
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✓ Backend health check passed"
else
    echo "  ✗ Backend health check failed (HTTP $HTTP_CODE)"
    echo ""
    echo "DEPLOYMENT FAILED - Rolling back..."
    bash scripts/rollback.sh "$TIMESTAMP"
    exit 1
fi

echo ""
echo "=== Deployment Complete ==="
echo "Backup timestamp: $TIMESTAMP (use for rollback if needed)"
```

### Task 2: Create Rollback Script

**File to Create:** `scripts/rollback.sh`

```bash
#!/bin/bash
# Rollback script

set -e

BACKUP_DIR="/var/backups/cmbagent"
DEPLOY_DIR="/srv/cmbagent"
TIMESTAMP=${1:-$(ls -t "$BACKUP_DIR"/code_*.tar.gz 2>/dev/null | head -1 | sed 's/.*code_\(.*\)\.tar\.gz/\1/')}

if [ -z "$TIMESTAMP" ]; then
    echo "ERROR: No backup timestamp provided and no backups found"
    exit 1
fi

echo "=== CMBAgent Rollback Script ==="
echo "Rolling back to: $TIMESTAMP"
echo ""

# Stop services
echo "Stopping services..."
systemctl stop cmbagent-backend || pkill -f "uvicorn main:app" || true
systemctl stop cmbagent-frontend || true
echo "  ✓ Services stopped"

# Restore database
echo ""
echo "Restoring database..."
if [ -f "$BACKUP_DIR/cmbagent_$TIMESTAMP.db" ]; then
    cp "$BACKUP_DIR/cmbagent_$TIMESTAMP.db" ~/.cmbagent/cmbagent.db
    echo "  ✓ Database restored"
else
    echo "  ⚠ No database backup found for $TIMESTAMP"
fi

# Restore code
echo ""
echo "Restoring code..."
if [ -f "$BACKUP_DIR/code_$TIMESTAMP.tar.gz" ]; then
    rm -rf "$DEPLOY_DIR.bak"
    mv "$DEPLOY_DIR" "$DEPLOY_DIR.bak"
    mkdir -p "$DEPLOY_DIR"
    tar -xzf "$BACKUP_DIR/code_$TIMESTAMP.tar.gz" -C "$DEPLOY_DIR"
    echo "  ✓ Code restored"
else
    echo "  ✗ No code backup found for $TIMESTAMP"
    exit 1
fi

# Rollback migrations
echo ""
echo "Rolling back migrations..."
cd "$DEPLOY_DIR"
alembic downgrade -1 || true
echo "  ✓ Migration rollback attempted"

# Restart services
echo ""
echo "Restarting services..."
systemctl start cmbagent-backend || {
    cd "$DEPLOY_DIR/backend"
    nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /var/log/cmbagent/backend.log 2>&1 &
}
systemctl start cmbagent-frontend || true
echo "  ✓ Services restarted"

# Health check
echo ""
echo "Running health check..."
sleep 5
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "  ✓ Rollback successful - system healthy"
else
    echo "  ⚠ Health check failed - manual intervention required"
fi

echo ""
echo "=== Rollback Complete ==="
```

### Task 3: Create Health Check Endpoint

**File to Modify:** `backend/routers/__init__.py` or create `backend/routers/health.py`

```python
from fastapi import APIRouter, Response
from datetime import datetime, timezone

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Health check endpoint for deployment verification"""
    checks = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {}
    }

    # Check database
    try:
        from cmbagent.database import get_db_session
        db = get_db_session()
        db.execute("SELECT 1")
        db.close()
        checks["checks"]["database"] = "ok"
    except Exception as e:
        checks["checks"]["database"] = f"error: {str(e)}"
        checks["status"] = "degraded"

    # Check services
    try:
        from services.session_manager import get_session_manager
        sm = get_session_manager()
        checks["checks"]["session_manager"] = "ok"
    except Exception as e:
        checks["checks"]["session_manager"] = f"error: {str(e)}"
        checks["status"] = "degraded"

    return checks
```

### Task 4: Staging Environment Testing

**Checklist:**

```markdown
## Staging Test Plan

### Environment Setup
- [ ] Staging database migrated
- [ ] Staging backend running
- [ ] Staging frontend running
- [ ] Test data loaded

### Functional Tests
- [ ] Create new session (all modes)
- [ ] Execute one-shot task
- [ ] Execute planning-control task
- [ ] Test HITL approval flow
- [ ] Test copilot session continuation
- [ ] Suspend and resume session
- [ ] Delete session

### Concurrent Tests
- [ ] 10 simultaneous connections
- [ ] Output isolation verified
- [ ] No errors in logs

### Session Persistence
- [ ] Create session, execute, suspend
- [ ] Restart backend
- [ ] Resume session - verify state preserved

### Error Handling
- [ ] Invalid session ID - 404 returned
- [ ] Connection limit - proper rejection
- [ ] Approval timeout - handled gracefully

### Performance
- [ ] Connection latency acceptable
- [ ] Memory usage stable
- [ ] No connection leaks

### Monitoring
- [ ] Logs visible in aggregator
- [ ] Errors trigger alerts
- [ ] Metrics dashboards working
```

### Task 5: Production Deployment Procedure

```markdown
## Production Deployment Procedure

### T-24 Hours
- [ ] Announce maintenance window
- [ ] Verify staging tests pass
- [ ] Prepare rollback plan
- [ ] Brief support team

### T-1 Hour
- [ ] Final staging verification
- [ ] Create database backup
- [ ] Notify stakeholders

### Deployment (15 minutes)
1. [ ] Put system in maintenance mode (if applicable)
2. [ ] Stop backend service
3. [ ] Run database migrations
4. [ ] Deploy new code
5. [ ] Start backend service
6. [ ] Run health check
7. [ ] Run smoke tests
8. [ ] Remove maintenance mode

### T+15 Minutes
- [ ] Monitor error logs
- [ ] Check performance metrics
- [ ] Verify user reported issues

### T+1 Hour
- [ ] Full functional verification
- [ ] Confirm no rollback needed
- [ ] Update deployment log

### Rollback Triggers
Initiate rollback if:
- Health check fails
- Error rate > 5%
- Connection failures > 10%
- User reports critical issues
```

### Task 6: Environment Variables Documentation

**File to Create:** `docs/ENVIRONMENT_VARIABLES.md`

```markdown
# Environment Variables

## Required

| Variable | Description | Default |
|----------|-------------|---------|
| `CMBAGENT_DATABASE_URL` | Database connection URL | `sqlite:///~/.cmbagent/cmbagent.db` |
| `OPENAI_API_KEY` | OpenAI API key | None (required) |

## Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `LOG_JSON` | Output logs as JSON | `false` |
| `LOG_FILE` | Path to log file | None |
| `MAX_CONNECTIONS` | Max WebSocket connections | `100` |
| `SESSION_TTL` | Session timeout in seconds | `86400` (24h) |
| `APPROVAL_TIMEOUT` | Default approval timeout | `300` (5m) |

## Production Recommended

```bash
export LOG_LEVEL=INFO
export LOG_JSON=true
export LOG_FILE=/var/log/cmbagent/app.log
export MAX_CONNECTIONS=200
export SESSION_TTL=86400
export APPROVAL_TIMEOUT=600
```
```

## Verification Criteria

### Must Pass
- [ ] Deployment script runs without errors
- [ ] Rollback script works correctly
- [ ] Health check endpoint responds
- [ ] All staging tests pass
- [ ] No errors in first hour post-deployment

## Success Criteria

Stage 14 is complete when:
1. ✅ Deployment script tested
2. ✅ Rollback procedure verified
3. ✅ Staging tests pass
4. ✅ Production deployed successfully
5. ✅ No rollback needed within 24 hours

---

## Post-Deployment Monitoring

### Metrics to Watch
- Active WebSocket connections
- Error rate (should be < 1%)
- API response times
- Database query times
- Memory usage

### Log Queries
```bash
# Errors in last hour
grep -i error /var/log/cmbagent/app.log | tail -100

# Connection issues
grep -i "connection" /var/log/cmbagent/app.log | grep -i "error\|fail"

# Session activity
grep "session" /var/log/cmbagent/app.log | tail -50
```

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
