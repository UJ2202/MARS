# Stage 13: Load Testing

**Phase:** 5 - Testing & Deployment
**Dependencies:** Stage 12 (Unit Tests), Stage 6 (Isolation)
**Risk Level:** Medium
**Estimated Time:** 3-4 hours

## Objectives

1. Validate concurrent connection handling
2. Test output isolation under load
3. Measure performance metrics
4. Identify bottlenecks

## Implementation Tasks

### Task 1: Create Load Test Script

**File to Create:** `tests/test_load.py`

```python
"""
Load tests for WebSocket robustness

Run with: pytest tests/test_load.py -v -s
"""

import pytest
import asyncio
import aiohttp
import time
import random
import string
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class LoadTestResult:
    """Result of a load test run"""
    total_connections: int
    successful_connections: int
    failed_connections: int
    total_messages_sent: int
    total_messages_received: int
    connection_times: List[float]
    errors: List[str]
    duration: float

    @property
    def success_rate(self) -> float:
        return self.successful_connections / self.total_connections * 100

    @property
    def avg_connection_time(self) -> float:
        return sum(self.connection_times) / len(self.connection_times) if self.connection_times else 0


class WebSocketLoadTester:
    """Load tester for WebSocket connections"""

    def __init__(self, base_url: str = "ws://localhost:8000"):
        self.base_url = base_url
        self.results = LoadTestResult(
            total_connections=0,
            successful_connections=0,
            failed_connections=0,
            total_messages_sent=0,
            total_messages_received=0,
            connection_times=[],
            errors=[],
            duration=0
        )

    async def single_connection(
        self,
        task_id: str,
        task_text: str,
        timeout: float = 60.0
    ) -> Dict:
        """Run a single WebSocket connection test"""
        messages_received = []
        start_time = time.time()

        try:
            async with aiohttp.ClientSession() as session:
                ws_url = f"{self.base_url}/ws/{task_id}"

                connect_start = time.time()
                async with session.ws_connect(ws_url, timeout=timeout) as ws:
                    connect_time = time.time() - connect_start
                    self.results.connection_times.append(connect_time)
                    self.results.successful_connections += 1

                    # Send task
                    await ws.send_json({
                        "task": task_text,
                        "config": {"mode": "one-shot", "maxRounds": 5}
                    })
                    self.results.total_messages_sent += 1

                    # Receive messages until complete
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = msg.json()
                            messages_received.append(data)
                            self.results.total_messages_received += 1

                            if data.get("event_type") == "complete":
                                break
                            if data.get("event_type") == "error":
                                self.results.errors.append(
                                    f"{task_id}: {data.get('data', {}).get('message', 'Unknown error')}"
                                )
                                break

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            self.results.errors.append(f"{task_id}: WebSocket error")
                            break

                    return {
                        "task_id": task_id,
                        "success": True,
                        "messages": len(messages_received),
                        "duration": time.time() - start_time
                    }

        except asyncio.TimeoutError:
            self.results.failed_connections += 1
            self.results.errors.append(f"{task_id}: Connection timeout")
            return {"task_id": task_id, "success": False, "error": "timeout"}

        except Exception as e:
            self.results.failed_connections += 1
            self.results.errors.append(f"{task_id}: {str(e)}")
            return {"task_id": task_id, "success": False, "error": str(e)}

    async def run_concurrent_test(
        self,
        num_connections: int,
        task_prefix: str = "load_test"
    ) -> LoadTestResult:
        """Run multiple concurrent connections"""
        self.results = LoadTestResult(
            total_connections=num_connections,
            successful_connections=0,
            failed_connections=0,
            total_messages_sent=0,
            total_messages_received=0,
            connection_times=[],
            errors=[],
            duration=0
        )

        start_time = time.time()

        tasks = []
        for i in range(num_connections):
            task_id = f"{task_prefix}_{i}_{random.randint(1000, 9999)}"
            task_text = f"Echo test message {i}"
            tasks.append(self.single_connection(task_id, task_text))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        self.results.duration = time.time() - start_time

        # Count exceptions
        for r in results:
            if isinstance(r, Exception):
                self.results.failed_connections += 1
                self.results.errors.append(str(r))

        return self.results


class TestConcurrentConnections:
    """Load tests for concurrent WebSocket connections"""

    @pytest.fixture
    def tester(self):
        return WebSocketLoadTester("ws://localhost:8000")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_10_concurrent_connections(self, tester):
        """Test 10 concurrent connections"""
        result = await tester.run_concurrent_test(10)

        print(f"\n--- 10 Connection Test ---")
        print(f"Success rate: {result.success_rate:.1f}%")
        print(f"Avg connection time: {result.avg_connection_time:.3f}s")
        print(f"Total duration: {result.duration:.2f}s")
        print(f"Errors: {len(result.errors)}")

        assert result.success_rate >= 90, f"Success rate too low: {result.success_rate}%"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_50_concurrent_connections(self, tester):
        """Test 50 concurrent connections"""
        result = await tester.run_concurrent_test(50)

        print(f"\n--- 50 Connection Test ---")
        print(f"Success rate: {result.success_rate:.1f}%")
        print(f"Avg connection time: {result.avg_connection_time:.3f}s")
        print(f"Total duration: {result.duration:.2f}s")
        print(f"Errors: {len(result.errors)}")
        if result.errors:
            print(f"First 5 errors: {result.errors[:5]}")

        assert result.success_rate >= 80, f"Success rate too low: {result.success_rate}%"


class TestOutputIsolation:
    """Tests for output isolation under concurrent load"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_output_isolation(self):
        """Test that concurrent tasks don't mix output"""
        outputs_by_task = defaultdict(list)

        async def connect_and_collect(task_id: str, unique_marker: str):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(f"ws://localhost:8000/ws/{task_id}") as ws:
                        await ws.send_json({
                            "task": f"Print exactly: MARKER_{unique_marker}",
                            "config": {"mode": "one-shot"}
                        })

                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = msg.json()
                                if data.get("event_type") == "output":
                                    message = data.get("data", {}).get("message", "")
                                    outputs_by_task[task_id].append(message)
                                if data.get("event_type") in ["complete", "error"]:
                                    break
            except Exception as e:
                outputs_by_task[task_id].append(f"ERROR: {e}")

        # Run 5 concurrent tasks with unique markers
        tasks = []
        markers = {}
        for i in range(5):
            task_id = f"isolation_test_{i}"
            marker = ''.join(random.choices(string.ascii_uppercase, k=8))
            markers[task_id] = marker
            tasks.append(connect_and_collect(task_id, marker))

        await asyncio.gather(*tasks)

        # Verify isolation: each task's output should only contain its marker
        for task_id, marker in markers.items():
            task_output = " ".join(outputs_by_task[task_id])
            other_markers = [m for t, m in markers.items() if t != task_id]

            # This task's output should not contain other markers
            for other_marker in other_markers:
                assert other_marker not in task_output, \
                    f"Task {task_id} contains marker from another task!"

        print("✅ Output isolation verified - no cross-contamination")


class TestMemoryUsage:
    """Tests for memory usage under load"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_memory_stability(self):
        """Test that memory doesn't grow unboundedly"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        tester = WebSocketLoadTester()

        # Run multiple batches
        for batch in range(3):
            await tester.run_concurrent_test(10, f"memory_test_batch_{batch}")

            current_memory = process.memory_info().rss / 1024 / 1024
            print(f"Batch {batch}: Memory = {current_memory:.1f} MB (delta: {current_memory - initial_memory:.1f} MB)")

            # Memory shouldn't grow by more than 500MB per batch
            assert current_memory - initial_memory < 500 * (batch + 1), \
                f"Memory growth too high: {current_memory - initial_memory:.1f} MB"

        print("✅ Memory usage stable")
```

