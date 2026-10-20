import { memo, useId, useLayoutEffect, useMemo, useRef, useEffect, useState, useCallback } from 'react'
import Plot from '../components/LazyPlot'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import KolomKop from '../components/KolomKop'
import TabelScroll from '../components/TabelScroll'
import KaartTerugval from '../components/KaartTerugval'
import CitedNumber from '../components/CitedNumber'
import { rehypeCitaties } from '../citations'
import { chatFigureLayout, figureHeight, isMapFigure } from '../figureLayout'
import { KAART_HOOGTE } from '../kaartBeeld'
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
import { useEscape } from '../hooks/useEscape'
import { useDarkMode } from '../hooks/useDarkMode'
import { useElementWidth } from '../hooks/useElementWidth'
import { useKaartStatus } from '../hooks/useKaartStatus'
import { useDocumentTitle, pageTitle } from '../hooks/useDocumentTitle'
import ReasoningStep from '../components/ReasoningStep'
import { markRecovered } from '../toolSteps'
import { useMediaQuery, NARROW_SCREEN } from '../hooks/useMediaQuery'
import { MAX_CHAT_TURNS, WARN_CHAT_TURNS, MAX_MESSAGE_CHARS } from '../constants'
import { saveWorkbookWithSync } from '../workbooks'
import { pickModel, loadModelChoice, saveModelChoice, conversationModel } from '../modelChoice'
import { canGenerateReport, lastDataQuestion } from '../reportEligibility'
import { answerModels } from '../answerModel'
import { personalizeQuestion, suggestionsFor } from '../suggestions'
import { PERSOONSGEGEVENS_WAARSCHUWING } from '../persoonsgegevens'
import {
  appendPage, clearCurrentChat, conversationMessages, conversationRecord, HISTORY_FETCH_LIMIT, historyPage,
  loadConversationHistory, loadCurrentChat, newConversationId, nextPageQuery, persistConversationHistory,
  persistCurrentChat, upsertConversation,
} from '../conversationStore'
import { getToken, sessionEndedSince } from '../auth'
import { isOpgeslagen, noteerOpgeslagen, volgOpslag } from '../gesprekOpslag'
import { uitgesteldeVerwijdering, terugInLijst, UITSTEL_MS } from '../verwijderenMetUitstel'
import { isVerwijderd, markeerVerwijderd } from '../verwijderdGesprek'
import {
  fetchConversation, fetchConversations, putConversation, renameConversationApi, deleteConversationApi, fetchSettingsConfig,
} from '../api'
import { buildReportHtml } from '../reportHtml'
import { figureToCsv, figureCsvProblem, figureCsvFilename } from '../figureCsv'
import { figuurBeschrijving } from '../figuurBeschrijving'
import { saveFile } from '../saveFile'
import DataExport from '../components/DataExport'
import AnswerBlocks from '../components/AnswerBlocks'
import IngetrokkenVersies from '../components/IngetrokkenVersies'
import { hasExport, roundSettled } from '../dataExport'
import { groepeerFiguren } from '../figuurGroep'
import ConversationExport from '../components/ConversationExport'
import ChatNavActies from '../components/ChatNavActies'
import ModelPicker from '../components/ModelPicker'
import AnswerFeedback from '../components/AnswerFeedback'
import CopyButton from '../components/CopyButton'
import { useAnswerFeedback } from '../hooks/useAnswerFeedback'
import DataSourcesModal from '../components/DataSourcesModal'
import PrivacyLink from '../components/PrivacyLink'
import FeedbackLink from '../components/FeedbackLink'
import { relatieveDatum } from '../relatieveDatum'
import { inVolgorde, noteerGesprek, useRecent } from '../recentBekeken'
import ConfirmModal from '../components/ConfirmModal'
import ScrollToBottom from '../components/ScrollToBottom'
import useAutoScroll from '../hooks/useAutoScroll'
import Composer from '../components/Composer'
import ErrorRetry, { offersRetry } from '../components/ErrorRetry'
import RunProgress, { countRunSteps, currentRunStep, heavyRun } from '../components/RunProgress'
import ReportProgress from '../components/ReportProgress'
import ClarificationButtons from '../components/ClarificationButtons'
import { clarificationAnswer, hasOpenClarification, originalQuestion } from '../clarificationState'
import { useConversationSearch } from '../hooks/useConversationSearch'
import { splitsTelling } from '../telling'
import { answerBlocks, metBronnen } from '../answerBlocks'
import { vervolgvragenTekst } from '../vervolgvragen'
import { platteTekst } from '../platteTekst'
import { welkomstSub } from '../functies'

function codeTheme() {
  return document.documentElement.classList.contains('dark') ? oneDark : oneLight
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
  table: TabelScroll,
  th: KolomKop,
  span: CitedNumber,
}

// The answer of the last turn, which carries its follow-up questions (#364). A chart arrives as a
// message of its own after the answer (shown inside the answer, figuurGroep.js), so it does not count.
function lastAnswerIndex(messages) {
  return messages.findLastIndex(m => m.role === 'assistant' && !m.figures?.length)
}

// Announced once an answer is complete; streaming deltas would flood a screen reader. As plain text,
// so it does not read out the markdown signs (#589).
function lastAnswerText(messages) {
  const last = messages.findLast(m => m.role !== 'assistant' || m.content)
  return last?.role === 'assistant' && last.done ? platteTekst(last.content) : ''
}

