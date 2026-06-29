import { useState, useEffect } from 'react'
import Nav from './components/Nav'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import SettingsModal from './components/SettingsModal'
import { fetchAuthStatus, getToken, clearToken } from './auth'
import { STORAGE_SETTINGS, STORAGE_ONBOARDED } from './constants'

const SETTINGS_KEY = STORAGE_SETTINGS
const ONBOARDED_KEY = STORAGE_ONBOARDED

function loadSettings() {
  try { return JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}') } catch { return {} }
}

function applyMode(mode) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const isDark = mode === 'dark' || (mode === 'system' && prefersDark)
  document.documentElement.classList.toggle('dark', isDark)
}

export default function App() {
  const [page, setPage] = useState('home')
  const [pendingWorkbookId, setPendingWorkbookId] = useState(null)

  const openDashboard = (workbookId) => {
    setPendingWorkbookId(workbookId ?? null)
    setPage('dashboard')
  }
  const [authRequired, setAuthRequired] = useState(false)
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [settings, setSettings] = useState(loadSettings)
  const [showSettings, setShowSettings] = useState(false)
  const [isOnboarding, setIsOnboarding] = useState(false)

  useEffect(() => { applyMode(settings.mode || 'system') }, [settings.mode])

  useEffect(() => {
    fetchAuthStatus().then(({ required }) => {
      setAuthRequired(required)
      if (!required) {
        setUser('gast')
      } else if (getToken()) {
        setUser('gebruiker')
      }
      setAuthLoading(false)
    })
  }, [])

  const handleLogin = (u) => {
    setUser(u)
    if (!localStorage.getItem(ONBOARDED_KEY)) {
      setIsOnboarding(true)
      setShowSettings(true)
    }
  }

  const handleSaveSettings = (newSettings) => {
    setSettings(newSettings)
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(newSettings))
    applyMode(newSettings.mode || 'system')
  }

  const handleCloseSettings = () => {
    localStorage.setItem(ONBOARDED_KEY, '1')
    setIsOnboarding(false)
    setShowSettings(false)
  }

  if (authLoading) return null

  if (authRequired && !user) {
    return <LoginPage onLogin={handleLogin} />
  }

  const handleLogout = () => {
    clearToken()
    setUser(null)
  }

  return (
    <>
      <Nav
        page={page} setPage={setPage} user={user}
        onLogout={authRequired ? handleLogout : null}
        onOpenSettings={() => { setIsOnboarding(false); setShowSettings(true) }}
        instelling={settings.instelling}
      />
      <div className="page-wrap">
        {page === 'home' && <HomePage setPage={setPage} />}
        {page === 'chat' && <ChatPage setPage={setPage} openDashboard={openDashboard} settings={settings} />}
        {page === 'dashboard' && (
          <DashboardPage
            setPage={setPage}
            settings={settings}
            pendingWorkbookId={pendingWorkbookId}
            clearPendingWorkbook={() => setPendingWorkbookId(null)}
          />
        )}
      </div>
      <MobileTabs page={page} setPage={setPage} />
      {showSettings && (
        <SettingsModal
          settings={settings}
          onSave={handleSaveSettings}
          onClose={handleCloseSettings}
          isOnboarding={isOnboarding}
        />
      )}
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
