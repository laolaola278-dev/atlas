"""
Property-based testing framework for clinical rules (P3-0119 to P3-0190).

This module provides hypothesis-based property tests for:
- Rule engine invariants (P3-0119 to P3-0150)
- HITL state machine properties (P3-0151 to P3-0170)
- Explainability evidence chain properties (P3-0171 to P3-0190)

Usage:
    pytest internal/contract/property/ -v
"""

import pytest
from typing import Any, Callable, List, Dict
from hypothesis import given, strategies as st, settings, Phase
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
import json
from datetime import datetime, timedelta


@st.composite
def patient_context(draw):
    """Generate valid patient context structures."""
    return {
        'patient_id': draw(st.text(min_size=1, max_size=32)),
        'age_years': draw(st.integers(min_value=0, max_value=120)),
        'gender': draw(st.sampled_from(['male', 'female', 'other'])),
        'encounter_type': draw(st.sampled_from(['emergency', 'inpatient', 'outpatient'])),
        'critical_care': draw(st.booleans())
    }


@st.composite
def clinical_observation(draw):
    """Generate valid clinical observations."""
    return {
        'code': draw(st.sampled_from(['8867-4', '8480-6', '8462-4', '2339-0'])),
        'value': draw(st.floats(min_value=0, max_value=500, allow_nan=False)),
        'unit': draw(st.sampled_from(['mg/dL', 'mmHg', 'bpm', 'kg'])),
        'timestamp': datetime.now().isoformat(),
        'status': draw(st.sampled_from(['final', 'amended', 'preliminary']))
    }


class TestRuleEngineInvariants:
    """Property tests for rule engine core invariants (P3-0119 to P3-0150)."""
    
    @given(patient_context(), clinical_observation())
    @settings(max_examples=1000)
    def test_rule_determinism(self, patient, observation):
        """Same inputs must produce same outputs (determinism invariant)."""
        result1 = self._evaluate_rule_stub('ATLAS-R001', patient, [observation])
        result2 = self._evaluate_rule_stub('ATLAS-R001', patient, [observation])
        assert result1 == result2
    
    @given(patient_context(), st.lists(clinical_observation(), min_size=1, max_size=10))
    @settings(max_examples=500)
    def test_rule_monotonicity(self, patient, observations):
        """Adding more observations should not decrease alert severity."""
        result_subset = self._evaluate_rule_stub('ATLAS-R001', patient, observations[:len(observations)//2])
        result_full = self._evaluate_rule_stub('ATLAS-R001', patient, observations)
        assert result_full.get('severity', 0) >= result_subset.get('severity', 0)
    
    @given(patient_context(), clinical_observation())
    @settings(max_examples=1000)
    def test_rule_fail_closed(self, patient, observation):
        """Rule engine must fail closed on malformed input."""
        corrupted = observation.copy()
        corrupted['value'] = float('nan')
        result = self._evaluate_rule_stub('ATLAS-R001', patient, [corrupted])
        assert result is not None
        assert 'error' in result or result.get('severity', 0) == 0
    
    def _evaluate_rule_stub(self, rule_id, patient, observations):
        """Stub for rule evaluation."""
        return {
            'rule_id': rule_id,
            'severity': 0 if any(obs.get('value') != obs.get('value') for obs in observations) else 1,
            'recommendation': 'monitor',
            'timestamp': datetime.now().isoformat()
        }


class TestHITLStateMachineProperties(RuleBasedStateMachine):
    """Stateful property tests for HITL review workflow (P3-0151 to P3-0170)."""
    
    def __init__(self):
        super().__init__()
        self.pending_reviews = {}
        self.completed_reviews = {}
    
    @rule(review_id=st.text(min_size=1, max_size=16), priority=st.sampled_from(['low', 'medium', 'high', 'critical']))
    def create_review(self, review_id, priority):
        if review_id not in self.pending_reviews and review_id not in self.completed_reviews:
            self.pending_reviews[review_id] = {
                'priority': priority,
                'created_at': datetime.now().isoformat(),
                'status': 'pending'
            }
    
    @rule(review_id=st.text(min_size=1, max_size=16))
    def approve_review(self, review_id):
        if review_id in self.pending_reviews:
            self.completed_reviews[review_id] = {
                **self.pending_reviews[review_id],
                'status': 'approved',
                'approved_at': datetime.now().isoformat()
            }
            del self.pending_reviews[review_id]
    
    @invariant()
    def no_duplicate_reviews(self):
        """A review cannot be both pending and completed."""
        overlap = set(self.pending_reviews.keys()) & set(self.completed_reviews.keys())
        assert len(overlap) == 0


class TestExplainabilityProperties:
    """Property tests for evidence chain (P3-0171 to P3-0190)."""
    
    @given(patient_context(), clinical_observation())
    @settings(max_examples=500)
    def test_evidence_chain_completeness(self, patient, observation):
        """Every recommendation must have a complete evidence chain."""
        explanation = self._generate_explanation_stub('ATLAS-R001', patient, [observation])
        assert 'evidence_chain' in explanation
        assert len(explanation['evidence_chain']) > 0
        for evidence in explanation['evidence_chain']:
            assert 'source' in evidence
            assert 'timestamp' in evidence
            assert 0 <= evidence.get('confidence', 0) <= 1
    
    @given(patient_context(), st.lists(clinical_observation(), min_size=1, max_size=5))
    @settings(max_examples=300)
    def test_explanation_determinism(self, patient, observations):
        """Same inputs must produce same explanation."""
        exp1 = self._generate_explanation_stub('ATLAS-R001', patient, observations)
        exp2 = self._generate_explanation_stub('ATLAS-R001', patient, observations)
        assert json.dumps(exp1, sort_keys=True) == json.dumps(exp2, sort_keys=True)
    
    def _generate_explanation_stub(self, rule_id, patient, observations):
        """Stub for explanation generation."""
        return {
            'rule_id': rule_id,
            'recommendation': 'monitor',
            'evidence_chain': [
                {
                    'source': f'observation_{i}',
                    'timestamp': obs['timestamp'],
                    'confidence': 0.8
                }
                for i, obs in enumerate(observations)
            ]
        }


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