### Task 2: Create Performance Benchmark

**File to Create:** `tests/benchmark_websocket.py`

```python
"""
Performance benchmarks for WebSocket operations

Run with: python tests/benchmark_websocket.py
"""

import asyncio
import aiohttp
import time
import statistics
from typing import List


async def benchmark_connection_latency(
    url: str = "ws://localhost:8000/ws/benchmark",
    iterations: int = 100
) -> dict:
    """Benchmark WebSocket connection latency"""
    latencies = []

    for i in range(iterations):
        start = time.perf_counter()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(f"{url}_{i}") as ws:
                    latency = time.perf_counter() - start
                    latencies.append(latency)
                    await ws.close()
        except Exception as e:
            print(f"Connection {i} failed: {e}")

    return {
        "iterations": iterations,
        "min": min(latencies) * 1000,
        "max": max(latencies) * 1000,
        "mean": statistics.mean(latencies) * 1000,
        "median": statistics.median(latencies) * 1000,
        "stdev": statistics.stdev(latencies) * 1000 if len(latencies) > 1 else 0
    }


async def benchmark_message_throughput(
    url: str = "ws://localhost:8000/ws/throughput",
    messages: int = 1000
) -> dict:
    """Benchmark message sending throughput"""
    sent_times = []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                for i in range(messages):
                    start = time.perf_counter()
                    await ws.send_json({"type": "ping", "seq": i})
                    sent_times.append(time.perf_counter() - start)

                await ws.close()

    except Exception as e:
        print(f"Throughput test failed: {e}")
        return {}

    total_time = sum(sent_times)
    msgs_per_sec = messages / total_time

    return {
        "messages": messages,
        "total_time_ms": total_time * 1000,
        "msgs_per_second": msgs_per_sec,
        "avg_send_time_us": statistics.mean(sent_times) * 1_000_000
    }


async def run_benchmarks():
    """Run all benchmarks"""
    print("=" * 60)
    print("WebSocket Performance Benchmarks")
    print("=" * 60)

    print("\n1. Connection Latency (100 connections)")
    print("-" * 40)
    latency = await benchmark_connection_latency(iterations=100)
    print(f"  Min:    {latency['min']:.2f} ms")
    print(f"  Max:    {latency['max']:.2f} ms")
    print(f"  Mean:   {latency['mean']:.2f} ms")
    print(f"  Median: {latency['median']:.2f} ms")
    print(f"  StdDev: {latency['stdev']:.2f} ms")

    print("\n2. Message Throughput (1000 messages)")
    print("-" * 40)
    throughput = await benchmark_message_throughput(messages=1000)
    if throughput:
        print(f"  Total time:     {throughput['total_time_ms']:.2f} ms")
        print(f"  Messages/sec:   {throughput['msgs_per_second']:.0f}")
        print(f"  Avg send time:  {throughput['avg_send_time_us']:.2f} µs")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(run_benchmarks())
```

