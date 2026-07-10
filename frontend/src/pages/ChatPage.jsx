import { useRef, useEffect, useState, useCallback } from 'react'
import Plot from 'react-plotly.js'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python'
import sql from 'react-syntax-highlighter/dist/esm/languages/prism/sql'
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json'
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash'
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

SyntaxHighlighter.registerLanguage('python', python)
SyntaxHighlighter.registerLanguage('sql', sql)
SyntaxHighlighter.registerLanguage('json', json)
SyntaxHighlighter.registerLanguage('bash', bash)
import { useChat } from '../hooks/useChat'
import { SUGGESTED, STORAGE_CONVERSATIONS, STORAGE_CURRENT_CHAT, MAX_CONVERSATIONS, MAX_TEXTAREA_HEIGHT } from '../constants'
import { saveWorkbookWithSync } from '../workbooks'
import { fetchConversations, putConversation, deleteConversationApi } from '../api'
import { buildDashboardHtml } from '../dashboardHtml'
import ModelPicker from '../components/ModelPicker'
import DataSourcesModal from '../components/DataSourcesModal'
import ConfirmModal from '../components/ConfirmModal'
import ScrollToBottom from '../components/ScrollToBottom'

function loadConversationHistory() {
  try { return JSON.parse(localStorage.getItem(STORAGE_CONVERSATIONS) || '[]') } catch { return [] }
}

function persistConversationHistory(list) {
  localStorage.setItem(STORAGE_CONVERSATIONS, JSON.stringify(list))
}

function codeTheme() {
  return document.documentElement.classList.contains('dark') ? oneDark : oneLight
}

