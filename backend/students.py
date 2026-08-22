"""SQL queries for the student directory. Search never touches Google."""
from typing import Any

from backend.db import pool

# UI field chip -> column. Whitelist prevents injection via ?field=.
FIELD_COLS = {
    "name": "full_name",
    "matric": "matric",
    "sid": "student_id",
    "email": "email",
    "programme": "programme",
    "cohort": "cohort",
}
ROW_COLS = ("id, natural_key, student_id, matric, full_name, email, "
            "programme, cohort, level_semester, photo_drive_file_id")


def _row(r) -> dict[str, Any]:
    return {
        "id": r[0], "natural_key": r[1], "student_id": r[2], "matric": r[3],
        "full_name": r[4], "email": r[5], "programme": r[6], "cohort": r[7],
        "level_semester": r[8], "photo_drive_file_id": r[9],
    }


def page(q: str | None, field: str, programme: str | None, cohort: str | None,
         level: str | None, has_photo: bool, limit: int, offset: int) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []
    if programme:
        where.append("programme = %s")
        params.append(programme)
    if cohort:
        where.append("cohort = %s")
        params.append(cohort)
    if level:
        where.append("level_semester = %s")
        params.append(level)
    if has_photo:
        where.append("photo_drive_file_id IS NOT NULL")
    if q:
        like = f"%{q}%"
        col = FIELD_COLS.get(field)
        if col:
            where.append(f"{col} ILIKE %s")
            params.append(like)
        else:  # all fields
            ors = " OR ".join(f"{c} ILIKE %s" for c in FIELD_COLS.values())
            where.append(f"({ors})")
            params.extend([like] * len(FIELD_COLS))
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM students {where_sql}", params)
        total = int((cur.fetchone() or [0])[0])
        cur.execute(
            f"SELECT {ROW_COLS} FROM students {where_sql} ORDER BY full_name, id LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        rows = [_row(r) for r in cur.fetchall()]
    return {"rows": rows, "total": total, "limit": limit, "offset": offset}


def get(student_pk: int) -> dict[str, Any] | None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {ROW_COLS} FROM students WHERE id = %s", (student_pk,))
        r = cur.fetchone()
    return _row(r) if r else None


def facets() -> dict[str, Any]:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT programme FROM students WHERE programme IS NOT NULL ORDER BY 1")
        programmes = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT cohort FROM students WHERE cohort IS NOT NULL ORDER BY 1")
        cohorts = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT level_semester FROM students WHERE level_semester IS NOT NULL ORDER BY 1")
        levels = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM students")
        total = int((cur.fetchone() or [0])[0])
    return {"programmes": programmes, "cohorts": cohorts, "levels": levels, "total": total}
