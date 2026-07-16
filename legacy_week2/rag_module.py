import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# .env 파일에 저장된 API 키 로드
load_dotenv()

def create_rag_chain(pdf_path):
    # [1단계] 문서 로드 (Document Load)
    loader = PyMuPDFLoader(pdf_path)
    docs = loader.load()

    # [2단계] 문서 분할 (Text Split)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,         # 청크 사이즈 조절
        chunk_overlap=500,      # 오버랩 조절
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    split_documents = text_splitter.split_documents(docs)

    # [3~4단계] 임베딩 및 벡터 DB 저장 (Embedding & Vector DB)
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(documents=split_documents, embedding=embeddings)
    
    # [디버깅 메모] 아래 for문은 테스트 용도이므로 실제 함수 흐름에서는 생략하거나 pass 처리해야 함
    # for doc in vectorstore.similarity_search("투자"):
    #     print(doc.page_content) 

    # [5단계] 검색기(Retriever) 생성
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5}
    )

    # [6~7단계] 프롬프트 및 LLM 설정 (Prompt & LLM)
    template = """당신은 청주시청 종합 정보 제공 서비스의 AI 상담원입니다.
시민들이 민원, 서류, 행정 절차에 대해 편하게 질문할 수 있도록 친절하고 정확하게 안내하는 것이 당신의 역할입니다.

아래 [참고 문서]를 바탕으로 질문에 답변하세요. 답변할 때는 다음 순서로 생각하세요:
1. 질문에서 시민이 실제로 알고 싶어하는 핵심이 무엇인지 파악합니다.
2. [참고 문서]에서 관련된 내용을 찾습니다.
3. 찾은 내용을 바탕으로 명확하고 친절한 답변을 작성합니다.

[답변 규칙]
- 반드시 [참고 문서]에 있는 내용만을 근거로 답변하세요. 문서에 없는 내용을 추측하거나 지어내지 마세요.
- 필요한 서류나 절차는 번호 목록(1, 2, 3...)으로 정리해서 안내하세요.
- 전문 용어가 나오면 간단히 풀어서 설명하세요.
- 만약 [참고 문서]에서 질문에 대한 답을 찾을 수 없다면, "죄송합니다. 해당 내용은 제공된 자료에서 확인이 어렵습니다. 정확한 안내를 위해 청주시청 관련 부서(☎ 043-200-2000) 또는 정부24(www.gov.kr)를 통해 문의해 주세요." 라고 답변하세요.
- 답변은 한국어로, 존댓말로 작성하세요.

[참고 문서]
{context}

[시민 질문]
{question}

[답변]"""
    
    prompt = ChatPromptTemplate.from_template(template)
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0)

    # [8단계] 체인 생성 (Chain)
    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain