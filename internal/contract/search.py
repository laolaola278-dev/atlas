"""Search parameter allow-list.

A search may use only named parameters. Direct identifiers and unknown names
fail closed. This is not an official FHIR search implementation.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


ALLOWED = frozenset({
    "_count",
    "_id",
    "clinical-status",
    "code",
    "date",
    "encounter",
    "patient",
    "priority",
    "status",
    "subject",
})


def require_parameters(names: object) -> tuple[str, ...]:
    """Return the accepted parameter names in stable order."""
    if not isinstance(names, (list, tuple)) or not names:
        raise ContractError("search-parameter-missing")
    accepted: list[str] = []
    for name in names:
        token = str(name)
        if token not in ALLOWED or path_has_direct_identifier(token):
            raise ContractError("search-parameter-forbidden")
        if token not in accepted:
            accepted.append(token)
    return tuple(sorted(accepted))
