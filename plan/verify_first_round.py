#!/usr/bin/env python3
"""Validate the Atlas first-round planning deliverables.

The verifier is intentionally dependency-free so it can run in an offline,
air-gapped build environment before any service code exists.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PHASE_LOC = {
    "P0": 28_000,
    "P1": 86_000,
    "P2": 60_000,
    "P3": 106_000,
    "P4": 94_000,
    "P5": 24_000,
    "P6": 66_000,
    "P7": 76_000,
    "P8": 20_000,
}
REQUIRED_FILES = [
    ROOT / "docs" / "design" / "architecture.md",
    ROOT / "plan" / "batches.jsonl",
    ROOT / "plan" / "milestones.md",
    ROOT / "plan" / "risks.md",
    ROOT / "docs" / "compliance" / "mlps-level3-evidence-matrix.md",
    ROOT / "docs" / "compliance" / "crypto-assessment-evidence-matrix.md",
    ROOT / "tools" / "locaudit" / "README.md",
    ROOT / "tools" / "phi-scan" / "README.md",
    ROOT / "plan" / "first-round-report.md",
    ROOT / "plan" / "p0-execution.md",
]
ID_RE = re.compile(r"^ATLAS-P[0-8]-(\d{4})$")
FMEA_RE = re.compile(r"^\|\s*(?:FMEA|FM)-\d{2,3}\s*\|", re.MULTILINE)
RISK_RE = re.compile(r"^\|\s*R-\d{2,3}\s*\|", re.MULTILINE)
PLACEHOLDER_RE = re.compile(r"\b(?:TODO|TBD|xxx)\b|panic\(\"not implemented\"\)", re.IGNORECASE)


def fail(message: str) -> None:
    raise AssertionError(message)


def verify_utf8_text() -> None:
    text_suffixes = {".md", ".py", ".jsonl", ".yaml", ".yml", ".txt"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in text_suffixes and path.name not in {".gitignore", ".gitattributes"}:
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            fail(f"non-UTF-8 text file {path.relative_to(ROOT)}: {error}")


def verify_required_files() -> None:
    for path in REQUIRED_FILES:
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"missing or empty required file: {path.relative_to(ROOT)}")


ADR_TOPIC_KEYWORDS = {
    1: "HITL",
    2: "双人",
    3: "EMPI",
    4: "FHIR",
    5: "HL7",
    6: "DICOM",
    7: "CDSS",
    8: "证据链",
    9: "置信度",
    10: "医保",
    11: "DRG",
    12: "去标识化",
    13: "知情同意",
    14: "审计",
    15: "不出院",
    16: "模型",
    17: "生理流",
    18: "文书",
    19: "急诊",
    20: "国密",
    21: "联邦",
    22: "时钟",
    23: "幂等",
    24: "证书",
    25: "日志",
    26: "备份",
    27: "性能隔离",
    28: "成本",
    29: "兼容性",
    30: "灾备",
    31: "压测",
    32: "临床评测",
}


def verify_adrs() -> None:
    adr_dir = ROOT / "docs" / "adr"
    for number in range(1, 33):
        path = adr_dir / f"ADR-{number:03d}.md"
        if not path.is_file() or path.stat().st_size == 0:
            fail(f"missing ADR: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        if f"ADR-{number:03d}" not in text:
            fail(f"ADR heading does not contain its number: {path.name}")
        keyword = ADR_TOPIC_KEYWORDS[number]
        heading = text.splitlines()[0] if text.splitlines() else ""
        if keyword not in heading:
            fail(f"ADR-{number:03d} heading does not contain topic keyword {keyword!r}: {heading}")
        for section in ("状态", "日期", "当前角色", "背景", "选项", "决策", "安全后果", "回滚", "[待验证]"):
            if section not in text:
                fail(f"ADR-{number:03d} missing required section/marker: {section}")
        if text.count("```") % 2:
            fail(f"ADR-{number:03d} has unbalanced fenced code blocks")


def verify_architecture() -> None:
    text = REQUIRED_FILES[0].read_text(encoding="utf-8")
    required_terms = [
        "拓扑",
        "数据流",
        "部署",
        "容量",
        "数据不出院",
        "HITL",
        "状态机",
    ]
    for term in required_terms:
        if term not in text:
            fail(f"architecture missing required section or concept: {term}")
    fmea_count = len(FMEA_RE.findall(text))
    if fmea_count < 30:
        fail(f"architecture FMEA count {fmea_count} is below 30")
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 6_000:
        fail(f"architecture compact character count {len(compact)} is below 6000")
    if text.count("```") % 2:
        fail("architecture has unbalanced fenced code blocks")
    if text.count("flowchart") < 3 or "stateDiagram" not in text:
        fail("architecture is missing required topology/data/deployment/state diagrams")


def verify_batches() -> list[dict[str, object]]:
    path = REQUIRED_FILES[1]
    rows: list[dict[str, object]] = []
    required_keys = {
        "id",
        "phase",
        "module",
        "title",
        "depends_on",
        "inputs",
        "outputs",
        "loc_target",
        "acceptance",
        "reviewer",
    }
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            fail(f"blank JSONL row at line {line_number}")
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as error:
            fail(f"invalid JSON at batches line {line_number}: {error}")
        if not isinstance(row, dict):
            fail(f"batch row {line_number} is not an object")
        missing = required_keys - row.keys()
        if missing:
            fail(f"batch row {line_number} missing fields: {sorted(missing)}")
        rows.append(row)

    if not 340 <= len(rows) <= 400:
        fail(f"batch count {len(rows)} outside 340..400")

    ids = [str(row["id"]) for row in rows]
    if len(ids) != len(set(ids)):
        duplicates = [item for item, count in Counter(ids).items() if count > 1]
        fail(f"duplicate batch ids: {duplicates[:5]}")

    sequence = [int(ID_RE.match(item).group(1)) for item in ids if ID_RE.match(item)]
    if len(sequence) != len(ids) or sequence != list(range(1, len(rows) + 1)):
        fail("batch ids are not continuous ATLAS-Pn-0001..NNNN records")

    phase_loc = Counter()
    total_loc = 0
    index_by_id: dict[str, int] = {}
    for row in rows:
        batch_id = str(row["id"])
        index_by_id[batch_id] = len(index_by_id)
        phase = str(row["phase"])
        if phase not in EXPECTED_PHASE_LOC:
            fail(f"unknown phase {phase} in {batch_id}")
        loc = row["loc_target"]
        if not isinstance(loc, int) or not 800 <= loc <= 2_500:
            fail(f"invalid loc_target in {batch_id}: {loc}")
        if "production_loc" in row or "test_loc" in row:
            production = row.get("production_loc")
            test = row.get("test_loc")
            if not isinstance(production, int) or not isinstance(test, int) or production + test != loc:
                fail(f"production_loc/test_loc do not sum to loc_target in {batch_id}")
        phase_loc[phase] += loc
        total_loc += loc
        depends_on = row["depends_on"]
        acceptance = row["acceptance"]
        if not isinstance(depends_on, list) or not all(isinstance(item, str) for item in depends_on):
            fail(f"depends_on must be a string array in {batch_id}")
        if not isinstance(acceptance, list) or not acceptance or not all(
            isinstance(item, str) and item.strip() for item in acceptance
        ):
            fail(f"acceptance must be a non-empty string array in {batch_id}")

    for row in rows:
        current_index = index_by_id[str(row["id"])]
        for dependency in row["depends_on"]:
            if dependency not in index_by_id:
                fail(f"unknown dependency {dependency} in {row['id']}")
            if index_by_id[dependency] >= current_index:
                fail(f"non-lower dependency {dependency} in {row['id']}")

    if total_loc != 560_000:
        fail(f"total loc_target {total_loc} != 560000")
    for phase, expected in EXPECTED_PHASE_LOC.items():
        if phase_loc[phase] != expected:
            fail(f"{phase} loc_target {phase_loc[phase]} != {expected}")
    return rows


def verify_supporting_docs() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for term in ("临床协作", "不做自主诊断", "人工签核", "数据不出院"):
        if term not in readme:
            fail(f"README missing safety boundary: {term}")
    compliance_terms = {
        REQUIRED_FILES[4]: ("等保三级", "证据", "WORM", "失败处置"),
        REQUIRED_FILES[5]: ("SM2", "SM3", "SM4", "密钥", "密评"),
        REQUIRED_FILES[6]: ("560,000", "重复", "生成代码", "benchmark"),
        REQUIRED_FILES[7]: ("fail-closed", "熵", "OCR", "合成"),
        REQUIRED_FILES[8]: ("未完成项", "ATLAS-P0-0001", "PASS"),
        REQUIRED_FILES[9]: ("文件白名单", "ATLAS-P0-0001", "go test"),
    }
    for path, terms in compliance_terms.items():
        text = path.read_text(encoding="utf-8")
        for term in terms:
            if term not in text:
                fail(f"supporting document {path.relative_to(ROOT)} missing {term!r}")


def verify_risks() -> None:
    text = REQUIRED_FILES[3].read_text(encoding="utf-8")
    count = len(RISK_RE.findall(text))
    if count < 20:
        fail(f"risk count {count} is below 20")


def verify_placeholders() -> None:
    # Tool design documents legitimately name forbidden markers in their gate
    # definitions. The prose deliverables themselves must not use them.
    checked = [
        REQUIRED_FILES[0],
        REQUIRED_FILES[1],
        REQUIRED_FILES[2],
        REQUIRED_FILES[3],
        REQUIRED_FILES[8],
        REQUIRED_FILES[9],
        *sorted((ROOT / "docs" / "adr").glob("ADR-*.md")),
    ]
    for path in checked:
        match = PLACEHOLDER_RE.search(path.read_text(encoding="utf-8"))
        if match:
            fail(f"forbidden placeholder {match.group(0)!r} in {path.relative_to(ROOT)}")


def main() -> int:
    try:
        verify_utf8_text()
        verify_required_files()
        verify_adrs()
        verify_architecture()
        rows = verify_batches()
        verify_supporting_docs()
        verify_risks()
        verify_placeholders()
    except (AssertionError, OSError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print("PASS: Atlas first-round planning verification")
    print(f"ADR files: 32")
    print(f"Batch records: {len(rows)}")
    print("Phase LOC: " + ", ".join(f"{phase}={EXPECTED_PHASE_LOC[phase]}" for phase in EXPECTED_PHASE_LOC))
    print("Total LOC: 560000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
