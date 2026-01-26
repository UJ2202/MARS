# Stage 14: Observability and Metrics

**Phase:** 4 - Advanced Features
**Estimated Time:** 45-55 minutes
**Dependencies:** Stages 1-13 complete
**Risk Level:** Medium

## Objectives

1. Integrate OpenTelemetry for distributed tracing
2. Implement comprehensive metrics collection
3. Add structured logging with correlation IDs
4. Create trace visualization and analysis
5. Set up metrics dashboard
6. Implement performance monitoring
7. Add anomaly detection and alerting

## Current State Analysis

### What We Have
- Basic console logging
- No distributed tracing
- Limited metrics collection
- No correlation between logs and operations
- Difficult to debug multi-step workflows
- No performance insights

### What We Need
- OpenTelemetry integration
- Distributed traces across workflow
- Structured JSON logging
- Correlation IDs linking logs/traces/metrics
- Metrics for all key operations
- Jaeger or similar for trace visualization
- Performance dashboards
- Anomaly detection

## Pre-Stage Verification

### Check Prerequisites
1. Stages 1-13 complete and verified
2. Database operational
3. WebSocket infrastructure working
4. Workflow execution stable

### Expected State
- Workflows executing successfully
- Database recording operations
- Ready to add observability layer
- Tests passing

## Implementation Tasks

### Task 1: Install OpenTelemetry Dependencies
**Objective:** Add OpenTelemetry SDK and exporters

**Dependencies to Add:**
```toml
# pyproject.toml
dependencies = [
    # Existing dependencies...
    "opentelemetry-api>=1.22",
    "opentelemetry-sdk>=1.22",
    "opentelemetry-instrumentation>=0.43",
    "opentelemetry-instrumentation-fastapi>=0.43",
    "opentelemetry-instrumentation-sqlalchemy>=0.43",
    "opentelemetry-instrumentation-requests>=0.43",
    "opentelemetry-exporter-jaeger>=1.22",
    "opentelemetry-exporter-prometheus>=0.43",
    "prometheus-client>=0.19"
]
```

**Files to Modify:**
- `pyproject.toml`

**Verification:**
- Dependencies install without conflicts
- Can import OpenTelemetry modules
- `pip list` shows correct versions

### Task 2: Create OpenTelemetry Configuration
**Objective:** Set up tracing and metrics infrastructure

**Implementation:**

```python
# cmbagent/observability/__init__.py
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.resources import Resource
import os
import logging

# Service identification
SERVICE_NAME = "cmbagent"
SERVICE_VERSION = "0.2.0"

# Create resource
resource = Resource.create({
    "service.name": SERVICE_NAME,
    "service.version": SERVICE_VERSION,
    "deployment.environment": os.getenv("ENVIRONMENT", "development")
})

# Configure tracing
trace_provider = TracerProvider(resource=resource)

# Jaeger exporter
jaeger_exporter = JaegerExporter(
    agent_host_name=os.getenv("JAEGER_AGENT_HOST", "localhost"),
    agent_port=int(os.getenv("JAEGER_AGENT_PORT", 6831)),
)

trace_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
trace.set_tracer_provider(trace_provider)

# Get tracer
tracer = trace.get_tracer(__name__)

# Configure metrics
prometheus_reader = PrometheusMetricReader()
meter_provider = MeterProvider(
    resource=resource,
    metric_readers=[prometheus_reader]
)
metrics.set_meter_provider(meter_provider)

# Get meter
meter = metrics.get_meter(__name__)

# Create metrics
workflow_duration = meter.create_histogram(
    name="workflow.duration",
    description="Workflow execution duration in seconds",
    unit="s"
)

workflow_cost = meter.create_histogram(
    name="workflow.cost",
    description="Workflow cost in USD",
    unit="usd"
)

workflow_count = meter.create_counter(
    name="workflow.count",
    description="Number of workflows executed"
)

step_duration = meter.create_histogram(
    name="step.duration",
    description="Step execution duration in seconds",
    unit="s"
)

llm_call_duration = meter.create_histogram(
    name="llm.call.duration",
    description="LLM API call duration in seconds",
    unit="s"
)

llm_tokens = meter.create_histogram(
    name="llm.tokens",
    description="Number of tokens per LLM call",
    unit="tokens"
)

error_count = meter.create_counter(
    name="error.count",
    description="Number of errors encountered"
)

logger = logging.getLogger(__name__)
logger.info(f"OpenTelemetry initialized for {SERVICE_NAME}")
```

