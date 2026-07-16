import saengiHead from './assets/saengi-head.png'
import myeongiHead from './assets/myeongi-head.png'
import duoImg from './assets/saengi-myeongi.png'

function Mascot({ variant = 'saeng', size = 48, animated = false, className = '' }) {
  const src = variant === 'myeong' ? myeongiHead : saengiHead
  const alt = variant === 'myeong' ? '명이' : '생이'
  const classes = ['mascot', animated ? 'mascot-bounce' : '', className].filter(Boolean).join(' ')

  return (
    <img
      src={src}
      alt={alt}
      className={classes}
      style={{ width: size, height: size }}
    />
  )
}

export function MascotDuo({ className = '' }) {
  return <img src={duoImg} alt="생이와 명이" className={`mascot-duo ${className}`} />
}

export default Mascot
