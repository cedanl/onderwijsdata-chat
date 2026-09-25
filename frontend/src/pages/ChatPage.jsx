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
import { SUGGESTED, MAX_TEXTAREA_HEIGHT, MAX_CHAT_TURNS, WARN_CHAT_TURNS } from '../constants'
import { saveWorkbookWithSync } from '../workbooks'
import { pickModel, loadModelChoice, saveModelChoice } from '../modelChoice'
import { canGenerateReport } from '../reportEligibility'
import { personalizeQuestion } from '../suggestions'
import {
  clearCurrentChat, conversationRecord, loadConversationHistory, loadCurrentChat, newConversationId,
  persistConversationHistory, persistCurrentChat, upsertConversation,
} from '../conversationStore'
import { getToken, sessionEndedSince } from '../auth'
import { fetchConversations, putConversation, renameConversationApi, deleteConversationApi, fetchSettingsConfig } from '../api'
import { buildReportHtml } from '../reportHtml'
import { figureToCsv } from '../figureCsv'
import DataSourcesModal from '../components/DataSourcesModal'
import ConfirmModal from '../components/ConfirmModal'
import ScrollToBottom from '../components/ScrollToBottom'
import ChatInputFooter from '../components/ChatInputFooter'

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
    <button type="button" className={`copy-btn ${className || ''}`} onClick={handleCopy} title="Kopieer" aria-label="Kopieer">
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

// Announced once an answer is complete; streaming deltas would flood a screen reader.
function lastAnswerText(messages) {
  const last = messages.findLast(m => m.role !== 'assistant' || m.content)
  return last?.role === 'assistant' && last.done ? last.content : ''
}

