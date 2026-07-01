import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import useDashboardChat from '../hooks/useDashboardChat'
import { saveWorkbookWithSync, getWorkbooks } from '../workbooks'
import { MIN_RESPONSE_LENGTH, MAX_TEXTAREA_HEIGHT } from '../constants'
import ModelPicker from './ModelPicker'

// ─── Helpers ─────────────────────────────────────────────────────────────────

const INSTELLING_REGIO = {
  'avans': 'Brabant', 'fontys': 'Brabant',
  'tilburg': 'Brabant', 'breda': 'Brabant',
  'hva': 'Amsterdam', 'amsterdam': 'Amsterdam', 'inholland': 'Amsterdam',
  'utrecht': 'Utrecht', 'hu ': 'Utrecht',
  'rotterdam': 'Rotterdam', 'hogeschool rotterdam': 'Rotterdam',
  'leiden': 'Zuid-Holland', 'delft': 'Zuid-Holland', 'haagse': 'Zuid-Holland',
  'hanze': 'Groningen', 'groningen': 'Groningen',
  'saxion': 'Oost-Nederland', 'windesheim': 'Overijssel',
  'arnhem': 'Gelderland', 'nijmegen': 'Gelderland', 'han': 'Gelderland',
  'zuyd': 'Limburg', 'maastricht': 'Limburg',
  'NHL': 'Friesland', 'stenden': 'Friesland', 'friesland': 'Friesland',
  'zeeland': 'Zeeland', 'vlissingen': 'Zeeland',
}

function getRegio(instelling) {
  if (!instelling) return 'de regio'
  const lower = instelling.toLowerCase()
  for (const [key, regio] of Object.entries(INSTELLING_REGIO)) {
    if (lower.includes(key.toLowerCase())) return regio
  }
  return 'de regio'
}

