import { Component, useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
import Nav from './components/Nav'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'
import DashboardPage from './pages/DashboardPage'
import RapportenPage from './pages/RapportenPage'
import LoginPage from './pages/LoginPage'
import SettingsModal from './components/SettingsModal'
import { fetchAuthStatus, getToken, clearToken, consumeTokenFromUrl, getStoredUserInfo, fetchUserInfo, refreshAuthToken } from './auth'
import { matchKnownInstelling } from './instellingenMatch'
import { STORAGE_SETTINGS, STORAGE_ONBOARDED, STORAGE_CONVERSATIONS, STORAGE_CURRENT_CHAT, STORAGE_WORKBOOKS } from './constants'

function loadSettings() {
  try { return JSON.parse(localStorage.getItem(STORAGE_SETTINGS) || '{}') } catch { return {} }
}

function applyMode(mode) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const isDark = mode === 'dark' || (mode === 'system' && prefersDark)
  document.documentElement.classList.toggle('dark', isDark)
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}

let _tokenRefreshTimer = null

function startTokenRefreshTimer(token) {
  // Decode token to get expiration time (format: payload.signature)
  try {
    const [payload] = token.split('.')
    const decoded = JSON.parse(atob(payload + '=='))  // Add padding for base64
    const [, expStr] = decoded.split('|')
    const expTime = parseInt(expStr) * 1000  // Convert to ms
    const now = Date.now()
    const timeUntilExp = expTime - now

    if (timeUntilExp > 0) {
      // Refresh 5 minutes before expiration
      const refreshTime = Math.max(60000, timeUntilExp - 5 * 60 * 1000)

      if (_tokenRefreshTimer) clearTimeout(_tokenRefreshTimer)
      _tokenRefreshTimer = setTimeout(async () => {
        try {
          const result = await refreshAuthToken(token)
          if (result) {
            startTokenRefreshTimer(result.newToken)
          }
        } catch (err) {
          console.warn('Token refresh failed:', err)
        }
      }, refreshTime)
    }
  } catch (err) {
    console.warn('Failed to decode token for refresh timer:', err)
  }
}

