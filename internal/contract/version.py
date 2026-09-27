"""Contract version compatibility.

The current contract accepts itself and the immediately previous minor
version. A future version or a skipped minor version is rejected.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.errors import ContractError


CURRENT = (1, 0)


@dataclass(frozen=True)
class ContractVersion:
    major: int
    minor: int

    def text(self) -> str:
        return f"{self.major}.{self.minor}"


def parse_version(value: str) -> ContractVersion:
    """Parse major.minor and reject every other shape."""
    parts = value.split(".")
    if len(parts) == 1 and parts[0].isdigit():
        parts = [parts[0], "0"]
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        parts = parts[:2]
    if len(parts) != 2 or any(not part.isdigit() for part in parts):
        raise ContractError("version-invalid")
    return ContractVersion(int(parts[0]), int(parts[1]))


def compatible(value: str, current: tuple[int, int] = CURRENT) -> bool:
    """Return true only for current or N-1 within the same major version."""
    parsed = parse_version(value)
    major, minor = current
    if parsed.major != major:
        return False
    return parsed.minor in {minor, minor - 1} and parsed.minor >= 0


def require_resource_version(expected: str, current: str) -> str:
    """Accept one write only when it names the stored resource version."""
    if expected == "" or current == "":
        raise ContractError("resource-version-missing")
    if not expected.isdigit() or not current.isdigit():
        raise ContractError("resource-version-invalid")
    if expected != current:
        raise ContractError("version-conflict")
    return current
