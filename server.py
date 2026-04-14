"""
server.py — Vel API

Endpoints:
  POST /query                  — RAG query (Vel native)
  POST /v1/chat/completions    — OpenAI-compatible chat (streaming supported)
  GET  /health                 — Health check
  GET  /stats                  — Query log stats
  GET  /v1/models              — Model list (OpenAI compat)
  POST /reload                 — Hot-reload RAG index after pipeline run
  POST /optimize               — Physics-based mod optimization
  GET  /viz/list               — List available charts
  POST /viz/scatter            — Generate scatter plot
  POST /viz/bar                — Generate bar chart
  POST /viz/histogram          — Generate histogram
  POST /viz/heatmap            — Generate correlation heatmap
  POST /viz/compare            — Compare specific engines
  GET  /stats/specs            — List available numeric specs
  POST /stats/correlation      — Pearson correlation between two specs
  POST /stats/outliers         — Outlier detection for a spec
  POST /stats/summary          — Summary statistics for a spec
  POST /stats/regression       — OLS regression
  GET  /reports                — List generated analysis reports
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Any
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

from llama_index.core import StorageContext, load_index_from_storage, Settings
from llama_index.core.prompts import PromptTemplate
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

import os
import logging
from datetime import datetime
import time
import json

load_dotenv()

MODEL_NAME      = os.getenv("MODEL_NAME",      "mistral")
EMBED_MODEL     = os.getenv("EMBED_MODEL",     "nomic-embed-text")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300.0"))
VEL_API_KEY     = os.getenv("VEL_API_KEY")
BASE_DIR        = os.getenv("BASE_DIR",        "/home/_homeos/engine-analysis")
VEL_PORT        = os.getenv("VEL_PORT",        "8001")

# ── PERSIST_DIR ───────────────────────────────────────────────────────────────
PERSIST_DIR     = os.getenv("PERSIST_DIR", os.path.join(BASE_DIR, "storage"))
DISCOVERY_QUEUE = os.path.join(BASE_DIR, "discovery_queue.txt")

# ── LlamaIndex settings ───────────────────────────────────────────────────────
Settings.llm         = Ollama(model=MODEL_NAME, request_timeout=REQUEST_TIMEOUT)
Settings.embed_model = OllamaEmbedding(model_name=EMBED_MODEL)

import sys
sys.path.insert(0, BASE_DIR)
from rag import build_hybrid_query_engine

# ── Vel QA prompt ─────────────────────────────────────────────────────────────
VEL_QA_PROMPT = PromptTemplate(
    "You are Vel, a precise automotive engine analysis AI.\n\n"
    "Context from the Vel database:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n\n"
    "Rules:\n"
    "1. Answer ONLY using data from the context above. No exceptions.\n"
    "2. Do NOT speculate, hedge, or add information from outside the context.\n"
    "3. Be concise — 1-3 sentences maximum.\n"
    "4. State the confidence level (verified_manual, epa_verified, wikipedia_scraped) when relevant.\n"
    "5. If the context lacks the answer, say only: 'No verified data available.'\n"
    "6. Forbidden words: possibly, potentially, likely, may, might, some other, also used in, known to be.\n"
    "7. List ONLY the exact vehicles named in the context. Nothing else.\n\n"
    "Question: {query_str}\n"
    "Answer:"
)

# ── Logging ───────────────────────────────────────────────────────────────────
query_logger = logging.getLogger("vel.queries")
query_logger.setLevel(logging.INFO)
_handler = logging.FileHandler(os.path.join(BASE_DIR, "query.log"))
_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
query_logger.addHandler(_handler)

# ── Discovery queue ───────────────────────────────────────────────────────────

def add_to_discovery_queue(query: str):
    try:
        with open(DISCOVERY_QUEUE, "a") as f:
            f.write(f"{datetime.now().isoformat()} | {query}\n")
        logging.info(f"Added to discovery queue: {query}")
    except Exception as e:
        logging.error(f"Could not write to discovery queue: {e}")


def response_flags_unknown(text: str) -> bool:
    signals = [
        "discovery queue",
        "don't have verified data",
        "adding it to the discovery",
        "no verified data available",
    ]
    return any(s in text.lower() for s in signals)


# ── Tabular data detector ─────────────────────────────────────────────────────

def _looks_like_tabular(text: str) -> bool:
    """Return True if message looks like CSV/TSV tabular data."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if len(lines) < 3:
        return False
    for delim in [",", "\t", ";", "|"]:
        counts = [line.count(delim) for line in lines[:6]]
        if len(set(counts)) <= 2 and counts[0] >= 2 and counts[0] == counts[1]:
            return True
    return False


# ── Index loader ──────────────────────────────────────────────────────────────

def _load_index():
    """Load the RAG index from PERSIST_DIR. Returns (index, query_engine)."""
    if not os.path.exists(PERSIST_DIR):
        raise RuntimeError(
            f"No index found at {PERSIST_DIR} — run rag.py first"
        )
    storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
    idx = load_index_from_storage(storage_context)
    qe  = build_hybrid_query_engine(idx, streaming=True)
    return idx, qe