**Files to Create:**
- `cmbagent/observability/__init__.py`
- `cmbagent/observability/config.py`
- `cmbagent/observability/tracing.py`
- `cmbagent/observability/metrics.py`

**Verification:**
- OpenTelemetry providers configured
- Tracer and meter available
- Jaeger exporter connected
- Metrics exportable to Prometheus

### Task 3: Implement Trace Decorators
**Objective:** Easy-to-use decorators for tracing

**Implementation:**

```python
# cmbagent/observability/tracing.py
from functools import wraps
from typing import Callable, Optional, Dict, Any
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
import time

tracer = trace.get_tracer(__name__)

def traced(
    name: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None
):
    """Decorator to trace function execution."""

    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(span_name) as span:
                # Add attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Add function parameters as attributes
                if args:
                    span.set_attribute("args", str(args))
                if kwargs:
                    for k, v in kwargs.items():
                        span.set_attribute(f"param.{k}", str(v))

                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result

                except Exception as e:
                    span.set_status(
                        Status(StatusCode.ERROR, str(e))
                    )
                    span.record_exception(e)
                    raise

        return wrapper

    return decorator

def trace_workflow(run_id: str, mode: str, agent: str, model: str):
    """Create workflow-level trace span."""

    span = tracer.start_span(
        "workflow.execution",
        attributes={
            "workflow.run_id": run_id,
            "workflow.mode": mode,
            "workflow.agent": agent,
            "workflow.model": model
        }
    )

    return span

def trace_step(step_id: str, agent: str, step_number: int):
    """Create step-level trace span."""

    span = tracer.start_span(
        "workflow.step",
        attributes={
            "step.id": step_id,
            "step.agent": agent,
            "step.number": step_number
        }
    )

    return span

def trace_llm_call(model: str, provider: str, prompt_length: int):
    """Create LLM call trace span."""

    span = tracer.start_span(
        "llm.call",
        attributes={
            "llm.model": model,
            "llm.provider": provider,
            "llm.prompt_length": prompt_length
        }
    )

    return span

class TraceContext:
    """Context manager for tracing with automatic timing."""

    def __init__(self, operation: str, **attributes):
        self.operation = operation
        self.attributes = attributes
        self.span = None
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        self.span = tracer.start_span(
            self.operation,
            attributes=self.attributes
        )
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.span.set_attribute("duration_seconds", duration)

        if exc_type is not None:
            self.span.set_status(
                Status(StatusCode.ERROR, str(exc_val))
            )
            self.span.record_exception(exc_val)
        else:
            self.span.set_status(Status(StatusCode.OK))

        self.span.end()

# Example usage:
"""
@traced(name="agent.execute")
def execute_agent(task: str):
    # Function automatically traced
    pass

# Or with context manager:
with TraceContext("planning", run_id=run_id) as span:
    # Code here is traced
    result = planner.plan(task)
    span.set_attribute("plan_steps", len(result))
"""
```

**Files to Create:**
- `cmbagent/observability/tracing.py`

**Verification:**
- Decorators create spans
- Attributes captured correctly
- Exceptions recorded in traces
- Context manager works

### Task 4: Implement Structured Logging
**Objective:** JSON logging with correlation IDs

**Implementation:**

```python
# cmbagent/observability/logging.py
import logging
import json
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from opentelemetry import trace
import uuid

class StructuredFormatter(logging.Formatter):
    """JSON formatter with trace context."""

    def format(self, record: logging.LogRecord) -> str:
        # Get trace context
        span = trace.get_current_span()
        span_context = span.get_span_context() if span else None

        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add trace IDs if available
        if span_context and span_context.is_valid:
            log_data["trace_id"] = f"{span_context.trace_id:032x}"
            log_data["span_id"] = f"{span_context.span_id:016x}"

        # Add correlation ID from record
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

        # Add custom fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

class CorrelationFilter(logging.Filter):
    """Add correlation ID to log records."""

    def __init__(self):
        super().__init__()
        self.correlation_id = None

    def filter(self, record: logging.LogRecord) -> bool:
        if self.correlation_id:
            record.correlation_id = self.correlation_id
        return True

def setup_logging(level: str = "INFO", structured: bool = True):
    """Configure structured logging."""

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers = []

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Add correlation filter
    correlation_filter = CorrelationFilter()
    root_logger.addFilter(correlation_filter)

    return correlation_filter

class LogContext:
    """Context manager for adding extra fields to logs."""

    def __init__(self, **fields):
        self.fields = fields
        self.old_factory = None

    def __enter__(self):
        old_factory = logging.getLogRecordFactory()
        self.old_factory = old_factory

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.extra_fields = self.fields
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)

# Example usage:
"""
logger = logging.getLogger(__name__)

# Structured log with trace context
logger.info("Workflow started", extra={
    "extra_fields": {
        "run_id": run_id,
        "agent": agent,
        "model": model
    }
})

# With context manager
with LogContext(run_id=run_id, step=1):
    logger.info("Processing step 1")
    # All logs in this block have run_id and step fields
"""
```

