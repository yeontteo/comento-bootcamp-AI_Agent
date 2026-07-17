# LLM 기반 청주시청 종합 정보 제공 서비스 AI 시스템

RFP 기획(React + FastAPI + ChromaDB + LLM API)을 기준으로 3주차에 실제 아키텍처를 전환한 버전입니다.

## 아키텍처 변화

| 구분 | 1주차 기획 | 2주차 실습(legacy_week2/) | 3주차 구현(현재) |
| --- | --- | --- | --- |
| 프론트엔드 | React 챗봇 위젯 | Streamlit (업로드+채팅 결합) | **React (Vite)** |
| 백엔드 | FastAPI | Streamlit 내부 함수 호출 | **FastAPI** |
| 벡터 DB | ChromaDB | FAISS (세션마다 재생성) | **ChromaDB (영속, 증분 임베딩)** |
| LLM/임베딩 | GPT-4o / Claude | OpenAI (GPT-4o + Embeddings) | **Google Gemini (gemini-3.5-flash + gemini-embedding-001)** — 무료 티어 사용 |
| 검색 방식 | 명시 안 됨 | 벡터 유사도 단독 | **벡터 + BM25 Hybrid Search** |
| 대화 | 단발성 질문 | 단발성 질문 | **세션별 멀티턴 히스토리** |
| 출처 표시 | 명시 안 됨 | 없음 | **부서·문서유형·페이지 표시** |

2주차 실습에서 검증한 RAG 파이프라인 원리(문서 로드→분할→임베딩→검색→프롬프트→생성)와 파라미터 실험 결과(`chunk_size=1000`, `overlap=500`, `k=5`)는 그대로 이어받았습니다.

카카오톡 채널 연동, 이중 인증, 동시 접속자 500명 이상, TLS 종단 설정, 로그인 기반 관리자 대시보드는 이번 프로토타입 범위 밖이며, 1주차 기획의 "향후 구현" 과제로 남아 있습니다.

## 디렉터리 구조

```
backend/
  main.py            # FastAPI 앱: /health, /chat
  rag/
    loader.py          # PDF 로드·분할, 부서/문서유형/페이지 메타데이터 태깅
    vectorstore.py      # ChromaDB 영속화, 신규/변경 문서만 증분 임베딩
    chain.py             # Hybrid Search 리트리버 + 멀티턴 RAG 체인
  data/
    manifest.json         # 문서별 부서/문서유형 메타데이터 등록
    cheongju_civil_docs.pdf
  chroma_db/             # 벡터 인덱스 영속 저장소 (자동 생성, git 제외)
frontend/
  src/App.jsx           # 랜딩/채팅 화면 전환 라우터
  src/LandingScreen.jsx    # 첫 화면
  src/ChatScreen.jsx       # 채팅 UI (세션 유지, 출처 표시, 단계별 로딩 문구)
  src/api.js              # 백엔드 /chat 호출
legacy_week2/            # 2주차 Streamlit+FAISS 프로토타입 (비교 참고용 보존)
```

저장소 루트의 `*.pptx`, `*.png`는 과제 제출용 원본 자료로, 앱 실행에는 사용되지 않습니다. (기존에 함께 있던 중복 PDF는 `backend/data/cheongju_civil_docs.pdf`와 동일해 삭제했습니다.)

## 실행 방법

### 1. Google API 키 발급

https://aistudio.google.com/apikey 에서 무료로 발급받아 `.env`의 `GOOGLE_API_KEY`에 입력합니다.

### 2. 백엔드 실행

```
cd backend
python -m venv ../venv        # 최초 1회
..\venv\Scripts\activate
pip install -r requirements.txt   # 최초 1회
uvicorn main:app --reload --port 8000
```

첫 실행 시 `data/manifest.json`에 등록된 문서를 임베딩해 `chroma_db/`에 저장합니다. 이후 실행부터는 내용이 바뀌지 않은 문서는 재임베딩하지 않습니다.

### 3. 프론트엔드 실행

```
cd frontend
npm install   # 최초 1회
npm run dev
```

`http://localhost:5173` 접속. 로컬 개발 시 기본 백엔드 주소(`http://localhost:8000`)는 저장소에 커밋된 `frontend/.env.development`에 설정되어 있으며, 다른 주소를 쓰려면 이 파일을 수정하거나 `frontend/.env.local`을 새로 만들어 `VITE_API_BASE_URL`을 재정의합니다.

## 문서 추가 방법

1. `backend/data/`에 PDF를 추가합니다.
2. `backend/data/manifest.json`에 `{"filename": "...", "department": "...", "doc_type": "..."}` 항목을 추가합니다.
3. 백엔드를 재시작하면 새 문서만 자동으로 임베딩됩니다.

## 보안 메모

- `.env`는 `.gitignore`에 포함되어 있으며 절대 커밋하지 않습니다.
- 기존에 사용하던 OpenAI API 키는 더 이상 쓰지 않으므로 [OpenAI 대시보드](https://platform.openai.com/api-keys)에서 재발급/폐기를 권장합니다.
- 배포 환경에서는 `.env` 대신 클라우드 시크릿 매니저(예: GCP Secret Manager) 사용을 권장합니다.

## 알려진 한계 (향후 개선 과제)

- 대화 히스토리는 프로세스 메모리에만 보관되어 서버 재시작 시 초기화됩니다. 영속화가 필요하면 세션 저장소(SQLite/Redis)로 교체해야 합니다.
- 문서가 대량으로 늘어날 경우 부서별 인덱스 분리, 문서 유형별 chunk_size/overlap 튜닝을 고려해야 합니다.
- 관리자 대시보드(질문 로그·응답률·만족도 통계)는 아직 구현되지 않았습니다.
