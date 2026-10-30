import { useState, useEffect, useRef, useCallback } from 'react'
import { chatSocket, checkSession, endSession } from '../auth'
import { trimHistory } from '../contextLimits'
import { zijnBronlinks } from '../bronLink'
import { finishStep } from '../toolSteps'
import { closeWithoutText, metDeeltekst, withdrawText } from '../turnTrace'
import { createHeartbeat, createRetry, opgevenBij, watchNetwork } from '../socketHealth'
import { vervolgvragenTekst } from '../vervolgvragen'
import { reportBlockReason } from '../reportBlockReason'

// A report without report_ready after this long counts as failed (#219). Reports take
// around five minutes (#417); the server has no limit of its own, so the wait ends here.
export const REPORT_TIMEOUT_MS = 10 * 60 * 1000
// How long the toast with the reason a report cannot start stays up (#648).
export const REASON_TOAST_MS = 4000

// A clarification question stays in: without it a restored choice ("2023/24") answers nothing (#109).
// An answer that was stopped or cut off by a dropped connection goes along marked `afgebroken`, even
// without text: the server then closes that turn, so the next question does not continue it (#548).
const afgebroken = m => !!(m.interrupted || m.stopped)

// Cut like the server (#789): at most maxHistory messages, the first question stays.
export function buildHistory(messages, maxHistory) {
  const history = messages
    .filter(m =>
      (m.role === 'user' || m.role === 'assistant') &&
      (m.content || afgebroken(m)) &&
      !m.isError &&
      !m.figures &&
      !m.starterQuestions
    )
    .map(m => ({ role: m.role, content: m.content || '', ...(afgebroken(m) && { afgebroken: true }) }))
  return trimHistory(history, maxHistory)
}

const NO_REPORT_PROGRESS = { steps: 0, label: null }

