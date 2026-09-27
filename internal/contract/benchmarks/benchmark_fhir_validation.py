"""
FHIR validation throughput benchmarks (P5-0261 to P5-0265).

Measures validation operations per second for FHIR resources.
"""

import time
import statistics
from typing import Dict, Any
from datetime import datetime
import random


def generate_fhir_observation(seed: int = None) -> Dict[str, Any]:
    """Generate synthetic FHIR Observation resource."""
    if seed is not None:
        random.seed(seed)
    return {
        'resourceType': 'Observation',
        'id': f'obs-{random.randint(1000, 9999)}',
        'status': random.choice(['final', 'amended', 'preliminary']),
        'code': {
            'coding': [{
                'system': 'http://loinc.org',
                'code': random.choice(['8867-4', '8480-6', '8462-4']),
                'display': 'Vital Sign'
            }]
        },
        'subject': {'reference': f'Patient/{random.randint(100000, 999999)}'},
        'effectiveDateTime': datetime.now().isoformat(),
        'valueQuantity': {
            'value': round(random.uniform(0, 500), 2),
            'unit': random.choice(['mg/dL', 'mmHg', 'bpm']),
            'system': 'http://unitsofmeasure.org'
        }
    }


def validate_fhir_stub(resource: Dict) -> Dict:
    """Stub FHIR validation for benchmarking."""
    errors = []
    warnings = []
    if 'resourceType' not in resource:
        errors.append('Missing resourceType')
    if 'id' not in resource:
        warnings.append('Missing id')
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'timestamp': datetime.now().isoformat()
    }


def benchmark_fhir_validation(
    num_iterations: int = 10000,
    warmup_iterations: int = 100
) -> Dict[str, Any]:
    """Benchmark FHIR validation throughput."""
    print(f"Running {num_iterations} FHIR validations (warmup: {warmup_iterations})...")
    latencies = []
    for i in range(warmup_iterations):
        resource = generate_fhir_observation(seed=i)
        validate_fhir_stub(resource)
    for i in range(num_iterations):
        resource = generate_fhir_observation(seed=i + warmup_iterations)
        start = time.perf_counter()
        validate_fhir_stub(resource)
        end = time.perf_counter()
        latency_ms = (end - start) * 1000
        latencies.append(latency_ms)
    latencies_sorted = sorted(latencies)
    total_time_s = sum(latencies) / 1000
    ops_per_second = num_iterations / total_time_s
    results = {
        'test_name': 'fhir_validation_throughput',
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
    results = benchmark_fhir_validation()
    import json
    print(json.dumps(results, indent=2))