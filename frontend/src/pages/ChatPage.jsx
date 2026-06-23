import { useRef, useEffect, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { useChat } from '../hooks/useChat'
import { SOURCES, SUGGESTED } from '../constants'
import { saveWorkbook } from '../workbooks'

export default function ChatPage({ setPage }) {
  const handleUnauthorized = useCallback(() => window.location.reload(), [])
  const { messages, busy, toasts, send, sendClarification, sendSettings, stop, clear } = useChat({
    onUnauthorized: handleUnauthorized,
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

  const buildTurns = () => {
    const userMsgs = messages.filter(m => m.role === 'user')
    const assistantMsgs = messages.filter(m => m.role === 'assistant' && m.done && !m.isError)
    return userMsgs.map((m, i) => ({ question: m.content, answer: assistantMsgs[i]?.content || '' }))
  }

  const fetchExportHtml = async (type) => {
    const res = await fetch(`/api/export/${type}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ turns: buildTurns() }),
    })
    return { blob: await res.blob(), disposition: res.headers.get('Content-Disposition') || '' }
  }

  const handleExport = async (type) => {
    const { blob, disposition } = await fetchExportHtml(type)
    const filename = disposition.split('filename=')[1] || `${type}.html`
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = filename; a.click()
    URL.revokeObjectURL(url)
  }

  const handleSaveAsWorkbook = async () => {
    const { blob } = await fetchExportHtml('samenvatting')
    const html = await blob.text()
    const title = messages.find(m => m.role === 'user')?.content?.slice(0, 60) || 'Nieuw werkboek'
    const date = new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
    saveWorkbook({ title, description: `Gegenereerd op ${date}`, htmlContent: html })
    setPage?.('dashboard')
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
                  <div className="source-dot green" />
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
                <button className="export-btn export-btn-save" onClick={handleSaveAsWorkbook}>💾 Opslaan als werkboek</button>
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
  return (
    <div className="model-picker">
      <select value={value} onChange={e => onChange(e.target.value)}>
        {models.map(m => (
          <option key={m.id} value={m.id}>{m.name}{m.description ? ` — ${m.description}` : ''}</option>
        ))}
      </select>
      <svg className="model-picker-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
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
    <div className="suggested-category">
      <button className="suggested-category-btn" onClick={() => setOpen(o => !o)}>
        <span>{category}</span>
        <svg className={`suggested-category-chevron${open ? ' open' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="suggested-list">
          {questions.map(q => (
            <button key={q} className="suggested-btn" onClick={() => !busy && onSend(q)}>{q}</button>
          ))}
        </div>
      )}
    </div>
  )
}
