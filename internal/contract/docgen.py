"""Document arrival rates.

Counts are synthetic. The gate returns a percent and never stores document text.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


def arrival_rate(delivered: int, expected: int) -> int:
    """Accept a delivery only when at least 95 percent arrived."""
    counts = (delivered, expected)
    if any(type(item) is not int for item in counts):
        raise ContractError("doc-arrival-invalid")
    if expected < 1 or expected > 10000 or delivered < 0 or delivered > expected:
        raise ContractError("doc-arrival-invalid")
    percent = (delivered * 100) // expected
    if percent < 95:
        raise ContractError("doc-arrival-below")
    return percent


_TEMPLATE = ("section", "title", "version")


def template_schema(fields: dict[str, str]) -> str:
    """Accept one template schema. Document text stays outside this gate."""
    names = tuple(sorted(fields))
    if names != _TEMPLATE:
        raise ContractError("template-fields-invalid")
    version = fields["version"]
    if version not in {"1.0", "1.1"}:
        raise ContractError("template-version-invalid")
    labeled = (fields["section"], fields["title"])
    if any(path_has_direct_identifier(item) for item in labeled):
        raise ContractError("template-identifier-forbidden")
    if any(item == "" or " " in item for item in labeled):
        raise ContractError("template-text-forbidden")
    return version


_CHAPTERS = ("assessment", "plan", "orders")


def required_chapters(chapters: tuple[str, ...]) -> int:
    """Require the three chapters in order. Text stays outside this gate."""
    if any(path_has_direct_identifier(item) for item in chapters):
        raise ContractError("chapter-identifier-forbidden")
    if chapters != _CHAPTERS:
        raise ContractError("chapter-required-missing")
    return len(chapters)


_TERMS = frozenset({"assessment", "order-note", "plan"})


def term_check(label: str, digest: str, known: frozenset[str]) -> str:
    """Accept one document term only when its digest is registered."""
    if label not in _TERMS:
        raise ContractError("doc-term-unknown")
    if len(digest) != 64 or digest not in known:
        raise ContractError("doc-term-unregistered")
    return label


_LANES = {"accepted": 1, "draft": 0}


def draft_isolation(source: str, target: str) -> str:
    """Keep a model draft out of the accepted document table."""
    left = _LANES.get(source)
    right = _LANES.get(target)
    if left is None or right is None:
        raise ContractError("draft-lane-invalid")
    if left < right:
        raise ContractError("draft-isolated")
    if left > right:
        raise ContractError("accepted-isolated")
    return target


_AUTOMATIC = frozenset({"model", "system"})


def adopt_boundary(actor: str, state: str) -> str:
    """Let a human adopt a draft. A model cannot adopt its own text."""
    named = actor.strip()
    if named == "" or state not in {"accepted", "draft"}:
        raise ContractError("adopt-input-invalid")
    if named in _AUTOMATIC or path_has_direct_identifier(named):
        raise ContractError("adopt-actor-forbidden")
    if state != "draft":
        raise ContractError("adopt-state-invalid")
    return "accepted"


_TIMED = frozenset({"render", "review", "term"})


def segment_p95(samples: dict[str, tuple[int, ...]], budget: int) -> int:
    """Return the slowest segment P95 when every segment stays in budget."""
    if set(samples) != _TIMED or type(budget) is not int or budget < 1 or budget > 10000:
        raise ContractError("segment-time-invalid")
    slowest = 0
    for values in samples.values():
        if not values or len(values) > 100:
            raise ContractError("segment-time-invalid")
        if any(type(item) is not int or item < 0 or item > 10000 for item in values):
            raise ContractError("segment-time-invalid")
        ordered = tuple(sorted(values))
        index = max(0, (len(ordered) * 95 + 99) // 100 - 1)
        slowest = max(slowest, ordered[index])
    if slowest > budget:
        raise ContractError("segment-p95-exceeded")
    return slowest


_ROLLBACK = {("1.1", "1.0"): "1.0"}


def doc_rollback(current: str, target: str, sealed: bool) -> str:
    """Roll an unsealed document back one minor version."""
    if type(sealed) is not bool:
        raise ContractError("doc-rollback-invalid")
    rolled = _ROLLBACK.get((current, target))
    if rolled is None:
        raise ContractError("doc-rollback-invalid")
    if sealed:
        raise ContractError("doc-rollback-sealed")
    return rolled


def cited_evidence(digests: tuple[str, ...], known: frozenset[str]) -> int:
    """Count registered evidence digests. Document text stays outside."""
    if not digests or len(digests) > 8:
        raise ContractError("citation-set-invalid")
    if len(set(digests)) != len(digests):
        raise ContractError("citation-duplicate")
    missing = [item for item in digests if len(item) != 64 or item not in known]
    if missing:
        raise ContractError("citation-unregistered")
    return len(digests)


def synthetic_load(copies: int, bytes_each: int, synthetic: bool) -> int:
    """Bound a synthetic document load. No document body is created."""
    pair = (copies, bytes_each)
    if any(type(item) is not int for item in pair) or type(synthetic) is not bool:
        raise ContractError("doc-load-invalid")
    if copies < 1 or copies > 1000 or bytes_each < 1 or bytes_each > 4096:
        raise ContractError("doc-load-invalid")
    total = copies * bytes_each
    if total > 1_000_000:
        raise ContractError("doc-load-exceeded")
    if synthetic is not True:
        raise ContractError("doc-load-not-synthetic")
    return total


_RESULTS = frozenset({"done", "rejected", "unknown"})


def doc_retry(attempt: int, result: str) -> str:
    """Retry an unknown document result at most twice."""
    if type(attempt) is not int or attempt < 1 or attempt > 3 or result not in _RESULTS:
        raise ContractError("doc-retry-invalid")
    if result == "done":
        return "done"
    if result == "rejected":
        raise ContractError("doc-retry-forbidden")
    if attempt == 3:
        raise ContractError("doc-retry-exhausted")
    raise ContractError("doc-retry-unknown")


_OUTPUT = frozenset({"plan", "section", "version"})


def redact_output(fields: tuple[str, ...]) -> int:
    """Count safe labels. Document text and identifiers stay outside."""
    if not fields or len(fields) > 3 or len(set(fields)) != len(fields):
        raise ContractError("redact-output-invalid")
    if any(path_has_direct_identifier(item) for item in fields):
        raise ContractError("redact-identifier-forbidden")
    if any(item not in _OUTPUT for item in fields):
        raise ContractError("redact-field-forbidden")
    return len(fields)
