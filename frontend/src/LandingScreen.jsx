import { MascotDuo } from './Mascot'
import './LandingScreen.css'

function LandingScreen({ onStart }) {
  return (
    <div className="landing">
      <div className="landing-card">
        <MascotDuo className="landing-mascot" />
        <h1 className="landing-title">안녕하세요, 생이·명이예요!</h1>
        <p className="landing-subtitle">
          청주시 민원·서류·행정 절차를 무엇이든 편하게 물어보세요.
          <br />
          궁금한 걸 대화하듯 물어보면 생이·명이가 알려드릴게요.
        </p>
        <button type="button" className="landing-cta" onClick={onStart}>
          대화 시작하기 →
        </button>
        <p className="landing-disclaimer">
          AI가 생성한 답변은 참고용입니다. 정확한 안내는 청주시청(☎ 043-200-2000)으로 문의해 주세요.
        </p>
      </div>
    </div>
  )
}

export default LandingScreen
