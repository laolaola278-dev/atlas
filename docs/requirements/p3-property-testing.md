# P3 Property Testing Framework

> Generated: 2026-09-27T15:45:57.079Z
> Framework: Hypothesis (property-based testing)
> Batch coverage: P3-0119 to P3-0190 (72 batches)

## Overview

Property-based testing verifies that **invariants hold across all valid inputs**, unlike example-based tests.

## Test Categories

### 1. Rule Engine Invariants (P3-0119 to P3-0150)

**Properties:**
- Determinism: Same inputs → same outputs
- Monotonicity: More data → same or higher severity
- Fail-closed: Malformed input → safe default

### 2. HITL State Machine (P3-0151 to P3-0170)

**Properties:**
- No duplicates: Review not in both pending and completed
- Priority enforcement: Critical reviews have priority='critical'

### 3. Explainability (P3-0171 to P3-0190)

**Properties:**
- Evidence chain completeness: All required fields present
- Explanation determinism: Same inputs → same explanation

## Running Tests

```bash
pytest internal/contract/property/ -v --hypothesis-show-statistics
python tools/evidence/run_property_tests.py
```

## Status

✓ Framework created with stub implementations
⚠ Requires real evaluate_rule() and generate_explanation() implementations
