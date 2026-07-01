import { useState } from 'react'
import InstellingPicker from './InstellingPicker'

const FUNCTIES = ['Bestuurder', 'Directeur', 'Beleidsmedewerker', 'Onderzoeker', 'Anders']
const MODES = [
  { id: 'system', label: 'Systeem' },
  { id: 'light',  label: 'Licht' },
  { id: 'dark',   label: 'Donker' },
]

function ModeIcon({ id }) {
  if (id === 'light') return (
    <>
      <circle cx="12" cy="12" r="5"/>
      <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
      <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </>
  )
  if (id === 'dark') return <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  return (
    <>
      <circle cx="12" cy="12" r="4"/>
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
    </>
  )
}

export default function SettingsModal({ settings, onSave, onClose, isOnboarding }) {
  const [instelling, setInstelling] = useState(settings.instelling || '')
  const [functie, setFunctie] = useState(settings.functie || '')
  const [mode, setMode] = useState(settings.mode || 'system')

  const handleSave = () => {
    onSave({ instelling, functie, mode })
    onClose()
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 2000,
        background: 'linear-gradient(160deg, rgba(13,35,64,.92) 0%, rgba(30,74,122,.88) 60%, rgba(13,148,136,.82) 100%)',
        backdropFilter: 'blur(6px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
      }}
      onClick={isOnboarding ? undefined : onClose}
    >
      <div
        style={{
          background: 'var(--white)', borderRadius: 'var(--radius-xl)',
          padding: '44px 40px', width: '100%', maxWidth: 440,
          boxShadow: 'var(--shadow-lg)',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28 }}>
          <div className="navbar-logo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="navbar-name">openEDU<span>data+</span></span>
        </div>

        <h2 style={{ fontSize: '1.35rem', fontWeight: 800, marginBottom: 6 }}>
          {isOnboarding ? 'Welkom' : 'Instellingen'}
        </h2>
        <p style={{ fontSize: '.88rem', color: 'var(--gray-500)', marginBottom: 32 }}>
          {isOnboarding
            ? 'Stel je profiel in. Je kunt dit altijd later wijzigen via je gebruikersnaam.'
            : 'Pas je profiel en weergave aan.'}
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <div>
            <label style={{ fontSize: '.8rem', fontWeight: 600, color: 'var(--gray-700)', display: 'block', marginBottom: 8 }}>
              Onderwijsinstelling
            </label>
            <InstellingPicker value={instelling} onChange={setInstelling} />
          </div>

          <div>
            <label style={{ fontSize: '.8rem', fontWeight: 600, color: 'var(--gray-700)', display: 'block', marginBottom: 8 }}>
              Functie
            </label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {FUNCTIES.map(f => (
                <button
                  key={f}
                  onClick={() => setFunctie(functie === f ? '' : f)}
                  style={{
                    padding: '7px 14px', borderRadius: 'var(--radius-sm)', fontSize: '.82rem', fontWeight: 600,
                    border: `1.5px solid ${functie === f ? 'var(--blue-500)' : 'var(--gray-200)'}`,
                    background: functie === f ? 'var(--blue-50)' : 'var(--white)',
                    color: functie === f ? 'var(--blue-700)' : 'var(--gray-600)',
                    transition: 'all .15s',
                  }}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={{ fontSize: '.8rem', fontWeight: 600, color: 'var(--gray-700)', display: 'block', marginBottom: 8 }}>
              Weergave
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {MODES.map(m => (
                <button
                  key={m.id}
                  onClick={() => setMode(m.id)}
                  style={{
                    padding: '10px 8px', borderRadius: 'var(--radius-sm)',
                    border: `1.5px solid ${mode === m.id ? 'var(--blue-500)' : 'var(--gray-200)'}`,
                    background: mode === m.id ? 'var(--blue-50)' : 'var(--white)',
                    color: mode === m.id ? 'var(--blue-700)' : 'var(--gray-600)',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
                    fontSize: '.8rem', fontWeight: 600, transition: 'all .15s',
                  }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 18, height: 18 }}>
                    <ModeIcon id={m.id} />
                  </svg>
                  {m.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, marginTop: 32 }}>
          <button
            onClick={handleSave}
            style={{
              flex: 1, padding: '12px', borderRadius: 'var(--radius)',
              background: 'var(--blue-600)', color: 'var(--white)',
              fontWeight: 700, fontSize: '.95rem', transition: 'background .15s',
            }}
            onMouseEnter={e => e.target.style.background = 'var(--blue-700)'}
            onMouseLeave={e => e.target.style.background = 'var(--blue-600)'}
          >
            Opslaan
          </button>
          {isOnboarding && (
            <button
              onClick={onClose}
              style={{
                padding: '12px 18px', borderRadius: 'var(--radius)',
                border: '1.5px solid var(--gray-200)', background: 'var(--white)',
                color: 'var(--gray-600)', fontWeight: 600, fontSize: '.9rem',
              }}
            >
              Overslaan
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