function CopyButton({ text, className }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <button className={`copy-btn ${className || ''}`} onClick={handleCopy} title="Kopieer" aria-label="Kopieer">
      {copied ? (
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
    </button>
  )
}

function CodeBlock({ className, children }) {
  const language = /language-(\w+)/.exec(className || '')?.[1]
  if (!language) return <code className={className}>{children}</code>
  const code = String(children).replace(/\n$/, '')
  return (
    <div className="code-block-wrap">
      <CopyButton text={code} className="copy-btn-code" />
      <SyntaxHighlighter
        language={language}
        style={codeTheme()}
        customStyle={{ borderRadius: 6, fontSize: '0.8125rem', margin: '8px 0' }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

const MARKDOWN_COMPONENTS = {
  pre({ children }) { return <>{children}</> },
  code: CodeBlock,
}

function ToolStep({ tool }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="tool-step-wrap">
      <div className="tool-step">
        <div className={`tool-step-dot${tool.done ? ' done' : ''}`} />
        {tool.label}
        {tool.snippet && (
          <button className="tool-snippet-btn" onClick={() => setOpen(o => !o)} title="Toon reproduceerbare code">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
            </svg>
          </button>
        )}
      </div>
      {open && tool.snippet && (
        <div className="tool-snippet-code">
          <SyntaxHighlighter
            language="python"
            style={codeTheme()}
            customStyle={{ margin: 0, background: 'transparent', padding: 0, fontSize: '0.75rem' }}
          >
            {tool.snippet}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  )
}

export default function ChatPage({ openRapport, settings = {} }) {
  const handleUnauthorized = useCallback(() => window.location.reload(), [])
  const { messages, busy, connected, toasts, send, sendClarification, sendSettings, stop, clear } = useChat({
    onUnauthorized: handleUnauthorized,
  })
  const [input, setInput] = useState('')
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [showSources, setShowSources] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [restoredMessages, setRestoredMessages] = useState(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_CURRENT_CHAT) || '[]') } catch { return [] }
  })
  const [conversationHistory, setConversationHistory] = useState(loadConversationHistory)
  const [saveError, setSaveError] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)
  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)
  const textareaRef = useRef(null)
  const messagesRef = useRef(messages)
  // Load conversations from server on mount; migrate localStorage if server is empty
  useEffect(() => {
    fetchConversations().then(serverConvs => {
      if (serverConvs.length > 0) {
        const parsed = serverConvs.map(c => ({
          ...c,
          messages: typeof c.messages === 'string' ? JSON.parse(c.messages) : c.messages,
        }))
        persistConversationHistory(parsed)
        setConversationHistory(parsed)
      } else {
        const local = loadConversationHistory()
        if (local.length > 0) {
          Promise.allSettled(local.map(c =>
            putConversation(String(c.id), { title: c.title, timestamp: c.timestamp, messages: c.messages })
          )).catch(() => {})
        }
      }
    }).catch(() => {})
  }, [])

  // Keep messagesRef in sync with latest messages
  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  // Persist full visible chat so it survives browser refresh / tab close
  useEffect(() => {
    const all = [...restoredMessages, ...messages]
    if (!all.length) return
    try { localStorage.setItem(STORAGE_CURRENT_CHAT, JSON.stringify(all)) } catch {}
  }, [messages, restoredMessages])

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
    putConversation(String(conv.id), { title: conv.title, timestamp: conv.timestamp, messages: conv.messages }).catch(() => {})
  }, [messages])

  const handleClear = useCallback(() => {
    saveCurrentConversation()
    setRestoredMessages([])
    setSidebarOpen(false)
    try { localStorage.removeItem(STORAGE_CURRENT_CHAT) } catch {}
    clear()
  }, [clear, saveCurrentConversation])

  const handleLoad = useCallback((conv) => {
    saveCurrentConversation()
    clear()
    setSidebarOpen(false)
    try { localStorage.removeItem(STORAGE_CURRENT_CHAT) } catch {}
    setRestoredMessages(conv.messages)
  }, [clear, saveCurrentConversation])

  const handleDeleteConversation = useCallback((id) => {
    setPendingDelete(id)
  }, [])

  const confirmDeleteConversation = useCallback(() => {
    if (!pendingDelete) return
    const updated = conversationHistory.filter(c => c.id !== pendingDelete)
    persistConversationHistory(updated)
    setConversationHistory(updated)
    deleteConversationApi(String(pendingDelete)).catch(() => {})
    setPendingDelete(null)
  }, [pendingDelete, conversationHistory])

  const handleRenameConversation = useCallback((id, newTitle) => {
    const trimmed = newTitle.trim()
    if (!trimmed) return
    const updated = conversationHistory.map(c => c.id === id ? { ...c, title: trimmed } : c)
    persistConversationHistory(updated)
    setConversationHistory(updated)
    putConversation(String(id), { title: trimmed }).catch(() => {})
  }, [conversationHistory])

  // Save conversation on unmount (navigation away); clear current-chat key since it's now in history
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
      const updated = [conv, ...loadConversationHistory()].slice(0, MAX_CONVERSATIONS)
      persistConversationHistory(updated)
      putConversation(String(conv.id), { title: conv.title, timestamp: conv.timestamp, messages: conv.messages }).catch(() => {})
      try { localStorage.removeItem(STORAGE_CURRENT_CHAT) } catch {}
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
      .catch(() => setModels([]))
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

  const handleMakeRapport = () => {
    setSaveError(null)
    const allMsgs = [...restoredMessages, ...messages]
    const assistantContent = allMsgs
      .filter(m => m.role === 'assistant' && !m.isError && m.content)
      .map(m => m.content)
      .join('\n\n')
    if (!assistantContent) return
    const title = allMsgs.find(m => m.role === 'user')?.content?.slice(0, 60) || 'Rapport'
    const figuresJson = allMsgs
      .filter(m => m.role === 'assistant' && m.figures?.length)
      .flatMap(m => m.figures.map(f => typeof f.json === 'string' ? f.json : JSON.stringify(f.json)))
    const htmlContent = buildDashboardHtml(title, assistantContent, figuresJson, settings?.instelling)
    const date = new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
    saveWorkbookWithSync({
      title,
      description: `Aangemaakt op ${date}`,
      htmlContent,
      type: 'report',
    }).then(result => {
      if (result.ok) {
        openRapport?.(result.workbook.id)
      } else {
        setSaveError(result.error)
      }
    })
  }

  const displayMessages = [...restoredMessages, ...messages]
  const hasMessages = displayMessages.length > 0

  return (
    <>
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.level}`}>{t.message}</div>
      ))}
      <div className="chat-layout">
        {/* Sidebar overlay (mobile) */}
        {sidebarOpen && (
          <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
        )}

        {/* Sidebar */}
        <aside className={`chat-sidebar${sidebarOpen ? ' open' : ''}`}>
          <button className="new-chat-btn" onClick={handleClear}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Nieuw gesprek
          </button>
          <div style={{ marginTop: 20 }}>
            <div className="sidebar-section-title" style={{ marginBottom: 10 }}>Suggestie vragen</div>
            {SUGGESTED.map(cat => (
              <SuggestedCategory key={cat.category} category={cat.category} questions={cat.questions} onSend={send} busy={busy} instelling={settings.instelling} />
            ))}
          </div>
          <ConversationHistory
            history={conversationHistory}
            onLoad={handleLoad}
            onDelete={handleDeleteConversation}
            onRename={handleRenameConversation}
          />
        </aside>

        {/* Main */}
        <div className="chat-main">
          {/* Mobile topbar with hamburger */}
          <div className="chat-mobile-topbar">
            <button className="hamburger-btn" onClick={() => setSidebarOpen(o => !o)} aria-label="Menu">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 20, height: 20 }}>
                <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <span className="chat-mobile-topbar-title">openEDUdata+</span>
          </div>

          <div className="chat-messages" ref={messagesContainerRef}>
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
            <ScrollToBottom sentinelRef={messagesEndRef} scrollContainerRef={messagesContainerRef} />
          </div>

          <div className="chat-input-area">
            {hasMessages && !busy && displayMessages.some(m => m.role === 'assistant' && !m.isError && m.content) && (
              <div>
                <button className="make-rapport-btn" onClick={handleMakeRapport}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
                  </svg>
                  Genereer rapport
                </button>
                {saveError && (
                  <p style={{ color: '#DC2626', fontSize: 13, margin: '4px 0 0' }}>
                    Rapport opslaan mislukt: {saveError}
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
                {!connected && (
                  <span className="ws-reconnecting">
                    <span className="ws-dot" />
                    Verbinding herstellen...
                  </span>
                )}
                {models.length > 0 && (
                  <ModelPicker models={models} value={selectedModel} onChange={setSelectedModel} />
                )}
                {busy ? (
                  <button className="send-btn" onClick={stop} title="Stop genereren">
                    <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: 14, height: 14 }}><rect x="5" y="5" width="14" height="14" rx="2" /></svg>
                  </button>
                ) : (
                  <button className="send-btn" onClick={handleSend} disabled={!input.trim() || !connected}>
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

      {showSources && <DataSourcesModal onClose={() => setShowSources(false)} />}

      {pendingDelete && (
        <ConfirmModal
          message="Weet je zeker dat je dit gesprek wilt verwijderen?"
          onConfirm={confirmDeleteConversation}
          onCancel={() => setPendingDelete(null)}
        />
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
  return '?'
}

function MessageContent({ msg }) {
  const isStreaming = !msg.done && !msg.content && !msg.tools?.length && !msg.figures?.length
  if (isStreaming) return <div className="ai-typing"><span /><span /><span /></div>
  if (!msg.content) return null
  return <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>{msg.content}</ReactMarkdown>
}

function ClarificationButtons({ options, onSelect, busy }) {
  if (!options) return null
  return (
    <div className="clarification-btns">
      {options.map((opt, i) => {
        const label = typeof opt === 'string' ? opt : opt.label
        const desc = typeof opt === 'object' ? opt.beschrijving : null
        return (
          <button key={i} className="clarification-btn" onClick={() => !busy && onSelect(label)}>
            {opt.aanbevolen ? '✓ ' : ''}{label}{desc ? ` — ${desc}` : ''}
          </button>
        )
      })}
    </div>
  )
}

function StarterButtons({ questions, onSend, busy }) {
  if (!questions) return null
  return (
    <div className="clarification-btns" style={{ marginTop: 8 }}>
      {questions.map((q, i) => (
        <button key={i} className="suggested-btn" onClick={() => !busy && onSend(q)}>{q}</button>
      ))}
    </div>
  )
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
          <ToolStep key={i} tool={t} />
        ))}
        <div className="message-bubble message-bubble-assistant" style={msg.isError ? { borderColor: '#FECACA', background: '#FFF5F5' } : {}}>
          {msg.content && <CopyButton text={msg.content} className="copy-btn-message" />}
          <MessageContent msg={msg} />
          {msg.figures?.map((fig, i) => (
            <PlotlyFigure key={i} figureJson={fig.json} label={fig.label} />
          ))}
          <ClarificationButtons options={msg.clarification} onSelect={onClarification} busy={busy} />
          <StarterButtons questions={msg.starterQuestions} onSend={onSend} busy={busy} />
        </div>
      </div>
    </div>
  )
}

function PlotlyFigure({ figureJson, label }) {
  let figure
  try {
    figure = typeof figureJson === 'string' ? JSON.parse(figureJson) : figureJson
  } catch {
    return null
  }
  const isMap = figure.data?.some(t => t.type?.includes('choropleth'))
  const dark = document.documentElement.classList.contains('dark')
  const bg = dark ? '#1E293B' : '#fff'
  const fontColor = dark ? '#E2E8F0' : '#374151'
  const layout = {
    ...figure.layout,
    paper_bgcolor: bg,
    plot_bgcolor: bg,
    margin: isMap ? { l: 0, r: 0, t: 32, b: 0 } : { l: 48, r: 24, t: 32, b: 40 },
    font: { family: 'system-ui, sans-serif', size: 12, color: fontColor },
    autosize: true,
  }
  return (
    <div style={{ margin: '8px 0' }}>
      {label && <div style={{ fontSize: '.75rem', color: 'var(--gray-500)', marginBottom: 4 }}>{label}</div>}
      <Plot
        data={figure.data || []}
        layout={layout}
        config={{ responsive: true, displayModeBar: false }}
        useResizeHandler
        style={{ width: '100%', height: isMap ? 480 : 340 }}
      />
    </div>
  )
}

function ConversationHistory({ history, onLoad, onDelete, onRename }) {
  const [editingId, setEditingId] = useState(null)
  const [editDraft, setEditDraft] = useState('')
  const titleInputRef = useRef(null)

  if (history.length === 0) return null

  const relativeDate = (ts) => {
    const diff = Date.now() - ts
    const days = Math.floor(diff / 86400000)
    if (days === 0) return 'Vandaag'
    if (days === 1) return 'Gisteren'
    return new Date(ts).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
  }

  const startEditing = (conv, e) => {
    e.stopPropagation()
    setEditDraft(conv.title)
    setEditingId(conv.id)
    setTimeout(() => titleInputRef.current?.focus(), 0)
  }

  const saveEdit = (id) => {
    const trimmed = editDraft.trim()
    if (trimmed && trimmed !== history.find(c => c.id === id)?.title) {
      onRename(id, trimmed)
    }
    setEditingId(null)
  }

  return (
    <div style={{ marginTop: 24 }}>
      <div className="sidebar-section-title" style={{ marginBottom: 10 }}>Gesprek geschiedenis</div>
      <div className="history-list">
        {history.map(conv => (
          <div key={conv.id} className="history-item">
            <div className="history-item-row">
              <button
                className="history-btn"
                onClick={() => onLoad(conv)}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 12, height: 12, flexShrink: 0, opacity: .45 }}>
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <div className="history-btn-content">
                  {editingId === conv.id ? (
                    <input
                      ref={titleInputRef}
                      className="history-title-input"
                      value={editDraft}
                      onChange={e => setEditDraft(e.target.value)}
                      onBlur={() => saveEdit(conv.id)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') saveEdit(conv.id)
                        if (e.key === 'Escape') setEditingId(null)
                      }}
                      onClick={e => e.stopPropagation()}
                    />
                  ) : (
                    <span className="history-btn-title">{conv.title}</span>
                  )}
                  <span className="history-btn-date">{relativeDate(conv.timestamp)}</span>
                </div>
              </button>
              <div className="history-item-actions">
                <button
                  className="history-action-icon"
                  title="Hernoemen"
                  onClick={e => startEditing(conv, e)}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
                <button
                  className="history-action-icon history-action-icon-delete"
                  title="Verwijderen"
                  onClick={e => { e.stopPropagation(); onDelete(conv.id) }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4h6v2" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function personalizeQuestion(q, instelling) {
  if (!instelling) return q
  return q
    .replace('ons onderwijsaanbod', `het aanbod van ${instelling}`)
    .replace('onze instelling', instelling)
    .replace('mijn lerenden', `de lerenden van ${instelling}`)
    .replace('bij ons', `bij ${instelling}`)
}

function SuggestedCategory({ category, questions, onSend, busy, instelling }) {
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
          {questions.map(q => {
            const label = personalizeQuestion(q, instelling)
            return <button key={q} className="suggested-btn" onClick={() => !busy && onSend(label)}>{label}</button>
          })}
        </div>
      )}
    </div>
  )
}
