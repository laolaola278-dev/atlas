"""
HITL state machine operation benchmarks (P5-0266 to P5-0268).

Measures throughput for review creation, approval, and rejection.
"""

import time
import statistics
from typing import Dict, Any
from datetime import datetime
import random


class HITLStateMachineStub:
    """Stub HITL state machine for benchmarking."""
    
    def __init__(self):
        self.pending = {}
        self.completed = {}
    
    def create_review(self, review_id: str, priority: str) -> bool:
        """Create a new review."""
        if review_id in self.pending or review_id in self.completed:
            return False
        self.pending[review_id] = {
            'priority': priority,
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        return True
    
    def approve_review(self, review_id: str) -> bool:
        """Approve a review."""
        if review_id not in self.pending:
            return False
        self.completed[review_id] = {
            **self.pending[review_id],
            'status': 'approved',
            'approved_at': datetime.now().isoformat()
        }
        del self.pending[review_id]
        return True
    
    def reject_review(self, review_id: str) -> bool:
        """Reject a review."""
        if review_id not in self.pending:
            return False
        self.completed[review_id] = {
            **self.pending[review_id],
            'status': 'rejected',
            'rejected_at': datetime.now().isoformat()
        }
        del self.pending[review_id]
        return True


def benchmark_hitl_operations(
    num_iterations: int = 10000,
    warmup_iterations: int = 100
) -> Dict[str, Any]:
    """Benchmark HITL state machine operations."""
    print(f"Running {num_iterations} HITL operation cycles (warmup: {warmup_iterations})...")
    
    sm = HITLStateMachineStub()
    latencies = []
    priorities = ['low', 'medium', 'high', 'critical']
    
    # Warmup
    for i in range(warmup_iterations):
        review_id = f'review-{i}'
        sm.create_review(review_id, random.choice(priorities))
        if random.random() < 0.7:
            sm.approve_review(review_id)
        else:
            sm.reject_review(review_id)
    
    # Reset for measurement
    sm = HITLStateMachineStub()
    
    # Measurement
    for i in range(num_iterations):
        review_id = f'review-{i + warmup_iterations}'
        priority = random.choice(priorities)
        
        start = time.perf_counter()
        sm.create_review(review_id, priority)
        if random.random() < 0.7:
            sm.approve_review(review_id)
        else:
            sm.reject_review(review_id)
        end = time.perf_counter()
        
        latency_ms = (end - start) * 1000
        latencies.append(latency_ms)
    
    # Calculate metrics
    latencies_sorted = sorted(latencies)
    total_time_s = sum(latencies) / 1000
    ops_per_second = num_iterations / total_time_s
    
    results = {
        'test_name': 'hitl_state_machine_throughput',
        'iterations': num_iterations,
        'total_time_s': round(total_time_s, 3),
        'ops_per_second': round(ops_per_second, 2),
        'p50_ms': round(statistics.median(latencies_sorted), 3),
        'p95_ms': round(latencies_sorted[int(len(latencies_sorted) * 0.95)], 3),
        'p99_ms': round(latencies_sorted[int(len(latencies_sorted) * 0.99)], 3),
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"  Throughput: {results['ops_per_second']} ops/sec")
    print(f"  P50: {results['p50_ms']} ms")
    print(f"  P95: {results['p95_ms']} ms")
    print(f"  P99: {results['p99_ms']} ms")
    
    return results


if __name__ == '__main__':
    results = benchmark_hitl_operations()
    import json
    print(json.dumps(results, indent=2))