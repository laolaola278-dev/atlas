#!/usr/bin/env python3
"""
P5 Performance benchmark runner.

Executes all performance benchmarks and generates evidence report.
Covers P5-0255 to P5-0270 (16 batches).
"""

import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from internal.contract.benchmarks.benchmark_rule_eval import benchmark_rule_evaluation
from internal.contract.benchmarks.benchmark_fhir_validation import benchmark_fhir_validation
from internal.contract.benchmarks.benchmark_hitl_operations import benchmark_hitl_operations
from internal.contract.benchmarks.benchmark_audit_chain import benchmark_audit_writes


def run_all_benchmarks():
    """Run all performance benchmarks and generate evidence report."""
    print("=" * 70)
    print("P5 Performance Benchmark Suite")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    results = []
    
    print("[1/4] Running rule evaluation latency benchmark...")
    print("-" * 70)
    try:
        rule_results = benchmark_rule_evaluation()
        results.append(rule_results)
        print("✓ Completed")
    except Exception as e:
        print(f"✗ Failed: {e}")
        results.append({'test_name': 'rule_evaluation_latency', 'error': str(e)})
    print()
    
    print("[2/4] Running FHIR validation throughput benchmark...")
    print("-" * 70)
    try:
        fhir_results = benchmark_fhir_validation()
        results.append(fhir_results)
        print("✓ Completed")
    except Exception as e:
        print(f"✗ Failed: {e}")
        results.append({'test_name': 'fhir_validation_throughput', 'error': str(e)})
    print()
    
    print("[3/4] Running HITL state machine operations benchmark...")
    print("-" * 70)
    try:
        hitl_results = benchmark_hitl_operations()
        results.append(hitl_results)
        print("✓ Completed")
    except Exception as e:
        print(f"✗ Failed: {e}")
        results.append({'test_name': 'hitl_state_machine_throughput', 'error': str(e)})
    print()
    
    print("[4/4] Running audit chain write performance benchmark...")
    print("-" * 70)
    try:
        audit_results = benchmark_audit_writes()
        results.append(audit_results)
        print("✓ Completed")
    except Exception as e:
        print(f"✗ Failed: {e}")
        results.append({'test_name': 'audit_chain_writes', 'error': str(e)})
    print()
    
    # Generate evidence report
    print("=" * 70)
    print("Generating evidence report...")
    print("=" * 70)
    
    evidence = {
        'timestamp': datetime.now().isoformat(),
        'framework': 'custom_benchmark_suite',
        'batch_coverage': {
            'P5-0255 to P5-0260': 'Rule evaluation latency (P50/P95/P99)',
            'P5-0261 to P5-0265': 'FHIR validation throughput',
            'P5-0266 to P5-0268': 'HITL state machine operations',
            'P5-0269 to P5-0270': 'Audit chain write performance'
        },
        'benchmarks': results,
        'summary': {
            'total_benchmarks': len(results),
            'successful': sum(1 for r in results if 'error' not in r),
            'failed': sum(1 for r in results if 'error' in r)
        }
    }
    
    evidence_dir = Path('docs/evidence')
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / 'p5-benchmarks.json'
    
    with open(evidence_file, 'w') as f:
        json.dump(evidence, f, indent=2)
    
    print(f"Evidence report: {evidence_file}")
    print(f"Total benchmarks: {evidence[\"summary\"][\"total_benchmarks\"]}")
    print(f"Successful: {evidence[\"summary\"][\"successful\"]}")
    print(f"Failed: {evidence[\"summary\"][\"failed\"]}")
    
    return 0 if evidence["summary"]["failed"] == 0 else 1


if __name__ == '__main__':
    sys.exit(run_all_benchmarks())