**Files to Create:**
- `cmbagent/observability/logging.py`

**Verification:**
- Logs output as JSON
- Trace IDs included in logs
- Correlation IDs working
- Extra fields captured

### Task 5: Integrate Tracing into CMBAgent
**Objective:** Add traces to all major operations

**Implementation:**

```python
# cmbagent/cmbagent.py (modifications)
from cmbagent.observability import tracer, workflow_duration, workflow_cost, workflow_count
from cmbagent.observability.tracing import trace_workflow, trace_step, TraceContext
from cmbagent.observability.logging import setup_logging
import time

class CMBAgent:
    def __init__(self, ...):
        # Existing initialization
        ...

        # Setup structured logging
        setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))

    def planning_and_control_context_carryover(self, task, agent="engineer", ...):
        """Execute workflow with full tracing."""

        # Start workflow span
        with trace_workflow(
            run_id=str(run_id),
            mode="planning_control",
            agent=agent,
            model=model
        ) as workflow_span:

            start_time = time.time()

            try:
                # Planning phase
                with TraceContext("planning", run_id=str(run_id)) as planning_span:
                    logger.info("Starting planning phase", extra={
                        "extra_fields": {"run_id": str(run_id), "agent": agent}
                    })

                    plan_result = self._execute_planning(task)

                    planning_span.set_attribute("plan_steps", len(plan_result))

                # Control phase
                with TraceContext("control", run_id=str(run_id)) as control_span:
                    logger.info("Starting control phase")

                    for step_num, step in enumerate(plan_result):
                        # Step span
                        with trace_step(
                            step_id=str(step.id),
                            agent=step.agent,
                            step_number=step_num
                        ) as step_span:

                            step_start = time.time()

                            result = self._execute_step(step)

                            step_duration.record(
                                time.time() - step_start,
                                attributes={
                                    "agent": step.agent,
                                    "step_number": step_num
                                }
                            )

                            step_span.set_attribute("result_length", len(result))

                # Record workflow metrics
                duration = time.time() - start_time
                workflow_duration.record(duration, attributes={"agent": agent, "model": model})

                total_cost = self.get_total_cost(run_id)
                workflow_cost.record(total_cost, attributes={"agent": agent, "model": model})

                workflow_count.add(1, attributes={"agent": agent, "status": "success"})

                workflow_span.set_attribute("total_cost_usd", total_cost)
                workflow_span.set_attribute("duration_seconds", duration)

                return result

            except Exception as e:
                # Record error
                workflow_span.set_status(Status(StatusCode.ERROR, str(e)))
                workflow_span.record_exception(e)

                error_count.add(1, attributes={"agent": agent, "error_type": type(e).__name__})

                workflow_count.add(1, attributes={"agent": agent, "status": "failed"})

                logger.error(f"Workflow failed: {e}", extra={
                    "extra_fields": {"run_id": str(run_id), "error": str(e)}
                })

                raise
```

**Files to Modify:**
- `cmbagent/cmbagent.py`
- `cmbagent/agents/base_agent.py`
- Agent implementations

**Verification:**
- Traces created for workflows
- Spans nested correctly
- Metrics recorded
- Logs correlated with traces

### Task 6: Add LLM Call Tracing
**Objective:** Trace all LLM API calls

**Implementation:**