// The code of one step, behind "Bekijk code" (#595): one tap away, without filling the phone screen before the
// answer. Long lines wrap instead of scrolling sideways.
function StapCode({ code }) {
  const thema = codeTheme()
  return (
    <details className="reasoning-step-code">
      <summary>Bekijk code</summary>
      <SyntaxHighlighter
        language="python"
        style={thema}
        wrapLongLines
        // The theme sets white-space: pre on the code element, which beats wrapLongLines.
        codeTagProps={{ style: { ...thema['code[class*="language-"]'], whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' } }}
        customStyle={{ margin: '4px 0 0', padding: 8, fontSize: 'var(--font-code)', background: 'var(--white)', border: '1px solid var(--gray-200)', borderRadius: 6 }}
      >
        {code}
      </SyntaxHighlighter>
    </details>
  )
}

// De hoogte van de open stappenlijst als de kop van de kaart in beeld staat (#609); 0 als de kaart boven of onder
// het beeld ligt, of als er niets te meten is (jsdom). Met de kop in beeld verankert de browser de scroll aan de kop
// en niet aan wat eronder wegvalt, dus dan compenseert ReasoningPanel zelf.
function zichtbareKaarthoogte(panel) {
  const content = panel?.querySelector('.reasoning-content')
  const scroller = panel?.closest('.chat-messages')
  if (!content || !scroller) return 0
  const kop = panel.getBoundingClientRect()
  const zicht = scroller.getBoundingClientRect()
  const inBeeld = kop.top >= zicht.top && kop.top < zicht.bottom
  return inBeeld ? content.getBoundingClientRect().height : 0
}

function ReasoningPanel({ tools, tussentekst, isDone }) {
  const [open, setOpen] = useState(!isDone) // Auto-open while tools are running
  // On a phone the code sits under its own step, folded (#595); in one block under the steps it filled the
  // screen before the answer. A wide screen keeps the block.
  const codePerStap = useMediaQuery(NARROW_SCREEN)
  const panelRef = useRef(null)
  // Wie de kaart zelf open- of dichtdeed, houdt die stand (#609): het inklappen hieronder is alleen voor de kaart
  // die vanzelf openging bij het wachten.
  const handmatig = useRef(false)
  // Op een telefoon klapt de kaart in zodra het antwoord compleet is (#609): open bleef hij 380–430 px hoog en begon
  // het antwoord onder de vouw. Desktop ongewijzigd. Staat de kaart in beeld, dan zou het antwoord eronder omhoog
  // springen (layout-shift, #594): de scroller compenseert de weggevallen hoogte en schuift daarna vloeiend naar
  // de dichte kop, zodat het begin van het antwoord in beeld komt zonder sprong. Ligt de kaart boven het beeld
  // (de lezer is al bij het eind), dan houdt de scroll-verankering van de browser alles op zijn plek.
  const compensatie = useRef(0)
  useLayoutEffect(() => {
    if (!isDone || !codePerStap || !open || handmatig.current) return
    compensatie.current = zichtbareKaarthoogte(panelRef.current)
    setOpen(false)
  }, [isDone, codePerStap, open])
  useLayoutEffect(() => {
    if (open || !compensatie.current) return
    const scroller = panelRef.current?.closest('.chat-messages')
    if (scroller) {
      scroller.scrollTop -= compensatie.current
      panelRef.current.scrollIntoView({ block: 'start', behavior: 'smooth' })
    }
    compensatie.current = 0
  }, [open])
  if (!tools?.length) return null
  const hasSnippets = tools.some(t => t.snippet)
  const toggle = () => { handmatig.current = true; setOpen(o => !o) }

  return (
    <div className="reasoning-panel" ref={panelRef}>
      <button type="button" className="reasoning-toggle" onClick={toggle} aria-expanded={open}>
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
          {markRecovered(tools).map((t, i) => (
            <ReasoningStep key={`${t.name}-${i}`} tool={t}>
              {codePerStap && t.snippet && <StapCode code={t.snippet} />}
            </ReasoningStep>
          ))}
          {/* What the model wrote between tool rounds: worth a look, but no answer (#393). */}
          {tussentekst?.map((tekst, i) => (
            <p key={i} className="reasoning-tussentekst">{tekst}</p>
          ))}
          {hasSnippets && !codePerStap && (
            <div className="reasoning-snippets">
              {tools.map((t, i) => (
                t.snippet && (
                  <div key={`${t.name}-${i}`} className="reasoning-snippet-block">
                    <div className="reasoning-snippet-label">{t.label}</div>
                    <SyntaxHighlighter
                      language="python"
                      style={codeTheme()}
                      customStyle={{ margin: 0, background: 'transparent', padding: 0, fontSize: 'var(--font-code)' }}
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

// Parsing markdown is the costly part of a message; props are stable while a message is unchanged.
const Markdown = memo(function Markdown({ text, citaties }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeCitaties(citaties)]}
      components={MARKDOWN_COMPONENTS}
    >
      {text}
    </ReactMarkdown>
  )
})

// Het Telling-blok van de backend: de eerste zin, de rest uitklapbaar (#402). Onder de vaste
// bouwstenen (#416) staat het label er al naast; dan zonder eigen kop.
function TellingDetails({ msg, kop = true }) {
  const { telling, samenvatting } = splitsTelling(msg.content)
  if (!telling) return null
  return (
    <details className="telling">
      <summary>{kop ? <><strong>Telling</strong> {samenvatting}</> : samenvatting || 'Toon de telling'}</summary>
      <Markdown text={telling} citaties={msg.citaties} />
    </details>
  )
}

function MessageContent({ msg, blocks = null }) {
  if (isAwaitingFirstToken(msg)) return <div className="ai-typing"><span /><span /><span /></div>
  if (!msg.content && !msg.figures?.length && !msg.clarification && !msg.starterQuestions) return null
  const { antwoord, telling } = splitsTelling(msg.content)
  if (!telling) return <Markdown text={msg.content} citaties={msg.citaties} />
  return (
    <>
      <Markdown text={antwoord} citaties={msg.citaties} />
      {/* Met de vaste bouwstenen staat de Telling daar, op een vaste plek (#416). */}
      {!blocks && <TellingDetails msg={msg} />}
    </>
  )
}

export default function ChatPage({ openRapport, settings = {}, sector = null, user, feedbackEnabled = false, maxMessageChars = MAX_MESSAGE_CHARS, teOpenenGesprek = null, onGesprekGeopend }) {
  useDocumentTitle(pageTitle('Chat'))
  const { messages, withBufferedText, busy, slow, rejectedDraft, clearRejectedDraft, thinking, connected, resetting, historyDataKeys, toasts, reportBusy, reportProgress, reportSpec, send, sendClarification, sendSettings, sendHistory, stop, generateReport, cancelReport, clearReport, clear, startNewConversation, addToast } = useChat()
  // A question on its way into the input box, not sent: a follow-up question picked under the last
  // answer (#364), or the question behind a clarification card ("Anders formuleren", #494).
  const [prefill, setPrefill] = useState(null)
  const prefillComposer = useCallback(tekst => setPrefill({ tekst }), [])
  const clearPrefill = useCallback(() => setPrefill(null), [])
  // "Opnieuw" under an error sends past the composer; when send() refuses it, the composer says why (#585).
  const [refusal, setRefusal] = useState(null)
  const clearRefusal = useCallback(() => setRefusal(null), [])
  const [models, setModels] = useState([])
  const [selectedModel, setSelectedModel] = useState('')
  const [defaultModel, setDefaultModel] = useState('')
  const [showSources, setShowSources] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  useEscape(sidebarOpen, () => setSidebarOpen(false))
  // Below the breakpoint the sidebar is a drawer: closed, it is out of reach (inert), and the
  // welcome block carries the suggestions instead, so they are never in the page twice (#341).
  const narrowScreen = useMediaQuery(NARROW_SCREEN)
  const [initialChat] = useState(loadCurrentChat)
  // Uitloggen en sessie-einde wissen de opslag vóór deze pagina unmount. Een save of
  // fetch-resultaat dat React daarna nog uitvoert, mag het gesprek van de vorige
  // gebruiker niet terugschrijven (#507, zelfde race als useDashboardChat bij #498).
  const [tokenAtMount] = useState(getToken)
  const [conversationId, setConversationId] = useState(initialChat.id)
  const [restoredMessages, setRestoredMessages] = useState(initialChat.messages)
  const [conversationHistory, setConversationHistory] = useState(loadConversationHistory)
  const historySearch = useConversationSearch()
  const { results: zoekResultaten, removeResult, restoreResult } = historySearch
  const [hasMoreHistory, setHasMoreHistory] = useState(false)
  const [loadingMoreHistory, setLoadingMoreHistory] = useState(false)
  // The conversation being fetched to open it (#509); one at a time.
  const [openingId, setOpeningId] = useState(null)
  const [saveError, setSaveError] = useState(null)
  const [pendingDelete, setPendingDelete] = useState(null)
  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)
  const openChatRef = useRef(initialChat)
  // What the server has of the open conversation. A restored one only counts as saved when its last PUT
  // landed (#635): a reload during a question or a PUT while offline left it in this browser only.
  const savedJsonRef = useRef(null)
  if (savedJsonRef.current === null) {
    const json = JSON.stringify(initialChat.messages)
    savedJsonRef.current = isOpgeslagen(initialChat.id, json) ? json : ''
  }
  // Het verwijderde open gesprek (#530): geen lokale save schrijft het terug tot er een nieuw gesprek begint.
  const verwijderdRef = useRef(null)
  // The save in flight: answer feedback waits for it, the server reads the answer from it (#248).
  const savingRef = useRef(Promise.resolve())
  const initialHistorySentRef = useRef(false)

  // Ook de gesprekslijst kan op een vol quotum stuiten (#521). Eén melding per pagina, los
  // van die over het open gesprek; de lijst in het geheugen blijft staan, de server heeft alles.
  const lijstGemeldRef = useRef(false)
  const persistHistoryMetMelding = useCallback((list) => {
    if (persistConversationHistory(list) === 'ok' || lijstGemeldRef.current) return
    lijstGemeldRef.current = true
    addToast('De lokale opslag is vol: de gesprekslijst kan na verversen korter zijn.', 'warning')
  }, [addToast])

  // Een herstel zonder grafieken leek compleet (#521): zeg het één keer bij het openen.
  const onvolledigGemeldRef = useRef(false)
  useEffect(() => {
    if (!initialChat.onvolledig || onvolledigGemeldRef.current) return
    onvolledigGemeldRef.current = true
    addToast('Dit gesprek is niet volledig bewaard: grafieken ontbreken na verversen.', 'warning')
  }, [initialChat, addToast])

  // Seed backend with restored history on first connection
  useEffect(() => {
    if (!connected || initialHistorySentRef.current || !restoredMessages.length) return
    initialHistorySentRef.current = true
    sendHistory(restoredMessages, conversationId)
  }, [connected, restoredMessages, sendHistory, conversationId])

  // Load conversations from server on mount; migrate localStorage if server is empty
  useEffect(() => {
    fetchConversations({ limit: HISTORY_FETCH_LIMIT }).then(rows => {
      // Het antwoord kan na uitloggen binnenkomen; dan niets meer opslaan (#507).
      if (sessionEndedSince(tokenAtMount)) return
      if (rows.length > 0) {
        const { items, hasMore } = historyPage(rows)
        persistHistoryMetMelding(items)
        setConversationHistory(items)
        setHasMoreHistory(hasMore)
      } else {
        // Conversations from before the server copy; a cached list without messages has nothing to migrate (#509).
        const local = loadConversationHistory().filter(c => Array.isArray(c.messages))
        if (local.length > 0) {
          Promise.allSettled(local.map(c =>
            putConversation(String(c.id), { title: c.title, timestamp: c.timestamp, messages: c.messages })
          )).catch(() => {})
        }
      }
    }).catch(() => {})
  }, [tokenAtMount, persistHistoryMetMelding])

  // The unmount save runs after the last render, so it reads the open conversation from a ref.
  useEffect(() => {
    openChatRef.current = { id: conversationId, messages: [...restoredMessages, ...messages] }
  }, [conversationId, restoredMessages, messages])

  // Een vol quotum faalde stil (#511): meld het één keer; bij de terugval zonder
  // figuren blijft de tekst behouden en weet de gebruiker wat er na verversen mist.
  const quotaGemeldRef = useRef(false)
  const persistMetMelding = useCallback((id, all) => {
    const uitkomst = persistCurrentChat(id, all)
    if (uitkomst === 'ok' || quotaGemeldRef.current) return
    quotaGemeldRef.current = true
    addToast(uitkomst === 'zonder_figuren'
      ? 'De lokale opslag is bijna vol: grafieken van dit gesprek komen na verversen niet terug.'
      : 'De lokale opslag is vol: dit gesprek wordt niet lokaal bewaard.', 'warning')
  }, [addToast])

  // Persist full visible chat so it survives browser refresh / tab close.
  // Niet per tekstfragment (#511): tijdens het streamen verandert messages honderden
  // keren en elke keer het hele gesprek serialiseren groeit mee met de gesprekslengte.
  // Opslaan gebeurt bij elk afgerond antwoord (busy false) en bij pagehide hieronder.
  useEffect(() => {
    if (busy || sessionEndedSince(tokenAtMount)) return
    const all = [...restoredMessages, ...messages]
    if (all.length && !isVerwijderd(verwijderdRef.current, conversationId, all)) persistMetMelding(conversationId, all)
  }, [busy, conversationId, messages, restoredMessages, tokenAtMount, persistMetMelding])

  // Sluit de tab tijdens het streamen, dan is dit het laatste moment om te bewaren (#520).
  // Bij pagehide is de zichtbaarheid vaak nog 'visible' (Safari/iOS), dus die check hoort
  // alleen bij visibilitychange. De deltabuffer wordt meegelezen: een verborgen tab pauzeert
  // het frame dat hem leegt.
  useEffect(() => {
    const opslaan = () => {
      if (sessionEndedSince(tokenAtMount)) return
      const { id, messages: open } = openChatRef.current
      const all = withBufferedText(open)
      if (all.length && !isVerwijderd(verwijderdRef.current, id, all)) persistMetMelding(id, all)
    }
    const bijZichtbaarheid = () => {
      if (document.visibilityState === 'hidden') opslaan()
    }
    window.addEventListener('pagehide', opslaan)
    document.addEventListener('visibilitychange', bijZichtbaarheid)
    return () => {
      window.removeEventListener('pagehide', opslaan)
      document.removeEventListener('visibilitychange', bijZichtbaarheid)
    }
  }, [tokenAtMount, persistMetMelding, withBufferedText])

  // One record per conversation: each save overwrites it, and an unchanged conversation is not written again.
  // Sends the open conversation to the server and returns the updated history list, or null when
  // there is nothing new. It touches no state, so the unmount save can use it too (#521).
  // A deleted open conversation also returns null until a new question (#535); savedJsonRef stays
  // as it is then, so after an undo (which resets it) the next save writes the conversation again.
  const putOpenConversation = useCallback(() => {
    if (sessionEndedSince(tokenAtMount)) return null
    const { id, messages: all } = openChatRef.current
    if (isVerwijderd(verwijderdRef.current, id, all)) return null
    const record = conversationRecord(id, all)
    const json = JSON.stringify(all)
    if (!record || json === savedJsonRef.current) return null
    // A failed PUT does not count as saved (#635): the next chance (an answer, the connection back) sends it again.
    const vorige = savedJsonRef.current
    savedJsonRef.current = json
    savingRef.current = volgOpslag(putConversation(String(id), { title: record.title, timestamp: record.timestamp, messages: all }))
      .then(() => { if (!sessionEndedSince(tokenAtMount)) noteerOpgeslagen(id, json) }, () => {
        if (savedJsonRef.current === json) savedJsonRef.current = vorige
      })
    return upsertConversation(loadConversationHistory(), record)
  }, [tokenAtMount])

  // Returns the save in flight, so a caller can wait until the server has the conversation.
  const saveConversation = useCallback(() => {
    const updated = putOpenConversation()
    if (updated) {
      persistHistoryMetMelding(updated)
      setConversationHistory(updated)
    }
    return savingRef.current
  }, [putOpenConversation, persistHistoryMetMelding])
  const answerFeedback = useAnswerFeedback({ conversationId, enabled: feedbackEnabled, save: saveConversation })

  // Save every finished answer, so closing the tab loses nothing. Also when the connection is back: a save
  // that failed offline goes again then (#635); an unchanged conversation is not sent twice.
  useEffect(() => {
    if (!busy) saveConversation()
  }, [busy, connected, saveConversation])

  const handleClear = useCallback(() => {
    saveConversation()
    setRestoredMessages([])
    setSidebarOpen(false)
    clearCurrentChat()
    setConversationId(newConversationId())
    savedJsonRef.current = '[]'
    verwijderdRef.current = null
    // A new conversation starts on the user's own choice, not on the model of the one just open.
    setSelectedModel(pickModel(models, loadModelChoice(), defaultModel))
    startNewConversation()
  }, [startNewConversation, saveConversation, models, defaultModel])

  const openConversation = useCallback((conv) => {
    clear()
    setSidebarOpen(false)
    setConversationId(String(conv.id))
    const restored = conversationMessages(conv)
    savedJsonRef.current = JSON.stringify(restored)
    verwijderdRef.current = null
    setRestoredMessages(restored)
    // A follow-up continues on the model the conversation used, not on whatever the picker showed (#242).
    setSelectedModel(current => pickModel(models, conversationModel(restored), current))
    sendHistory(restored, String(conv.id))
  }, [clear, sendHistory, models])

  // The list holds no messages (#509): opening a conversation fetches it. The open conversation is
  // saved first and that save awaited, so reopening what was just asked never races its own PUT.
  const handleLoad = useCallback((conv) => {
    if (openingId) return
    setOpeningId(conv.id)
    Promise.resolve(saveConversation())
      .then(() => fetchConversation(String(conv.id)))
      .then(full => {
        if (sessionEndedSince(tokenAtMount)) return
        openConversation(full)
        noteerGesprek(full.id)
      })
      .catch(() => addToast('Gesprek openen is mislukt. Probeer het opnieuw.', 'error'))
      .finally(() => setOpeningId(null))
  }, [openingId, saveConversation, openConversation, addToast, tokenAtMount])

  // A conversation picked in the search palette (#602) opens here, once; App forgets it straight away.
  const handleLoadRef = useRef(handleLoad)
  useEffect(() => { handleLoadRef.current = handleLoad })
  useEffect(() => {
    if (!teOpenenGesprek) return
    onGesprekGeopend?.()
    handleLoadRef.current({ id: teOpenenGesprek })
  }, [teOpenenGesprek, onGesprekGeopend])

  // Older conversations stay on the server until asked for (#123).
  const handleLoadMoreHistory = useCallback(() => {
    if (!conversationHistory.length) return
    setLoadingMoreHistory(true)
    fetchConversations({ limit: HISTORY_FETCH_LIMIT, ...nextPageQuery(conversationHistory) })
      .then(rows => {
        if (sessionEndedSince(tokenAtMount)) return
        const { items, hasMore } = historyPage(rows)
        setConversationHistory(current => appendPage(current, items))
        setHasMoreHistory(hasMore)
      })
      .catch(() => addToast('Oudere gesprekken laden is mislukt. Probeer het opnieuw.', 'error'))
      .finally(() => setLoadingMoreHistory(false))
  }, [conversationHistory, addToast, tokenAtMount])

  const handleDeleteConversation = useCallback((id) => {
    setPendingDelete(id)
  }, [])

  // De DELETE gaat pas na de bedenktijd (#493); de lijst zonder het gesprek staat al lokaal.
  const conversationIdRef = useRef(conversationId)
  conversationIdRef.current = conversationId
  const sluitUndoToastRef = useRef(null)
  const verwijderingRef = useRef(null)
  if (!verwijderingRef.current) {
    verwijderingRef.current = uitgesteldeVerwijdering({
      voerUit: (conv) => {
        sluitUndoToastRef.current?.()
        sluitUndoToastRef.current = null
        deleteConversationApi(String(conv.id), { keepalive: true }).catch(() => {})
        // Het open gesprek: de lokale kopie gaat nu pas weg; wat op het scherm staat blijft tot een nieuw gesprek.
        // Kwam er binnen de bedenktijd een nieuwe vraag, dan is het weer een gesprek dat bewaard blijft (#535).
        const open = String(conv.id) === conversationIdRef.current
        if (open && isVerwijderd(verwijderdRef.current, conv.id, openChatRef.current.messages)) clearCurrentChat()
      },
    })
  }

  const ongedaanMaken = useCallback(() => {
    const hersteld = verwijderingRef.current.ongedaan()
    sluitUndoToastRef.current?.()
    sluitUndoToastRef.current = null
    if (!hersteld) return
    // Terug waar het stond: in de lijst en/of in de zoekresultaten (#529); een treffer buiten de lijst blijft eruit.
    const { lijst, zoek } = hersteld.index
    restoreResult(hersteld.conv, zoek)
    if (lijst >= 0) {
      const updated = terugInLijst(loadConversationHistory(), hersteld.conv, lijst)
      persistHistoryMetMelding(updated)
      setConversationHistory(updated)
    }
    // Was het het open gesprek, dan mag de volgende save het weer wegschrijven; de lokale kopie meteen (#530).
    if (String(hersteld.conv.id) !== conversationIdRef.current) return
    savedJsonRef.current = ''
    verwijderdRef.current = null
    if (sessionEndedSince(tokenAtMount)) return
    const { id, messages: open } = openChatRef.current
    const all = withBufferedText(open)
    if (all.length) persistMetMelding(id, all)
  }, [persistHistoryMetMelding, restoreResult, persistMetMelding, withBufferedText, tokenAtMount])

  const confirmDeleteConversation = useCallback(() => {
    if (!pendingDelete) return
    const index = conversationHistory.findIndex(c => c.id === pendingDelete)
    // Een zoektreffer hoeft niet in de geladen lijst te staan (#529): dan komt het gesprek uit de zoekresultaten.
    const zoekIndex = zoekResultaten?.findIndex(c => String(c.id) === String(pendingDelete)) ?? -1
    const conv = conversationHistory[index] ?? zoekResultaten?.[zoekIndex]
    if (index >= 0) {
      const updated = conversationHistory.filter(c => c.id !== pendingDelete)
      persistHistoryMetMelding(updated)
      setConversationHistory(updated)
    }
    // Deleting the open conversation must not bring it back on the next save; only a new question does.
    const openVerwijderd = String(pendingDelete) === conversationId
    if (openVerwijderd) savedJsonRef.current = JSON.stringify(openChatRef.current.messages)
    setPendingDelete(null)
    // Nergens meer te vinden (de zoekresultaten ververst?): nooit stil sluiten, de gebruiker denkt dat het weg is.
    if (!conv) {
      addToast('Gesprek verwijderen is mislukt. Probeer het opnieuw.', 'error')
      return
    }
    // Al bij het bevestigen, niet pas in voerUit: zo schrijft ook een pagehide binnen de bedenktijd
    // het gesprek niet terug, in welke volgorde de listeners ook lopen (#530).
    if (openVerwijderd) verwijderdRef.current = markeerVerwijderd(conversationId, openChatRef.current.messages)
    removeResult(conv.id)
    verwijderingRef.current.plan(conv, { lijst: index, zoek: zoekIndex })
    sluitUndoToastRef.current?.()
    sluitUndoToastRef.current = addToast('Gesprek verwijderd.', 'info', {
      duur: UITSTEL_MS,
      actie: { label: 'Ongedaan maken', onClick: ongedaanMaken },
    })
  }, [pendingDelete, conversationHistory, zoekResultaten, removeResult, conversationId, addToast, ongedaanMaken, persistHistoryMetMelding])

  // Tab sluiten of weg van deze pagina: een lopende bedenktijd eindigt dan meteen in de DELETE.
  useEffect(() => {
    const nu = () => verwijderingRef.current.nu()
    window.addEventListener('pagehide', nu)
    return () => {
      window.removeEventListener('pagehide', nu)
      nu()
    }
  }, [])

  const handleRenameConversation = useCallback((id, newTitle) => {
    const trimmed = newTitle.trim()
    if (!trimmed) return
    const previous = conversationHistory
    const updated = previous.map(c => c.id === id ? { ...c, title: trimmed } : c)
    persistHistoryMetMelding(updated)
    setConversationHistory(updated)
    renameConversationApi(String(id), trimmed).catch(() => {
      persistHistoryMetMelding(previous)
      setConversationHistory(previous)
      addToast('Hernoemen is mislukt. Probeer het opnieuw.', 'error')
    })
  }, [conversationHistory, addToast, persistHistoryMetMelding])

  // Save conversation on unmount (navigation away); clear current-chat key since it's now in history
  useEffect(() => () => {
    // Logging out unmounts this page after App cleared the stored history;
    // saving here would write the conversation straight back.
    if (sessionEndedSince(tokenAtMount)) return
    // No toast or state here: both live in the page that is going away. A full storage
    // was already reported by the save after each finished answer (#521).
    const updated = putOpenConversation()
    if (updated) persistConversationHistory(updated)
    clearCurrentChat()
  }, [putOpenConversation, tokenAtMount])

  const handleModelChange = useCallback((id) => {
    setSelectedModel(id)
    saveModelChoice(id)
  }, [])

  // Load available models once
  useEffect(() => {
    fetchSettingsConfig()
      .then(cfg => {
        const offered = cfg.models || []
        const own = pickModel(offered, loadModelChoice(), cfg.default_model || '')
        setModels(offered)
        setDefaultModel(cfg.default_model || '')
        setSelectedModel(pickModel(offered, conversationModel(initialChat.messages), own))
      })
      .catch(() => setModels([]))
  }, [initialChat])

  useEffect(() => {
    const s = chatSettings(selectedModel, settings.instelling, settings.functie)
    if (Object.keys(s).some(k => s[k])) sendSettings(s)
  }, [selectedModel, settings.instelling, settings.functie, sendSettings])

  useAutoScroll(messagesContainerRef, messages)

  // Opnieuw na een foutmelding (#333). Met een ander model gaan de instellingen eerst:
  // de server beantwoordt de vraag met het model uit zijn instellingen.
  const handleRetry = (question, modelId) => {
    if (modelId && modelId !== selectedModel) {
      handleModelChange(modelId)
      sendSettings(chatSettings(modelId, settings.instelling, settings.functie))
    }
    if (!send(question)) setRefusal({})
  }

  // De vraag achter het antwoord op index i opnieuw: na een herstart haalt alleen dat de data terug (CH-44).
  const herhaalVoor = i => {
    const vraag = questionBefore(displayMessages, i)?.content
    return vraag ? () => handleRetry(vraag) : null
  }

  // "Anders formuleren" op de kaart op index i (#494): de vraag gaat terug in de invoer, niet de deur uit.
  // Zonder vraag ervoor (een gesprek dat met de kaart begint) is er geen knop.
  const andersFormulerenVoor = i => {
    const vraag = originalQuestion(displayMessages, i)
    return vraag ? () => prefillComposer(vraag) : null
  }

  const handleMakeRapport = useCallback(() => {
    setSaveError(null)
    generateReport(user)
  }, [generateReport, user])

  // Save the generated report as a workbook when the spec arrives
  useEffect(() => {
    if (!reportSpec || sessionEndedSince(tokenAtMount)) return
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
  }, [reportSpec, settings?.instelling, openRapport, clearReport, tokenAtMount])

  const displayMessages = [...restoredMessages, ...messages]
  // Een grafiek staat in de bubbel van zijn antwoord, niet als bericht eronder (#610).
  const rijen = groepeerFiguren(displayMessages)
  const vervolgIndex = lastAnswerIndex(displayMessages)
  const modelLabels = answerModels(displayMessages, models)
  const hasMessages = displayMessages.length > 0
  const userTurnCount = displayMessages.filter(m => m.role === 'user' && !m.isError).length
  const atContextLimit = userTurnCount >= MAX_CHAT_TURNS
  const nearContextLimit = userTurnCount >= WARN_CHAT_TURNS
  const reportState = canGenerateReport(messages, restoredMessages, historyDataKeys)

  // Op een telefoon staat de knop onder het laatste antwoord, in de berichten (#596); op desktop in de statusrij.
  const rapportKnop = canGenerateReport(messages, restoredMessages, historyDataKeys) === 'ready' && (
    <button type="button" className="make-rapport-btn" onClick={handleMakeRapport} disabled={reportBusy}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
      </svg>
      {reportBusy ? 'Rapport wordt gegenereerd…' : 'Genereer rapport'}
    </button>
  )

  // A conversation with a question counts as opened in this browser (#603), also a new one.
  useEffect(() => { if (hasMessages) noteerGesprek(conversationId) }, [hasMessages, conversationId])
  const recent = useRecent()
  const gaVerder = inVolgorde(recent.gesprekken, conversationHistory).find(c => String(c.id) !== conversationId)

  return (
    <>
      <div className="toast-stack">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.level}`} role="status">
            {t.message}
            {t.actie && (
              <button type="button" className="toast-actie" onClick={t.actie.onClick}>{t.actie.label}</button>
            )}
          </div>
        ))}
      </div>
      <div className="chat-layout">
        {/* Sidebar overlay (mobile) */}
        {sidebarOpen && (
          <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} aria-hidden="true" />
        )}

        {/* Sidebar */}
        <aside className={`chat-sidebar${sidebarOpen ? ' open' : ''}`} inert={narrowScreen && !sidebarOpen}>
          <button type="button" className="new-chat-btn" onClick={handleClear}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Nieuw gesprek
          </button>
          {/* Op een telefoon staat de modelkeuze hier, niet in het invoerkader (#596). */}
          {narrowScreen && models.length > 0 && (
            <div className="sidebar-model">
              <div className="sidebar-section-title">Model</div>
              <ModelPicker models={models} value={selectedModel} onChange={handleModelChange} />
            </div>
          )}
          <div style={{ marginTop: 20 }}>
            <div className="sidebar-section-title" style={{ marginBottom: 10 }}>Suggestie vragen</div>
            <SuggestedQuestions onSend={send} busy={busy} instelling={settings.instelling} sector={sector} />
          </div>
          <ConversationHistory
            history={conversationHistory}
            hasMore={hasMoreHistory}
            loadingMore={loadingMoreHistory}
            openingId={openingId}
            onLoadMore={handleLoadMoreHistory}
            onLoad={handleLoad}
            onDelete={handleDeleteConversation}
            onRename={handleRenameConversation}
            search={historySearch}
          />
        </aside>

        {/* Main */}
        <div className="chat-main">
          <h1 className="sr-only">Chat</h1>
          {/* Op een telefoon staan de knoppen van de chat in de navbar, geen tweede balk eronder (#596). */}
          <ChatNavActies
            sidebarOpen={sidebarOpen}
            onToggleSidebar={() => setSidebarOpen(o => !o)}
            exportMessages={hasMessages ? displayMessages : null}
            feedback={feedbackEnabled}
          />

          <div className="sr-only" aria-live="polite">{busy ? '' : lastAnswerText(displayMessages)}</div>
          <div className="chat-messages" ref={messagesContainerRef}>
            {!hasMessages && (
              <WelcomeScreen instelling={settings.instelling} functie={settings.functie}>
                {/* The conversation this browser opened last (#603), only if it is one of this account. */}
                {gaVerder && (
                  <button type="button" className="ga-verder-chip" onClick={() => handleLoad(gaVerder)} disabled={!!openingId}>
                    Ga verder met <span className="ga-verder-titel">{gaVerder.title}</span>
                  </button>
                )}
                {/* On phones and tablets the sidebar is a drawer; without this, nobody finds the suggestions. */}
                {narrowScreen && (
                  <div className="chat-welcome-suggestions">
                    <SuggestedQuestions onSend={send} busy={busy} instelling={settings.instelling} sector={sector} />
                  </div>
                )}
              </WelcomeScreen>
            )}
            {restoredMessages.length > 0 && messages.length === 0 && (
              <div className="restored-banner">
                {hasOpenClarification(restoredMessages)
                  ? 'Ingeladen gesprek — kies een optie of stel een nieuwe vraag om door te gaan'
                  : 'Ingeladen gesprek — stel een nieuwe vraag om door te gaan'}
              </div>
            )}
            {rijen.map(({ msg, index: i, figures, laatsteId }) => (
              <Message
                key={msg.id} msg={msg} figures={figures} verbinding={connected}
                onClarification={sendClarification} onSend={send} busy={busy}
                onVervolgvraag={i === vervolgIndex && !atContextLimit ? prefillComposer : null}
                clarification={msg.clarification ? clarificationAnswer(displayMessages, i) : null}
                onAndersFormuleren={msg.clarification && !atContextLimit ? andersFormulerenVoor(i) : null}
                settings={settings} modelLabel={modelLabels[laatsteId] ?? modelLabels[msg.id]}
                settled={roundSettled(displayMessages, i, busy)}
                herhaal={msg.role === 'assistant' ? herhaalVoor(i) : null}
                retry={offersRetry(msg) ? {
                  question: questionBefore(displayMessages, i),
                  models, selectedModel, onRetry: handleRetry,
                  modelafhankelijk: msg.modelafhankelijk !== false,
                  // Een geweigerd rapport opnieuw (#515), alleen als er nu een rapport kan komen.
                  herstel: msg.herstel, onRapport: reportState === 'ready' ? handleMakeRapport : null,
                  reportBusy,
                } : null}
                feedback={feedbackEnabled && !busy && canJudge(msg) ? {
                  value: answerFeedback.oordelen[i] ?? null,
                  onSubmit: (oordeel, toelichting) => answerFeedback.submit(i, oordeel, toelichting),
                } : null}
              />
            ))}
            {thinking && (
              <div className="message assistant">
                <div className="message-avatar">AI</div>
                <div className="message-body">
                  <div className="message-bubble message-bubble-assistant">
                    <div className="ai-thinking">
                      <div className="ai-thinking-dots"><span /><span /><span /></div>
                      <span className="ai-thinking-label">AI denkt na...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
            {narrowScreen && hasMessages && !busy && rapportKnop && (
              <div className="chat-rapport-rij">{rapportKnop}</div>
            )}
            <div ref={messagesEndRef} />
            {/* Only a filled chat needs it; on the welcome screen it covered a suggestion (#592). */}
            {hasMessages && <ScrollToBottom sentinelRef={messagesEndRef} scrollContainerRef={messagesContainerRef} />}
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
            {/* Eén vaste statusrij (#594): tijdens een antwoord de voortgang, daarna de acties, op dezelfde
                hoogte. Onder de berichten zakte de voortgang bij elke stap mee met de redeneerkaart, en de
                acties die na het antwoord terugkwamen duwden het invoerveld 50 px omhoog, net toen je begon te
                lezen. De acties staan op één compacte rij (#527). */}
            {hasMessages && (
              <div className="chat-statusrij">
                {busy ? (
                  <RunProgress busy={busy} steps={countRunSteps(messages)} stepLabel={currentRunStep(messages)} heavy={heavyRun(messages)} slow={slow} />
                ) : !narrowScreen && (
                  <div className="chat-actions">
                    <ConversationExport messages={displayMessages} />
                    {rapportKnop}
                  </div>
                )}
              </div>
            )}
            {hasMessages && !busy && saveError && (
              <p style={{ color: '#DC2626', fontSize: 13, margin: '4px 0 0', textAlign: 'center' }}>
                Rapport opslaan mislukt: {saveError}
              </p>
            )}
            {/* Outside the button's conditions: whatever the chat does, the wait and its way out stay until the report ends (#417). */}
            <ReportProgress busy={reportBusy} progress={reportProgress} onCancel={cancelReport} />
            {/* Geen recept om de data uit te herladen: dan is de laatste datavraag opnieuw stellen de enige
                weg, met één klik in plaats van zelf een vraag verzinnen (#551). */}
            {hasMessages && !busy && reportState === 'needs_reload' && (
              <p className="report-reload-hint">
                De data van dit gesprek is niet meer geladen. Stel een vraag om haar opnieuw te laden, dan kun je een rapport genereren.
                {lastDataQuestion(restoredMessages) && (
                  <button type="button" className="message-continue" disabled={reportBusy}
                    onClick={() => send(lastDataQuestion(restoredMessages))}>
                    Stel de laatste vraag opnieuw
                  </button>
                )}
              </p>
            )}
            <Composer
              compact={narrowScreen}
              hasMessages={hasMessages}
              connected={connected}
              busy={busy}
              resetting={resetting}
              reportBusy={reportBusy}
              atContextLimit={atContextLimit}
              models={models}
              selectedModel={selectedModel}
              onModelChange={handleModelChange}
              onStop={stop}
              onSubmit={send}
              max={maxMessageChars}
              rejectedDraft={rejectedDraft}
              clearRejectedDraft={clearRejectedDraft}
              prefill={prefill}
              clearPrefill={clearPrefill}
              refusal={refusal}
              clearRefusal={clearRefusal}
            />
            {!narrowScreen && <p className="chat-disclaimer">openEDUdata+ gebruikt <button type="button" className="disclaimer-link" onClick={() => setShowSources(true)}>open onderwijsdata</button>. Controleer altijd de bronnen bij beleidsbeslissingen. {PERSOONSGEGEVENS_WAARSCHUWING} <PrivacyLink className="disclaimer-link" />{feedbackEnabled && <> · <FeedbackLink className="disclaimer-link" /></>}</p>}
          </div>
        </div>
      </div>

      {showSources && <DataSourcesModal onClose={() => setShowSources(false)} />}

      {pendingDelete && (
        <ConfirmModal
          message={GESPREK_VERWIJDEREN}
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
  return (
    <div className="chat-welcome">
      <div className="chat-welcome-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <h2>{greeting}</h2>
      <p>{welkomstSub(functie)}</p>
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

// Questions to click under a message. The "Verken …" starters send one at once (onPick = send); a
// follow-up question goes into the input box (#364). `label` names the group; with `kop` it also
// stands above the buttons.
function QuestionButtons({ questions, onPick, busy, label, kop = false }) {
  const kopId = useId()
  if (!questions?.length) return null
  const naam = kop ? { 'aria-labelledby': kopId } : { 'aria-label': label }
  return (
    <div className="clarification-btns question-buttons" role="group" {...naam}>
      {kop && <div id={kopId} className="question-buttons-kop">{label}</div>}
      {questions.map(q => (
        <button type="button" key={q} className="suggested-btn" onClick={() => !busy && onPick(q)}>{q}</button>
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

function chatSettings(model, instelling, functie) {
  const s = { model: model || undefined }
  if (instelling) s.instelling = instelling
  if (functie) s.functie = functie
  return s
}

// De gebruikersvraag waar het bericht op index i een antwoord op is.
function questionBefore(messages, i) {
  for (let j = i - 1; j >= 0; j--) {
    if (messages[j].role === 'user') return messages[j]
  }
  return null
}

// What the server can judge: a finished answer with text (core/answer_feedback.py).
const canJudge = msg => msg.role === 'assistant' && msg.done && !!msg.content && !msg.isError

// onVervolgvraag: only the last answer gets it; its follow-up questions then show while nothing runs (#364).
// onAndersFormuleren: a clarification card whose question is known gets it, also while something runs (#494).
// figures: de grafieken in deze bubbel; zonder opgave die van het bericht zelf (#610, figuurGroep.js).
// verbinding: of de chat nu verbonden is; een afgebroken antwoord zegt dan dat opnieuw proberen kan (#617).
export function Message({ msg, figures = null, verbinding = false, onClarification, onSend, busy, settled = true, settings = {}, retry = null, herhaal = null, modelLabel = null, clarification = null, feedback = null, onVervolgvraag = null, onAndersFormuleren = null }) {
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
            aria-label="Vraag opnieuw sturen"
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
  const figuren = figures ?? msg.figures ?? []
  const inhoud = hasAssistantContent(msg) || figuren.length > 0
  // A round with only data steps has no text, but its tables can still be downloaded.
  const exportable = settled && hasExport(msg)
  // A data answer gets its fixed building blocks; any other message renders as before (#416).
  const blocks = answerBlocks(msg, { settled })
  const dataExport = (
    <DataExport tools={msg.tools} citaties={msg.citaties} settled={settled} onHerhaal={herhaal || null} busy={busy} />
  )
  if (!awaiting && !msg.tools?.length && !msg.vervangen?.length && !inhoud) return null

  return (
    <div className="message assistant">
      <div className="message-avatar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 0 }}>
        <ReasoningPanel tools={msg.tools} tussentekst={msg.tussentekst} isDone={msg.done} />
        <IngetrokkenVersies versies={msg.vervangen} eindtekst={msg.content || ''} />
        {(awaiting || exportable || inhoud) && (
          <div className={`message-bubble message-bubble-assistant${msg.isError ? ' message-bubble-error' : ''}`}>
            {msg.content && <CopyButton text={metBronnen(msg.content, msg.bronnen)} className="copy-btn-message" />}
            <MessageContent msg={msg} blocks={blocks} />
            {/* Direct onder de tekst (#429): een ingehouden antwoord zegt "Hieronder staat wat er
                niet klopte", en grafieken met hun knoppen mogen daar niet tussen staan. */}
            {msg.controle?.map(zin => <div key={zin} className="message-controle">Let op: {zin}</div>)}
            {/* Vóór de blokken en de vervolgvragen: wat na de grafiek landt, verschuift hem niet (#610). */}
            {figuren.map((fig, i) => (
              <PlotlyFigure key={fig.label || i} figureJson={fig.json} label={fig.label} />
            ))}
            {blocks
              ? <AnswerBlocks blocks={blocks} msg={msg} telling={<TellingDetails msg={msg} kop={false} />} dataExport={dataExport} />
              : dataExport}
            <ClarificationButtons options={msg.clarification} onSelect={onClarification} busy={busy} answer={clarification} onAndersFormuleren={onAndersFormuleren}
              vraag={typeof msg.content === 'string' ? msg.content : null} />
            <QuestionButtons questions={msg.starterQuestions} onPick={onSend} busy={busy} label="Voorbeeldvragen" />
            {onVervolgvraag && !busy && (
              <QuestionButtons questions={vervolgvragenTekst(msg.vervolgvragen)} onPick={onVervolgvraag} busy={busy} label="Vervolgvragen" kop />
            )}
            {msg.stopped && <div className="message-stopped">Genereren gestopt</div>}
            {msg.truncated && (
              <div className="message-stopped">
                Antwoord afgebroken: de maximale lengte is bereikt.{' '}
                <button type="button" className="message-continue" onClick={() => onSend('Ga verder waar je gebleven was.')} disabled={busy}>
                  Ga verder
                </button>
              </div>
            )}
            {msg.interrupted && (
              /* Zodra de verbinding terug is, zegt de regel dat en licht de knop op (#617): wie in de trein weer
                 bereik heeft, hoeft de knop niet zelf te bedenken. Alleen als er een knop is (een ingeladen gesprek
                 zonder vraag ervoor heeft er geen); geen automatische tweede run (die telt mee in de berichtlimiet,
                 #444). aria-live: ook voor een schermlezer een melding, geen tweede knop. */
              <div className={`message-stopped${verbinding && herhaal ? ' verbinding-terug' : ''}`} role="status" aria-live="polite">
                {verbinding && herhaal ? 'Verbinding terug — probeer opnieuw' : 'Verbinding verbroken — antwoord onvolledig'}
                {/* Herstel bij de fout (#547, WCAG 3.3.3): de vraag ervoor opnieuw, zonder ander model. */}
                {herhaal && (
                  <>
                    {' '}
                    <button type="button" className={`message-continue${verbinding ? ' message-continue--licht' : ''}`} onClick={herhaal} disabled={busy}>
                      Probeer opnieuw
                    </button>
                  </>
                )}
              </div>
            )}
            {msg.empty && <div className="message-stopped">Geen antwoord ontvangen — stuur je vraag opnieuw</div>}
            {retry && (
              <ErrorRetry
                question={retry.question?.content}
                failedModel={retry.question?.model || retry.selectedModel}
                models={retry.models}
                modelafhankelijk={retry.modelafhankelijk}
                busy={busy || !!retry.reportBusy}
                onRetry={retry.onRetry}
                herstel={retry.herstel}
                onRapport={retry.onRapport}
              />
            )}
          </div>
        )}
        {modelLabel && <div className="message-model">Antwoord van {modelLabel}</div>}
        {feedback && <AnswerFeedback value={feedback.value} onSubmit={feedback.onSubmit} />}
      </div>
    </div>
  )
}

// Een rapport is een eigen kopie van het gesprek en blijft staan als het gesprek weg is (#513, besluit:
// informeren, niet meeverwijderen); wie dat niet wil, verwijdert het los op de rapportenpagina.
const GESPREK_VERWIJDEREN = 'Weet je zeker dat je dit gesprek wilt verwijderen? Een rapport dat je van dit gesprek ' +
  'hebt gemaakt, blijft bewaard; dat verwijder je los via Rapporten.'

function downloadCsv(csv, filename) {
  saveFile(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }), filename)
}

function parseFigure(figureJson) {
  try {
    return typeof figureJson === 'string' ? JSON.parse(figureJson) : figureJson
  } catch {
    return null
  }
}

const NO_TRACES = []
const PLOT_CONFIG = { responsive: true, displayModeBar: false }
// The chart's width in steps of 16 px: its title is broken again when a phone turns (#587), not
// for every pixel.
const WIDTH_STEP = 16

// react-plotly redraws when data, layout or config change by reference, and a redraw is costly. So
// everything handed to <Plot> is derived once per figure, theme and width step, not once per render.
const PlotlyFigure = memo(function PlotlyFigure({ figureJson, label }) {
  const dark = useDarkMode()
  const [wrapRef, width] = useElementWidth(WIDTH_STEP)
  const figure = useMemo(() => parseFigure(figureJson), [figureJson])
  const layout = useMemo(() => figure && chatFigureLayout(figure, dark, width), [figure, dark, width])
  const csv = useMemo(() => figure && figureToCsv(figure), [figure])
  const csvProblem = useMemo(() => figure && figureCsvProblem(figure), [figure])
  const beschrijving = useMemo(() => figure && figuurBeschrijving(figure), [figure])
  const isMap = Boolean(figure && isMapFigure(figure))
  const kaart = useKaartStatus(isMap)
  if (!figure) return null
  // Een kaart die niet getekend is, heet niet "Kaart aangemaakt" (#632): de melding en de tabel nemen haar plaats in.
  const kaartMislukt = isMap && kaart.status === 'mislukt'
  return (
    <div ref={wrapRef} style={{ margin: '8px 0', position: 'relative' }} className="plotly-figure-wrap">
      {label && <div style={{ fontSize: 'var(--font-klein)', color: 'var(--gray-500)', marginBottom: 4 }}>{kaartMislukt ? 'Kaart niet getekend' : label}</div>}
      {kaartMislukt && <KaartTerugval figure={figure} />}
      {csvProblem && (
        <div role="alert" style={{ fontSize: 'var(--font-klein)', color: 'var(--danger, #b42318)', marginBottom: 4 }}>
          Deze grafiek is niet te exporteren: {csvProblem}. Controleer de cijfers in het antwoord.
        </div>
      )}
      {csv && (
        <button type="button"
          className="csv-download-btn"
          title="Download als CSV"
          onClick={() => downloadCsv(csv, figureCsvFilename(figure, label || 'data'))}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          CSV
        </button>
      )}
      {/* The chart's accessible name (#588), on the chart only: role="img" makes its children
          presentational, and the CSV button above must stay a button. */}
      <div hidden={kaartMislukt} {...(beschrijving && { role: 'img', 'aria-label': beschrijving })}>
        <Plot
          data={figure.data || NO_TRACES}
          layout={layout}
          config={PLOT_CONFIG}
          useResizeHandler
          onInitialized={kaart.onInitialized}
          onError={kaart.onError}
          style={{ width: '100%', height: isMap ? KAART_HOOGTE : figureHeight(figure.layout, 340) }}
        />
      </div>
    </div>
  )
})

export function ConversationHistory({ history, hasMore = false, loadingMore = false, openingId = null, onLoadMore, onLoad, onDelete, onRename, search = null }) {
  const [editingId, setEditingId] = useState(null)
  const [editDraft, setEditDraft] = useState('')
  const titleInputRef = useRef(null)

  if (history.length === 0) return null

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

  // While there is a query, the hits replace the list (#124); they come from the server in one page.
  const searchActive = !!search?.query.trim()
  const shown = searchActive ? (search.results ?? []) : history
  let searchNote = null
  if (searchActive && search.error) searchNote = 'Zoeken lukt nu niet. Probeer het zo opnieuw.'
  else if (searchActive && search.searching && !search.results) searchNote = 'Zoeken…'
  else if (searchActive && !shown.length) searchNote = 'Geen gesprekken gevonden'

  return (
    <div style={{ marginTop: 24 }}>
      <div className="sidebar-section-title" style={{ marginBottom: 10 }}>Gesprek geschiedenis</div>
      {search && (
        <input
          type="search"
          className="history-search"
          placeholder="Zoek in gesprekken"
          aria-label="Zoek in gesprekken"
          value={search.query}
          onChange={e => search.setQuery(e.target.value)}
        />
      )}
      {searchNote && <p className="history-search-note" role="status">{searchNote}</p>}
      <div className="history-list">
        {shown.map(conv => (
          <div key={conv.id} className="history-item">
            <div className="history-item-row">
              <button type="button"
                className="history-btn"
                onClick={() => onLoad(conv)}
                disabled={openingId !== null}
                aria-busy={openingId === conv.id}
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
                    <span className="history-btn-title" title={conv.title}>{conv.title}</span>
                  )}
                  <span className="history-btn-date">{openingId === conv.id ? 'Openen…' : relatieveDatum(conv.timestamp)}</span>
                </div>
              </button>
              <div className="history-item-actions">
                <button type="button"
                  className="history-action-icon"
                  title="Hernoemen"
                  aria-label={`Hernoem gesprek ${conv.title}`}
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
                  aria-label={`Verwijder gesprek ${conv.title}`}
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
      {hasMore && !searchActive && (
        <button type="button" className="history-more-btn" onClick={onLoadMore} disabled={loadingMore}>
          {loadingMore ? 'Laden…' : 'Meer laden'}
        </button>
      )}
    </div>
  )
}

export function SuggestedQuestions({ onSend, busy, instelling, sector = null }) {
  // Without an institution only the general questions: "onze instelling" ended in a scope refusal (CH-42).
  return suggestionsFor(sector, { profiel: Boolean(instelling?.trim()) }).map(cat => (
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