try:
    index, query_engine = _load_index()
    logging.info(f"Index loaded from {PERSIST_DIR}")
except Exception as e:
    logging.error(f"Failed to load index at startup: {e}")
    index        = None
    query_engine = None


# ── FastAPI app ───────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)
app     = FastAPI(title="Vel — Engine Analysis API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount charts
_charts_dir = os.path.join(BASE_DIR, "charts")
if os.path.exists(_charts_dir):
    app.mount("/charts", StaticFiles(directory=_charts_dir), name="charts")
else:
    logging.warning(f"Charts directory not found at {_charts_dir}")

# Mount reports
_reports_dir = os.path.join(BASE_DIR, "reports")
os.makedirs(_reports_dir, exist_ok=True)
app.mount("/reports", StaticFiles(directory=_reports_dir), name="reports")


# ── Auth ──────────────────────────────────────────────────────────────────────

security = HTTPBearer()

def verify_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not VEL_API_KEY:
        raise HTTPException(status_code=500, detail="VEL_API_KEY not configured")
    if credentials.credentials != VEL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials

def require_index():
    if query_engine is None:
        raise HTTPException(
            status_code=503,
            detail="RAG index not loaded — run rag.py then POST /reload"
        )


# ── Pydantic models ───────────────────────────────────────────────────────────

class Query(BaseModel):
    message: str

class ChatMessage(BaseModel):
    role:    str
    content: Any  # Any to handle both str and list (multipart)

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream:   Optional[bool] = False
    model:    Optional[str]  = "vel"

class SpecRequest(BaseModel):
    spec: str

class CorrelationRequest(BaseModel):
    spec1: str
    spec2: str

class RegressionRequest(BaseModel):
    target:     str
    predictors: List[str] = []

class ScatterRequest(BaseModel):
    x:     str
    y:     str
    title: Optional[str] = None

class BarRequest(BaseModel):
    spec:  str
    top_n: Optional[int]  = 15
    title: Optional[str]  = None

class HistogramRequest(BaseModel):
    spec:  str
    title: Optional[str] = None

class CompareRequest(BaseModel):
    engines: List[str]
    spec:    str

class OptimizeRequest(BaseModel):
    query:      str
    budget_usd: Optional[int] = None


# ── Core query endpoints ──────────────────────────────────────────────────────

@app.post("/query", dependencies=[Depends(verify_key), Depends(require_index)])
@limiter.limit("10/minute")
async def query(request: Request, q: Query):
    start    = time.time()
    response = query_engine.query(q.message)
    result   = ""
    for token in response.response_gen:
        result += token
    elapsed = round(time.time() - start, 2)
    query_logger.info(f"Q: {q.message} | T: {elapsed}s")
    if response_flags_unknown(result):
        add_to_discovery_queue(q.message)
    return {"response": result, "response_time": elapsed}


@app.post(
    "/v1/chat/completions",
    dependencies=[Depends(verify_key), Depends(require_index)],
)
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest):
    start = time.time()

    # Extract text from last message (handles str and multipart list)
    raw = body.messages[-1].content
    if isinstance(raw, list):
        message = " ".join(
            p.get("text", "") for p in raw
            if isinstance(p, dict) and p.get("type") == "text"
        )
    else:
        message = str(raw)

    # Route tabular data to universal analyzer
    if _looks_like_tabular(message):
        try:
            from universal_analyzer import analyze as run_analyze
            summary, report_path = run_analyze(message, vel_port=VEL_PORT)
        except Exception as e:
            summary = f"Analysis error: {e}"

        if body.stream:
            def gen_analyze():
                for line in summary.split("\n"):
                    chunk = {
                        "choices": [
                            {"delta": {"content": line + "\n"}, "finish_reason": None}
                        ]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(gen_analyze(), media_type="text/event-stream")

        return {
            "choices": [
                {"message": {"role": "assistant", "content": summary}}
            ]
        }

    # Normal RAG query
    if body.stream:
        def generate():
            resp = query_engine.query(message)
            for token in resp.response_gen:
                chunk = {
                    "choices": [
                        {"delta": {"content": token}, "finish_reason": None}
                    ]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
            elapsed = round(time.time() - start, 2)
            query_logger.info(f"Q: {message} | T: {elapsed}s | stream=true")

        return StreamingResponse(generate(), media_type="text/event-stream")

    response = query_engine.query(message)
    result   = ""
    for token in response.response_gen:
        result += token
    elapsed = round(time.time() - start, 2)
    query_logger.info(f"Q: {message} | T: {elapsed}s")
    if response_flags_unknown(result):
        add_to_discovery_queue(message)
    return {
        "choices": [
            {"message": {"role": "assistant", "content": result}}
        ]
    }


# ── Index reload ──────────────────────────────────────────────────────────────

@app.post("/reload", dependencies=[Depends(verify_key)])
async def reload_index():
    global index, query_engine
    try:
        index, query_engine = _load_index()
        logging.info("Index reloaded via /reload")
        return {"status": "ok", "message": f"Index reloaded from {PERSIST_DIR}"}
    except Exception as e:
        logging.error(f"Reload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")


# ── Info endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status":       "ok",
        "model":        MODEL_NAME,
        "index_loaded": query_engine is not None,
        "persist_dir":  PERSIST_DIR,
    }


@app.get("/stats")
async def stats():
    log_path = os.path.join(BASE_DIR, "query.log")
    try:
        with open(log_path) as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        return {
            "total_queries": len(lines),
            "last_query":    lines[-1] if lines else "none",
        }
    except FileNotFoundError:
        return {"total_queries": 0, "last_query": "none"}
    except Exception as e:
        return {"total_queries": 0, "last_query": "none", "error": str(e)}


@app.get("/v1/models")
async def models():
    return {
        "data": [
            {"id": "vel", "object": "model", "owned_by": "aveltura"}
        ]
    }


# ── Optimization endpoint ─────────────────────────────────────────────────────

@app.post("/optimize", dependencies=[Depends(verify_key)])
@limiter.limit("5/minute")
async def optimize(request: Request, body: OptimizeRequest):
    from optimization_engine import optimize as run_optimize
    result = run_optimize(body.query, body.budget_usd)
    return {"plan": result}


# ── Reports endpoint ──────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    type:       str   # "optimization" | "spec" | "analysis"
    query:      Optional[str] = None
    car_name:   Optional[str] = None
    engine_name:Optional[str] = None

@app.post("/report", dependencies=[Depends(verify_key)])
async def generate_report(body: ReportRequest):
    from report_generator import generate_optimization_report, generate_vehicle_spec_report
    if body.type == "optimization" and body.query:
        from optimization_engine import optimize, load_car_specs, solve_performance_build, extract_car_from_query, extract_engine_from_query, detect_goal_type
        car    = extract_car_from_query(body.query)
        engine = extract_engine_from_query(body.query)
        specs  = load_car_specs(car, engine)
        goal_type, target = detect_goal_type(body.query)
        if goal_type == "performance" and target:
            plan = solve_performance_build(specs, target)
            pdf_path, err = generate_optimization_report(plan, car or "")
            if err:
                raise HTTPException(status_code=500, detail=err)
            report_id = os.path.basename(pdf_path)
            return {"report_url": f"http://100.104.58.38:{VEL_PORT}/reports/{report_id}", "path": pdf_path}
    raise HTTPException(status_code=400, detail="Unsupported report type or missing parameters")

@app.get("/reports")
async def list_reports():
    try:
        reports = sorted(
            f for f in os.listdir(_reports_dir)
            if f.endswith("_report.html")
        )
        return {"reports": reports}
    except Exception as e:
        return {"reports": [], "error": str(e)}


# ── Stats endpoints ───────────────────────────────────────────────────────────

@app.get("/stats/specs")
async def stats_specs():
    from stats_engine import available_specs
    return {"specs": available_specs()}


@app.post("/stats/correlation", dependencies=[Depends(verify_key)])
async def stats_correlation(body: CorrelationRequest):
    from stats_engine import correlation_analysis
    return correlation_analysis(body.spec1, body.spec2)


@app.post("/stats/outliers", dependencies=[Depends(verify_key)])
async def stats_outliers(body: SpecRequest):
    from stats_engine import outlier_detection
    return outlier_detection(body.spec)


@app.post("/stats/summary", dependencies=[Depends(verify_key)])
async def stats_summary(body: SpecRequest):
    from stats_engine import summary_stats
    return summary_stats(body.spec)


@app.post("/stats/regression", dependencies=[Depends(verify_key)])
async def stats_regression(body: RegressionRequest):
    from stats_engine import regression_analysis
    return regression_analysis(body.target, body.predictors)


# ── Viz endpoints ─────────────────────────────────────────────────────────────

@app.get("/viz/list")
async def viz_list():
    if not os.path.exists(_charts_dir):
        return {"charts": []}
    charts = sorted(f for f in os.listdir(_charts_dir) if f.endswith(".html"))
    return {"charts": charts}


@app.post("/viz/scatter", dependencies=[Depends(verify_key)])
async def viz_scatter(body: ScatterRequest):
    from viz_engine import scatter_plot
    return scatter_plot(body.x, body.y, body.title)


@app.post("/viz/bar", dependencies=[Depends(verify_key)])
async def viz_bar(body: BarRequest):
    from viz_engine import bar_chart
    return bar_chart(body.spec, body.top_n, body.title)


@app.post("/viz/histogram", dependencies=[Depends(verify_key)])
async def viz_histogram(body: HistogramRequest):
    from viz_engine import histogram
    return histogram(body.spec, body.title)


@app.post("/viz/heatmap", dependencies=[Depends(verify_key)])
async def viz_heatmap():
    from viz_engine import correlation_heatmap
    return correlation_heatmap()


@app.post("/viz/compare", dependencies=[Depends(verify_key)])
async def viz_compare(body: CompareRequest):
    from viz_engine import compare_engines
    return compare_engines(body.engines, body.spec)
