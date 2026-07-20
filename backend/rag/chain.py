import time

from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

ANSWER_TEMPLATE = """당신은 청주시청 종합 정보 제공 서비스의 AI 상담원입니다.
시민들이 민원, 서류, 행정 절차에 대해 편하게 질문할 수 있도록 친절하고 정확하게 안내하는 것이 당신의 역할입니다.

아래 [참고 문서]를 바탕으로 질문에 답변하세요. 답변할 때는 다음 순서로 생각하세요:
1. 질문에서 시민이 실제로 알고 싶어하는 핵심이 무엇인지 파악합니다.
2. [참고 문서]에서 관련된 내용을 찾습니다.
3. 찾은 내용을 바탕으로 명확하고 친절한 답변을 작성합니다.

[답변 규칙]
- 반드시 [참고 문서]에 있는 내용만을 근거로 답변하세요. 문서에 없는 내용을 추측하거나 지어내지 마세요.
- 필요한 서류나 절차는 번호 목록(1, 2, 3...)으로 정리해서 안내하세요.
- 전문 용어가 나오면 간단히 풀어서 설명하세요.
- 답변 마지막 줄에 참고한 문서의 출처를 "(출처: 부서 · 문서유형 · p.페이지)" 형태로 간단히 덧붙이세요.
- 만약 [참고 문서]에서 질문에 대한 답을 찾을 수 없다면, "죄송합니다. 해당 내용은 제공된 자료에서 확인이 어렵습니다. 정확한 안내를 위해 청주시청 관련 부서(☎ 043-200-2000) 또는 정부24(www.gov.kr)를 통해 문의해 주세요." 라고 답변하세요.
- 답변은 한국어로, 존댓말로 작성하세요.

[참고 문서]
{context}

[시민 질문]
{question}

[답변]"""

CONTEXTUALIZE_TEMPLATE = """아래는 시민과 상담원의 이전 대화와 시민의 최신 질문입니다.
이전 대화 내용을 몰라도 이해할 수 있도록 최신 질문을 독립적인 하나의 질문으로 다시 작성하세요.
질문에 답하지 말고, 다시 작성된 질문만 출력하세요. 최신 질문이 이미 독립적이라면 그대로 반환하세요.

[이전 대화]
{chat_history}

[최신 질문]
{question}

[다시 작성된 질문]"""

FALLBACK_ANSWER = (
    "죄송합니다. 일시적인 오류로 답변을 생성하지 못했습니다. "
    "잠시 후 다시 시도해 주시거나, 청주시청 콜센터(☎ 043-200-2000)로 문의해 주세요."
)

RATE_LIMIT_ANSWER = (
    "죄송합니다. 지금 요청이 많아 답변이 지연되고 있습니다. 잠시 후 다시 시도해 주세요."
)

HISTORY_TURNS_KEPT = 3  # 컨텍스트 재구성에 사용할 최근 대화 턴 수

# vectorstore.py의 배치 임베딩 백오프와 같은 목적이지만, 실시간 채팅은 사용자가
# 화면 앞에서 기다리므로 재시도 횟수/대기 시간을 훨씬 짧게 둔다.
CHAT_MAX_RETRIES = 2
CHAT_RETRY_DELAY_SEC = 3


def _invoke_with_backoff(chain, inputs: dict):
    """Gemini 무료 티어 429(RESOURCE_EXHAUSTED)에 한해 짧게 재시도한다.
    그 외 예외는 재시도하지 않고 즉시 상위로 올린다."""
    for attempt in range(CHAT_MAX_RETRIES + 1):
        try:
            return chain.invoke(inputs)
        except Exception as e:
            is_rate_limited = "RESOURCE_EXHAUSTED" in str(e)
            if is_rate_limited and attempt < CHAT_MAX_RETRIES:
                wait = CHAT_RETRY_DELAY_SEC * (attempt + 1)
                print(f"[chain] 속도 제한, {wait}초 대기 후 재시도 ({attempt + 1}/{CHAT_MAX_RETRIES})")
                time.sleep(wait)
            else:
                raise


def build_retriever(vectorstore, all_chunks, k: int = 5) -> EnsembleRetriever:
    """벡터 유사도 검색과 BM25 키워드 검색을 결합한 Hybrid Search 리트리버.
    "제19호 양식"처럼 정확한 서식명·법령 용어가 중요한 문서 특성을 보완한다.
    """
    chroma_retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": k})

    bm25_retriever = BM25Retriever.from_documents(all_chunks)
    bm25_retriever.k = k

    return EnsembleRetriever(retrievers=[chroma_retriever, bm25_retriever], weights=[0.5, 0.5])


def _format_context(docs) -> str:
    parts = []
    for doc in docs:
        meta = doc.metadata
        label = f"[{meta.get('department', '미분류')} · {meta.get('doc_type', '미분류')} · p.{meta.get('page', '?')}]"
        parts.append(f"{label}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def _format_sources(docs) -> list[dict]:
    seen = set()
    sources = []
    for doc in docs:
        meta = doc.metadata
        key = (meta.get("source_file"), meta.get("page"))
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "department": meta.get("department", "미분류"),
                "doc_type": meta.get("doc_type", "미분류"),
                "source_file": meta.get("source_file"),
                "page": meta.get("page"),
            }
        )
    return sources


def _format_history(history: list) -> str:
    if not history:
        return "(이전 대화 없음)"
    lines = []
    for msg in history[-HISTORY_TURNS_KEPT * 2:]:
        role = "시민" if isinstance(msg, HumanMessage) else "상담원"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


class RAGService:
    """세션별 대화 이력을 기억하며 답변하는 RAG 서비스.
    이력은 프로세스 메모리에만 보관하므로 서버 재시작 시 초기화된다.
    """

    def __init__(self, retriever: EnsembleRetriever, model_name: str = "gemini-3.5-flash"):
        self.retriever = retriever
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        self.answer_chain = ChatPromptTemplate.from_template(ANSWER_TEMPLATE) | self.llm | StrOutputParser()
        self.contextualize_chain = (
            ChatPromptTemplate.from_template(CONTEXTUALIZE_TEMPLATE) | self.llm | StrOutputParser()
        )
        self._histories: dict[str, list] = {}

    def _get_history(self, session_id: str) -> list:
        return self._histories.setdefault(session_id, [])

    def ask(self, session_id: str, question: str) -> dict:
        history = self._get_history(session_id)

        try:
            if history:
                standalone_question = _invoke_with_backoff(
                    self.contextualize_chain,
                    {"chat_history": _format_history(history), "question": question},
                ).strip()
            else:
                standalone_question = question

            docs = self.retriever.invoke(standalone_question)
            answer = _invoke_with_backoff(
                self.answer_chain, {"context": _format_context(docs), "question": question}
            )
        except Exception as e:
            is_rate_limited = "RESOURCE_EXHAUSTED" in str(e)
            if is_rate_limited:
                print(f"[RAGService] 속도 제한으로 답변 생성 실패: {e}")
                return {"answer": RATE_LIMIT_ANSWER, "sources": []}
            print(f"[RAGService] 답변 생성 실패: {e}")
            return {"answer": FALLBACK_ANSWER, "sources": []}

        history.append(HumanMessage(content=question))
        history.append(AIMessage(content=answer))

        return {"answer": answer, "sources": _format_sources(docs)}
