from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from time import perf_counter
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from app.schemas import PredictRequest, PredictResponse
from app.logging_utils import get_logger, with_request_id
from app.llm_rag.rag_pipeline import answer_query, RagResult
from app import db
from app.security import require_api_key
import os

app = FastAPI(title="DOSM Insights API", version=os.getenv("MODEL_VERSION", "dosm-rag-local"))
logger = get_logger(__name__)

# Prometheus metrics
HTTP_REQUESTS = Counter("http_requests_total", "Total HTTP requests", ["path", "method", "status"])
HTTP_LATENCY = Histogram("http_request_latency_ms", "Latency (ms)", buckets=(50,100,200,400,800,1600,3200))
RAG_DECISIONS = Counter(
    "rag_decisions_total",
    "RAG decision outcomes",
    ["decision", "failure_mode"]
)
RAG_REFUSALS = Counter("rag_refusals_total", "Total refusal events")
RAG_LOW_CONF = Counter("rag_low_confidence_total", "Total low confidence events")

def build_health_payload():
    db_status = "unconfigured"
    try:
        conn = db.get_conn()
        if conn is not None:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            db_status = "ok"
        else:
            # if DATABASE_URL absent treat as unconfigured rather than error
            if os.getenv("DATABASE_URL"):
                db_status = "error"
    except Exception:
        db_status = "error"
    payload = {
        "status": "ok" if db_status in ("ok","unconfigured") else "degraded",
        "version": app.version,
        "checks": {
            "db": db_status,
            "vector_store": "pending"  # placeholder until retrieval implemented
        }
    }
    return payload

@app.get("/health")
def health():
    return build_health_payload()


@app.get("/metrics")
def metrics():
    data = generate_latest()
    return PlainTextResponse(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

@app.post("/predict", response_model=PredictResponse, dependencies=[Depends(require_api_key)])
def predict(req: PredictRequest):
    start = perf_counter()
    try:
        rr: RagResult = answer_query(req.query, {"user_id": req.user_id, "tool_name": req.tool_name})
        latency_ms = int((perf_counter() - start) * 1000)
        resp = PredictResponse(
            prediction={
                "answer": rr.answer,
                "citations": rr.citations,
                "confidence": rr.confidence,
                "failure_mode": rr.failure_mode,
            },
            latency_ms=latency_ms,
            model_version=app.version
        )
        HTTP_REQUESTS.labels(path="/predict", method="POST", status="200").inc()
        HTTP_LATENCY.observe(latency_ms)
        # RAG decision classification
        decision = "answer"
        if rr.failure_mode == "refuse":
            decision = "refuse"
            RAG_REFUSALS.inc()
        elif rr.failure_mode == "low_confidence":
            decision = "low_confidence"
            RAG_LOW_CONF.inc()
        elif rr.failure_mode == "clarify":
            decision = "clarify"
        RAG_DECISIONS.labels(decision=decision, failure_mode=rr.failure_mode or "none").inc()
        # DB logging best-effort (non-blocking failures)
        db.log_inference(req.user_id, req.query, rr.answer, app.version, latency_ms, rr.failure_mode, rr.confidence)
        logger.info(with_request_id({
            "event": "predict_ok",
            "latency_ms": latency_ms,
            "model_version": app.version,
            "user_id": req.user_id,
            "tool_name": req.tool_name
        }))
        return resp
    except Exception as e:
        HTTP_REQUESTS.labels(path="/predict", method="POST", status="500").inc()
        logger.exception("predict_failed")
        raise HTTPException(status_code=500, detail=str(e))
