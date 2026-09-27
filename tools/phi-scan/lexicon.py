"""PHI scanner constants and patterns."""
import re

SCHEMA_VERSION = "1.0"
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

# Directories which cannot contain useful repository source for this gate.
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".cache",
    "cache",
    "caches",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "vendor",
    "third_party",
    "third-party",
    "build",
    "dist",
    "coverage",
    ".coverage",
}

# Keep the allow-list broad enough for the source/configuration formats in the
# repository, but do not try to decode binaries as text.
TEXT_EXTENSIONS = {
    ".txt",
    ".text",
    ".json",
    ".jsonl",
    ".ndjson",
    ".yaml",
    ".yml",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".sql",
    ".proto",
    ".cue",
    ".graphql",
    ".gql",
    ".go",
    ".py",
    ".pyi",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".kt",
    ".kts",
    ".scala",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".cs",
    ".rs",
    ".rb",
    ".php",
    ".swift",
    ".sh",
    ".bash",
    ".ps1",
    ".toml",
    ".ini",
    ".conf",
    ".cfg",
    ".xml",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".tf",
    ".properties",
    ".env.example",
}
TEXT_BASENAMES = {
    "Dockerfile",
    "Makefile",
    "README",
    "LICENSE",
}

# Candidate patterns.  They are deliberately not generic digit runs: generic
# numbers in plans and source are not PHI.  Check-digit functions below turn
# candidates into high-confidence findings.
_CN_ID_RE = re.compile(r"(?<![0-9A-Za-z])(?:\d[ -]?){17}[\dXx](?![0-9A-Za-z])", re.IGNORECASE)
_CN_ID15_RE = re.compile(r"(?<![0-9A-Za-z])\d{15}(?![0-9A-Za-z])")
_CN_PHONE_RE = re.compile(r"(?<!\d)1[3-9](?:[ -]?\d){9}(?!\d)")
_BANK_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+"
    r"(?![A-Za-z0-9-])"
)
_US_SSN_RE = re.compile(r"(?<!\d)\d{3}[- ]?\d{2}[- ]?\d{4}(?!\d)")
_DICOM_TAG_RE = re.compile(r"\([0-9A-Fa-f]{4},[0-9A-Fa-f]{4}\)")
_HL7_RE = re.compile(r"(?im)(?:^|[|\s])PID\|[^\n|]{0,40}(?:[^\n|]*\|){2,}[^\n|]*")

# Context words are deliberately broad enough to catch source/YAML/JSON keys,
# while requiring a non-placeholder scalar before reporting a finding.
SENSITIVE_KEYS = {
    "patient_id",
    "patientid",
    "patient_name",
    "patientname",
    "subject_id",
    "subject_name",
    "person_id",
    "person_name",
    "medical_record_number",
    "medical_record_no",
    "medical_record",
    "record_number",
    "mrn",
    "hospital_id",
    "admission_id",
    "encounter_id",
    "insurance_id",
    "insurance_number",
    "national_id",
    "id_card",
    "idcard",
    "identity_number",
    "phone",
    "telephone",
    "mobile",
    "email",
    "e_mail",
    "address",
    "dob",
    "date_of_birth",
    "birth_date",
    "birthdate",
    "diagnosis",
    "diagnoses",
    "prescription",
    "medication",
    "lab_result",
    "lab_results",
    "patient",
    "姓名",
    "患者",
    "病历号",
    "病案号",
    "住院号",
    "门诊号",
    "身份证",
    "手机号",
    "电话",
    "邮箱",
    "地址",
    "出生日期",
    "诊断",
    "处方",
    "检验结果",
}
STRONG_SENSITIVE_KEYS = SENSITIVE_KEYS - {"name", "patient"}
MEDICAL_CONTEXT_WORDS = {
    "patient",
    "患者",
    "病历",
    "病案",
    "诊断",
    "检验",
    "检查",
    "处方",
    "用药",
    "住院",
    "就诊",
    "医生",
    "临床",
    "medical",
    "clinical",
    "diagnosis",
    "prescription",
    "medication",
    "lab",
    "encounter",
    "admission",
}
IDENTIFIER_CONTEXT_WORDS = {
    "patient",
    "患者",
    "姓名",
    "name",
    "mrn",
    "病历",
    "病案",
    "住院",
    "phone",
    "mobile",
    "telephone",
    "email",
    "身份证",
    "id_card",
    "idcard",
    "dob",
    "birth",
    "address",
    "insurance",
    "医保",
}

# These values are unambiguous placeholders.  A value containing "synthetic"
# is intentionally *not* suppressed: provenance does not make a suspected
# identifier safe to silently pass.
PLACEHOLDERS = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "nil",
    "none",
    "null",
    "unknown",
    "redacted",
    "<redacted>",
    "***",
    "masked",
    "placeholder",
    "example",
    "test",
    "synthetic",
    "未填写",
    "已脱敏",
    "未知",
}
