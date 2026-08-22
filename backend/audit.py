"""Append-only audit trail. `details` must contain only ids and counts —
never student names, emails, or free text (PII minimization)."""
import json
import logging
from typing import Any

from backend.db import pool

logger = logging.getLogger(__name__)

INSERT_SQL = "INSERT INTO audit_log (actor, action, target, details) VALUES (%s, %s, %s, %s)"
PAGE_SQL = (
    "SELECT id, ts, actor, action, target, details FROM audit_log {where} "
    "ORDER BY ts DESC LIMIT %s OFFSET %s"
)
COUNT_SQL = "SELECT COUNT(*) FROM audit_log {where}"


def record(actor: str, action: str, target: str | None = None, details: dict | None = None) -> None:
    try:
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute(INSERT_SQL, (actor, action, target, json.dumps(details) if details else None))
            conn.commit()
    except Exception:
        # An audit failure must never fail the audited request.
        logger.exception("audit write failed (action=%s)", action)


def page(actor: str | None, action: str | None, limit: int, offset: int) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    if actor:
        where.append("actor = %s")
        params.append(actor)
    if action:
        where.append("action = %s")
        params.append(action)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(COUNT_SQL.format(where=where_sql), params)
        total = int((cur.fetchone() or [0])[0])
        cur.execute(PAGE_SQL.format(where=where_sql), [*params, limit, offset])
        rows = [
            {
                "id": r[0],
                "ts": r[1].isoformat() if r[1] else None,
                "actor": r[2],
                "action": r[3],
                "target": r[4],
                "details": r[5],
            }
            for r in cur.fetchall()
        ]
    return {"rows": rows, "total": total, "limit": limit, "offset": offset}