### Task 3: Create Test Runner Script

**File to Create:** `scripts/run_load_tests.sh`

```bash
#!/bin/bash
# Run load tests

set -e

echo "Starting load tests..."
echo "Make sure the backend is running on localhost:8000"
echo ""

# Run pytest load tests
pytest tests/test_load.py -v -s -m slow

# Run benchmarks
echo ""
echo "Running performance benchmarks..."
python tests/benchmark_websocket.py

echo ""
echo "Load tests complete!"
```

## Verification Criteria

### Must Pass
- [ ] 10 concurrent connections: >90% success
- [ ] 50 concurrent connections: >80% success
- [ ] Output isolation: No cross-contamination
- [ ] Memory: No unbounded growth

### Performance Targets

| Metric | Target |
|--------|--------|
| Connection latency (median) | <100ms |
| Max concurrent connections | 50+ |
| Success rate at 50 connections | >80% |
| Memory per connection | <50MB |

## Success Criteria

Stage 13 is complete when:
1. ✅ Load tests pass
2. ✅ Performance meets targets
3. ✅ Output isolation verified
4. ✅ Memory stable under load

## Next Stage

Once Stage 13 is verified complete, proceed to:
**Stage 14: Migration & Deployment**

---

**Stage Status:** Not Started
**Last Updated:** 2026-02-11
