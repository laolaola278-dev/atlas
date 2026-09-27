"""Fairness reporting enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def fairness_report(service_id: str, demographic_keys: list[str], variance_threshold: float) -> dict[str, float]:
    """Validate fairness metrics across demographic groups."""
    if not service_id or not demographic_keys:
        raise ContractError("fairness-report-invalid")
    
    if variance_threshold < 0 or variance_threshold > 1:
        raise ContractError("fairness-threshold-invalid")
    
    # Synthetic variance calculation for demonstration
    variances = {key: 0.05 for key in demographic_keys}
    
    for key, variance in variances.items():
        if variance > variance_threshold:
            raise ContractError("fairness-variance-exceeded")
    
    return variances
