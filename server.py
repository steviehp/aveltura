from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from llama_index.core import StorageContext, load_index_from_storage
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv
import os
import logging
import time
import json

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "mistral")
PERSIST_DIR = os.getenv("PERSIST_DIR", "./storage")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300.0"))
VEL_API_KEY = os.getenv("VEL_API_KEY")
BASE_DIR = os.getenv("BASE_DIR", "/home/_homeos/engine-analysis")

query_logger = logging.getLogger("vel.queries")
query_logger.setLevel(logging.INFO)
handler = logging.FileHandler(os.path.join(BASE_DIR, "query.log"))
handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
query_logger.addHandler(handler)

Settings.llm = Ollama(model=MODEL_NAME, request_timeout=REQUEST_TIMEOUT)
Settings.embed_model = OllamaEmbedding(model_name=MODEL_NAME)

storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
index = load_index_from_storage(storage_context)
query_engine = index.as_query_engine(streaming=True)

security = HTTPBearer()
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Vel")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

def verify_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != VEL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials

class Query(BaseModel):
    message: str

@app.post("/query", dependencies=[Depends(verify_key)])
@limiter.limit("10/minute")
async def query(request: Request, q: Query):
    start = time.time()
    response = query_engine.query(q.message)
    result = ""
    for token in response.response_gen:
        result += token
    elapsed = round(time.time() - start, 2)
    query_logger.info(f"Q: {q.message} | T: {elapsed}s")
    return {"response": result, "response_time": elapsed}

@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME}

@app.get("/stats")
async def stats():
    try:
        with open(os.path.join(BASE_DIR, "query.log")) as f:
            lines = f.readlines()
        return {
            "total_queries": len(lines),
            "last_query": lines[-1].strip() if lines else "none"
        }
    except:
        return {"total_queries": 0, "last_query": "none"}

@app.get("/v1/models")
async def models():
    return {
        "data": [
            {
                "id": "vel",
                "object": "model",
                "owned_by": "aveltura"
            }
        ]
    }

@app.post("/v1/chat/completions", dependencies=[Depends(verify_key)])
@limiter.limit("10/minute")
async def chat(request: Request, request_body: dict):
    start = time.time()
    message = request_body["messages"][-1]["content"]
    stream = request_body.get("stream", False)

    if stream:
        def generate():
            response = query_engine.query(message)
            for token in response.response_gen:
                chunk = {
                    "choices": [
                        {
                            "delta": {"content": token},
                            "finish_reason": None
                        }
                    ]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
            elapsed = round(time.time() - start, 2)
            query_logger.info(f"Q: {message} | T: {elapsed}s")

        return StreamingResponse(generate(), media_type="text/event-stream")

    response = query_engine.query(message)
    result = ""
    for token in response.response_gen:
        result += token
    elapsed = round(time.time() - start, 2)
    query_logger.info(f"Q: {message} | T: {elapsed}s")
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": result
                }
            }
        ]
    }

@app.get("/stats/specs")
async def stats_specs():
    from stats_engine import available_specs
    return {"specs": available_specs()}

@app.post("/stats/correlation", dependencies=[Depends(verify_key)])
async def stats_correlation(request: dict):
    from stats_engine import correlation_analysis
    spec1 = request.get("spec1")
    spec2 = request.get("spec2")
    return correlation_analysis(spec1, spec2)

@app.post("/stats/outliers", dependencies=[Depends(verify_key)])
async def stats_outliers(request: dict):
    from stats_engine import outlier_detection
    spec = request.get("spec")
    return outlier_detection(spec)

@app.post("/stats/summary", dependencies=[Depends(verify_key)])
async def stats_summary(request: dict):
    from stats_engine import summary_stats
    spec = request.get("spec")
    return summary_stats(spec)

@app.post("/stats/regression", dependencies=[Depends(verify_key)])
async def stats_regression(request: dict):
    from stats_engine import regression_analysis
    target = request.get("target")
    predictors = request.get("predictors", [])
    return regression_analysis(target, predictors)