// maxHistory: the server's MAX_HISTORY from /api/config (#789); without it the constant.
export function useChat({ maxHistory } = {}) {
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [thinking, setThinking] = useState(false)
  // The server calls the current run slow after RUN_SLOW_S (#599); the next question starts without.
  const [slow, setSlow] = useState(false)
  const [toasts, setToasts] = useState([])
  const [connected, setConnected] = useState(false)
  // Geen eigen pogingen meer (#783): 'weg' na de laatste, 'te_veel' als de server nog een venster weigerde.
  const [opgegeven, setOpgegeven] = useState(null)
  const verbindOpnieuwRef = useRef(() => {})
  const [reportBusy, setReportBusy] = useState(false)
  const [reportSpec, setReportSpec] = useState(null)
  // Steps of the report run, shown while the report is being made (#339).
  const [reportProgress, setReportProgress] = useState(NO_REPORT_PROGRESS)
  const [resetting, setResetting] = useState(false)
  const [rejectedDraft, setRejectedDraft] = useState(null)
  // How many data keys the server restored for a reopened conversation (#472): its report can be made then.
  const [historyDataKeys, setHistoryDataKeys] = useState(0)
  const wsRef = useRef(null)
  const currentMsgRef = useRef(null)
  const reportingRef = useRef(false)
  // Asked for, but no report_generating yet: a busy or error in that window is the server refusing the report (#648).
  const reportRequestedRef = useRef(false)
  // De laatste instellingen: elke verbinding is een nieuwe serversessie en krijgt ze bij het openen (#756).
  const settingsRef = useRef(null)
  // Via a ref, so sendHistory stays the same function: a new one would send the open conversation again.
  const maxHistoryRef = useRef(maxHistory)
  useEffect(() => { maxHistoryRef.current = maxHistory })
  // Each question records the model it went out with, so a reopened conversation can resume it (#242).
  const modelRef = useRef(null)
  const idRef = useRef(0)
  const manualCloseRef = useRef(false)
  const busyRef = useRef(false)
  const lastSentRef = useRef(null)
  const currentHasTextRef = useRef(false)
  const resettingRef = useRef(false)
  const reportTimeoutRef = useRef(null)
  // text_delta's per animation frame bundelen (#510): 100+ fragmenten per seconde werden
  // 100+ renders, en react-markdown parset dan elke keer het hele groeiende antwoord.
  const deltaBufferRef = useRef('')
  const deltaFrameRef = useRef(null)
  // Een geplande flush annuleren én de ref leegmaken: `??=` plant anders nooit meer een frame
  // (na een StrictMode/HMR-remount of een clear() zou de tekst dan niet meer binnenkomen).
  const cancelDeltaFrame = useCallback(() => {
    if (deltaFrameRef.current === null) return
    cancelAnimationFrame(deltaFrameRef.current)
    deltaFrameRef.current = null
  }, [])
  // Het lopende antwoord mét de tekst die nog in de deltabuffer zit (#520): een verborgen tab
  // pauzeert requestAnimationFrame, dus `messages` loopt dan achter op wat al binnen is. Puur:
  // wie bewaart, leest de buffer mee zonder state-update af te wachten. Het lopende antwoord is
  // altijd het laatste bericht.
  const withBufferedText = useCallback((all) => {
    const tekst = deltaBufferRef.current
    const id = currentMsgRef.current
    if (!tekst || id === null) return all
    const i = all.findLastIndex(m => m.id === id)
    return i < 0 ? all : all.with(i, { ...all[i], content: all[i].content + tekst })
  }, [])
  // A report run that was stopped but not yet ended by the server: what it still sends is dropped.
  const reportAbandonedRef = useRef(false)
  // Per reason, until when its toast shows: quick taps during an outage stacked identical toasts (#648).
  const reasonToastUntilRef = useRef({})
  const nextId = () => ++idRef.current

  // The report is over, with or without a result: no more waiting, button free again.
  const endReport = useCallback(() => {
    clearTimeout(reportTimeoutRef.current)
    reportTimeoutRef.current = null
    reportingRef.current = false
    reportRequestedRef.current = false
    setReportBusy(false)
  }, [])

  // A failed report stays visible as a chat message; the button is the retry (#219).
  // Stop the report run: nothing it still sends may reach the user, until the server ends it.
  const abandonReport = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ action: 'stop' }))
    reportAbandonedRef.current = true
    endReport()
    setReportSpec(null)
  }, [endReport])

  // `herstel` names the way back the server offers (#515): 'rapport' means the report can be made again.
  const failReport = useCallback((message, herstel) => {
    endReport()
    setReportSpec(null)
    setMessages(prev => [...prev, {
      id: ++idRef.current, role: 'assistant', content: message, done: true, isError: true, ...(herstel && { herstel }),
    }])
  }, [endReport])

  // `opties.actie` ({ label, onClick }) zet een knop in de toast, `opties.duur` de tijd in ms (#493).
  // `duur: null` sluit hem niet vanzelf: dat doet de aanroeper, zoals de melding van een verwijdering
  // als de bedenktijd om is (die kan stilstaan, #776). `focus`, `pauzeer`, `hervat` en `verlaat` zijn
  // voor de ToastStack. Geeft een functie terug die de toast eerder weghaalt.
  const addToast = useCallback((message, level = 'info', opties = {}) => {
    const id = nextId()
    const weg = () => setToasts(t => t.filter(x => x.id !== id))
    const { focus = false, pauzeer = null, hervat = null, verlaat = null } = opties
    setToasts(t => [...t, { id, message, level, actie: opties.actie || null, focus, pauzeer, hervat, verlaat }])
    if (opties.duur !== null) setTimeout(weg, opties.duur || 4000)
    return weg
  }, [])

  // The open card ends without an answer: its steps stay as the turn's trace (#398).
  const closeCurrentMsg = useCallback(() => {
    if (!currentMsgRef.current) return
    const id = currentMsgRef.current
    setMessages(prev => prev.flatMap(m => m.id !== id ? [m] : (closeWithoutText(m) ?? [])))
    currentMsgRef.current = null
  }, [])

  useEffect(() => {
    manualCloseRef.current = false

    // Resolve the target id now: React runs the state updater later, by which
    // time message_end may already have cleared currentMsgRef.
    function updateCurrentMsg(updater) {
      const id = currentMsgRef.current
      if (id === null) return
      setMessages(prev => prev.map(m => m.id === id ? updater(m) : m))
    }

    function finishStream() {
      currentMsgRef.current = null
      busyRef.current = false
      setBusy(false)
    }

    // Gebufferde deltas als één state-update toepassen. Loopt vóór elk ander event leeg,
    // zodat message_end, message_cancel en de toolstappen hun vaste volgorde houden (#510).
    function flushDeltas() {
      cancelDeltaFrame()
      const tekst = deltaBufferRef.current
      deltaBufferRef.current = ''
      if (tekst) updateCurrentMsg(m => ({ ...m, content: m.content + tekst }))
    }

    // The server refused the report it was just asked for (#648): `busy` (its previous task still ran) or `error`
    // (the request limit). Both used to leave the button on "wordt gegenereerd" until the timeout (`error` was even
    // dropped as a stream event); now the wait ends at once and the user reads why.
    function refuseReport(ev) {
      endReport()
      const tekst = ev.message || 'Het rapport kon nu niet starten. Probeer het zo opnieuw.'
      addToast(tekst, ev.type === 'error' ? 'error' : 'warning', { duur: 8000 })
    }

    // The server session is gone with its socket, and so is the answer it was writing.
    function endInterruptedTurn() {
      if (!busyRef.current) return
      if (currentMsgRef.current) {
        updateCurrentMsg(m => metDeeltekst({ ...m, done: true, interrupted: true }))
      } else {
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant', done: true, isError: true,
          content: 'De verbinding viel weg voordat er een antwoord kwam. Stel je vraag opnieuw.',
        }])
      }
      setThinking(false)
      finishStream()
    }

    const messageHandlers = {
      system_message(ev) {
        addToast(ev.message, 'warning')
      },
      toast(ev) {
        addToast(ev.message, ev.level || 'info')
      },
      run_slow() {
        if (busyRef.current) setSlow(true)
      },
      history_data(ev) {
        setHistoryDataKeys(ev.data_keys || 0)
        // The server stopped the old run before it read the history frame: what comes now is this conversation's (#761).
        resettingRef.current = false
        setResetting(false)
      },
      // The server refused a question because a run is still going (#145): say so,
      // take the question back out of the transcript and give it back to the input.
      busy(ev) {
        addToast(ev.message, 'warning')
        const sent = lastSentRef.current
        lastSentRef.current = null
        setThinking(false)
        if (!sent) return
        // The refused question never became a run: nothing will end it, so the chat is free (#417).
        finishStream()
        setMessages(prev => prev.filter(m => m.id !== sent.id))
        if (sent.draft) setRejectedDraft(sent.content)
      },
      message_start() {
        lastSentRef.current = null
        setThinking(false)
        // Every model round announces itself. A round before the last one called tools: its
        // steps belong in the same reasoning card as the next round's (#76), and what it
        // wrote on the way ('We need to capture the result…') is no answer (#393).
        if (currentMsgRef.current !== null) {
          if (currentHasTextRef.current) {
            updateCurrentMsg(m => ({ ...m, content: '', tussentekst: [...(m.tussentekst || []), m.content] }))
            currentHasTextRef.current = false
          }
          return
        }
        currentHasTextRef.current = false
        const msgId = nextId()
        currentMsgRef.current = msgId
        setMessages(prev => [...prev, { id: msgId, role: 'assistant', content: '', tools: [], done: false }])
      },
      // The answer was withdrawn (correction or clarification): the next round writes on in
      // the same card, so the steps before and after the correction stay together (#398).
      message_cancel(ev) {
        currentHasTextRef.current = false
        updateCurrentMsg(m => withdrawText(m, ev.reden))
      },
      text_delta(ev) {
        currentHasTextRef.current = true
        setThinking(false)
        deltaBufferRef.current += ev.content
        deltaFrameRef.current ??= requestAnimationFrame(flushDeltas)
      },
      tool_start(ev) {
        setThinking(false)
        updateCurrentMsg(m => ({
          ...m, tools: [...m.tools, { name: ev.name, label: ev.label, done: false }],
        }))
      },
      tool_end(ev) {
        updateCurrentMsg(m => ({
          ...m,
          // The first step of this name still running: the same tool can run twice in one card.
          tools: m.tools.map((t, i, all) =>
            t.name === ev.name && !t.done && all.findIndex(x => x.name === ev.name && !x.done) === i
              ? finishStep(t, ev)
              : t
          ),
        }))
      },
      figure(ev) {
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant',
          content: '', figures: [{ label: ev.label, json: ev.figure_json }], done: true,
        }])
      },
      message_end(ev) {
        // The follow-up questions the server picked from the catalogue (#364).
        const vragen = vervolgvragenTekst(ev.vervolgvragen)
        // The server sends the full text; it wins over the accumulated deltas.
        updateCurrentMsg(m => {
          const content = typeof ev.content === 'string' ? ev.content : m.content
          return {
            ...m,
            content,
            done: true,
            ...(ev.aborted && { stopped: true }),
            // Stopped by the time limit, not by the stop button (#775): the reason stays with the message, with retry.
            ...(ev.timeout && { timeout: true, ...(typeof ev.stopreden === 'string' && { stopreden: ev.stopreden }) }),
            ...(ev.truncated && { truncated: true }),
            // Step budget spent: a partial answer, which another model often completes (#405).
            ...(ev.partial && { partial: true }),
            // A fixed answer from code, written by no model: no "Antwoord van <model>" under it (#565).
            ...(ev.vast === true && { vast: true }),
            // What the server's check on this answer still found wrong (#185, #187).
            ...(ev.controle?.length && { controle: ev.controle }),
            // Sentences in which the model revised itself go to the reasoning card, not the answer (#412).
            ...(ev.tussentekst?.length && { tussentekst: [...(m.tussentekst || []), ...ev.tussentekst] }),
            // The numbers that passed the check, each with the step it came from (#365).
            ...(ev.citaties?.length && { citaties: ev.citaties }),
            // The sources the server derived from the steps, also when empty: they mark a data answer (#416).
            ...(Array.isArray(ev.bronnen) && { bronnen: ev.bronnen }),
            // Source line → link to its source page, from the catalogue (#621); a line without one stays text.
            ...(zijnBronlinks(ev.bronlinks) && { bronlinks: ev.bronlinks }),
            // Where the answer came from: model, versions, data version (#345). The export of the conversation shows it (#713).
            ...(ev.manifest?.model && { manifest: ev.manifest }),
            // Questions to ask next; a click puts one in the input box (#364).
            ...(vragen.length && { vervolgvragen: vragen }),
            // A finished turn without text would otherwise render nothing at all.
            ...(!content.trim() && !ev.aborted && { empty: true }),
          }
        })
        finishStream()
      },
      clarification(ev) {
        setThinking(false)
        closeCurrentMsg()
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant',
          content: ev.vraag, clarification: ev.opties, done: true,
        }])
        finishStream()
      },
      starter_questions(ev) {
        setThinking(false)
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant',
          content: `Hier zijn voorbeeldvragen over **${ev.label}**:`,
          starterQuestions: ev.questions, done: true,
        }])
        finishStream()
      },
      reset_done() {
        resettingRef.current = false
        setResetting(false)
      },
      report_generating() {
        reportingRef.current = true
        reportRequestedRef.current = false
        setReportBusy(true)
        setReportSpec(null)
      },
      report_cancelled() {
        if (reportingRef.current) endReport()
      },
      // Not waiting any more (timed out, see generateReport): the user has been told already.
      report_ready(ev) {
        if (!reportingRef.current) return
        endReport()
        setReportSpec(ev.spec)
      },
      report_error(ev) {
        if (!reportingRef.current) return
        failReport(ev.message, ev.herstel)
      },
      error(ev) {
        setThinking(false)
        closeCurrentMsg()
        setMessages(prev => [...prev, {
          id: nextId(), role: 'assistant', content: ev.message, done: true, isError: true,
          modelafhankelijk: ev.modelafhankelijk !== false,
        }])
        busyRef.current = false
        setBusy(false)
      },
    }

    const chatStreamEvents = new Set([
      'message_start', 'message_cancel', 'text_delta', 'tool_start',
      'tool_end', 'figure', 'message_end', 'clarification', 'starter_questions', 'error', 'run_slow',
    ])
    const reportEndEvents = new Set(['report_ready', 'report_error', 'report_cancelled'])
    const reportRefusals = new Set(['busy', 'error'])

    // A silently dead connection (wifi drop) fires onclose only after the TCP timeout;
    // until then the user saw a counting pill and no melding (#489).
    const heartbeat = createHeartbeat(() => wsRef.current, connectionLost)
    const retry = createRetry(connect, { opgegeven: () => setOpgegeven('weg') })

    // One live socket at a time (#522). A real close() is asynchronous, so the onclose of a
    // socket that was already replaced can come after its successor opened. Only the socket
    // in wsRef counts, and only until its loss has been handled.
    let opened = false
    let ended = false
    const isCurrent = (ws) => wsRef.current === ws && !ended

    // Offline, heartbeat death or onclose, whichever comes first: the server session is gone
    // with its socket, and so is the answer it was writing.
    function connectionLost(ws, code) {
      if (!isCurrent(ws)) return
      ended = true
      heartbeat.stop()
      flushDeltas()
      setConnected(false)
      endInterruptedTurn()
      if (reportingRef.current) {
        failReport('De verbinding viel weg tijdens het maken van het rapport. Probeer het opnieuw.')
      }

      if (code === 4001) {
        endSession()
        return
      }

      if (manualCloseRef.current) return
      // De server wil deze verbinding niet (#783): opnieuw proberen geeft alleen een nieuwe foutmelding.
      const reden = opgevenBij(code)
      if (reden) {
        retry.reset()
        setOpgegeven(reden)
        return
      }
      // A refused handshake (expired token) closes as a bare 1006 before opening (#480).
      if (!opened) checkSession()
      retry.schedule()
    }

    function connect() {
      const ws = chatSocket()
      wsRef.current = ws
      opened = false
      ended = false
      setOpgegeven(null)

      ws.onopen = () => {
        if (!isCurrent(ws)) return
        opened = true
        setConnected(true)
        heartbeat.start()
        // A new connection is a new server session, so a pending reset is moot.
        resettingRef.current = false
        setResetting(false)
        // Not a reset: a socket the server closes right away (1013) must not start the count over (#783).
        retry.opened()
        endReport()
        reportAbandonedRef.current = false
        setReportSpec(null)
        // A new server session knows no data keys until ChatPage sends the open conversation again (#756).
        setHistoryDataKeys(0)
        if (settingsRef.current) ws.send(JSON.stringify({ action: 'settings', settings: settingsRef.current }))
      }

      ws.onclose = (e) => connectionLost(ws, e.code)

      ws.onmessage = (e) => {
        if (!isCurrent(ws)) return
        heartbeat.alive()
        const event = JSON.parse(e.data)
        // Alles wat geen delta is, ziet eerst de tekst die al binnen was (#510).
        if (event.type !== 'text_delta') flushDeltas()
        if (reportAbandonedRef.current) {
          if (reportEndEvents.has(event.type)) reportAbandonedRef.current = false
          if (reportEndEvents.has(event.type) || chatStreamEvents.has(event.type)) return
        }
        if (reportRequestedRef.current && reportRefusals.has(event.type)) {
          refuseReport(event)
          return
        }
        if (reportingRef.current && chatStreamEvents.has(event.type)) {
          if (event.type === 'tool_start') {
            setReportProgress(p => ({ steps: p.steps + 1, label: event.label || null }))
          }
          return
        }
        // Until reset_done, stream events belong to the run of the conversation that was just left (#337).
        if (resettingRef.current && chatStreamEvents.has(event.type)) return
        const handler = messageHandlers[event.type]
        if (handler) handler(event)
      }
    }

    connect()

    // Offline: the melding may not wait for a socket error (#489).
    const detachNetwork = watchNetwork({ getWs: () => wsRef.current, lost: connectionLost, retry, connect })

    // "Opnieuw verbinden" (#783): de teller begint opnieuw, net als bij online. Een socket die al open is of opent, blijft.
    verbindOpnieuwRef.current = () => {
      const state = wsRef.current?.readyState
      if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) return
      retry.reset()
      connect()
    }

    return () => {
      manualCloseRef.current = true
      detachNetwork()
      heartbeat.stop()
      retry.reset()
      cancelDeltaFrame()
      wsRef.current?.close()
    }
  }, [addToast, cancelDeltaFrame, closeCurrentMsg, endReport, failReport])

  // A question can go out: connected, no run, no reset and no report going (#417).
  const canSend = useCallback(() =>
    wsRef.current?.readyState === WebSocket.OPEN && !busyRef.current && !resettingRef.current && !reportingRef.current,
  [])

  // Returns whether the question went out, so the caller only clears what was typed when it did.
  const send = useCallback((content) => {
    if (!canSend()) return false
    busyRef.current = true
    setBusy(true)
    setSlow(false)
    setThinking(true)
    const id = nextId()
    lastSentRef.current = { id, content, draft: true }
    setMessages(prev => [...prev, { id, role: 'user', content, done: true, model: modelRef.current }])
    wsRef.current.send(JSON.stringify({ action: 'message', content }))
    return true
  }, [canSend])

  // Zegt net als send() of de keuze wegging, zodat de kaart pas dan dichtgaat (#774).
  const sendClarification = useCallback((choice) => {
    if (!canSend()) return false
    busyRef.current = true
    setBusy(true)
    setSlow(false)
    const id = nextId()
    lastSentRef.current = { id, content: choice, draft: false }
    setMessages(prev => [...prev, { id, role: 'user', content: choice, done: true, model: modelRef.current }])
    wsRef.current.send(JSON.stringify({ action: 'clarification_choice', choice }))
    return true
  }, [canSend])

  const sendSettings = useCallback((settings) => {
    if (settings.model) modelRef.current = settings.model
    settingsRef.current = settings
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'settings', settings }))
    }
  }, [])

  // The conversation id lets the server find the data keys this conversation saved (#472). Only on an open
  // connection: ChatPage sends the open conversation on every (re)connect itself (#756).
  // Returns whether the frame went out.
  const sendHistory = useCallback((msgs, convId = null) => {
    const history = buildHistory(msgs, maxHistoryRef.current)
    if (!history.length || wsRef.current?.readyState !== WebSocket.OPEN) return false
    wsRef.current.send(JSON.stringify({ action: 'history', messages: history, ...(convId ? { conv_id: String(convId) } : {}) }))
    return true
  }, [])

  const stop = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ action: 'stop' }))
  }, [])

  // Every tap gives a result (#648): whether a report can start now; when it cannot, a toast says why.
  const checkReportStart = useCallback(() => {
    const reden = reportBlockReason({
      connected: wsRef.current?.readyState === WebSocket.OPEN,
      open: currentMsgRef.current !== null || busyRef.current,
      reporting: reportingRef.current,
      resetting: resettingRef.current,
    })
    if (!reden) return true
    const nu = Date.now()
    if ((reasonToastUntilRef.current[reden.key] ?? 0) <= nu) {
      reasonToastUntilRef.current[reden.key] = nu + REASON_TOAST_MS
      addToast(reden.text, 'warning', { duur: REASON_TOAST_MS })
    }
    return false
  }, [addToast])

  // The report starts, or a toast says why it cannot start now. Returns whether the request went out.
  // onderzoeksvraag: the research question the user confirmed (#751); without it the server takes the first question.
  const generateReport = useCallback((author, onderzoeksvraag) => {
    if (!checkReportStart()) return false
    reportingRef.current = true
    reportRequestedRef.current = true
    setReportBusy(true)
    setReportSpec(null)
    setReportProgress(NO_REPORT_PROGRESS)
    const vraag = onderzoeksvraag?.trim()
    wsRef.current.send(JSON.stringify({ action: 'generate_report', author, ...(vraag && { onderzoeksvraag: vraag }) }))
    clearTimeout(reportTimeoutRef.current)
    reportTimeoutRef.current = setTimeout(() => {
      // Stop the server too: a report arriving after this message would contradict it.
      abandonReport()
      failReport(`Het rapport is na ${REPORT_TIMEOUT_MS / 60000} minuten nog niet klaar en is afgebroken. Probeer het opnieuw.`)
    }, REPORT_TIMEOUT_MS)
    return true
  }, [abandonReport, checkReportStart, failReport])

  // The user stops the report (#339): no error, the button is free at once.
  const cancelReport = useCallback(() => {
    if (!reportingRef.current) return
    abandonReport()
    addToast('Rapport geannuleerd')
  }, [abandonReport, addToast])

  const clearRejectedDraft = useCallback(() => setRejectedDraft(null), [])

  const clearReport = useCallback(() => {
    endReport()
    setReportSpec(null)
  }, [endReport])

  const clear = useCallback(() => {
    setMessages([])
    // Nog gebufferde deltas horen bij het gesprek dat nu sluit (#510): buffer weg, frame ook.
    deltaBufferRef.current = ''
    cancelDeltaFrame()
    // The ref too: send() checks it, and a stale true refused every next question (#337).
    busyRef.current = false
    setBusy(false)
    setThinking(false)
    setHistoryDataKeys(0)
    currentMsgRef.current = null
    lastSentRef.current = null
  }, [cancelDeltaFrame])

  // "Nieuw gesprek": the server must forget the previous conversation too,
  // otherwise the next question is answered with its context (#70).
  const startNewConversation = useCallback(() => {
    clear()
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      resettingRef.current = true
      setResetting(true)
      wsRef.current.send(JSON.stringify({ action: 'reset' }))
    }
  }, [clear])

  const verbindOpnieuw = useCallback(() => verbindOpnieuwRef.current(), [])

  // Opening a saved conversation leaves the running one as "Nieuw gesprek" does (#761): the server stops the old run
  // when it reads the history frame, and until its history_data, stream events still belong to that old run. The
  // server answers only a frame with a conversation id, so only then is there a window to wait for.
  const openConversation = useCallback((msgs, convId) => {
    clear()
    if (sendHistory(msgs, convId) && convId) {
      resettingRef.current = true
      setResetting(true)
    }
  }, [clear, sendHistory])

  return { messages, withBufferedText, busy, slow, rejectedDraft, clearRejectedDraft, thinking, toasts, connected, opgegeven, verbindOpnieuw, resetting, historyDataKeys, reportBusy, reportProgress, reportSpec, send, sendClarification, sendSettings, sendHistory, stop, checkReportStart, generateReport, cancelReport, clearReport, clear, startNewConversation, openConversation, addToast }
}