function buildExamples(instelling) {
  const naam = instelling || 'uw instelling'
  const regio = getRegio(instelling)
  return [
    `Hoeveel gediplomeerden levert ${naam} per jaar op ten opzichte van andere instellingen in ${regio}?`,
    `Hoe heeft de instroom bij ${naam} zich de afgelopen jaren ontwikkeld?`,
    `Hoe is het onderwijsaanbod van ${naam} verdeeld over sectoren als Economie, Zorg en Techniek?`,
  ]
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function DashboardCreator({ onSaved, instelling }) {
  const { messages, figures, busy, connected, send, sendClarification, sendSettings, reset, generateDashboard, generatingDashboard, dashboardSpec } = useDashboardChat()
  const [input, setInput] = useState('')
  const [followUp, setFollowUp] = useState('')
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    fetch('/api/settings/config')
      .then(r => r.json())
      .then(cfg => { setModels(cfg.models || []); setSelectedModel(cfg.default_model || '') })
      .catch(() => setModels([]))
  }, [])

  useEffect(() => {
    if (selectedModel) sendSettings({ model: selectedModel })
  }, [selectedModel, sendSettings])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const assistantMsgs = messages.filter(m => m.role === 'assistant')
  const lastAssistant = assistantMsgs[assistantMsgs.length - 1]
  // Show save when not streaming and there's any substantial assistant answer
  const hasResponse = !busy && messages.some(m => m.role === 'assistant' && !m.isError && (m.content?.length ?? 0) > MIN_RESPONSE_LENGTH)

  const handleSend = (text, clear = false) => {
    if (!text.trim() || busy) return
    if (clear) setInput('')
    else setFollowUp('')
    send(text.trim())
  }

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [pendingConfirm, setPendingConfirm] = useState(null)
  const [maxStep, setMaxStep] = useState(0)
  const prevBusyRef = useRef(false)

  useEffect(() => {
    const wasBusy = prevBusyRef.current
    prevBusyRef.current = busy
    if (busy && !wasBusy) setMaxStep(1)
    else if (!busy && wasBusy && hasResponse) setMaxStep(3)
    else if (!busy && wasBusy) setMaxStep(0)
  }, [busy, hasResponse])

  useEffect(() => {
    if (busy && figures.length > 0) setMaxStep(s => Math.max(s, 2))
  }, [figures.length, busy])

  useEffect(() => {
    if (messages.length === 0) setMaxStep(0)
  }, [messages.length])
  // pendingConfirm = { message: string, onConfirm: () => void } | null

  const handleSave = () => {
    if (saving || generatingDashboard) return
    setSaving(true)
    setSaveError(null)
    generateDashboard()
  }

  useEffect(() => {
    if (!dashboardSpec) return
    const doSave = async () => {
      try {
        const title = dashboardSpec.title || messages.find(m => m.role === 'user')?.content?.slice(0, 60) || 'Dashboard'
        const date = new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
        const result = await saveWorkbookWithSync({
          title,
          description: dashboardSpec.description || `Aangemaakt op ${date}`,
          dashboardSpec,
          instelling,
        })
        if (!result.ok) {
          setSaving(false)
          setSaveError(result.error || 'Opslaan mislukt')
          return
        }
        setSaving(false)
        reset()
        onSaved?.(result.workbook)
      } catch (err) {
        setSaving(false)
        setSaveError(`Fout bij opslaan: ${err.message}`)
      }
    }
    doSave()
  }, [dashboardSpec])

  const handleReset = () => {
    setPendingConfirm({
      message: 'Weet je zeker dat je dit gesprek wilt wissen?',
      onConfirm: () => { reset(); setInput(''); setFollowUp('') },
    })
  }

  const isEmpty = messages.length === 0

  return (
    <>
    {pendingConfirm && (
      <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
        <div style={{ background: 'var(--bg)', borderRadius: 12, padding: 24, maxWidth: 360, width: '90%', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
          <p style={{ marginBottom: 20, fontSize: '.95rem' }}>{pendingConfirm.message}</p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button onClick={() => setPendingConfirm(null)} style={{ padding: '8px 16px', borderRadius: 8, border: '1.5px solid var(--border)', background: 'none', cursor: 'pointer' }}>Annuleren</button>
            <button onClick={() => { pendingConfirm.onConfirm(); setPendingConfirm(null) }} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: '#DC2626', color: 'white', cursor: 'pointer', fontWeight: 600 }}>Wissen</button>
          </div>
        </div>
      </div>
    )}
    <div className="dc-wrap">
      <div className="dc-header">
        <div>
          <div className="section-label">Dashboard</div>
          <h2 className="section-title" style={{ fontSize: '1.3rem', margin: 0 }}>Cre&euml;er je eigen dashboard</h2>
        </div>
        {!isEmpty && (
          <button className="dc-reset-btn" onClick={handleReset}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
              <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.95"/>
            </svg>
            Opnieuw beginnen
          </button>
        )}
      </div>

      {isEmpty ? (
        <div className="dc-empty">
          <div className="dc-empty-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
            </svg>
          </div>
          <p>Beschrijf welke onderwijsdata je wilt zien. Kies zelf het onderwerp, de regio of de periode.</p>
          <div className="dc-examples">
            {buildExamples(instelling).map(ex => (
              <button key={ex} className="dc-example-btn" onClick={() => { setInput(ex); inputRef.current?.focus() }}>
                {ex}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="dc-conversation">
          {maxStep > 0 && (
            <div className="dc-steps">
              {[['Data ophalen', 1], ['Grafieken bouwen', 2], ['Klaar', 3]].map(([label, step]) => (
                <div key={step} className={`dc-step${maxStep >= step ? ' done' : ''}${maxStep === step && busy ? ' active' : ''}`}>
                  <div className="dc-step-node" />
                  {label}
                </div>
              ))}
            </div>
          )}
          {messages.map(msg => (
            <div key={msg.id} className={`dc-msg dc-msg-${msg.role}`}>
              {msg.role === 'assistant' && (
                <div className="dc-msg-avatar">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
                  </svg>
                </div>
              )}
              <div className={`dc-msg-bubble${msg.isError ? ' dc-msg-error' : ''}`}>
                {msg.toolLabel && (
                  <div className="dc-tool-label">
                    <span className="dc-tool-dot" />
                    {msg.toolLabel}
                  </div>
                )}
                {!msg.done && !msg.content && !msg.toolLabel
                  ? <div className="ai-typing"><span/><span/><span/></div>
                  : msg.content ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown> : null
                }
                {msg.clarification && (
                  <div className="dc-clarification-btns">
                    {msg.clarification.map((opt, i) => {
                      const label = typeof opt === 'string' ? opt : opt.label
                      return (
                        <button key={i} className="dc-clarification-btn" onClick={() => !busy && sendClarification(label)}>
                          {opt.aanbevolen ? '✓ ' : ''}{label}
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Input area */}
      <div className="dc-input-area">
        {isEmpty ? (
          <div className="dc-input-wrap">
            <textarea
              ref={inputRef}
              className="dc-textarea"
              rows={1}
              placeholder="Beschrijf welke data je wilt zien..."
              value={input}
              onChange={e => { setInput(e.target.value); e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, MAX_TEXTAREA_HEIGHT) + 'px' }}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(input, true) } }}
              disabled={busy}
            />
            <div className="dc-input-footer">
              {!connected && (
                <span className="ws-reconnecting">
                  <span className="ws-dot" />
                  Verbinding herstellen...
                </span>
              )}
              {models.length > 0 && <ModelPicker models={models} value={selectedModel} onChange={setSelectedModel} />}
              <button className="send-btn" onClick={() => handleSend(input, true)} disabled={!input.trim() || busy || !connected}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
                  <path d="M12 19V5M5 12l7-7 7 7"/>
                </svg>
              </button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {hasResponse && (
              <div className="dc-actions">
                <button className="dc-save-btn" onClick={handleSave} disabled={saving || generatingDashboard}>
                  {generatingDashboard ? (
                    <div className="ai-typing" style={{ display: 'inline-flex', gap: 3 }}><span/><span/><span/></div>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
                      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
                      <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
                    </svg>
                  )}
                  {generatingDashboard ? 'Dashboard genereren…' : 'Genereer dashboard'}
                </button>
                {saveError && <div style={{ color: '#DC2626', fontSize: '.8rem' }}>{saveError}</div>}
              </div>
            )}
            <div className="dc-input-wrap">
              <textarea
                className="dc-textarea"
                rows={1}
                placeholder="Stel een vervolgvraag..."
                value={followUp}
                onChange={e => { setFollowUp(e.target.value); e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, MAX_TEXTAREA_HEIGHT) + 'px' }}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(followUp) } }}
                disabled={busy}
              />
              <div className="dc-input-footer">
                {!connected && (
                  <span className="ws-reconnecting">
                    <span className="ws-dot" />
                    Verbinding herstellen...
                  </span>
                )}
                {models.length > 0 && <ModelPicker models={models} value={selectedModel} onChange={setSelectedModel} />}
                <button className="send-btn" onClick={() => handleSend(followUp)} disabled={!followUp.trim() || busy || !connected}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
                    <path d="M12 19V5M5 12l7-7 7 7"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
    </>
  )
}
