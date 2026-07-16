import hashlib
import json
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"

# 2주차 파라미터 실험(chunk_size 400/1000, overlap 100/500/950, k 3/5)에서
# 검증된 값(chunk_size=1000, overlap=500)을 그대로 이어감
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 500


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest() -> list[dict]:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_and_split_documents():
    """manifest.json에 등록된 문서를 모두 로드·분할하고, 부서/문서유형/페이지/파일해시를
    메타데이터로 붙여 반환한다. (source_file, file_hash는 증분 임베딩 판단에 사용)
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )

    all_chunks = []
    file_hashes: dict[str, str] = {}

    for entry in load_manifest():
        path = DATA_DIR / entry["filename"]
        if not path.exists():
            print(f"[loader] 경고: {path} 파일이 없어 건너뜁니다.")
            continue

        file_hash = _file_hash(path)
        file_hashes[entry["filename"]] = file_hash

        try:
            docs = PyMuPDFLoader(str(path)).load()
        except Exception as e:
            print(f"[loader] 경고: {path} 로드 실패 ({e}), 건너뜁니다.")
            continue

        chunks = splitter.split_documents(docs)
        for chunk in chunks:
            chunk.metadata.update(
                {
                    "department": entry.get("department", "미분류"),
                    "doc_type": entry.get("doc_type", "미분류"),
                    "source_file": entry["filename"],
                    "file_hash": file_hash,
                    # PyMuPDFLoader의 page는 0-base이므로 1-base로 보정
                    "page": chunk.metadata.get("page", 0) + 1,
                }
            )
        all_chunks.extend(chunks)

    return all_chunks, file_hashes
