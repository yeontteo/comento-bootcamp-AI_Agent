import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rag.chain import RAGService, build_retriever
from rag.vectorstore import build_or_load_vectorstore

load_dotenv()

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
STATIC_DIR = Path(__file__).resolve().parent / "static"

_state: dict[str, RAGService | None] = {"rag_service": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key.startswith("여기에"):
        print(
            "[main] 경고: GOOGLE_API_KEY가 설정되지 않았습니다. "
            "https://aistudio.google.com/apikey 에서 발급받아 .env에 입력하세요. "
            "/chat 호출 시 오류가 발생합니다."
        )
    else:
        vectorstore, all_chunks = build_or_load_vectorstore()
        retriever = build_retriever(vectorstore, all_chunks)
        _state["rag_service"] = RAGService(retriever)
    yield


app = FastAPI(title="청주시청 종합 정보 제공 서비스 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str
    message: str


class Source(BaseModel):
    department: str
    doc_type: str
    source_file: str | None = None
    page: int | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]


@app.get("/health")
def health():
    return {"status": "ok", "rag_ready": _state["rag_service"] is not None}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="메시지를 입력해 주세요.")

    rag_service = _state["rag_service"]
    if rag_service is None:
        raise HTTPException(
            status_code=503,
            detail="서비스가 아직 준비되지 않았습니다. GOOGLE_API_KEY 설정을 확인하고 서버를 재시작해 주세요.",
        )

    return rag_service.ask(req.session_id, req.message)


# 프론트엔드 빌드 결과물(frontend/dist)이 배포 시 이 경로로 복사되어 들어온다.
# 위에서 정의한 /health, /chat 라우트가 먼저 매칭되고, 나머지 경로는 정적 파일로 서빙된다.
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
