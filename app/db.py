import os
import logging
import uuid

logger = logging.getLogger(__name__)

_conn = None

def _connect():
    global _conn
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    try:
        import psycopg2
        _conn = psycopg2.connect(db_url)
        _conn.autocommit = True
        return _conn
    except Exception as e:
        logger.warning(f"db_connect_failed: {e}")
        _conn = None
        return None

def get_conn():
    global _conn
    if _conn is not None:
        try:
            _conn.cursor().execute("SELECT 1")
            return _conn
        except Exception:
            _conn = None
    return _connect()

def log_inference(user_id: str | None, query: str, answer: str, model_version: str, latency_ms: int, failure_mode: str | None, confidence: float):
    conn = get_conn()
    if conn is None:
        return False
    is_refusal = failure_mode == "low_confidence" or failure_mode == "refuse"
    is_low_confidence = failure_mode == "low_confidence"
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO inference_requests (request_id, user_id, query, answer, model_version, latency_ms, is_refusal, is_low_confidence)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            [str(uuid.uuid4()), user_id, query, answer, model_version, latency_ms, is_refusal, is_low_confidence]
        )
        return True
    except Exception as e:
        logger.warning(f"inference_log_failed: {e}")
        return False