```python
# cmbagent/observability/llm_instrumentation.py
from opentelemetry import trace
from cmbagent.observability import llm_call_duration, llm_tokens
import time

tracer = trace.get_tracer(__name__)

def instrument_llm_call(func):
    """Decorator to instrument LLM API calls."""

    def wrapper(*args, **kwargs):
        # Extract parameters
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        prompt_length = sum(len(m.get("content", "")) for m in messages)

        # Create span
        with tracer.start_as_current_span(
            "llm.api.call",
            attributes={
                "llm.model": model,
                "llm.provider": _get_provider(model),
                "llm.prompt_length": prompt_length,
                "llm.request_type": "chat_completion"
            }
        ) as span:

            start_time = time.time()

            try:
                # Make API call
                response = func(*args, **kwargs)

                # Record duration
                duration = time.time() - start_time
                llm_call_duration.record(
                    duration,
                    attributes={"model": model, "provider": _get_provider(model)}
                )

                # Extract usage data
                if hasattr(response, "usage"):
                    usage = response.usage
                    prompt_tokens = usage.prompt_tokens
                    completion_tokens = usage.completion_tokens
                    total_tokens = usage.total_tokens

                    # Add to span
                    span.set_attribute("llm.prompt_tokens", prompt_tokens)
                    span.set_attribute("llm.completion_tokens", completion_tokens)
                    span.set_attribute("llm.total_tokens", total_tokens)

                    # Record metrics
                    llm_tokens.record(
                        total_tokens,
                        attributes={"model": model, "token_type": "total"}
                    )

                span.set_attribute("llm.response_length", len(str(response)))
                span.set_status(Status(StatusCode.OK))

                return response

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    return wrapper

def _get_provider(model: str) -> str:
    """Determine provider from model name."""
    if "gpt" in model.lower():
        return "openai"
    elif "claude" in model.lower():
        return "anthropic"
    elif "gemini" in model.lower():
        return "google"
    else:
        return "unknown"

# Auto-instrument LLM libraries
def auto_instrument():
    """Automatically instrument LLM client libraries."""

    try:
        import openai
        original_create = openai.ChatCompletion.create
        openai.ChatCompletion.create = instrument_llm_call(original_create)
    except ImportError:
        pass

    try:
        import anthropic
        original_create = anthropic.Anthropic().messages.create
        anthropic.Anthropic().messages.create = instrument_llm_call(original_create)
    except ImportError:
        pass
```

**Files to Create:**
- `cmbagent/observability/llm_instrumentation.py`

**Verification:**
- LLM calls traced
- Token counts captured
- Duration metrics recorded
- Provider identified correctly

### Task 7: Create Metrics Export Endpoint
**Objective:** Expose metrics for Prometheus

**Implementation:**

```python
# backend/api/metrics.py
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/")
async def metrics():
    """Prometheus metrics endpoint."""
    return PlainTextResponse(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "cmbagent"}
```

**Files to Create:**
- `backend/api/metrics.py`

**Update Backend:**
```python
# backend/main.py
from backend.api import metrics

app.include_router(metrics.router)
```

**Verification:**
- `/metrics` endpoint returns Prometheus format
- Metrics include custom workflow metrics
- `/health` endpoint responds

### Task 8: Create Observability Dashboard
**Objective:** Visualize traces and metrics

**Implementation:**

```yaml
# docker-compose.observability.yml
version: '3.8'

services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "6831:6831/udp"  # Agent
      - "16686:16686"    # UI
    environment:
      - COLLECTOR_OTLP_ENABLED=true

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"  # 3000 conflicts with Next.js
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
```

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'cmbagent'
    static_configs:
      - targets: ['host.docker.internal:8000']
```

**Grafana Dashboard JSON:**
```json
{
  "dashboard": {
    "title": "CMBAgent Observability",
    "panels": [
      {
        "title": "Workflow Duration",
        "targets": [{
          "expr": "histogram_quantile(0.95, workflow_duration_bucket)"
        }]
      },
      {
        "title": "Workflow Cost",
        "targets": [{
          "expr": "sum(workflow_cost) by (agent)"
        }]
      },
      {
        "title": "LLM Call Latency",
        "targets": [{
          "expr": "histogram_quantile(0.95, llm_call_duration_bucket)"
        }]
      },
      {
        "title": "Error Rate",
        "targets": [{
          "expr": "rate(error_count[5m])"
        }]
      }
    ]
  }
}
```

**Files to Create:**
- `docker-compose.observability.yml`
- `prometheus.yml`
- `grafana/dashboards/cmbagent.json`
- `grafana/datasources/prometheus.yml`

**Verification:**
- Jaeger UI accessible at http://localhost:16686
- Prometheus at http://localhost:9090
- Grafana at http://localhost:3001
- Traces visible in Jaeger
- Metrics in Prometheus
- Dashboards in Grafana

### Task 9: Add Performance Monitoring
**Objective:** Monitor and alert on performance issues

**Implementation:**

```python
# cmbagent/observability/performance.py
from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class PerformanceAlert:
    alert_type: str
    severity: str
    message: str
    metric: str
    value: float
    threshold: float
    timestamp: datetime

