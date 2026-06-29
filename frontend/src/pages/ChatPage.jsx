import { useRef, useEffect, useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { useChat } from '../hooks/useChat'
import { SUGGESTED, STORAGE_CONVERSATIONS, MAX_CONVERSATIONS, MAX_TEXTAREA_HEIGHT } from '../constants'
import { saveWorkbook } from '../workbooks'
import { buildDashboardHtml } from '../dashboardHtml'
import ModelPicker from '../components/ModelPicker'

const HISTORY_KEY = STORAGE_CONVERSATIONS

function loadConversationHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { return [] }
}

function persistConversationHistory(list) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list))
}

export default function ChatPage({ setPage, openDashboard, settings = {} }) {
  const handleUnauthorized = useCallback(() => window.location.reload(), [])
  const { messages, busy, toasts, send, sendClarification, sendSettings, stop, clear } = useChat({
    onUnauthorized: handleUnauthorized,
  })
  const [input, setInput] = useState('')
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [showSources, setShowSources] = useState(false)
  const [restoredMessages, setRestoredMessages] = useState([])
  const [conversationHistory, setConversationHistory] = useState(loadConversationHistory)
  const [saveError, setSaveError] = useState(null)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)
  const messagesRef = useRef(messages)
  const pendingRestartMsgRef = useRef(null)

  // Keep messagesRef in sync with latest messages
  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  // Send pending restart message once busy clears after a clear()
  useEffect(() => {
    if (!busy && pendingRestartMsgRef.current) {
      const msg = pendingRestartMsgRef.current
      pendingRestartMsgRef.current = null
      send(msg)
    }
  }, [busy, send])

  const saveCurrentConversation = useCallback((msgs) => {
    const toSave = msgs || messages
    const userMsgs = toSave.filter(m => m.role === 'user')
    if (!userMsgs.length) return
    const conv = {
      id: Date.now(),
      title: userMsgs[0].content.slice(0, 80),
      timestamp: Date.now(),
      messages: toSave,
    }
    const updated = [conv, ...loadConversationHistory()].slice(0, MAX_CONVERSATIONS)
    persistConversationHistory(updated)
    setConversationHistory(updated)
  }, [messages])

  const handleClear = useCallback(() => {
    if (!window.confirm('Weet je zeker dat je een nieuw gesprek wilt starten?')) return
    saveCurrentConversation()
    setRestoredMessages([])
    clear()
  }, [clear, saveCurrentConversation])

  const handleRestart = useCallback((conv) => {
    const firstUserMsg = conv.messages.find(m => m.role === 'user')?.content
    setRestoredMessages([])
    clear()
    if (firstUserMsg) pendingRestartMsgRef.current = firstUserMsg
  }, [clear])

  const handleLoad = useCallback((conv) => {
    clear()
    setRestoredMessages(conv.messages)
  }, [clear])

  // Save conversation on unmount using ref to avoid stale closure
  useEffect(() => {
    return () => {
      const latestMessages = messagesRef.current
      const userMsgs = latestMessages.filter(m => m.role === 'user')
      if (!userMsgs.length) return
      const conv = {
        id: Date.now(),
        title: userMsgs[0].content.slice(0, 80),
        timestamp: Date.now(),
        messages: latestMessages,
      }
      const updated = [conv, ...loadConversationHistory()].slice(0, 15)
      persistConversationHistory(updated)
    }
  }, [])

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
    const s = { model: selectedModel || undefined }
    if (settings.instelling) s.instelling = settings.instelling
    if (settings.functie) s.functie = settings.functie
    if (Object.keys(s).some(k => s[k])) sendSettings(s)
  }, [selectedModel, settings.instelling, settings.functie, sendSettings])

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
    e.target.style.height = Math.min(e.target.scrollHeight, MAX_TEXTAREA_HEIGHT) + 'px'
  }

  const handleMakeDashboard = () => {
    setSaveError(null)
    const allMsgs = [...restoredMessages, ...messages]
    const assistantContent = allMsgs
      .filter(m => m.role === 'assistant' && !m.isError && m.content)
      .map(m => m.content)
      .join('\n\n')
    if (!assistantContent) return
    const title = allMsgs.find(m => m.role === 'user')?.content?.slice(0, 60) || 'Dashboard'
    const htmlContent = buildDashboardHtml(title, assistantContent, [], settings?.instelling)
    const date = new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
    const result = saveWorkbook({
      title,
      description: `Aangemaakt op ${date}`,
      htmlContent,
    })
    if (result.ok) {
      openDashboard?.(result.workbook.id)
    } else {
      setSaveError(result.error)
    }
  }

  const displayMessages = [...restoredMessages, ...messages]
  const hasMessages = displayMessages.length > 0

  return (
    <>
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.level}`}>{t.message}</div>
      ))}
      <div className="chat-layout">
        {/* Sidebar */}
        <aside className="chat-sidebar">
          <button className="new-chat-btn" onClick={handleClear}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Nieuw gesprek
          </button>
          <div style={{ marginTop: 20 }}>
            <div className="sidebar-section-title" style={{ marginBottom: 10 }}>Suggestie vragen</div>
            {SUGGESTED.map(cat => (
              <SuggestedCategory key={cat.category} category={cat.category} questions={cat.questions} onSend={send} busy={busy} />
            ))}
          </div>
          <ConversationHistory
            history={conversationHistory}
            onRestart={handleRestart}
            onLoad={handleLoad}
          />
        </aside>

        {/* Main */}
        <div className="chat-main">
          <div className="chat-messages">
            {!hasMessages && <WelcomeScreen instelling={settings.instelling} functie={settings.functie} />}
            {restoredMessages.length > 0 && messages.length === 0 && (
              <div className="restored-banner">
                Ingeladen gesprek — stel een nieuwe vraag om door te gaan
              </div>
            )}
            {displayMessages.map((msg) => (
              <Message
                key={msg.id} msg={msg}
                onClarification={sendClarification} onSend={send} busy={busy}
                settings={settings}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-area">
            {hasMessages && !busy && displayMessages.some(m => m.role === 'assistant' && !m.isError && m.content) && (
              <div>
                <button className="make-dashboard-btn" onClick={handleMakeDashboard}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
                    <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
                    <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
                  </svg>
                  Maak dashboard van dit gesprek
                </button>
                {saveError && (
                  <p style={{ color: '#DC2626', fontSize: 13, margin: '4px 0 0' }}>
                    Dashboard opslaan mislukt: {saveError}
                  </p>
                )}
              </div>
            )}
            <div className="chat-input-wrap">
              <textarea
                ref={textareaRef}
                className="chat-input"
                rows={1}
                placeholder="Verken betrouwbare regionale en landelijke (open) onderwijsdata en versterk je strategische koers."
                value={input}
                onChange={e => { setInput(e.target.value); autoResize(e) }}
                onKeyDown={handleKey}
                disabled={busy}
              />
              <div className="chat-input-footer">
                {models.length > 0 && (
                  <ModelPicker models={models} value={selectedModel} onChange={setSelectedModel} />
                )}
                {busy ? (
                  <button className="send-btn" onClick={stop} title="Stop genereren">
                    <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: 14, height: 14 }}><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
                  </button>
                ) : (
                  <button className="send-btn" onClick={handleSend} disabled={!input.trim()}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
                      <path d="M12 19V5M5 12l7-7 7 7" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
            <p className="chat-disclaimer">openEDUdata+ gebruikt <button onClick={() => setShowSources(true)} style={{ background: 'none', border: 'none', padding: 0, font: 'inherit', fontSize: 'inherit', color: 'var(--blue-600)', textDecoration: 'underline', cursor: 'pointer' }}>open onderwijsdata</button>. Controleer altijd de bronnen bij beleidsbeslissingen.</p>
          </div>
        </div>
      </div>

      {showSources && (
        <div className="modal-overlay" onClick={() => setShowSources(false)}>
          <button className="modal-overlay-close" onClick={() => setShowSources(false)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 20, height: 20 }}>
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <div className="section-label" style={{ marginBottom: 4 }}>Transparantie</div>
                <h2>Databronnen</h2>
              </div>
            </div>
            <div className="modal-body">
              <table className="modal-table">
                <thead>
                  <tr><th>Bron</th><th>Inhoud</th><th>Catalogus</th></tr>
                </thead>
                <tbody>
                  {[
                    ['CBS', '68 datasets met onderwijsstatistieken', 'cedanl.github.io/cbs-onderwijsdata', 'https://cedanl.github.io/cbs-onderwijsdata'],
                    ['RIO', 'Register van onderwijsinstellingen en opleidingen (14 resources)', 'cedanl.github.io/rio-onderwijsdata', 'https://cedanl.github.io/rio-onderwijsdata'],
                    ['DUO', '57 open datasets: prognoses, diplomering, instroom, adressen', 'onderwijsdata.duo.nl', 'https://onderwijsdata.duo.nl'],
                  ].map(([bron, inhoud, catalogus, href]) => (
                    <tr key={bron}>
                      <td><span className="source-name">{bron}</span></td>
                      <td><span className="source-desc">{inhoud}</span></td>
                      <td><a href={href} target="_blank" rel="noreferrer">{catalogus}</a></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </>
  )
}


function WelcomeScreen({ instelling, functie }) {
  const greeting = instelling
    ? `Wat wil je weten over ${instelling}?`
    : 'Stel je vraag aan openEDUdata+'
  const sub = functie
    ? `Als ${functie} krijg je onderbouwde antwoorden over instroom, voortgang, arbeidsmarkt en diplomering — direct uit open onderwijsdata.`
    : 'Vraag wat je wilt weten over instroom, voortgang, arbeidsmarkt of diplomering. Ik combineer de open-onderwijs-databronnen en geef je een onderbouwd antwoord.'
  return (
    <div className="chat-welcome">
      <div className="chat-welcome-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <h2>{greeting}</h2>
      <p>{sub}</p>
    </div>
  )
}

function userInitials(settings) {
  if (settings.instelling) {
    const words = settings.instelling.trim().split(/\s+/)
    return words.length >= 2
      ? (words[0][0] + words[1][0]).toUpperCase()
      : words[0].slice(0, 2).toUpperCase()
  }
  if (settings.functie) return settings.functie.slice(0, 2).toUpperCase()
  return 'JB'
}

function Message({ msg, onClarification, onSend, busy, settings = {} }) {
  if (msg.role === 'user') {
    return (
      <div className="message user">
        <div className="message-avatar">{userInitials(settings)}</div>
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

function ConversationHistory({ history, onRestart, onLoad }) {
  const [expandedId, setExpandedId] = useState(null)

  if (history.length === 0) return null

  const relativeDate = (ts) => {
    const diff = Date.now() - ts
    const days = Math.floor(diff / 86400000)
    if (days === 0) return 'Vandaag'
    if (days === 1) return 'Gisteren'
    return new Date(ts).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
  }

  return (
    <div style={{ marginTop: 24 }}>
      <div className="sidebar-section-title" style={{ marginBottom: 10 }}>Gesprek geschiedenis</div>
      <div className="history-list">
        {history.map(conv => (
          <div key={conv.id} className="history-item">
            <button
              className={`history-btn${expandedId === conv.id ? ' active' : ''}`}
              onClick={() => setExpandedId(expandedId === conv.id ? null : conv.id)}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 12, height: 12, flexShrink: 0, opacity: .45 }}>
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <div className="history-btn-content">
                <span className="history-btn-title">{conv.title}</span>
                <span className="history-btn-date">{relativeDate(conv.timestamp)}</span>
              </div>
            </button>
            {expandedId === conv.id && (
              <div className="history-actions">
                <button className="history-action-btn" onClick={() => { onLoad(conv); setExpandedId(null) }}>
                  Inladen &amp; verdergaan
                </button>
                <button className="history-action-btn history-action-restart" onClick={() => { onRestart(conv); setExpandedId(null) }}>
                  Opnieuw starten
                </button>
              </div>
            )}
          </div>
        ))}
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
