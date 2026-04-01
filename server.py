from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from llama_index.core import StorageContext, load_index_from_storage
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import Settings
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
import os
import logging
import time
import json

load_dotenv()

VEL_API_KEY = os.getenv("VEL_API_KEY")
security = HTTPBearer()

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Vel")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

def verify_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != VEL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials

MODEL_NAME = os.getenv("MODEL_NAME", "mistral")
PERSIST_DIR = os.getenv("PERSIST_DIR", "./storage")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300.0"))

query_logger = logging.getLogger("vel.queries")
query_logger.setLevel(logging.INFO)
handler = logging.FileHandler("query.log")
handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
query_logger.addHandler(handler)

Settings.llm = Ollama(model=MODEL_NAME, request_timeout=REQUEST_TIMEOUT)
Settings.embed_model = OllamaEmbedding(model_name=MODEL_NAME)

storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
index = load_index_from_storage(storage_context)
query_engine = index.as_query_engine(streaming=True)

app = FastAPI(title="Vel")

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

@app.get("/stats", dependencies=[Depends(verify_key)])
async def stats():
    try:
        with open("query.log") as f:
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
async def chat(request: dict):
    start = time.time()
    message = request["messages"][-1]["content"]
    stream = request.get("stream", False)

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
