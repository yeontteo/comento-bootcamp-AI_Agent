import json
import time
from pathlib import Path

from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from .loader import load_and_split_documents

PERSIST_DIR = Path(__file__).resolve().parent.parent / "chroma_db"
INDEX_STATE_PATH = PERSIST_DIR / "indexed_files.json"
COLLECTION_NAME = "cheongju_civil_docs"

# Gemini 임베딩 무료 티어는 분당 요청 한도가 낮아, 청크를 한 번에 모두 보내면
# RESOURCE_EXHAUSTED(429)가 발생한다. 작은 배치로 나누고 배치 사이에 대기한다.
EMBED_BATCH_SIZE = 10
EMBED_BATCH_DELAY_SEC = 8
EMBED_MAX_RETRIES = 5

_embeddings = None


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    return _embeddings


def _load_index_state() -> dict:
    if INDEX_STATE_PATH.exists():
        return json.loads(INDEX_STATE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_index_state(state: dict) -> None:
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _add_documents_with_backoff(vectorstore: Chroma, chunks: list) -> None:
    """무료 티어 분당 요청 한도를 넘지 않도록 작은 배치로 나눠 임베딩하고,
    429(RESOURCE_EXHAUSTED) 발생 시 대기 후 재시도한다."""
    total_batches = (len(chunks) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE

    for batch_idx in range(total_batches):
        start = batch_idx * EMBED_BATCH_SIZE
        batch = chunks[start : start + EMBED_BATCH_SIZE]

        for attempt in range(EMBED_MAX_RETRIES):
            try:
                vectorstore.add_documents(batch)
                break
            except Exception as e:
                is_rate_limited = "RESOURCE_EXHAUSTED" in str(e)
                if is_rate_limited and attempt < EMBED_MAX_RETRIES - 1:
                    wait = EMBED_BATCH_DELAY_SEC * (attempt + 1)
                    print(
                        f"[vectorstore] 배치 {batch_idx + 1}/{total_batches} 속도 제한, "
                        f"{wait}초 대기 후 재시도 ({attempt + 1}/{EMBED_MAX_RETRIES})"
                    )
                    time.sleep(wait)
                else:
                    raise

        print(f"[vectorstore] 배치 {batch_idx + 1}/{total_batches} 임베딩 완료")
        if batch_idx < total_batches - 1:
            time.sleep(EMBED_BATCH_DELAY_SEC)


def build_or_load_vectorstore():
    """ChromaDB를 영속 디렉터리에서 로드하고, manifest 기준으로 신규/변경된 문서만
    추가 임베딩한다. 문서가 많아질수록 매번 전체를 재임베딩하던 기존 방식보다
    비용·시간이 크게 줄어든다.
    """
    PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(PERSIST_DIR),
    )

    all_chunks, current_hashes = load_and_split_documents()
    indexed_state = _load_index_state()

    changed_files = [
        fname for fname, file_hash in current_hashes.items()
        if indexed_state.get(fname) != file_hash
    ]

    if changed_files:
        # 내용이 바뀐 파일은 기존 청크를 지우고 새로 임베딩해 중복을 방지한다
        for fname in changed_files:
            if fname in indexed_state:
                vectorstore.delete(where={"source_file": fname})

        new_chunks = [c for c in all_chunks if c.metadata["source_file"] in changed_files]
        print(f"[vectorstore] 신규/변경 문서 {len(changed_files)}건, 청크 {len(new_chunks)}개 임베딩 중...")
        _add_documents_with_backoff(vectorstore, new_chunks)

        indexed_state.update(current_hashes)
        _save_index_state(indexed_state)
    else:
        print("[vectorstore] 신규/변경 문서 없음. 기존 인덱스를 재사용합니다.")

    return vectorstore, all_chunks
