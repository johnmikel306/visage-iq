"""Pure mapping from 'Pack Prosessing' sheet rows to student records.
No I/O here — everything is unit-testable."""
import re
from datetime import datetime

# canonical name -> exact sheet header (headers are stripped before matching)
CANONICAL_HEADERS = {
    "ts": "Timestamp",
    "student_id": "Student ID",
    "matric_form": "Matriculation Number",
    "matric_staff": "Matriculation No",
    "name_form": "Full Names",
    "name_staff": "Student Name",
    "email": "Student Email",
    "prog_form": "Programme of Study",
    "prog_staff": "Programme",
    "cohort": "Cohort",
    "level": "Current Level-Semester",
    "photo": "Upload Passport Photograph",
}
# staff variants may be blank mid-processing; everything else must exist
OPTIONAL = {"matric_staff", "name_staff", "prog_staff"}

_DRIVE_ID = re.compile(r"(?:/d/|[?&]id=)([A-Za-z0-9_-]{10,})")
_BARE_ID = re.compile(r"^[A-Za-z0-9_-]{20,}$")
_WS = re.compile(r"\s+")

# Google Forms timestamps: "M/D/YYYY H:MM:SS"; tolerate ISO too.
_TS_FORMATS = ("%m/%d/%Y %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")


class HeaderError(Exception):
    pass


def _clean(value: str | None) -> str:
    return _WS.sub(" ", (value or "").strip())


def parse_ts(raw: str) -> datetime | None:
    raw = _clean(raw)
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_drive_id(url: str | None) -> str | None:
    url = _clean(url)
    if not url:
        return None
    m = _DRIVE_ID.search(url)
    if m:
        return m.group(1)
    if _BARE_ID.match(url):
        return url
    return None


def resolve_headers(headers: list[str]) -> dict[str, int]:
    stripped = [h.strip() for h in headers]
    out: dict[str, int] = {}
    missing: list[str] = []
    for canon, header in CANONICAL_HEADERS.items():
        try:
            out[canon] = stripped.index(header)
        except ValueError:
            if canon not in OPTIONAL:
                missing.append(header)
    if missing:
        raise HeaderError("worksheet is missing expected column(s): " + ", ".join(missing))
    return out


def map_rows(rows: list[dict[str, str]]) -> tuple[list[dict], int]:
    """rows: canonical-keyed raw strings. Returns (records, skipped_no_key).
    Coalesce staff>form; dedupe by natural key, latest Timestamp wins."""
    by_key: dict[str, dict] = {}
    skipped = 0
    for raw in rows:
        student_id = _clean(raw.get("student_id"))
        matric = _clean(raw.get("matric_staff")) or _clean(raw.get("matric_form"))
        email = _clean(raw.get("email"))
        key = student_id or matric or email
        full_name = _clean(raw.get("name_staff")) or _clean(raw.get("name_form"))
        if not key or not full_name:
            skipped += 1
            continue
        record = {
            "natural_key": key,
            "student_id": student_id or None,
            "matric": matric or None,
            "full_name": full_name,
            "email": email or None,
            "programme": _clean(raw.get("prog_staff")) or _clean(raw.get("prog_form")) or None,
            "cohort": _clean(raw.get("cohort")) or None,
            "level_semester": _clean(raw.get("level")) or None,
            "photo_drive_file_id": parse_drive_id(raw.get("photo")),
            "row_ts": parse_ts(raw.get("ts", "")),
        }
        prior = by_key.get(key)
        if prior is None or (record["row_ts"] or datetime.min) >= (prior["row_ts"] or datetime.min):
            by_key[key] = record
    return list(by_key.values()), skipped
