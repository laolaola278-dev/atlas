"""
Audit chain write performance benchmarks (P5-0269 to P5-0270).

Measures audit event write latency and throughput.
"""

import time
import statistics
from typing import Dict, Any, List
from datetime import datetime
import random
import hashlib


class AuditChainStub:
    """Stub audit chain for benchmarking."""
    
    def __init__(self):
        self.events: List[Dict] = []
        self.last_hash = 'genesis'
    
    def write_event(self, event: Dict) -> str:
        """Write an audit event to the chain."""
        event['timestamp'] = datetime.now().isoformat()
        event['prev_hash'] = self.last_hash
        event_str = str(event)
        event_hash = hashlib.sha256(event_str.encode()).hexdigest()
        event['hash'] = event_hash
        self.events.append(event)
        self.last_hash = event_hash
        return event_hash


def generate_audit_event(seed: int = None) -> Dict[str, Any]:
    """Generate synthetic audit event."""
    if seed is not None:
        random.seed(seed)
    event_types = ['rule_evaluation', 'review_created', 'review_approved', 'data_access', 'consent_check']
    return {
        'event_type': random.choice(event_types),
        'user_id': f'user-{random.randint(1000, 9999)}',
        'patient_id': f'patient-{random.randint(100000, 999999)}',
        'details': {
            'action': random.choice(['read', 'write', 'evaluate', 'approve']),
            'resource': random.choice(['observation', 'medication', 'review'])
        }
    }


def benchmark_audit_writes(
    num_iterations: int = 10000,
    warmup_iterations: int = 100
) -> Dict[str, Any]:
    """Benchmark audit chain write performance."""
    print(f"Running {num_iterations} audit writes (warmup: {warmup_iterations})...")
    chain = AuditChainStub()
    latencies = []
    for i in range(warmup_iterations):
        event = generate_audit_event(seed=i)
        chain.write_event(event)
    chain = AuditChainStub()
    for i in range(num_iterations):
        event = generate_audit_event(seed=i + warmup_iterations)
        start = time.perf_counter()
        chain.write_event(event)
        end = time.perf_counter()
        latency_ms = (end - start) * 1000
        latencies.append(latency_ms)
    latencies_sorted = sorted(latencies)
    total_time_s = sum(latencies) / 1000
    ops_per_second = num_iterations / total_time_s
    results = {
        'test_name': 'audit_chain_writes',
        'iterations': num_iterations,
        'total_time_s': round(total_time_s, 3),
        'ops_per_second': round(ops_per_second, 2),
        'p50_ms': round(statistics.median(latencies_sorted), 3),
        'p95_ms': round(latencies_sorted[int(len(latencies_sorted) * 0.95)], 3),
        'p99_ms': round(latencies_sorted[int(len(latencies_sorted) * 0.99)], 3),
        'chain_length': len(chain.events),
        'timestamp': datetime.now().isoformat()
    }
    print(f"  Throughput: {results['ops_per_second']} writes/sec")
    print(f"  P50: {results['p50_ms']} ms")
    print(f"  P95: {results['p95_ms']} ms")
    print(f"  P99: {results['p99_ms']} ms")
    print(f"  Chain length: {results['chain_length']} events")
    return results


if __name__ == '__main__':
    results = benchmark_audit_writes()
    import json
    print(json.dumps(results, indent=2))