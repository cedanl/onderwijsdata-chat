export default function Nav({ page, setPage, user, onLogout }) {
  return (
    <nav className="navbar">
      <div className="container">
        <div className="navbar-brand">
          <div className="navbar-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="navbar-name">EDU<span>data</span></span>
        </div>

        <div className="navbar-nav">
          <NavBtn id="home" label="Home" page={page} setPage={setPage}>
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />
          </NavBtn>
          <NavBtn id="chat" label="Chat" page={page} setPage={setPage}>
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </NavBtn>
          <NavBtn id="dashboard" label="Dashboard" page={page} setPage={setPage}>
            <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
            <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
          </NavBtn>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {user && onLogout && (
            <span style={{ fontSize: '.8rem', color: 'var(--gray-500)' }}>{user}</span>
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

function NavBtn({ id, label, page, setPage, children }) {
  return (
    <button className={`nav-btn${page === id ? ' active' : ''}`} onClick={() => setPage(id)}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
      {label}
    </button>
  )
}
