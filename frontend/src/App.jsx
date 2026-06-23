import { useState, useEffect } from 'react'
import Nav from './components/Nav'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import { fetchAuthStatus, getToken, clearToken } from './auth'

export default function App() {
  const [page, setPage] = useState('home')
  const [authRequired, setAuthRequired] = useState(false)
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)

  useEffect(() => {
    fetchAuthStatus().then(({ required }) => {
      setAuthRequired(required)
      if (!required) {
        setUser('gast')
      } else if (getToken()) {
        // Token present — assume valid until WS rejects it
        setUser('gebruiker')
      }
      setAuthLoading(false)
    })
  }, [])

  if (authLoading) return null

  if (authRequired && !user) {
    return <LoginPage onLogin={(u) => setUser(u)} />
  }

  const handleLogout = () => {
    clearToken()
    setUser(null)
  }

  return (
    <>
      <Nav page={page} setPage={setPage} user={user} onLogout={authRequired ? handleLogout : null} />
      <div className="page-wrap">
        {page === 'home' && <HomePage setPage={setPage} />}
        {page === 'chat' && <ChatPage setPage={setPage} />}
        {page === 'dashboard' && <DashboardPage setPage={setPage} />}
      </div>
      <MobileTabs page={page} setPage={setPage} />
    </>
  )
}

function MobileTabs({ page, setPage }) {
  return (
    <nav className="mobile-tabs">
      <MobileTabBtn icon="home" label="Home" id="home" page={page} setPage={setPage} />
      <MobileTabBtn icon="chat" label="Chat" id="chat" page={page} setPage={setPage} />
      <MobileTabBtn icon="dashboard" label="Dashboard" id="dashboard" page={page} setPage={setPage} />
    </nav>
  )
}

function MobileTabBtn({ icon, label, id, page, setPage }) {
  const icons = {
    home: <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />,
    chat: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
    dashboard: <><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /></>,
  }
  return (
    <button className={`mobile-tab-btn${page === id ? ' active' : ''}`} onClick={() => setPage(id)}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        {icons[icon]}
      </svg>
      {label}
    </button>
  )
}