class PerformanceMonitor:
    """Monitor performance and detect anomalies."""

    def __init__(self, db_session):
        self.db = db_session
        self.thresholds = {
            "workflow_duration": 600,  # 10 minutes
            "step_duration": 120,      # 2 minutes
            "llm_call_duration": 30,   # 30 seconds
            "cost_per_workflow": 1.00, # $1.00
            "error_rate": 0.05         # 5%
        }

    def check_workflow_performance(self, run_id: str) -> List[PerformanceAlert]:
        """Check workflow against performance thresholds."""

        alerts = []

        # Check duration
        from cmbagent.database.models import WorkflowRuns

        run = self.db.query(WorkflowRuns).filter(
            WorkflowRuns.id == run_id
        ).first()

        if run and run.completed_at:
            duration = (run.completed_at - run.started_at).total_seconds()

            if duration > self.thresholds["workflow_duration"]:
                alerts.append(PerformanceAlert(
                    alert_type="slow_workflow",
                    severity="warning",
                    message=f"Workflow took {duration:.0f}s (threshold: {self.thresholds['workflow_duration']}s)",
                    metric="workflow_duration",
                    value=duration,
                    threshold=self.thresholds["workflow_duration"],
                    timestamp=datetime.utcnow()
                ))

        # Check cost
        if run and run.total_cost_usd:
            if run.total_cost_usd > self.thresholds["cost_per_workflow"]:
                alerts.append(PerformanceAlert(
                    alert_type="high_cost",
                    severity="info",
                    message=f"Workflow cost ${run.total_cost_usd:.4f} exceeded threshold",
                    metric="cost_per_workflow",
                    value=run.total_cost_usd,
                    threshold=self.thresholds["cost_per_workflow"],
                    timestamp=datetime.utcnow()
                ))

        return alerts

    def get_performance_summary(
        self,
        session_id: str,
        time_window_hours: int = 24
    ) -> Dict[str, Any]:
        """Get performance summary for session."""

        from cmbagent.database.models import WorkflowRuns
        from sqlalchemy import func

        since = datetime.utcnow() - timedelta(hours=time_window_hours)

        # Query runs
        runs = self.db.query(WorkflowRuns).filter(
            WorkflowRuns.session_id == session_id,
            WorkflowRuns.started_at >= since
        ).all()

        if not runs:
            return {"runs": 0, "message": "No runs in time window"}

        # Calculate stats
        durations = [
            (r.completed_at - r.started_at).total_seconds()
            for r in runs if r.completed_at
        ]

        costs = [r.total_cost_usd for r in runs if r.total_cost_usd]

        failed_runs = [r for r in runs if r.status == "failed"]

        return {
            "total_runs": len(runs),
            "completed_runs": len(durations),
            "failed_runs": len(failed_runs),
            "error_rate": len(failed_runs) / len(runs) if runs else 0,
            "avg_duration_seconds": sum(durations) / len(durations) if durations else 0,
            "max_duration_seconds": max(durations) if durations else 0,
            "total_cost_usd": sum(costs) if costs else 0,
            "avg_cost_usd": sum(costs) / len(costs) if costs else 0,
            "time_window_hours": time_window_hours
        }
```

**Files to Create:**
- `cmbagent/observability/performance.py`

**API Endpoint:**
```python
# backend/api/observability.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/observability", tags=["observability"])

@router.get("/performance/{session_id}")
async def get_performance_summary(session_id: str, hours: int = 24):
    """Get performance summary for session."""
    from cmbagent.observability.performance import PerformanceMonitor

    monitor = PerformanceMonitor(db)
    summary = monitor.get_performance_summary(session_id, hours)

    return summary

@router.get("/traces/{run_id}")
async def get_trace_link(run_id: str):
    """Get Jaeger trace link for workflow."""
    # Trace ID would be stored in workflow_runs table
    jaeger_url = f"http://localhost:16686/trace/{run_id}"

    return {"trace_url": jaeger_url}
```

**Verification:**
- Performance alerts generated
- Thresholds configurable
- Summary statistics accurate
- API endpoints functional

## Files to Create (Summary)

### New Files
```
cmbagent/observability/
├── __init__.py
├── config.py
├── tracing.py
├── metrics.py
├── logging.py
├── llm_instrumentation.py
└── performance.py

