import { useNavigate, useLocation } from 'react-router-dom'

export default function Nav({ user, onLogout, onOpenSettings, instelling }) {
  return (
    <nav className="navbar">
      <div className="container">
        <div className="navbar-brand" style={{ flex: 1 }}>
          <div className="navbar-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="navbar-name">openEDU<span>data+</span></span>
        </div>

        <div className="navbar-nav">
          <NavBtn to="/" label="Home">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />
          </NavBtn>
          <NavBtn to="/chat" label="Chat">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </NavBtn>
          <NavBtn to="/rapporten" label="Rapporten">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
          </NavBtn>
          <NavBtn to="/dashboards" label="Dashboard">
            <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
            <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
          </NavBtn>
        </div>

        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 10 }}>
          {user && (
            <button
              onClick={onOpenSettings}
              style={{
                display: 'flex', flexDirection: 'column', alignItems: 'flex-end',
                background: 'none', border: 'none',
                cursor: onOpenSettings ? 'pointer' : 'default', padding: '4px 6px',
                borderRadius: 'var(--radius-sm)', transition: 'all .15s',
              }}
              title="Instellingen"
            >
              {instelling && (
                <span style={{ fontSize: '.75rem', fontWeight: 600, color: 'var(--gray-700)', lineHeight: 1.2 }}>
                  {instelling}
                </span>
              )}
              <span style={{ fontSize: '.72rem', color: 'var(--gray-400)', lineHeight: 1.2 }}>
                {user}
              </span>
            </button>
          )}
          {onLogout && (
            <button className="navbar-cta" onClick={onLogout} style={{ background: 'var(--gray-100)', color: 'var(--gray-700)' }}>
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
  const isActive = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)
  return (
    <a
      href={to}
      className={`nav-btn${isActive ? ' active' : ''}`}
      onClick={(e) => { e.preventDefault(); navigate(to) }}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
      {label}
    </a>
  )
}
