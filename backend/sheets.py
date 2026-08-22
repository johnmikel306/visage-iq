"""Google Sheets reads for the student directory.

PII rule: fetch row 1 (headers) first, then batchGet ONLY the whitelisted
columns — non-identity data never transits this service. Backoff per Google's
guidance: min(2^n + jitter, 64s) on 429/5xx. Quota (docs, 2026-08): 300
reads/min/project, 60/min/user; we do ~2 reads per 30-minute sync.
"""
import json
import logging
import random
import ssl
import threading
import time
from collections.abc import Callable

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
MAX_ATTEMPTS = 5


class SheetsError(Exception):
    pass


def col_letter(idx: int) -> str:
    """0-based column index -> A1 letter (A..Z, AA..)."""
    letters = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def backoff_delays(attempts: int, maximum: float = 64.0, jitter: Callable[[], float] = random.random) -> list[float]:
    return [min(2.0**n + jitter(), maximum) for n in range(attempts)]


_local = threading.local()


def _service():
    # Thread-local for the same reason as backend/gdrive.py: httplib2 is not
    # thread-safe across a shared client.
    svc = getattr(_local, "sheets_svc", None)
    if svc is None:
        if not settings.gdrive_sa_json:
            raise SheetsError("GDRIVE_SA_JSON is not set")
        try:
            info = json.loads(settings.gdrive_sa_json)
        except json.JSONDecodeError as exc:
            raise SheetsError(f"GDRIVE_SA_JSON is not valid JSON: {exc}") from exc
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        _local.sheets_svc = svc
    return svc


def _execute_with_backoff(request):
    delays = backoff_delays(MAX_ATTEMPTS)
    last: Exception | None = None
    for attempt, delay in enumerate(delays):
        try:
            return request.execute()
        except HttpError as exc:
            status = exc.resp.status if exc.resp is not None else None
            if status != 429 and not (status is not None and status >= 500):
                raise SheetsError(f"Sheets API error: {exc}") from exc
            last = exc
            logger.warning("sheets %s; retry %d/%d in %.1fs", status, attempt + 1, MAX_ATTEMPTS, delay)
        except (ssl.SSLError, OSError, TimeoutError) as exc:
            # Same transport as backend/gdrive.py (httplib2 over a shared
            # thread-local client) — a dropped socket/TLS record must retry
            # like a 5xx, not propagate raw.
            last = exc
            logger.warning("sheets transport error %r; retry %d/%d in %.1fs", exc, attempt + 1, MAX_ATTEMPTS, delay)
        if attempt + 1 < MAX_ATTEMPTS:
            time.sleep(delay)
    raise SheetsError(f"Sheets API kept failing after {MAX_ATTEMPTS} attempts: {last}")


def get_headers(sheet_id: str, worksheet: str) -> list[str]:
    resp = _execute_with_backoff(
        _service().spreadsheets().values().get(spreadsheetId=sheet_id, range=f"'{worksheet}'!1:1")
    )
    values = resp.get("values") or [[]]
    return [str(h) for h in values[0]]


def get_columns(sheet_id: str, worksheet: str, col_indexes: list[int]) -> dict[int, list[str]]:
    """Fetch full columns (row 2 down) for the given 0-based indexes only."""
    ranges = [f"'{worksheet}'!{col_letter(i)}2:{col_letter(i)}" for i in col_indexes]
    resp = _execute_with_backoff(
        _service().spreadsheets().values().batchGet(spreadsheetId=sheet_id, ranges=ranges)
    )
    out: dict[int, list[str]] = {}
    for idx, vr in zip(col_indexes, resp.get("valueRanges", [])):
        out[idx] = [str(row[0]) if row else "" for row in vr.get("values", [])]
    return out
