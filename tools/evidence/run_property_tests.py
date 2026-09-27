"""
Property test runner for P3 clinical rules.
"""

import pytest
import json
from datetime import datetime
from pathlib import Path


def run_property_tests():
    """Run all property tests and generate evidence report."""
    print("=== P3 Property Testing Framework ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    exit_code = pytest.main([
        'internal/contract/property/',
        '-v',
        '--tb=short',
        '--hypothesis-show-statistics'
    ])
    
    evidence = {
        'timestamp': datetime.now().isoformat(),
        'framework': 'hypothesis',
        'test_file': 'internal/contract/property/test_properties.py',
        'exit_code': exit_code,
        'status': 'passed' if exit_code == 0 else 'failed',
        'batch_coverage': {
            'P3-0119 to P3-0150': 'Rule engine invariants',
            'P3-0151 to P3-0170': 'HITL state machine properties',
            'P3-0171 to P3-0190': 'Explainability evidence properties'
        }
    }
    
    evidence_file = 'docs/evidence/p3-property-tests.json'
    Path('docs/evidence').mkdir(parents=True, exist_ok=True)
    with open(evidence_file, 'w') as f:
        json.dump(evidence, f, indent=2)
    
    print(f"Evidence report: {evidence_file}")
    return exit_code


if __name__ == '__main__':
    exit(run_property_tests())