function ReasoningPanel({ tools, isDone }) {
  const [open, setOpen] = useState(!isDone) // Auto-open while tools are running
  if (!tools?.length) return null
  const hasSnippets = tools.some(t => t.snippet)
  
  return (
    <div className="reasoning-panel">
      <button type="button" className="reasoning-toggle" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 6 }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
        <span>Redenering ({tools.length} {tools.length === 1 ? 'stap' : 'stappen'})</span>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: 'auto', transform: open ? 'rotate(180deg)' : '' }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="reasoning-content">
          {tools.map((t, i) => (
            <div key={t.name || i} className="reasoning-step">
              <div className={`reasoning-step-dot${t.done ? ' done' : ''}`} />
              <span>{t.label}</span>
            </div>
          ))}
          {hasSnippets && (
            <div className="reasoning-snippets">
              {tools.map((t, i) => (
                t.snippet && (
                  <div key={t.name || i} className="reasoning-snippet-block">
                    <div className="reasoning-snippet-label">{t.label}</div>
                    <SyntaxHighlighter
                      language="python"
                      style={codeTheme()}
                      customStyle={{ margin: 0, background: 'transparent', padding: 0, fontSize: '0.7rem' }}
                    >
                      {t.snippet}
                    </SyntaxHighlighter>
                  </div>
                )
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function MessageContent({ msg }) {
  if (isAwaitingFirstToken(msg)) return <div className="ai-typing"><span /><span /><span /></div>
  if (!msg.content && !msg.figures?.length && !msg.clarification && !msg.starterQuestions) return null
  return <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>{msg.content}</ReactMarkdown>
}

export default function ChatPage({ openRapport, settings = {}, user }) {
  const handleUnauthorized = useCallback(() => window.location.reload(), [])
  const { messages, busy, thinking, connected, resetting, toasts, reportBusy, reportSpec, send, sendClarification, sendSettings, sendHistory, stop, generateReport, clearReport, clear, startNewConversation, addToast } = useChat({
    onUnauthorized: handleUnauthorized,
  })
  const [input, setInput] = useState('')
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [showSources, setShowSources] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [initialChat] = useState(loadCurrentChat)
  const [conversationId, setConversationId] = useState(initialChat.id)
  const [restoredMessages, setRestoredMessages] = useState(initialChat.messages)
  const [conversationHistory, setConversationHistory] = useState(loadConversationHistory)
  const [saveError, setSaveError] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)
  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)
  const textareaRef = useRef(null)
  const openChatRef = useRef(initialChat)
  const savedJsonRef = useRef(JSON.stringify(initialChat.messages))
  const initialHistorySentRef = useRef(false)

  // Seed backend with restored history on first connection
  useEffect(() => {
    if (!connected || initialHistorySentRef.current || !restoredMessages.length) return
    initialHistorySentRef.current = true
    sendHistory(restoredMessages)
  }, [connected, restoredMessages, sendHistory])

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

  // The unmount save runs after the last render, so it reads the open conversation from a ref.
  useEffect(() => {
    openChatRef.current = { id: conversationId, messages: [...restoredMessages, ...messages] }
  }, [conversationId, restoredMessages, messages])

  // Persist full visible chat so it survives browser refresh / tab close
  useEffect(() => {
    const all = [...restoredMessages, ...messages]
    if (all.length) persistCurrentChat(conversationId, all)
  }, [conversationId, messages, restoredMessages])

  // One record per conversation: each save overwrites it, and an unchanged conversation is not written again.
  const saveConversation = useCallback(() => {
    const { id, messages: all } = openChatRef.current
    const record = conversationRecord(id, all)
    const json = JSON.stringify(all)
    if (!record || json === savedJsonRef.current) return
    savedJsonRef.current = json
    const updated = upsertConversation(loadConversationHistory(), record)
    persistConversationHistory(updated)
    setConversationHistory(updated)
    putConversation(String(id), { title: record.title, timestamp: record.timestamp, messages: all }).catch(() => {})
  }, [])

  // Save every finished answer, so closing the tab loses nothing.
  useEffect(() => {
    if (!busy) saveConversation()
  }, [busy, saveConversation])

  const handleClear = useCallback(() => {
    saveConversation()
    setRestoredMessages([])
    setSidebarOpen(false)
    clearCurrentChat()
    setConversationId(newConversationId())
    savedJsonRef.current = '[]'
    startNewConversation()
  }, [startNewConversation, saveConversation])

  const handleLoad = useCallback((conv) => {
    saveConversation()
    clear()
    setSidebarOpen(false)
    setConversationId(String(conv.id))
    savedJsonRef.current = JSON.stringify(conv.messages)
    setRestoredMessages(conv.messages)
    sendHistory(conv.messages)
  }, [clear, saveConversation, sendHistory])

  const handleDeleteConversation = useCallback((id) => {
    setPendingDelete(id)
  }, [])

  const confirmDeleteConversation = useCallback(() => {
    if (!pendingDelete) return
    const updated = conversationHistory.filter(c => c.id !== pendingDelete)
    persistConversationHistory(updated)
    setConversationHistory(updated)
    deleteConversationApi(String(pendingDelete)).catch(() => {})
    // Deleting the open conversation must not bring it back on the next save; only a new question does.
    if (String(pendingDelete) === conversationId) savedJsonRef.current = JSON.stringify(openChatRef.current.messages)
    setPendingDelete(null)
  }, [pendingDelete, conversationHistory, conversationId])

  const handleRenameConversation = useCallback((id, newTitle) => {
    const trimmed = newTitle.trim()
    if (!trimmed) return
    const previous = conversationHistory
    const updated = previous.map(c => c.id === id ? { ...c, title: trimmed } : c)
    persistConversationHistory(updated)
    setConversationHistory(updated)
    renameConversationApi(String(id), trimmed).catch(() => {
      persistConversationHistory(previous)
      setConversationHistory(previous)
      addToast('Hernoemen is mislukt. Probeer het opnieuw.', 'error')
    })
  }, [conversationHistory, addToast])

  // Save conversation on unmount (navigation away); clear current-chat key since it's now in history
  useEffect(() => {
    const tokenAtMount = getToken()
    return () => {
      // Logging out unmounts this page after App cleared the stored history;
      // saving here would write the conversation straight back.
      if (sessionEndedSince(tokenAtMount)) return
      saveConversation()
      clearCurrentChat()
    }
  }, [saveConversation])

  const handleModelChange = useCallback((id) => {
    setSelectedModel(id)
    saveModelChoice(id)
  }, [])

  // Load available models once
  useEffect(() => {
    fetchSettingsConfig()
      .then(cfg => {
        const offered = cfg.models || []
        setModels(offered)
        setSelectedModel(pickModel(offered, loadModelChoice(), cfg.default_model || ''))
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
    // send() refuses while busy, resetting or reconnecting; the typed question then stays.
    if (!q || atContextLimit || !send(q)) return
    setInput('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
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

  const handleMakeRapport = useCallback(() => {
    setSaveError(null)
    generateReport(user)
  }, [generateReport, user])

  // Save the generated report as a workbook when the spec arrives
  useEffect(() => {
    if (!reportSpec) return
    const htmlContent = buildReportHtml(reportSpec, { instelling: settings?.instelling })
    const description = `Rapport door ${reportSpec.auteur || 'onbekend'} · gegenereerd op ${reportSpec.datum || ''}`
    saveWorkbookWithSync({
      title: reportSpec.title || 'Rapport',
      description,
      htmlContent,
      type: 'report',
    }).then(result => {
      if (result.ok) {
        openRapport?.(result.workbook)
      } else {
        setSaveError(result.error)
      }
      clearReport()
    })
  }, [reportSpec, settings?.instelling, openRapport, clearReport])

  const displayMessages = [...restoredMessages, ...messages]
  const hasMessages = displayMessages.length > 0
  const userTurnCount = displayMessages.filter(m => m.role === 'user' && !m.isError).length
  const atContextLimit = userTurnCount >= MAX_CHAT_TURNS
  const nearContextLimit = userTurnCount >= WARN_CHAT_TURNS

  return (
    <>
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.level}`}>{t.message}</div>
      ))}
      <div className="chat-layout">
        {/* Sidebar overlay (mobile) */}
        {sidebarOpen && (
          <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
        )}

        {/* Sidebar */}
        <aside className={`chat-sidebar${sidebarOpen ? ' open' : ''}`}>
          <button type="button" className="new-chat-btn" onClick={handleClear}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Nieuw gesprek
          </button>
          <div style={{ marginTop: 20 }}>
            <div className="sidebar-section-title" style={{ marginBottom: 10 }}>Suggestie vragen</div>
            <SuggestedQuestions onSend={send} busy={busy} instelling={settings.instelling} />
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
          <h1 className="sr-only">Chat</h1>
          {/* Mobile topbar with hamburger */}
          <div className="chat-mobile-topbar">
            <button type="button" className="hamburger-btn" onClick={() => setSidebarOpen(o => !o)} aria-label="Menu">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 20, height: 20 }}>
                <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <span className="chat-mobile-topbar-title">openEDUdata+</span>
          </div>

          <div className="sr-only" aria-live="polite">{busy ? '' : lastAnswerText(displayMessages)}</div>
          <div className="chat-messages" ref={messagesContainerRef}>
            {!hasMessages && (
              <WelcomeScreen instelling={settings.instelling} functie={settings.functie}>
                {/* On phones and tablets the sidebar is a drawer; without this, nobody finds the suggestions. */}
                <div className="chat-welcome-suggestions">
                  <SuggestedQuestions onSend={send} busy={busy} instelling={settings.instelling} />
                </div>
              </WelcomeScreen>
            )}
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
            {thinking && (
              <div className="message assistant">
                <div className="message-avatar">AI</div>
                <div className="message-body">
                  <div className="message-bubble" style={{ background: 'transparent', boxShadow: 'none' }}>
                    <div className="ai-thinking">
                      <div className="ai-thinking-dots"><span /><span /><span /></div>
                      <span className="ai-thinking-label">AI denkt na...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
            <ScrollToBottom sentinelRef={messagesEndRef} scrollContainerRef={messagesContainerRef} />
          </div>

          <div className="chat-input-area">
            {atContextLimit && (
              <div className="context-limit-banner context-limit-banner--full">
                Chat is vol ({MAX_CHAT_TURNS} berichten). Begin een nieuw gesprek om door te gaan.
              </div>
            )}
            {!atContextLimit && nearContextLimit && (
              <div className="context-limit-banner context-limit-banner--warn">
                Chat raakt vol ({userTurnCount}/{MAX_CHAT_TURNS} berichten). Overweeg een nieuw gesprek te starten.
              </div>
            )}
            {hasMessages && !busy && canGenerateReport(messages, restoredMessages) === 'ready' && (
              <div>
                <button type="button" className="make-rapport-btn" onClick={handleMakeRapport} disabled={reportBusy}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
                  </svg>
                  {reportBusy ? 'Rapport wordt gegenereerd…' : 'Genereer rapport'}
                </button>
                {saveError && (
                  <p style={{ color: '#DC2626', fontSize: 13, margin: '4px 0 0' }}>
                    Rapport opslaan mislukt: {saveError}
                  </p>
                )}
              </div>
            )}
            {hasMessages && !busy && canGenerateReport(messages, restoredMessages) === 'needs_reload' && (
              <p className="report-reload-hint">
                Stel eerst een vraag om de data opnieuw te laden, dan kun je een rapport genereren.
              </p>
            )}
            <div className="chat-input-wrap">
              <textarea
                ref={textareaRef}
                className="chat-input"
                aria-label="Chatbericht"
                rows={1}
                placeholder={hasMessages ? 'Stel een vervolgvraag...' : 'Bijv. hoeveel mbo-studenten zijn er in mijn regio?'}
                value={input}
                onChange={e => { setInput(e.target.value); autoResize(e) }}
                onKeyDown={handleKey}
              />
              <ChatInputFooter
                connected={connected}
                busy={busy}
                models={models}
                selectedModel={selectedModel}
                onModelChange={handleModelChange}
                onStop={stop}
                onSend={handleSend}
                canSend={Boolean(input.trim()) && connected && !busy && !resetting && !atContextLimit}
              />
            </div>
            <p className="chat-disclaimer">openEDUdata+ gebruikt <button type="button" onClick={() => setShowSources(true)} style={{ background: 'none', border: 'none', padding: 0, font: 'inherit', fontSize: 'inherit', color: 'var(--accent-text)', textDecoration: 'underline', cursor: 'pointer' }}>open onderwijsdata</button>. Controleer altijd de bronnen bij beleidsbeslissingen.</p>
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


function WelcomeScreen({ instelling, functie, children }) {
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
      {children}
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

function ClarificationButtons({ options, onSelect, busy }) {
  const [selected, setSelected] = useState(null)

  if (!options) return null

  const handleSelect = (label) => {
    if (busy || selected) return
    setSelected(label)
    onSelect(label)
  }

  return (
    <div className="clarification-btns">
      {options.map((opt, _i) => {
        const label = typeof opt === 'string' ? opt : opt.label
        const desc = typeof opt === 'object' ? opt.beschrijving : null
        const isSelected = selected === label
        return (
          <button type="button" key={label} className={`clarification-btn${isSelected ? ' selected' : ''}`} onClick={() => handleSelect(label)} disabled={busy || selected}>
            {isSelected ? '✓ ' : ''}{label}{desc ? ` — ${desc}` : ''}
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
      {questions.map((q, _i) => (
        <button type="button" key={q} className="suggested-btn" onClick={() => !busy && onSend(q)}>{q}</button>
      ))}
    </div>
  )
}

function hasAssistantContent(msg) {
  return !!(
    msg.content ||
    msg.figures?.length ||
    msg.clarification ||
    msg.starterQuestions ||
    msg.stopped ||
    msg.interrupted ||
    msg.empty
  )
}

// Started but nothing to show yet: render the typing dots instead of a bare avatar.
function isAwaitingFirstToken(msg) {
  return !msg.done && !msg.content && !msg.tools?.length && !msg.figures?.length
}

function Message({ msg, onClarification, onSend, busy, settings = {} }) {
  if (msg.role === 'user') {
    return (
      <div className="message user">
        <div className="message-avatar">{userInitials(settings)}</div>
        <div className="message-bubble">
          {msg.content && <CopyButton text={msg.content} className="copy-btn-message" />}
          {msg.content}
        </div>
        {!busy && (
          <button type="button"
            className="resend-btn"
            title="Opnieuw sturen"
            onClick={() => onSend(msg.content)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
            </svg>
          </button>
        )}
      </div>
    )
  }

  const awaiting = isAwaitingFirstToken(msg)
  if (!awaiting && !msg.tools?.length && !hasAssistantContent(msg)) return null

  return (
    <div className="message assistant">
      <div className="message-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 0 }}>
        <ReasoningPanel tools={msg.tools} isDone={msg.done} />
        {(awaiting || hasAssistantContent(msg)) && (
          <div className={`message-bubble message-bubble-assistant${msg.isError ? ' message-bubble-error' : ''}`}>
            {msg.content && <CopyButton text={msg.content} className="copy-btn-message" />}
            <MessageContent msg={msg} />
            {msg.figures?.map((fig, i) => (
              <PlotlyFigure key={fig.label || i} figureJson={fig.json} label={fig.label} />
            ))}
            <ClarificationButtons options={msg.clarification} onSelect={onClarification} busy={busy} />
            <StarterButtons questions={msg.starterQuestions} onSend={onSend} busy={busy} />
            {msg.stopped && <div className="message-stopped">Genereren gestopt</div>}
            {msg.truncated && (
              <div className="message-stopped">
                Antwoord afgebroken: de maximale lengte is bereikt.{' '}
                <button type="button" className="message-continue" onClick={() => onSend('Ga verder waar je gebleven was.')} disabled={busy}>
                  Ga verder
                </button>
              </div>
            )}
            {msg.controle?.map(zin => <div key={zin} className="message-stopped">Let op: {zin}</div>)}
            {msg.interrupted && <div className="message-stopped">Verbinding verbroken — antwoord onvolledig</div>}
            {msg.empty && <div className="message-stopped">Geen antwoord ontvangen — stuur je vraag opnieuw</div>}
          </div>
        )}
      </div>
    </div>
  )
}

function downloadCsv(csv, filename) {
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
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
  const legendBg = dark ? 'rgba(30,41,59,0.9)' : 'rgba(255,255,255,0.8)'
  const legendBorder = dark ? '#475569' : '#ddd'
  const layout = {
    ...figure.layout,
    paper_bgcolor: bg,
    plot_bgcolor: bg,
    margin: isMap ? { l: 0, r: 0, t: 32, b: 0 } : { l: 48, r: 24, t: 32, b: 40 },
    font: { family: 'system-ui, sans-serif', size: 12, color: fontColor },
    legend: {
      ...figure.layout?.legend,
      bgcolor: legendBg,
      bordercolor: legendBorder,
      font: { color: fontColor },
    },
    autosize: true,
  }
  const csv = figureToCsv(figure)
  return (
    <div style={{ margin: '8px 0', position: 'relative' }} className="plotly-figure-wrap">
      {label && <div style={{ fontSize: '.75rem', color: 'var(--gray-500)', marginBottom: 4 }}>{label}</div>}
      {csv && (
        <button type="button"
          className="csv-download-btn"
          title="Download als CSV"
          onClick={() => downloadCsv(csv, (label || 'data').replace(/[^a-zA-Z0-9]/g, '_') + '.csv')}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          CSV
        </button>
      )}
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
    // Locally-created timestamps are ms (Date.now()); the backend normalizes
    // and returns them in seconds (persistence/db.py's _normalize_ts). Same
    // > 1e12 heuristic as the backend uses, so either source renders correctly.
    const tsMs = ts > 1e12 ? ts : ts * 1000
    const diff = Date.now() - tsMs
    const days = Math.floor(diff / 86400000)
    if (days === 0) return 'Vandaag'
    if (days === 1) return 'Gisteren'
    return new Date(tsMs).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' })
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
              <button type="button"
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
                      className="title-edit-input"
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
                <button type="button"
                  className="history-action-icon"
                  title="Hernoemen"
                  onClick={e => startEditing(conv, e)}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                </button>
                <button type="button"
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

function SuggestedQuestions({ onSend, busy, instelling }) {
  return SUGGESTED.map(cat => (
    <SuggestedCategory key={cat.category} category={cat.category} questions={cat.questions} onSend={onSend} busy={busy} instelling={instelling} />
  ))
}

function SuggestedCategory({ category, questions, onSend, busy, instelling }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="suggested-category">
      <button type="button" className="suggested-category-btn" onClick={() => setOpen(o => !o)}>
        <span>{category}</span>
        <svg className={`suggested-category-chevron${open ? ' open' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="suggested-list">
          {questions.map(q => {
            const label = personalizeQuestion(q, instelling)
            return <button type="button" key={q} className="suggested-btn" onClick={() => !busy && onSend(label)}>{label}</button>
          })}
        </div>
      )}
    </div>
  )
}
