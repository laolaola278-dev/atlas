"""Alarm debounce.

A point alarm is raised only after the same condition repeats. One short
sample does not page.
"""
from __future__ import annotations

from internal.contract.errors import ContractError


_POINTS = frozenset({"hr", "spo2"})


def debounce(point: str, repeats: int, threshold: int) -> str:
    """Return raised only after enough repeated samples."""
    if point not in _POINTS:
        raise ContractError("alarm-point-unknown")
    if repeats < 1 or threshold < 2 or threshold > 10:
        raise ContractError("alarm-count-invalid")
    if repeats < threshold:
        raise ContractError("alarm-debounced")
    return "raised"


def critical_channel(channel: str, priority: str) -> str:
    """Keep a critical event off the ordinary channel."""
    if channel not in {"ordinary", "critical"} or priority not in {"routine", "critical"}:
        raise ContractError("channel-input-invalid")
    if priority == "critical" and channel != "critical":
        raise ContractError("channel-critical-isolated")
    if priority != "critical" and channel == "critical":
        raise ContractError("channel-ordinary-isolated")
    return channel


def downsample(point: str, priority: str, factor: int) -> int:
    """Return a sample factor, never for a critical point."""
    if point not in {"hr", "spo2"} or priority not in {"routine", "critical"}:
        raise ContractError("sample-input-invalid")
    if factor < 1 or factor > 60:
        raise ContractError("sample-factor-invalid")
    if priority == "critical" and factor != 1:
        raise ContractError("sample-critical-forbidden")
    return factor


def point_capacity(points: int, hertz: int, budget: int) -> int:
    """Return samples per second when they fit the budget."""
    if points < 1 or hertz < 1 or budget < 1:
        raise ContractError("capacity-input-invalid")
    total = points * hertz
    if total > budget:
        raise ContractError("capacity-exceeded")
    return total