function AppShell() {
  const navigate = useNavigate()
  const location = useLocation()

  const [authRequired, setAuthRequired] = useState(false)
  const [oidcEnabled, setOidcEnabled] = useState(false)
  const [user, setUser] = useState(null)
  const [userInfo, setUserInfo] = useState(null)
  const [instellingen, setInstellingen] = useState([])
  const [authLoading, setAuthLoading] = useState(true)
  const [settings, setSettings] = useState(loadSettings)
  const [showSettings, setShowSettings] = useState(false)
  const [isOnboarding, setIsOnboarding] = useState(false)
  const [dashboardsEnabled, setDashboardsEnabled] = useState(true)

  useEffect(() => { applyMode(settings.mode || 'system') }, [settings.mode])

  useEffect(() => {
    // A token in the URL means we just landed here via the SRAM callback
    // redirect — a fresh login, same as the password form's handleLogin, so
    // it needs the same anonymous-session cache clear (see handleLogin).
    const result = consumeTokenFromUrl()
    const freshOidcLogin = result?.token

    Promise.all([
      fetchAuthStatus().then(async ({ required, oidc_enabled }) => {
        setAuthRequired(required)
        setOidcEnabled(!!oidc_enabled)

        if (!required) {
          setUser('gast')
          return
        }

        const token = getToken()
        if (!token) {
          return  // Not authenticated
        }

        // Fetch user info from server (SDP/OIDC only)
        // GitHub version (basic auth) will skip this and use localStorage
        try {
          const userInfo = await fetchUserInfo(token)
          if (userInfo) {
            setUserInfo(userInfo)
            setUser(userInfo.name || userInfo.username)
            // Start token refresh timer (refresh 5 min before expiration)
            startTokenRefreshTimer(token)
          } else {
            // Endpoint doesn't exist (GitHub version) or token is invalid
            // Fallback to localStorage if available
            const stored = getStoredUserInfo()
            if (stored) {
              setUserInfo(stored)
              setUser(stored.name || stored.username)
            } else {
              // GitHub version: just use token as username
              setUser(token ? 'user' : null)
            }
          }
        } catch (err) {
          console.warn('Failed to fetch user info (expected on GitHub version):', err)
          // Fallback: try localStorage (GitHub version path)
          const stored = getStoredUserInfo()
          if (stored) {
            setUserInfo(stored)
            setUser(stored.name || stored.username)
          } else {
            setUser(null)
          }
        }
      }),
      fetch('/api/config').then(r => r.json()).then(config => {
        setDashboardsEnabled(config.dashboards_enabled !== false)
      }).catch(() => {
        setDashboardsEnabled(true)
      }),
      fetch('/api/instellingen').then(r => r.json()).then(setInstellingen).catch(() => {})
    ]).then(() => {
      setAuthLoading(false)
    })
  }, [])

  const handleLogin = (u) => {
    // Clear any anonymous-session cache from this browser before the
    // conversations/workbooks pages mount and sync with the server — their
    // migrate-local-to-server logic otherwise can't tell "genuinely unsynced
    // local data" apart from "leftover data from whoever used this browser
    // before login", and would attribute it to the newly logged-in user.
    localStorage.removeItem(STORAGE_CONVERSATIONS)
    localStorage.removeItem(STORAGE_CURRENT_CHAT)
    localStorage.removeItem(STORAGE_WORKBOOKS)
    setUser(u)
    if (!localStorage.getItem(STORAGE_ONBOARDED)) {
      setIsOnboarding(true)
      setShowSettings(true)
    }
  }

  const handleSaveSettings = (newSettings) => {
    setSettings(newSettings)
    localStorage.setItem(STORAGE_SETTINGS, JSON.stringify(newSettings))
    applyMode(newSettings.mode || 'system')
  }

  const handleCloseSettings = () => {
    localStorage.setItem(STORAGE_ONBOARDED, '1')
    setIsOnboarding(false)
    setShowSettings(false)
  }

  const openRapport = (workbook) => {
    navigate('/rapporten', workbook ? { state: { pendingWorkbook: workbook } } : undefined)
  }

  if (authLoading) return null

  if (authRequired && !user) {
    return <LoginPage onLogin={handleLogin} oidcEnabled={oidcEnabled} />
  }

  const handleLogout = () => {
    clearToken()
    if (_tokenRefreshTimer) clearTimeout(_tokenRefreshTimer)
    localStorage.removeItem(STORAGE_CONVERSATIONS)
    localStorage.removeItem(STORAGE_CURRENT_CHAT)
    localStorage.removeItem(STORAGE_WORKBOOKS)
    setUser(null)
    setUserInfo(null)
  }

  // Only use the SRAM identity as instelling when it matches a known
  // instelling in the list we provide; otherwise ignore it so the user
  // picks (or keeps) their own value.
  const sramInstelling = userInfo ? matchKnownInstelling([userInfo.org, userInfo.institution, userInfo.email_domein, userInfo.email], instellingen) : null

  return (
    <>
      <Nav
        user={user}
        onLogout={authRequired ? handleLogout : null}
        onOpenSettings={() => { setIsOnboarding(false); setShowSettings(true) }}
        instelling={sramInstelling || settings.instelling}
        dashboardsEnabled={dashboardsEnabled}
      />
      <div className="page-wrap">
        <ErrorBoundary key={location.pathname}>
          <Routes>
            <Route path="/" element={<HomePage dashboardsEnabled={dashboardsEnabled} />} />
            <Route path="/chat" element={<ChatPage openRapport={openRapport} settings={settings} />} />
            {dashboardsEnabled && <Route path="/dashboards" element={<DashboardPage settings={settings} />} />}
            <Route path="/rapporten" element={<RapportenPage settings={settings} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ErrorBoundary>
      </div>
      <MobileTabs dashboardsEnabled={dashboardsEnabled} />
      {showSettings && (
        <SettingsModal
          settings={settings}
          onSave={handleSaveSettings}
          onClose={handleCloseSettings}
          isOnboarding={isOnboarding}
          sramName={userInfo?.name || null}
          sramInstelling={sramInstelling || null}
          sramIdentity={userInfo ? [userInfo.org, userInfo.institution, userInfo.email_domein].filter(Boolean) : []}
        />
      )}
    </>
  )
}

function MobileTabs({ dashboardsEnabled }) {
  return (
    <nav className="mobile-tabs">
      <MobileTabBtn icon="home" label="Home" to="/" />
      <MobileTabBtn icon="chat" label="Chat" to="/chat" />
      <MobileTabBtn icon="rapporten" label="Rapporten" to="/rapporten" />
      {dashboardsEnabled && <MobileTabBtn icon="dashboard" label="Dashboard" to="/dashboards" />}
    </nav>
  )
}

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError() { return { hasError: true } }
  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info?.componentStack)
  }
  render() {
    if (this.state.hasError) return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <p style={{ color: '#DC2626', marginBottom: 16 }}>Er is een onverwachte fout opgetreden.</p>
        <button type="button" style={{ marginRight: 8 }} onClick={() => this.setState({ hasError: false })}>Probeer opnieuw</button>
        <button type="button" onClick={() => window.location.reload()}>Pagina vernieuwen</button>
      </div>
    )
    return this.props.children
  }
}

const TAB_ICONS = {
  home: <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />,
  chat: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
  rapporten: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></>,
  dashboard: <><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /></>,
}

function MobileTabBtn({ icon, label, to }) {
  const navigate = useNavigate()
  const location = useLocation()
  const isActive = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)
  return (
    <a
      href={to}
      className={`mobile-tab-btn${isActive ? ' active' : ''}`}
      onClick={(e) => { e.preventDefault(); navigate(to) }}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        {TAB_ICONS[icon]}
      </svg>
      {label}
    </a>
  )
}
