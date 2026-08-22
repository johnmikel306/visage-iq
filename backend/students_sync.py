"""Sync the students table from the 'Pack Prosessing' worksheet.
Runs in the worker: after every Drive photo sync, and standalone via
POST /students/sync. Sheet is the source of truth: upsert by natural key,
delete keys that vanished. Empty reads abort (same guard as photo prune)."""
import logging
from datetime import datetime, timezone

from backend.cache import set_students_sync_summary
from backend.config import settings
from backend.db import pool
from backend.sheets import SheetsError, get_columns, get_headers
from backend.students_map import HeaderError, map_rows, resolve_headers

logger = logging.getLogger(__name__)

UPSERT_SQL = """
INSERT INTO students (natural_key, student_id, matric, full_name, email,
                      programme, cohort, level_semester, photo_drive_file_id,
                      row_ts, synced_at)
VALUES (%(natural_key)s, %(student_id)s, %(matric)s, %(full_name)s, %(email)s,
        %(programme)s, %(cohort)s, %(level_semester)s, %(photo_drive_file_id)s,
        %(row_ts)s, NOW())
ON CONFLICT (natural_key) DO UPDATE SET
    student_id = EXCLUDED.student_id,
    matric = EXCLUDED.matric,
    full_name = EXCLUDED.full_name,
    email = EXCLUDED.email,
    programme = EXCLUDED.programme,
    cohort = EXCLUDED.cohort,
    level_semester = EXCLUDED.level_semester,
    photo_drive_file_id = EXCLUDED.photo_drive_file_id,
    row_ts = EXCLUDED.row_ts,
    synced_at = NOW()
"""
DELETE_MISSING_SQL = "DELETE FROM students WHERE NOT (natural_key = ANY(%s))"


def run_students_sync() -> dict:
    started = datetime.now(timezone.utc)
    summary = {"at": started.isoformat(), "ok": False, "rows": 0, "upserted": 0,
               "deleted": 0, "skipped_no_key": 0, "error": None}
    if not settings.students_sheet_id:
        summary["error"] = "STUDENTS_SHEET_ID not set"
        _write_summary(summary)
        return summary
    try:
        headers = get_headers(settings.students_sheet_id, settings.students_worksheet)
        cols = resolve_headers(headers)
        data = get_columns(settings.students_sheet_id, settings.students_worksheet, sorted(set(cols.values())))
        length = max((len(v) for v in data.values()), default=0)
        raw_rows = [
            {canon: (data[idx][i] if i < len(data[idx]) else "") for canon, idx in cols.items()}
            for i in range(length)
        ]
        records, skipped = map_rows(raw_rows)
        summary["rows"] = length
        summary["skipped_no_key"] = skipped
        if not records:
            raise SheetsError("sheet read produced 0 usable rows — refusing to wipe the students table")
        with pool.connection() as conn, conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, records)
            cur.execute(DELETE_MISSING_SQL, ([r["natural_key"] for r in records],))
            summary["deleted"] = cur.rowcount
            conn.commit()
        summary["upserted"] = len(records)
        summary["ok"] = True
        logger.info("students sync ok: upserted=%d deleted=%d skipped=%d of %d rows",
                    summary["upserted"], summary["deleted"], skipped, length)
    except (SheetsError, HeaderError) as exc:
        summary["error"] = str(exc)
        logger.error("students sync failed: %s", exc)
    except Exception as exc:  # unexpected — still record, never raise into the photo sync
        summary["error"] = f"unexpected: {exc}"
        logger.exception("students sync failed unexpectedly")
    _write_summary(summary)
    return summary


def _write_summary(summary: dict) -> None:
    # run_sync_job calls run_students_sync() bare on the "never raises"
    # contract — a Redis blip on the summary write must not fail the photo sync.
    try:
        set_students_sync_summary(summary)
    except Exception:
        logger.exception("failed to write students sync summary")


def run_students_sync_job() -> dict:
    from backend.sync import _ensure_pool_open

    _ensure_pool_open()
    return run_students_sync()
