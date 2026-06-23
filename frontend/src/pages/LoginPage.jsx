import { useState } from 'react'
import { login } from '../auth'

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const data = await login(username, password)
      onLogin(data.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(160deg, var(--blue-900) 0%, var(--blue-700) 60%, var(--teal-600) 100%)',
    }}>
      <div style={{
        background: 'var(--white)', borderRadius: 'var(--radius-xl)',
        padding: '48px 40px', width: '100%', maxWidth: 400,
        boxShadow: 'var(--shadow-lg)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
          <div className="navbar-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="navbar-name">EDU<span>data</span></span>
        </div>

        <h2 style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: 6 }}>Inloggen</h2>
        <p style={{ fontSize: '.9rem', color: 'var(--gray-500)', marginBottom: 28 }}>
          Log in om verder te gaan met EDUdata.
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ fontSize: '.8rem', fontWeight: 600, color: 'var(--gray-700)', display: 'block', marginBottom: 6 }}>
              Gebruikersnaam
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              autoFocus
              style={{
                width: '100%', padding: '10px 14px',
                border: '1.5px solid var(--gray-200)', borderRadius: 'var(--radius)',
                fontSize: '.9rem', outline: 'none', transition: 'border-color .15s',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--blue-400)'}
              onBlur={e => e.target.style.borderColor = 'var(--gray-200)'}
            />
          </div>
          <div>
            <label style={{ fontSize: '.8rem', fontWeight: 600, color: 'var(--gray-700)', display: 'block', marginBottom: 6 }}>
              Wachtwoord
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              style={{
                width: '100%', padding: '10px 14px',
                border: '1.5px solid var(--gray-200)', borderRadius: 'var(--radius)',
                fontSize: '.9rem', outline: 'none', transition: 'border-color .15s',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--blue-400)'}
              onBlur={e => e.target.style.borderColor = 'var(--gray-200)'}
            />
          </div>

          {error && (
            <div style={{
              background: '#FEE2E2', color: '#991B1B', borderRadius: 'var(--radius-sm)',
              padding: '10px 14px', fontSize: '.85rem', fontWeight: 500,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            style={{
              padding: '12px', borderRadius: 'var(--radius)',
              background: busy ? 'var(--gray-300)' : 'var(--blue-600)',
              color: 'var(--white)', fontWeight: 700, fontSize: '.95rem',
              transition: 'background .15s', marginTop: 4,
            }}
          >
            {busy ? 'Bezig…' : 'Inloggen'}
          </button>
        </form>
      </div>
    </div>
  )
}
