import { useState } from 'react'
import LandingScreen from './LandingScreen'
import ChatScreen from './ChatScreen'

function App() {
  const [view, setView] = useState('landing')

  if (view === 'landing') {
    return <LandingScreen onStart={() => setView('chat')} />
  }

  return <ChatScreen onBack={() => setView('landing')} />
}

export default App
