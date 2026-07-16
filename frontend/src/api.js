// 배포 환경에서는 프론트엔드가 백엔드와 같은 오리진에서 서빙되므로 빈 문자열(상대 경로)을 기본값으로 사용한다.
// 로컬에서 프론트/백엔드를 따로 띄울 때는 frontend/.env.development의 VITE_API_BASE_URL이 적용된다.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export async function sendMessage(sessionId, message) {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || '서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.')
  }

  return res.json()
}
