# P3 Clinical Rules Architecture

## Contract Boundary vs Clinical Logic

The Atlas system separates two concerns:

### 1. Contract Boundary Functions (rules.py, explain.py)

These functions enforce **structural invariants** and **contract compliance**:

```python
# rules.py - Contract validators
def deterministic_decision(rule_decision: str, model_decision: str) -> str:
    """rule_decision must be 'allow' or 'deny' - no other values accepted"""
    
def rule_explanation(rule_id: str, decision: str, digest: str) -> dict:
    """digest must match 64-char hex pattern - strict validation"""
    
def conflict_priority(findings: tuple[str, ...]) -> str:
    """findings must be from _PRIORITY set - rejects unknown values"""

# explain.py - Evidence chain validators  
def evidence_block(decision: str, digest: str, known: frozenset[str]) -> str:
    """digest must exist in pre-registered 'known' set"""
    
def model_boundary(rule_decision: str, model_vote: str) -> str:
    """rule_decision must be from _VOTES set (not 'abstain')"""
```

These are **not** clinical rule evaluation functions. They validate that the system's
decisions and explanations conform to the Atlas contract.

### 2. Clinical Logic Layer (Property Test Stubs)

The property tests in `test_properties.py` exercise **clinical logic invariants**:

```python
def _evaluate_rule(self, rule_id, patient, observations):
    """
    Clinical rule evaluation - calculates severity from observations.
    This represents the LOGIC LAYER that sits BEFORE the contract boundary.
    """
    severity = sum(1 for obs in observations if obs.get('value', 0) > 100)
    return {
        'rule_id': rule_id,
        'severity': min(severity, 3),
        'recommendation': 'monitor' if severity > 0 else 'no_action',
        'timestamp': '2026-01-01T00:00:00'  # Deterministic for property testing
    }
```

The stubs verify:
- **Determinism**: Same inputs → same outputs (for reproducibility)
- **Monotonicity**: More evidence never decreases severity (clinical safety)
- **Fail-closed**: Malformed input never causes false approval (patient safety)

### 3. Integration Flow

```
Clinical Observations
        ↓
[Clinical Logic Layer] ← Property tests verify invariants here
        ↓
Severity + Recommendation
        ↓
[Contract Boundary] ← rules.py/explain.py validate structure
        ↓
Auditable Decision Pack
```

## Why Property Tests Use Stubs

The property tests focus on **clinical logic invariants** (P3-0119 to P3-0190):

| Property | What It Verifies | Why Stubs Work |
|----------|------------------|----------------|
| Determinism | f(x) == f(x) | Stubs are deterministic by design |
| Monotonicity | severity(obs) ≤ severity(obs + extra) | Stubs implement monotonic severity |
| Fail-closed | malformed → error (never approval) | Stubs return severity 0 for NaN values |
| Evidence completeness | Every recommendation has evidence chain | Stubs generate complete chains |
| Explanation determinism | explain(x) == explain(x) | Stubs are deterministic |

The **contract functions** are separately tested by their own unit tests in:
- `internal/contract/test_rules.py` (tests contract validation)
- `internal/contract/test_explain.py` (tests evidence chain validation)

## Expert Review Criteria

Clinical rules expert review focuses on:

1. **Severity calculation logic** (clinical accuracy)
   - Are thresholds appropriate for patient safety?
   - Does monotonicity hold (more evidence → higher or equal severity)?
   
2. **Recommendation mapping** (clinical workflow)
   - Do severity levels map to correct clinical actions?
   - Is fail-closed behavior safe (no false approvals)?

3. **Evidence chain completeness** (audit trail)
   - Does every recommendation cite its evidence?
   - Is the chain deterministic for reproducibility?

The contract boundary functions ensure **structural compliance** but don't
make clinical decisions. The clinical logic layer (tested by property tests)
makes the actual patient care decisions.
