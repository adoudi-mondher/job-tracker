import logging
import os

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS lm_generation_runs (
    id SERIAL PRIMARY KEY,
    candidature_id INTEGER NOT NULL,
    analyse_json JSONB,
    lm_finale TEXT,
    statut_verification VARCHAR(20),
    motifs_json JSONB,
    nb_iterations INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

_CREATE_TABLE_LLM_CALLS = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id SERIAL PRIMARY KEY,
    candidature_id INTEGER,
    node VARCHAR(50),
    model VARCHAR(50),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd NUMERIC(10,6),
    created_at TIMESTAMP DEFAULT NOW()
);
"""


def _is_postgres() -> bool:
    url = os.environ.get("DATABASE_URL", "")
    return url.startswith("postgresql") or url.startswith("postgres")


def _get_conn():
    import psycopg2
    return psycopg2.connect(os.environ["DATABASE_URL"])


def ensure_table() -> None:
    if not _is_postgres():
        logger.info("DATABASE_URL n'est pas PostgreSQL — logging DB désactivé (mode local)")
        return
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(_CREATE_TABLE)
                cur.execute(_CREATE_TABLE_LLM_CALLS)
    except Exception as exc:
        logger.warning("ensure_table: impossible de créer la table (%s) — logging DB désactivé", exc)


def log_run(
    candidature_id: int,
    analyse: dict,
    lm_finale: str,
    statut: str,
    motifs: list,
    nb_iterations: int,
) -> None:
    if not _is_postgres():
        return
    try:
        from psycopg2.extras import Json
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO lm_generation_runs
                       (candidature_id, analyse_json, lm_finale, statut_verification, motifs_json, nb_iterations)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (candidature_id, Json(analyse), lm_finale, statut, Json(motifs), nb_iterations),
                )
    except Exception as exc:
        logger.warning("log_run failed candidature %s: %s", candidature_id, exc)


def log_llm_call(
    candidature_id: int,
    node: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    if not _is_postgres():
        return
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO llm_calls
                       (candidature_id, node, model, input_tokens, output_tokens, cost_usd)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (candidature_id, node, model, input_tokens, output_tokens, cost_usd),
                )
    except Exception as exc:
        logger.warning("log_llm_call failed candidature %s node %s: %s", candidature_id, node, exc)
