import { useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import DataSourcesModal from './DataSourcesModal'
import InstalleerUitleg from './InstalleerUitleg'
import PrivacyLink from './PrivacyLink'
import { useEscape } from '../hooks/useEscape'
import { sneltoetsHint } from '../hooks/useZoekSneltoets'
import { useInstallatieAanbod, vraagInstallatie } from '../installeerApp'

const BESTEMMINGEN = [
  {
    to: '/', label: 'Home',
    icoon: <><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></>,
  },
  {
    to: '/chat', label: 'Chat',
    icoon: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
  },
  {
    to: '/rapporten', label: 'Rapporten',
    icoon: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /></>,
  },
  {
    to: '/dashboards', label: 'Dashboard', dashboard: true,
    icoon: <><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /></>,
  },
]

const isActief = (to, pathname) => (to === '/' ? pathname === '/' : pathname.startsWith(to))

// slotRef: de plek in de balk waar een pagina op een telefoon zijn knoppen neerzet (navSlot.jsx).
export default function Nav({ user, onLogout, onOpenSettings, instelling, dashboardsEnabled = false, slotRef, onZoek = null }) {
  const bestemmingen = BESTEMMINGEN.filter(b => dashboardsEnabled || !b.dashboard)
  return (
    <nav className="navbar">
      <div className="container">
        <div className="navbar-brand" style={{ flex: 1 }}>
          <NavMenu
            bestemmingen={bestemmingen} user={user} instelling={instelling}
            onLogout={onLogout} onOpenSettings={onOpenSettings}
          />
          <div className="navbar-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="navbar-name">openEDU<span>data+</span></span>
        </div>

        <div className="navbar-nav">
          {bestemmingen.map(b => <NavBtn key={b.to} to={b.to} label={b.label}>{b.icoon}</NavBtn>)}
        </div>

        <div className="navbar-acties" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10 }}>
          <div className="navbar-pagina" ref={slotRef} />
          {/* Search over conversations and reports (#602); the hint shows the shortcut, on a phone only the icon. */}
          {onZoek && (
            <button type="button" className="navbar-zoek-btn" onClick={onZoek} aria-label="Zoeken" aria-keyshortcuts="Control+K Meta+K">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span className="navbar-zoek-label" aria-hidden="true">Zoeken</span>
              <kbd className="navbar-zoek-hint" aria-hidden="true">{sneltoetsHint()}</kbd>
            </button>
          )}
          {user && (
            <button type="button"
              className="navbar-profile-btn"
              onClick={onOpenSettings}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'flex-end', justifyContent: 'center',
                background: 'none', border: 'none',
                cursor: onOpenSettings ? 'pointer' : 'default', padding: '4px 6px',
                borderRadius: 'var(--radius-sm)', transition: 'all .15s',
              }}
              title="Instellingen"
            >
              {instelling && (
                <span className="navbar-profile-instelling">
                  {instelling}
                </span>
              )}
              <span className="navbar-profile-naam">
                {user}
              </span>
            </button>
          )}
          {onLogout && (
            <button type="button" className="navbar-cta" onClick={onLogout} style={{ background: 'var(--gray-100)', color: 'var(--gray-700)' }}>
              Uitloggen
            </button>
          )}
        </div>
      </div>
    </nav>
  )
}

function NavBtn({ to, label, children }) {
  const navigate = useNavigate()
  const location = useLocation()
  return (
    <a
      href={to}
      className={`nav-btn${isActief(to, location.pathname) ? ' active' : ''}`}
      onClick={(e) => { e.preventDefault(); navigate(to) }}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
      {label}
    </a>
  )
}

// Op een telefoon vervangt dit de vaste tabbalk (#596): een hamburger in de navbar, met de bestemmingen, de
// instellingen en de links die de chat niet meer onder het invoerveld toont (bronnen, privacy). De tabbalk
// nam 58 px van de chat. Hij verschijnt alleen onder de breakpoint (CSS); op desktop staat de navigatie in de balk.
function NavMenu({ bestemmingen, user, instelling, onLogout, onOpenSettings }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [bronnen, setBronnen] = useState(false)
  const [installeerUitleg, setInstalleerUitleg] = useState(false)
  const installeerAanbod = useInstallatieAanbod()
  const knopRef = useRef(null)
  const sluit = () => setOpen(false)
  // Escape en een tik op een bestemming geven de focus aan de knop terug, zodat toetsenbord en schermlezer
  // niet op <body> terechtkomen.
  const sluitMetFocus = () => { setOpen(false); knopRef.current?.focus() }
  useEscape(open, sluitMetFocus)
  // Een andere pagina (ook terug-knop van de browser): het menu hoort dicht.
  useEffect(() => { setOpen(false) }, [location.pathname])

  const kies = (actie) => () => { sluit(); actie() }

  return (
    <>
      <button
        type="button" ref={knopRef} className="navbar-menu-btn"
        aria-label="Menu" aria-expanded={open} aria-controls="navbar-menu"
        onClick={() => setOpen(o => !o)}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>
      {open && (
        <>
          <div className="navbar-menu-overlay" onClick={sluit} aria-hidden="true" />
          <div className="navbar-menu" id="navbar-menu">
            {bestemmingen.map(b => (
              <a
                key={b.to} href={b.to}
                className={`navbar-menu-item${isActief(b.to, location.pathname) ? ' active' : ''}`}
                aria-current={isActief(b.to, location.pathname) ? 'page' : undefined}
                onClick={(e) => { e.preventDefault(); navigate(b.to) }}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{b.icoon}</svg>
                {b.label}
              </a>
            ))}
            <div className="navbar-menu-scheiding" role="separator" />
            {user && onOpenSettings && (
              <button type="button" className="navbar-menu-item" onClick={kies(onOpenSettings)}>
                Instellingen
                <span className="navbar-menu-sub">{[instelling, user].filter(Boolean).join(' · ')}</span>
              </button>
            )}
            <button type="button" className="navbar-menu-item" onClick={kies(() => setBronnen(true))}>
              Gebaseerd op open onderwijsdata
            </button>
            {installeerAanbod && (
              <button
                type="button" className="navbar-menu-item"
                onClick={kies(installeerAanbod === 'prompt' ? vraagInstallatie : () => setInstalleerUitleg(true))}
              >
                Zet op je startscherm
              </button>
            )}
            <PrivacyLink className="navbar-menu-item">Privacy-informatie</PrivacyLink>
            {onLogout && (
              <button type="button" className="navbar-menu-item" onClick={kies(onLogout)}>Uitloggen</button>
            )}
          </div>
        </>
      )}
      {bronnen && <DataSourcesModal onClose={() => setBronnen(false)} />}
      {installeerUitleg && <InstalleerUitleg onClose={() => setInstalleerUitleg(false)} />}
    </>
  )
}
