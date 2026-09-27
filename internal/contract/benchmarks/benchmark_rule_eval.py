"""
Rule evaluation performance benchmarks (P5-0255 to P5-0260).

Measures P50/P95/P99 latency for clinical rule evaluation.
"""

import time
import statistics
from typing import List, Dict, Any
from datetime import datetime
import random


def generate_patient_context(seed: int = None) -> Dict[str, Any]:
    """Generate synthetic patient context for benchmarking."""
    if seed is not None:
        random.seed(seed)
    
    return {
        'patient_id': f'P{random.randint(100000, 999999)}',
        'age_years': random.randint(0, 120),
        'gender': random.choice(['male', 'female', 'other']),
        'encounter_type': random.choice(['emergency', 'inpatient', 'outpatient']),
        'critical_care': random.choice([True, False])
    }


def generate_clinical_observations(count: int, seed: int = None) -> List[Dict[str, Any]]:
    """Generate synthetic clinical observations."""
    if seed is not None:
        random.seed(seed)
    
    codes = ['8867-4', '8480-6', '8462-4', '2339-0', '72514-3']
    units = ['mg/dL', 'mmHg', 'bpm', 'kg', 'cm']
    
    observations = []
    for i in range(count):
        observations.append({
            'code': random.choice(codes),
            'value': random.uniform(0, 500),
            'unit': random.choice(units),
            'timestamp': datetime.now().isoformat(),
            'status': random.choice(['final', 'amended', 'preliminary'])
        })
    
    return observations


def evaluate_rule_stub(rule_id: str, patient: Dict, observations: List[Dict]) -> Dict:
    """Stub rule evaluation for benchmarking."""
    severity = 0
    for obs in observations:
        if obs.get('value', 0) > 100:
            severity += 1
    
    return {
        'rule_id': rule_id,
        'severity': min(severity, 3),
        'recommendation': 'monitor' if severity > 0 else 'no_action',
        'timestamp': datetime.now().isoformat()
    }


def benchmark_rule_evaluation(
    num_iterations: int = 10000,
    observations_per_call: int = 5,
    warmup_iterations: int = 100
) -> Dict[str, Any]:
    """
    Benchmark rule evaluation latency.
    
    Returns P50, P95, P99 latency in milliseconds.
    """
    print(f"Running {num_iterations} iterations (warmup: {warmup_iterations})...")
    
    latencies = []
    
    # Warmup phase
    for i in range(warmup_iterations):
        patient = generate_patient_context(seed=i)
        observations = generate_clinical_observations(observations_per_call, seed=i)
        evaluate_rule_stub('ATLAS-R001', patient, observations)
    
    # Measurement phase
    for i in range(num_iterations):
        patient = generate_patient_context(seed=i + warmup_iterations)
        observations = generate_clinical_observations(observations_per_call, seed=i + warmup_iterations)
        
        start = time.perf_counter()
        evaluate_rule_stub('ATLAS-R001', patient, observations)
        end = time.perf_counter()
        
        latency_ms = (end - start) * 1000
        latencies.append(latency_ms)
    
    # Calculate percentiles
    latencies_sorted = sorted(latencies)
    p50 = statistics.median(latencies_sorted)
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
    p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]
    
    results = {
        'test_name': 'rule_evaluation_latency',
        'iterations': num_iterations,
        'observations_per_call': observations_per_call,
        'p50_ms': round(p50, 3),
        'p95_ms': round(p95, 3),
        'p99_ms': round(p99, 3),
        'mean_ms': round(statistics.mean(latencies), 3),
        'stddev_ms': round(statistics.stdev(latencies), 3),
        'min_ms': round(min(latencies), 3),
        'max_ms': round(max(latencies), 3),
        'timestamp': datetime.now().isoformat()
    }
    
    print(f"Results:")
    print(f"  P50: {results['p50_ms']} ms")
    print(f"  P95: {results['p95_ms']} ms")
    print(f"  P99: {results['p99_ms']} ms")
    
    return results


if __name__ == '__main__':
    results = benchmark_rule_evaluation()
    import json
    print("\n" + json.dumps(results, indent=2))