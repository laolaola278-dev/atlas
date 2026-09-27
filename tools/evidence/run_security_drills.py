#!/usr/bin/env python3
"""
P6 Security drill runner.

Executes all security drills and generates evidence report.
Covers P6-0271 to P6-0314 (44 batches).
"""

import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from internal.contract.security.phi_leak_drills import run_phi_leak_drills
from internal.contract.security.authorization_bypass_drills import run_authorization_bypass_drills
from internal.contract.security.chaos_engineering_drills import run_chaos_engineering_drills
from internal.contract.security.recovery_verification_drills import run_recovery_verification_drills


def run_all_security_drills():
    """Run all security drills and generate evidence report."""
    print("=" * 70)
    print("P6 Security Drill Suite")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    results = []
    
    print("[1/4] Running PHI leak detection drills...")
    print("-" * 70)
    try:
        phi_results = run_phi_leak_drills()
        results.append(phi_results)
        print(f"✓ Completed: {phi_results['passed']} passed")
    except Exception as e:
        print(f"✗ Failed: {e}")
        results.append({"test_name": "phi_leak_detection", "error": str(e)})
    print()
    
    print("[2/4] Running authorization bypass prevention drills...")
    print("-" * 70)
    try:
        auth_results = run_authorization_bypass_drills()
        results.append(auth_results)
        print(f"✓ Completed: {auth_results['passed']} passed")
    except Exception as e:
        print(f"✗ Failed: {e}")
        results.append({"test_name": "authorization_bypass_prevention", "error": str(e)})
    print()
    
    print("[3/4] Running chaos engineering resilience drills...")
    print("-" * 70)
    try:
        chaos_results = run_chaos_engineering_drills()
        results.append(chaos_results)
        print(f"✓ Completed: {chaos_results['passed']} passed")
    except Exception as e:
        print(f"✗ Failed: {e}")
        results.append({"test_name": "chaos_engineering_resilience", "error": str(e)})
    print()
    
    print("[4/4] Running recovery verification drills...")
    print("-" * 70)
    try:
        recovery_results = run_recovery_verification_drills()
        results.append(recovery_results)
        print(f"✓ Completed: {recovery_results['passed']} passed")
    except Exception as e:
        print(f"✗ Failed: {e}")
        results.append({"test_name": "recovery_verification", "error": str(e)})
    print()
    
    # Generate evidence report
    print("=" * 70)
    print("Generating evidence report...")
    print("=" * 70)
    
    evidence = {
        "timestamp": datetime.now().isoformat(),
        "framework": "security_drill_suite",
        "batch_coverage": {
            "P6-0271 to P6-0280": "PHI leak detection (API responses, error messages, logs)",
            "P6-0281 to P6-0290": "Authorization bypass prevention (horizontal/vertical privilege escalation, IDOR)",
            "P6-0291 to P6-0300": "Chaos engineering resilience (network latency, service failure, database timeout, CPU stress)",
            "P6-0301 to P6-0314": "Recovery verification (backup integrity, failover, rollback, data integrity)"
        },
        "drills": results,
        "summary": {
            "total_drill_categories": len(results),
            "successful": sum(1 for r in results if "error" not in r and r.get("passed", False)),
            "failed": sum(1 for r in results if "error" in r or not r.get("passed", False))
        }
    }
    
    evidence_dir = Path("docs/evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / "p6-security-drills.json"
    
    with open(evidence_file, "w") as f:
        json.dump(evidence, f, indent=2)
    
    print(f"Evidence report: {evidence_file}")
    print(f"Total drill categories: {evidence['summary']['total_drill_categories']}")
    print(f"Successful: {evidence['summary']['successful']}")
    print(f"Failed: {evidence['summary']['failed']}")
    
    return 0 if evidence["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all_security_drills())