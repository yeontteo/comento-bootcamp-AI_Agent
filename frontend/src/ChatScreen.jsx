import { useEffect, useRef, useState } from 'react'
import { sendMessage } from './api'
import Mascot from './Mascot'
import './ChatScreen.css'

const SESSION_KEY = 'cheongju-chat-session-id'

function getOrCreateSessionId() {
  let id = localStorage.getItem(SESSION_KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(SESSION_KEY, id)
  }
  return id
}

const LOADING_STAGES = ['관련 문서를 검색하고 있어요...', '답변을 작성하고 있어요...']

function SourceBadge({ source }) {
  const label = [source.department, source.doc_type, source.page ? `p.${source.page}` : null]
    .filter(Boolean)
    .join(' · ')
  return <span className="source-badge">{label}</span>
}

function ChatScreen({ onBack }) {
  const [sessionId] = useState(getOrCreateSessionId)
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        '안녕하세요! 생이·명이예요 :) 청주시 민원, 서류, 행정 절차에 대해 무엇이든 물어보세요.',
      sources: [],
    },
  ])
  const [input, setInput] = useState('')
  const [loadingStage, setLoadingStage] = useState(null)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loadingStage])

  const handleSubmit = async (e) => {
    e.preventDefault()
    const question = input.trim()
    if (!question || loadingStage) return

    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setInput('')
    setError(null)
    setLoadingStage(LOADING_STAGES[0])

    const stageTimer = setTimeout(() => setLoadingStage(LOADING_STAGES[1]), 1200)

    try {
      const data = await sendMessage(sessionId, question)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.answer, sources: data.sources || [] },
      ])
    } catch (err) {
      setError(err.message)
    } finally {
      clearTimeout(stageTimer)
      setLoadingStage(null)
    }
  }

  return (
    <div className="chat-app">
      <header className="chat-header">
        <button type="button" className="back-button" onClick={onBack} aria-label="처음으로">
          ←
        </button>
        <Mascot variant="saeng" size={38} />
        <div className="chat-header-text">
          <h1>청주시청 AI 상담원</h1>
          <p>생이·명이가 도와드릴게요</p>
        </div>
      </header>

      <main className="chat-window">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            {msg.role === 'assistant' && <Mascot variant="saeng" size={30} className="message-avatar" />}
            <div className="bubble">
              <p>{msg.content}</p>
              {msg.sources && msg.sources.length > 0 && (
                <div className="sources">
                  {msg.sources.map((s, i) => (
                    <SourceBadge key={i} source={s} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loadingStage && (
          <div className="message assistant">
            <Mascot variant="myeong" size={30} className="message-avatar" animated />
            <div className="bubble loading">{loadingStage}</div>
          </div>
        )}

        {error && <div className="error-banner">⚠ {error}</div>}

        <div ref={bottomRef} />
      </main>

      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="질문을 입력하세요 (예: 출생신고는 어떻게 하나요?)"
          disabled={Boolean(loadingStage)}
        />
        <button
          type="submit"
          className="send-button"
          disabled={Boolean(loadingStage) || !input.trim()}
          aria-label="전송"
        >
          ↑
        </button>
      </form>
    </div>
  )
}

export default ChatScreen
