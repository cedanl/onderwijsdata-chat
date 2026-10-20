import { Component, Suspense, lazy, useState, useEffect, useCallback } from 'react'
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import Nav from './components/Nav'
import HomePage from './pages/HomePage'
import NotFoundPage from './pages/NotFoundPage'
import LoginPage from './pages/LoginPage'
import PrivacyPage from './pages/PrivacyPage'
import SettingsModal from './components/SettingsModal'
import ZoekPalet from './components/ZoekPalet'
import { useZoekSneltoets } from './hooks/useZoekSneltoets'
import { wachtOpOpslag } from './gesprekOpslag'
import { fetchAuthStatus, getToken, clearToken, onSessionEnded, consumeTokenFromUrl, getStoredUserInfo, fetchUserInfo, refreshAuthToken, tokenExpiresAt, logout } from './auth'
import { matchKnownInstelling, instellingType } from './instellingenMatch'
import { STORAGE_SETTINGS, STORAGE_ONBOARDED, MAX_MESSAGE_CHARS } from './constants'
import { clearLocalSessionData } from './sessionData'
import { resolveMaxMessageChars } from './messageLength'
import { applyMode } from './theme'
import { NavSlotContext } from './navSlot'

// Plotly and syntax highlighting are most of the bundle; the login and home routes do not need them (#110).
const ChatPage = lazy(() => import('./pages/ChatPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const RapportenPage = lazy(() => import('./pages/RapportenPage'))

function loadSettings() {
  try { return JSON.parse(localStorage.getItem(STORAGE_SETTINGS) || '{}') } catch { return {} }
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
  const expiresAt = tokenExpiresAt(token)
  if (!expiresAt || expiresAt <= Date.now()) return
  // Refresh 5 minutes before expiration
  const refreshIn = Math.max(60000, expiresAt - Date.now() - 5 * 60 * 1000)
  if (_tokenRefreshTimer) clearTimeout(_tokenRefreshTimer)
  _tokenRefreshTimer = setTimeout(async () => {
    const result = await refreshAuthToken(token)
    if (result) startTokenRefreshTimer(result.newToken)
  }, refreshIn)
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
  // De plek in de navbar waar een pagina op een telefoon zijn knoppen neerzet (#596).
  const [navSlot, setNavSlot] = useState(null)
  const [isOnboarding, setIsOnboarding] = useState(false)
  const [dashboardsEnabled, setDashboardsEnabled] = useState(true)
  const [feedbackEnabled, setFeedbackEnabled] = useState(false)
  const [maxMessageChars, setMaxMessageChars] = useState(MAX_MESSAGE_CHARS)
  // The server ended the session (#499): the login screen says why. Logout needs no notice.
  const [sessionExpired, setSessionExpired] = useState(false)
  const [zoekOpen, setZoekOpen] = useState(false)
  const [teOpenenGesprek, setTeOpenenGesprek] = useState(null)

  useEffect(() => { applyMode(settings.mode || 'system') }, [settings.mode])

  // Logout and a session the server ended (#480) leave the same state behind.
  const resetSession = useCallback(() => {
    if (_tokenRefreshTimer) clearTimeout(_tokenRefreshTimer)
    clearLocalSessionData()
    // The profile belongs to whoever logged out; on a shared device the next person starts fresh.
    localStorage.removeItem(STORAGE_SETTINGS)
    localStorage.removeItem(STORAGE_ONBOARDED)
    setSettings({})
    setUser(null)
    setUserInfo(null)
    setShowSettings(false)
  }, [])

  useEffect(() => onSessionEnded(() => {
    resetSession()
    setSessionExpired(true)
  }), [resetSession])

  useEffect(() => {
    // A token in the URL means we just landed here via the SRAM callback
    // redirect — a fresh login, same as the password form's handleLogin.
    if (consumeTokenFromUrl()) clearLocalSessionData()

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
          if (!getToken()) return  // The server refused the token: the session has ended
          if (userInfo) {
            setUserInfo(userInfo)
            setUser(userInfo.name || userInfo.username)
            // Start token refresh timer (refresh 5 min before expiration)
            startTokenRefreshTimer(token)
          } else {
            // Endpoint doesn't exist (GitHub version) or the server failed
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
        setFeedbackEnabled(config.feedback_enabled === true)
        setMaxMessageChars(resolveMaxMessageChars(config.max_message_chars))
      }).catch(() => {
        setDashboardsEnabled(true)
      }),
      fetch('/api/instellingen').then(r => r.json()).then(setInstellingen).catch(() => {})
    ]).then(() => {
      setAuthLoading(false)
    })
  }, [])

  const handleLogin = (u) => {
    clearLocalSessionData()
    setSessionExpired(false)
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

  // The search palette (#602): Ctrl/⌘K or the search button, on every route once logged in. A conversation
  // picked there opens in the chat (ChatPage reads `teOpenenGesprek`), a report on /rapporten by its id.
  const openZoeken = useCallback(() => setZoekOpen(true), [])
  useZoekSneltoets(!authLoading && (!authRequired || user) ? openZoeken : null)
  const openGesprekUitZoeken = (id) => {
    setZoekOpen(false)
    setTeOpenenGesprek(id)
    navigate('/chat')
  }
  const openRapportUitZoeken = (id) => {
    setZoekOpen(false)
    navigate(`/rapporten?id=${encodeURIComponent(id)}`)
  }
  const gesprekGeopend = useCallback(() => setTeOpenenGesprek(null), [])

  if (authLoading) return <div className="app-loading" role="status">openEDUdata+ wordt geladen…</div>

  if (authRequired && !user) {
    // De privacy-informatie moet vóór het inloggen te lezen zijn (#477): de loginpagina linkt ernaar.
    if (location.pathname === '/privacy') return <PrivacyPage standalone />
    return <LoginPage onLogin={handleLogin} oidcEnabled={oidcEnabled} sessionExpired={sessionExpired} />
  }

  // Logging out is immediate here, but the token is revoked on the server only once a save of the open
  // conversation that is still under way has landed (#635): it carries that token.
  const handleLogout = () => {
    const token = getToken()
    clearToken()
    resetSession()
    wachtOpOpslag().then(() => logout(token))
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
        slotRef={setNavSlot}
        onZoek={openZoeken}
      />
      <main className="page-wrap">
        <NavSlotContext.Provider value={navSlot}>
          <ErrorBoundary key={location.pathname}>
            <Suspense fallback={<div className="app-loading" role="status">Pagina wordt geladen…</div>}>
              <Routes>
                <Route path="/" element={<HomePage dashboardsEnabled={dashboardsEnabled} feedbackEnabled={feedbackEnabled} />} />
                <Route path="/chat" element={<ChatPage openRapport={openRapport} settings={settings} sector={instellingType(settings.instelling, instellingen)} user={user} feedbackEnabled={feedbackEnabled} maxMessageChars={maxMessageChars} teOpenenGesprek={teOpenenGesprek} onGesprekGeopend={gesprekGeopend} />} />
                <Route path="/dashboards" element={dashboardsEnabled ? <DashboardPage settings={settings} feedbackEnabled={feedbackEnabled} /> : <NotFoundPage unavailable />} />
                <Route path="/rapporten" element={<RapportenPage settings={settings} feedbackEnabled={feedbackEnabled} />} />
                <Route path="/privacy" element={<PrivacyPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </NavSlotContext.Provider>
      </main>
      {zoekOpen && (
        <ZoekPalet onClose={() => setZoekOpen(false)} onOpenGesprek={openGesprekUitZoeken} onOpenRapport={openRapportUitZoeken} />
      )}
      {showSettings && (
        <SettingsModal
          settings={settings}
          onSave={handleSaveSettings}
          onClose={handleCloseSettings}
          onLogout={authRequired ? handleLogout : null}
          isOnboarding={isOnboarding}
          feedbackEnabled={feedbackEnabled}
          sramName={userInfo?.name || null}
          sramInstelling={sramInstelling || null}
          sramIdentity={userInfo ? [userInfo.org, userInfo.institution, userInfo.email_domein].filter(Boolean) : []}
        />
      )}
    </>
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