backend/api/
├── metrics.py
└── observability.py

docker-compose.observability.yml
prometheus.yml
grafana/
├── dashboards/
│   └── cmbagent.json
└── datasources/
    └── prometheus.yml
```

### Modified Files
- `pyproject.toml` - Add OpenTelemetry dependencies
- `cmbagent/cmbagent.py` - Add tracing
- `cmbagent/agents/base_agent.py` - Add tracing
- `backend/main.py` - Add metrics router

## Verification Criteria

### Must Pass
- [ ] OpenTelemetry dependencies installed
- [ ] Tracing configured and functional
- [ ] Traces visible in Jaeger UI
- [ ] Metrics exported to Prometheus
- [ ] Structured logging with JSON output
- [ ] Correlation IDs link logs and traces
- [ ] LLM calls traced with token counts
- [ ] Performance monitoring functional

### Should Pass
- [ ] Grafana dashboards display metrics
- [ ] Trace spans nested correctly
- [ ] Performance alerts generated
- [ ] Metrics endpoint accessible
- [ ] No performance degradation from observability

### Nice to Have
- [ ] Anomaly detection working
- [ ] Automated performance reports
- [ ] Trace sampling for high-volume scenarios
- [ ] Custom Grafana dashboards

## Testing Checklist

### Unit Tests
```python
def test_trace_decorator():
    @traced(name="test_function")
    def test_func():
        return "result"

    result = test_func()
    # Verify span created
    assert result == "result"

def test_structured_logging():
    logger = logging.getLogger("test")
    with LogContext(test_id="123"):
        logger.info("Test message")
    # Verify JSON output with test_id
```

### Integration Tests
```python
def test_workflow_tracing():
    agent = CMBAgent()
    agent.one_shot("test task")

    # Check Jaeger for trace
    # Verify span hierarchy
    # Check metrics recorded
```

## Common Issues and Solutions

### Issue 1: Jaeger Not Receiving Traces
**Symptom:** No traces in Jaeger UI
**Solution:** Check Jaeger agent connection, verify exporter configuration, check network

### Issue 2: Performance Degradation
**Symptom:** System slower after adding tracing
**Solution:** Enable sampling, use batch export, optimize span creation

### Issue 3: Logs Missing Trace IDs
**Symptom:** Trace IDs not in logs
**Solution:** Verify trace context propagation, check logging configuration

### Issue 4: Metrics Not Updating
**Symptom:** Prometheus shows stale metrics
**Solution:** Check metrics endpoint, verify scrape configuration, check metric recording

## Rollback Procedure

If observability causes issues:

1. **Disable tracing:**
   ```python
   ENABLE_TRACING = os.getenv("ENABLE_TRACING", "false") == "true"
   ```

2. **Revert to simple logging:**
   ```python
   setup_logging(structured=False)
   ```

3. **Keep metrics collection** - Minimal overhead

4. **Stop external services:**
   ```bash
   docker-compose -f docker-compose.observability.yml down
   ```

## Post-Stage Actions

### Documentation
- Document observability setup
- Create monitoring guide
- Add Jaeger usage instructions
- Update architecture documentation

### Update Progress
- Mark Stage 14 complete in PROGRESS.md
- Note any deviations from plan
- Document time spent

### Prepare for Stage 15
- Observability operational
- Traces and metrics flowing
- Ready to add policy enforcement
- Stage 15 can proceed

## Success Criteria

Stage 14 is complete when:
1. OpenTelemetry integrated successfully
2. Traces visible in Jaeger
3. Metrics exported to Prometheus
4. Structured logging operational
5. Performance monitoring functional
6. Dashboards showing data
7. All tests passing
8. Verification checklist 100% complete

## Estimated Time Breakdown

- Dependencies and configuration: 8 min
- Trace implementation: 12 min
- Structured logging: 8 min
- CMBAgent integration: 10 min
- LLM instrumentation: 7 min
- Metrics and dashboards: 10 min
- Performance monitoring: 8 min
- Testing and verification: 10 min
- Documentation: 5 min

**Total: 45-55 minutes**

## Next Stage

Once Stage 14 is verified complete, proceed to:
**Stage 15: Open Policy Agent Integration**

---

**Stage Status:** Not Started
**Last Updated:** 2026-01-14
