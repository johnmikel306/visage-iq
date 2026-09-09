import logging
import re
from pathlib import Path

from psycopg import sql
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from backend.config import settings

logger = logging.getLogger(__name__)

INIT_SQL_PATH = Path(__file__).resolve().parent.parent / "scripts" / "init_db.sql"


def _ensure_extension(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()


def _configure(conn):
    _ensure_extension(conn)
    register_vector(conn)


pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=5,
    configure=_configure,
    open=False,
)


def _ensure_alt_indexes(cur) -> None:
    """Partial HNSW index per compare model (predicate must be a literal for
    the planner to match it, so these can't live in static init_db.sql)."""
    for model in settings.compare_models_list:
        safe = re.sub(r"[^a-z0-9_]", "_", model.lower())
        cur.execute(
            sql.SQL(
                "CREATE INDEX IF NOT EXISTS {} ON alt_embeddings "
                "USING hnsw (embedding vector_cosine_ops) WHERE model = {}"
            ).format(sql.Identifier(f"alt_emb_hnsw_{safe}"), sql.Literal(model))
        )


def bootstrap_schema() -> None:
    if not INIT_SQL_PATH.exists():
        logger.warning("init_db.sql not found at %s; skipping schema bootstrap", INIT_SQL_PATH)
        return
    init_sql = INIT_SQL_PATH.read_text(encoding="utf-8")
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(init_sql)
        _ensure_alt_indexes(cur)
        conn.commit()
    logger.info("schema bootstrap complete")
