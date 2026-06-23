import { useRef, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { useChat } from '../hooks/useChat'

const SOURCES = [
  { label: 'DUO Open Data', color: 'green' },
  { label: '1cijferHO', color: 'green' },
  { label: 'CBS StatLine', color: 'green' },
  { label: 'UWV Arbeidsmarkt', color: 'green' },
  { label: 'ROA / SBB', color: 'green' },
]

const SUGGESTED = [
  {
    category: 'Arbeidsmarkt',
    questions: [
      'Welk percentage van de bevolking in mijn regio neemt deel aan LLO?',
      'Wat is in mijn regio het opleidingsniveau van werkzoekenden?',
      'Hoeveel vacatures zijn er in mijn regio voor ons onderwijsaanbod?',
    ],
  },
  {
    category: 'Uitstroom',
    questions: [
      'Hoeveel gediplomeerden levert ons onderwijsaanbod op ten opzichte van andere instellingen in de regio?',
      'Wat verdienen gediplomeerden van onze instelling gemiddeld in de regio?',
      'Hoe groot is het aandeel voortijdig schoolverlaters dat werk heeft gevonden in mijn regio?',
    ],
  },
  {
    category: 'Instroom',
    questions: [
      'Waar komen mijn lerenden vandaan en met welke instellingen in de regio concurreer ik om dezelfde doelgroep?',
      'Hoeveel instromers komen rechtstreeks vanuit een andere opleiding uit de regio?',
      'Hoe heeft de deelname aan voltijdonderwijs bij ons zich ontwikkeld?',
    ],
  },
]

export default function ChatPage() {
  const { messages, busy, toasts, send, sendClarification, sendSettings, stop, clear } = useChat({
    onUnauthorized: () => window.location.reload(),
  })
  const [input, setInput] = useState('')
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  // Load available models once
  useEffect(() => {
    fetch('/api/settings/config')
      .then(r => r.json())
      .then(cfg => {
        setModels(cfg.models || [])
        setSelectedModel(cfg.default_model || '')
      })
      .catch(() => {})
  }, [])

  // Push model selection to backend whenever it changes
  useEffect(() => {
    if (selectedModel) sendSettings({ model: selectedModel })
  }, [selectedModel, sendSettings])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    const q = input.trim()
    if (!q || busy) return
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    send(q)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const autoResize = (e) => {
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
  }

  const handleExport = async (type) => {
    const userMsgs = messages.filter(m => m.role === 'user')
    const assistantMsgs = messages.filter(m => m.role === 'assistant' && m.done && !m.isError)
    const turns = userMsgs.map((m, i) => ({
      question: m.content,
      answer: assistantMsgs[i]?.content || '',
    }))
    const res = await fetch(`/api/export/${type}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ turns }),
    })
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') || ''
    const filename = disposition.split('filename=')[1] || `${type}.html`
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = filename; a.click()
    URL.revokeObjectURL(url)
  }

  const hasMessages = messages.length > 0

  return (
    <>
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.level}`}>{t.message}</div>
      ))}
      <div className="chat-layout">
        {/* Sidebar */}
        <aside className="chat-sidebar">
          <div>
            <div className="sidebar-section-title">Databronnen</div>
            <div className="chat-source-list">
              {SOURCES.map(s => (
                <div key={s.label} className="source-item">
                  <div className={`source-dot ${s.color}`} />
                  <span className="source-label">{s.label}</span>
                  <span className="source-badge">Open</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="sidebar-section-title" style={{ marginBottom: 10 }}>Suggestie vragen</div>
            {SUGGESTED.map(cat => (
              <SuggestedCategory key={cat.category} category={cat.category} questions={cat.questions} onSend={send} busy={busy} />
            ))}
          </div>
        </aside>

        {/* Main */}
        <div className="chat-main">
          <div className="chat-topbar">
            <div>
              <div className="chat-topbar-title">EDUdata Assistent</div>
              <div className="chat-topbar-sub">Stel een vraag over open onderwijsdata</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {models.length > 0 && (
                <ModelPicker models={models} value={selectedModel} onChange={setSelectedModel} />
              )}
              {hasMessages && (
                <button className="export-btn" onClick={clear}>Nieuw gesprek</button>
              )}
            </div>
          </div>

          <div className="chat-messages">
            {!hasMessages && <WelcomeScreen />}
            {messages.map(msg => (
              <Message key={msg.id} msg={msg} onClarification={sendClarification} onSend={send} busy={busy} />
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-area">
            {hasMessages && (
              <div className="chat-export-bar">
                <button className="export-btn" onClick={() => handleExport('rapport')}>📥 Rapport</button>
                <button className="export-btn" onClick={() => handleExport('samenvatting')}>🧾 Samenvatting</button>
              </div>
            )}
            <div className="chat-input-wrap">
              <textarea
                ref={textareaRef}
                className="chat-input"
                rows={1}
                placeholder="Stel een vraag over onderwijsdata…"
                value={input}
                onChange={e => { setInput(e.target.value); autoResize(e) }}
                onKeyDown={handleKey}
                disabled={busy}
              />
              {busy ? (
                <button className="send-btn" onClick={stop} title="Stop genereren">
                  <svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
                </button>
              ) : (
                <button className="send-btn" onClick={handleSend} disabled={!input.trim()}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              )}
            </div>
            <p className="chat-disclaimer">EDUdata gebruikt open onderwijsdata. Controleer altijd de bronnen bij beleidsbeslissingen.</p>
          </div>
        </div>
      </div>
    </>
  )
}

function ModelPicker({ models, value, onChange }) {
  const current = models.find(m => m.id === value)
  return (
    <div style={{ position: 'relative' }}>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{
          fontSize: '.8rem', padding: '6px 28px 6px 10px',
          border: '1px solid var(--gray-200)', borderRadius: 'var(--radius-sm)',
          background: 'var(--white)', color: 'var(--gray-700)',
          appearance: 'none', cursor: 'pointer', outline: 'none',
          fontWeight: 500,
        }}
      >
        {models.map(m => (
          <option key={m.id} value={m.id}>{m.name}{m.description ? ` — ${m.description}` : ''}</option>
        ))}
      </select>
      <svg style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', width: 12, height: 12, color: 'var(--gray-400)', pointerEvents: 'none' }}
        viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </div>
  )
}

function WelcomeScreen() {
  return (
    <div className="chat-welcome">
      <div className="chat-welcome-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <h2>Stel je vraag aan EDUdata</h2>
      <p>Vraag wat je wilt weten over instroom, voortgang, arbeidsmarkt of diplomering. Ik combineer data uit al je gekoppelde bronnen en geef je een onderbouwd antwoord.</p>
    </div>
  )
}

function Message({ msg, onClarification, onSend, busy }) {
  if (msg.role === 'user') {
    return (
      <div className="message user">
        <div className="message-avatar">JB</div>
        <div className="message-bubble">{msg.content}</div>
      </div>
    )
  }

  return (
    <div className="message assistant">
      <div className="message-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 0 }}>
        {msg.tools?.map((t, i) => (
          <div key={i} className="tool-step">
            <div className={`tool-step-dot${t.done ? ' done' : ''}`} />
            {t.label}
          </div>
        ))}
        <div className="message-bubble" style={msg.isError ? { borderColor: '#FECACA', background: '#FFF5F5' } : {}}>
          {!msg.done && !msg.content && !msg.tools?.length ? (
            <div className="ai-typing"><span /><span /><span /></div>
          ) : (
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          )}
          {msg.clarification && (
            <div className="clarification-btns">
              {msg.clarification.map((opt, i) => {
                const label = typeof opt === 'string' ? opt : opt.label
                const desc = typeof opt === 'object' ? opt.beschrijving : null
                return (
                  <button key={i} className="clarification-btn" onClick={() => !busy && onClarification(label)}>
                    {opt.aanbevolen ? '✓ ' : ''}{label}{desc ? ` — ${desc}` : ''}
                  </button>
                )
              })}
            </div>
          )}
          {msg.starterQuestions && (
            <div className="clarification-btns" style={{ marginTop: 8 }}>
              {msg.starterQuestions.map((q, i) => (
                <button key={i} className="suggested-btn" onClick={() => !busy && onSend(q)}>{q}</button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function SuggestedCategory({ category, questions, onSend, busy }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ marginBottom: 4 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 10px', borderRadius: 'var(--radius-sm)',
          background: 'var(--blue-50)', border: '1px solid var(--blue-100)',
          fontSize: '.78rem', fontWeight: 700, color: 'var(--blue-700)', cursor: 'pointer', marginBottom: 2,
        }}
      >
        <span>{category}</span>
        <svg style={{ width: 14, height: 14, transition: 'transform .2s', transform: open ? 'rotate(180deg)' : 'none' }}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="suggested-list" style={{ marginTop: 4 }}>
          {questions.map(q => (
            <button key={q} className="suggested-btn" onClick={() => !busy && onSend(q)}>{q}</button>
          ))}
        </div>
      )}
    </div>
  )
}
