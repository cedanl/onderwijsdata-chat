import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import { Bar, Line, Doughnut } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  ArcElement, Tooltip, Legend, Filler,
} from 'chart.js'
import { BUILTIN, BUILTIN_ARBEIDSMARKT, getWorkbooks, deleteWorkbook, saveWorkbook } from '../workbooks'
import { getToken } from '../auth'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Tooltip, Legend, Filler)

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('nl-NL', { day: 'numeric', month: 'short', year: 'numeric' })
}

// ─── Dashboard HTML builder ────────────────────────────────────────────────────

function parseNum(val) {
  if (!val) return null
  const s = String(val).replace(/[^\d,.\-+]/g, '').replace(',', '.')
  const n = parseFloat(s)
  return isNaN(n) ? null : n
}

function cleanLabel(val) {
  return String(val || '').replace(/[\u{1F300}-\u{1FFFF}]/gu, '').replace(/^\s+/, '').trim()
}

function parseTables(content) {
  const tables = []
  const reg = /((?:\|.+\|\n?)+)/g
  let m
  while ((m = reg.exec(content)) !== null) {
    const lines = m[1].trim().split('\n').filter(r => !/^\s*\|[-:| ]+\|\s*$/.test(r))
    if (lines.length < 2) continue
    const split = r => r.split('|').slice(1, -1).map(c => c.trim())
    const headers = split(lines[0])
    const rows = lines.slice(1).map(split)
    tables.push({ headers, rows })
  }
  return tables
}

function buildDashboardHtml(title, content, figures, instelling) {
  const date = new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
  const tables = parseTables(content)

  // ── Prose: narrative text outside tables ──────────────────────────────────
  const proseText = (content || '')
    .replace(/((?:\|.+\|\n?)+)/g, '')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^\s*[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>')

  // ── Build chart specs from tables ─────────────────────────────────────────
  const chartSpecs = tables.map((tbl, ti) => {
    const { headers, rows } = tbl
    const firstH = (headers[0] || '').toLowerCase()
    const isTimeSeries = /jaar|periode|school/.test(firstH)

    const labels = rows.map(r => cleanLabel(r[0]))
    const numericCols = headers.slice(1).map((h, ci) => {
      const vals = rows.map(r => parseNum(r[ci + 1]))
      const allNull = vals.every(v => v === null)
      return allNull ? null : { label: cleanLabel(h), data: vals }
    }).filter(Boolean)

    if (!numericCols.length) return null

    const COLORS = ['#2563EB', '#14B8A6', '#F59E0B', '#EF4444', '#8B5CF6', '#22C55E']
    const ALPHAS = ['rgba(37,99,235,.12)', 'rgba(20,184,166,.12)', 'rgba(245,158,11,.12)']

    const datasets = numericCols.map((col, i) => ({
      label: col.label,
      data: col.data,
      backgroundColor: isTimeSeries ? ALPHAS[i] || ALPHAS[0] : COLORS[i] || COLORS[0],
      borderColor: COLORS[i] || COLORS[0],
      borderWidth: isTimeSeries ? 2 : 0,
      borderRadius: isTimeSeries ? 0 : 6,
      fill: isTimeSeries,
      tension: 0.35,
      pointRadius: isTimeSeries ? 4 : 0,
    }))

    const chartType = isTimeSeries ? 'line' : (labels.length > 5 ? 'bar' : 'bar')
    const horizontal = !isTimeSeries && labels.length > 4

    // KPIs: max/min of first numeric col
    const primary = numericCols[0].data.filter(v => v !== null)
    const maxI = primary.indexOf(Math.max(...primary))
    const minI = primary.indexOf(Math.min(...primary))
    const kpis = [
      { label: 'Hoogste waarde', value: `${primary[maxI]}`, sub: cleanLabel(labels[maxI]) },
      { label: 'Laagste waarde', value: `${primary[minI]}`, sub: cleanLabel(labels[minI]) },
      numericCols.length > 1
        ? { label: 'Grootste verschil', value: (() => {
              if (!numericCols[numericCols.length - 1]) return ''
              const diff = numericCols[numericCols.length - 1].data
              const maxD = diff.filter(v => v !== null).reduce((a,b) => Math.abs(b) > Math.abs(a) ? b : a, 0)
              const di = diff.indexOf(maxD)
              return `${maxD > 0 ? '+' : ''}${maxD}`
            })(), sub: (() => {
              const diff = numericCols[numericCols.length - 1]?.data || []
              const maxD = diff.filter(v => v !== null).reduce((a,b) => Math.abs(b) > Math.abs(a) ? b : a, 0)
              return cleanLabel(labels[diff.indexOf(maxD)])
            })() }
        : { label: 'Gemiddelde', value: (primary.reduce((a,b) => a+b, 0) / primary.length).toFixed(1), sub: numericCols[0].label },
      { label: 'Aantal rijen', value: `${rows.length}`, sub: headers[0] },
    ]

    return { id: `chart${ti}`, chartType, horizontal, labels, datasets, kpis, tbl }
  }).filter(Boolean)

  // ── Table HTML renderer ────────────────────────────────────────────────────
  const tableHtml = (tbl) => {
    const { headers, rows } = tbl
    const hRow = '<tr>' + headers.map(h => `<th>${cleanLabel(h)}</th>`).join('') + '</tr>'
    const dRows = rows.map(r => '<tr>' + r.map(c => `<td>${c}</td>`).join('') + '</tr>').join('')
    return `<table><thead>${hRow}</thead><tbody>${dRows}</tbody></table>`
  }

  // ── Plotly figures ─────────────────────────────────────────────────────────
  const plotlySection = figures.length
    ? `<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"><\/script>
       ${figures.map((fj, i) => `
         <div class="card"><div id="pf${i}" style="height:360px"></div></div>
         <script>(function(){var f=${fj};Plotly.newPlot('pf${i}',f.data,Object.assign({},f.layout,{paper_bgcolor:'transparent',plot_bgcolor:'#F9FAFB',margin:{t:48,r:24,b:48,l:60},font:{family:'system-ui,sans-serif',size:12}}),{responsive:true,displayModeBar:false});})()</script>`
       ).join('\n')}`
    : ''

  // ── Chart.js sections ──────────────────────────────────────────────────────
  const chartJsSection = chartSpecs.length
    ? `<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"><\/script>
       ${chartSpecs.map(spec => {
         const kpiHtml = spec.kpis.map((k, i) =>
           `<div class="kpi" style="border-top:3px solid ${ ['#2563EB','#14B8A6','#F59E0B','#6B7280'][i] }">
             <div class="kpi-val">${k.value}</div>
             <div class="kpi-label">${k.label}</div>
             <div class="kpi-sub">${k.sub}</div>
           </div>`
         ).join('')

         const cfg = JSON.stringify({
           type: spec.chartType,
           data: { labels: spec.labels, datasets: spec.datasets },
           options: {
             responsive: true,
             maintainAspectRatio: false,
             indexAxis: spec.horizontal ? 'y' : 'x',
             plugins: {
               legend: { display: spec.datasets.length > 1, position: 'top',
                 labels: { font: { family: 'system-ui', size: 12 }, boxWidth: 12 } },
             },
             scales: {
               x: { grid: { color: '#F3F4F6' }, ticks: { font: { family: 'system-ui', size: 11 } } },
               y: { grid: { display: !spec.horizontal, color: '#F3F4F6' }, ticks: { font: { family: 'system-ui', size: 11 } } },
             },
           },
         })

         return `
           <div class="kpi-row">${kpiHtml}</div>
           <div class="card">
             <div style="height:${spec.horizontal ? Math.max(240, spec.labels.length * 38) : 300}px">
               <canvas id="${spec.id}"></canvas>
             </div>
           </div>
           <div class="card">${tableHtml(spec.tbl)}</div>
           <script>new Chart(document.getElementById('${spec.id}'), ${cfg})<\/script>`
       }).join('\n')}`
    : `<div class="card"><p style="color:#6B7280;font-size:.88rem">Geen tabeldata gevonden om te visualiseren.</p></div>`

  const instellingBadge = instelling
    ? `<div style="display:flex;align-items:center;gap:6px;margin-top:10px;background:#DCFCE7;color:#15803D;font-size:.75rem;font-weight:700;padding:5px 10px;border-radius:6px;width:fit-content">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px;flex-shrink:0"><path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 10v4M12 10v4M16 10v4"/></svg>
        ${instelling}
      </div>`
    : ''

  return `<!DOCTYPE html><html lang="nl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,-apple-system,sans-serif;font-size:14px;color:#111827;background:#F3F4F6;min-height:100vh}
  .header{background:#fff;border-bottom:1px solid #E5E7EB;padding:24px 32px}
  .header-top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
  .header-label{font-size:.7rem;font-weight:700;color:#2563EB;text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px}
  .header h1{font-size:1.25rem;font-weight:800;color:#111827;line-height:1.3}
  .header .meta{font-size:.75rem;color:#9CA3AF;margin-top:6px}
  .body{padding:28px 32px;max-width:1100px;margin:0 auto}
  .kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:20px}
  .kpi{background:#fff;border-radius:10px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,.07);border-top:3px solid #2563EB}
  .kpi:nth-child(2){border-top-color:#0D9488}
  .kpi:nth-child(3){border-top-color:#F59E0B}
  .kpi:nth-child(4){border-top-color:#6B7280}
  .kpi-val{font-size:1.6rem;font-weight:800;color:#111827;margin-bottom:4px}
  .kpi-label{font-size:.72rem;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px}
  .kpi-sub{font-size:.78rem;color:#9CA3AF;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .card{background:#fff;border-radius:10px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:20px}
  .card-title{font-size:.8rem;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:16px}
  table{width:100%;border-collapse:collapse;font-size:.85rem}
  th{background:#EFF6FF;color:#1D4ED8;font-weight:700;text-align:left;padding:10px 14px;border-bottom:2px solid #DBEAFE}
  td{padding:8px 14px;border-bottom:1px solid #F3F4F6}tr:nth-child(even) td{background:#F9FAFB}
  .prose{line-height:1.7;color:#374151}
  .prose h2,.prose h3{font-weight:700;margin:1em 0 .4em;color:#111827}
  .prose li{margin:.3em 0 .3em 1.4em}
  .prose strong{color:#111827}
  .prose p{margin:.5em 0}
  .footer{text-align:center;color:#9CA3AF;font-size:.72rem;padding:20px 32px 32px;border-top:1px solid #F3F4F6;margin-top:8px}
  @media(max-width:640px){.kpi-row{grid-template-columns:repeat(2,1fr)}.body{padding:16px}.header{padding:20px 16px}}
</style>
</head><body>
<div class="header">
  <div class="header-top">
    <div>
      <div class="header-label">Dashboard</div>
      <h1>${title}</h1>
      <div class="meta">Aangemaakt op ${date}</div>
    </div>
    ${instellingBadge}
  </div>
</div>
<div class="body">
  ${plotlySection}
  ${chartJsSection}
  ${proseText.trim() ? `<div class="card prose"><p>${proseText}</p></div>` : ''}
</div>
<div class="footer">Gegenereerd door openEDUdata+ · Gebaseerd op open onderwijsdata</div>
</body></html>`
}

// ─── WebSocket hook for dashboard creator ────────────────────────────────────

function useDashboardChat() {
  const [messages, setMessages] = useState([])
  const [figures, setFigures] = useState([])   // Plotly figure_json strings
  const [busy, setBusy] = useState(false)
  const wsRef = useRef(null)
  const currentIdRef = useRef(null)
  const pendingSettingsRef = useRef(null)

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const token = getToken()
    const query = token ? `?token=${encodeURIComponent(token)}` : ''
    const ws = new WebSocket(`${proto}://${location.host}/api/chat${query}`)
    wsRef.current = ws

    ws.onopen = () => {
      if (pendingSettingsRef.current) {
        ws.send(JSON.stringify({ action: 'settings', settings: pendingSettingsRef.current }))
        pendingSettingsRef.current = null
      }
    }

    ws.onmessage = (e) => {
      const ev = JSON.parse(e.data)
      if (ev.type === 'message_start') {
        const id = Date.now()
        currentIdRef.current = id
        setMessages(prev => [...prev, { id, role: 'assistant', content: '', done: false }])
      } else if (ev.type === 'message_cancel') {
        // clarify_scope cancelled the open streamed message
        setMessages(prev => prev.filter(m => m.id !== currentIdRef.current))
        currentIdRef.current = null
      } else if (ev.type === 'text_delta') {
        setMessages(prev => prev.map(m =>
          m.id === currentIdRef.current ? { ...m, content: m.content + ev.content } : m
        ))
      } else if (ev.type === 'tool_start') {
        setMessages(prev => prev.map(m =>
          m.id === currentIdRef.current ? { ...m, toolLabel: ev.label } : m
        ))
      } else if (ev.type === 'tool_end') {
        setMessages(prev => prev.map(m =>
          m.id === currentIdRef.current ? { ...m, toolLabel: null } : m
        ))
      } else if (ev.type === 'figure') {
        setFigures(prev => [...prev, ev.figure_json])
      } else if (ev.type === 'message_end') {
        setMessages(prev => prev.map(m =>
          m.id === currentIdRef.current ? { ...m, done: true, toolLabel: null } : m
        ))
        currentIdRef.current = null
        setBusy(false)
      } else if (ev.type === 'clarification') {
        setMessages(prev => [...prev, {
          id: Date.now(), role: 'assistant',
          content: ev.vraag, clarification: ev.opties, done: true,
        }])
        setBusy(false)
      } else if (ev.type === 'error') {
        setMessages(prev => [...prev, { id: Date.now(), role: 'assistant', content: ev.message, done: true, isError: true }])
        setBusy(false)
      }
    }
    ws.onclose = () => setBusy(false)
    return () => ws.close()
  }, [])

  const send = useCallback((content) => {
    if (!wsRef.current || busy) return
    setBusy(true)
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content, done: true }])
    wsRef.current.send(JSON.stringify({ action: 'message', content }))
  }, [busy])

  const sendClarification = useCallback((choice) => {
    if (!wsRef.current || busy) return
    setBusy(true)
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: choice, done: true }])
    wsRef.current.send(JSON.stringify({ action: 'clarification_choice', choice }))
  }, [busy])

  const sendSettings = useCallback((settings) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      pendingSettingsRef.current = settings
      return
    }
    wsRef.current.send(JSON.stringify({ action: 'settings', settings }))
  }, [])

  const reset = useCallback(() => {
    setMessages([])
    setFigures([])
    setBusy(false)
  }, [])

  return { messages, figures, busy, send, sendClarification, sendSettings, reset }
}

// ─── Saved dashboard view ─────────────────────────────────────────────────────

function buildFigureHtml(figJson) {
  return `<!DOCTYPE html><html><head><meta charset="utf-8">
<style>*{margin:0;padding:0;box-sizing:border-box}body{background:transparent;overflow:hidden}</style>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"><\/script>
</head><body>
<div id="p" style="height:100vh;width:100%"></div>
<script>(function(){try{var f=${figJson};Plotly.newPlot('p',f.data,Object.assign({},f.layout,{paper_bgcolor:'transparent',plot_bgcolor:'#F9FAFB',margin:{t:40,r:20,b:48,l:56},font:{family:'system-ui,sans-serif',size:12}}),{responsive:true,displayModeBar:false})}catch(e){}})()</script>
</body></html>`
}

function SavedDashboardView({ workbook, instelling }) {
  const eff = workbook.instelling || instelling
  const msgs = (workbook.messages || []).filter(m => m.role === 'assistant' && !m.isError && m.content)
  const figures = workbook.figures || []

  return (
    <div className="saved-db">
      <div className="saved-db-header">
        <div className="section-label">Dashboard</div>
        <h1 className="saved-db-title">{workbook.title}</h1>
        {eff && (
          <span className="meta-badge instelling" style={{ marginTop: 10, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 13, height: 13, flexShrink: 0 }}>
              <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 10v4M12 10v4M16 10v4"/>
            </svg>
            {eff}
          </span>
        )}
      </div>

      {figures.map((fig, i) => (
        <iframe
          key={i}
          className="saved-db-figure"
          srcDoc={buildFigureHtml(fig)}
          sandbox="allow-scripts"
          title={`Grafiek ${i + 1}`}
        />
      ))}

      {msgs.map((msg, i) => (
        <div key={i} className="card saved-db-card">
          <ReactMarkdown>{msg.content}</ReactMarkdown>
        </div>
      ))}

      <div className="dashboard-sources" style={{ marginTop: 8 }}>
        <span style={{ fontSize: '.72rem', color: 'var(--gray-400)' }}>
          Gegenereerd door openEDUdata+ · Gebaseerd op open onderwijsdata · {workbook.description}
        </span>
      </div>
    </div>
  )
}

// ─── Model picker ─────────────────────────────────────────────────────────────

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

// ─── Dashboard creator ────────────────────────────────────────────────────────

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

function DashboardCreator({ onSaved, instelling }) {
  const { messages, figures, busy, send, sendClarification, sendSettings, reset } = useDashboardChat()
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
      .catch(() => {})
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
  const hasResponse = !busy && messages.some(m => m.role === 'assistant' && !m.isError && (m.content?.length ?? 0) > 150)

  const handleSend = (text, clear = false) => {
    if (!text.trim() || busy) return
    if (clear) setInput('')
    else setFollowUp('')
    send(text.trim())
  }

  const [saving, setSaving] = useState(false)

  const handleSave = () => {
    const assistantMsgs = messages.filter(m => m.role === 'assistant' && !m.isError && m.content)
    if (!assistantMsgs.length || saving) return
    setSaving(true)
    const title = messages.find(m => m.role === 'user')?.content?.slice(0, 60) || 'Dashboard'
    const date = new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
    const wb = saveWorkbook({
      title,
      description: `Aangemaakt op ${date}`,
      messages: messages.filter(m => !m.isError),
      figures,
      instelling,
    })
    reset()
    onSaved?.(wb)
  }

  const handleReset = () => { reset(); setInput(''); setFollowUp('') }

  const isEmpty = messages.length === 0

  return (
    <div className="dc-wrap">
      <div className="dc-header">
        <div>
          <div className="section-label">Dashboard</div>
          <h2 className="section-title" style={{ fontSize: '1.3rem', margin: 0 }}>Creëer je eigen dashboard</h2>
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
                  : msg.content ? <ReactMarkdown>{msg.content}</ReactMarkdown> : null
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
              onChange={e => { setInput(e.target.value); e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px' }}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(input, true) } }}
              disabled={busy}
            />
            <div className="dc-input-footer">
              {models.length > 0 && <ModelPicker models={models} value={selectedModel} onChange={setSelectedModel} />}
              <button className="send-btn" onClick={() => handleSend(input, true)} disabled={!input.trim() || busy}>
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
                <button className="dc-save-btn" onClick={handleSave} disabled={saving}>
                  {saving ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
                      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
                      <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
                    </svg>
                  )}
                  {saving ? 'Dashboard opgeslagen' : 'Opslaan als dashboard'}
                </button>
              </div>
            )}
            <div className="dc-input-wrap">
              <textarea
                className="dc-textarea"
                rows={1}
                placeholder="Stel een vervolgvraag..."
                value={followUp}
                onChange={e => { setFollowUp(e.target.value); e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px' }}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(followUp) } }}
                disabled={busy}
              />
              <div className="dc-input-footer">
                {models.length > 0 && <ModelPicker models={models} value={selectedModel} onChange={setSelectedModel} />}
                <button className="send-btn" onClick={() => handleSend(followUp)} disabled={!followUp.trim() || busy}>
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
  )
}

// ─── Main DashboardPage ───────────────────────────────────────────────────────

const BUILTIN_INSTELLING = 'Hogeschool Utrecht'

export default function DashboardPage({ setPage, settings }) {
  const [userWorkbooks, setUserWorkbooks] = useState(getWorkbooks)
  const [selected, setSelected] = useState(null)
  const [showCreator, setShowCreator] = useState(false)

  const instelling = settings?.instelling?.trim() || BUILTIN_INSTELLING

  const all = [BUILTIN, BUILTIN_ARBEIDSMARKT, ...userWorkbooks]

  const handleDelete = (id) => {
    deleteWorkbook(id)
    setUserWorkbooks(getWorkbooks())
    if (selected?.id === id) setSelected(null)
  }

  const [newWbId, setNewWbId] = useState(null)

  const handleSaved = (newWb) => {
    setUserWorkbooks(getWorkbooks())
    setShowCreator(false)
    if (newWb?.id) setNewWbId(newWb.id)
  }

  if (selected) {
    return (
      <div className="wb-viewer">
        <div className="wb-viewer-bar">
          <button className="wb-back-btn" onClick={() => setSelected(null)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Dashboards
          </button>
          <span className="wb-viewer-title">{selected.title}</span>
          <div />
        </div>
        <div className="wb-viewer-content" style={{ overflowY: 'auto' }}>
          {selected.id === '__builtin__'
            ? <InlineDashboard instelling={instelling} />
            : selected.id === '__builtin_arbeidsmarkt__'
            ? <InlineDashboardArbeidsmarkt instelling={instelling} />
            : selected.messages
            ? <SavedDashboardView workbook={selected} instelling={instelling} />
            : <iframe className="wb-iframe" srcDoc={selected.htmlContent} title={selected.title} sandbox="allow-scripts" />
          }
        </div>
      </div>
    )
  }

  if (showCreator) {
    return (
      <div className="wb-gallery-page">
        <div className="wb-gallery-header">
          <button className="wb-back-btn" onClick={() => setShowCreator(false)} style={{ border: 'none', background: 'none', display: 'flex', alignItems: 'center', gap: 6, color: 'var(--gray-600)', fontWeight: 600, fontSize: '.88rem', cursor: 'pointer' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Dashboards
          </button>
        </div>
        <DashboardCreator onSaved={handleSaved} instelling={instelling} />
      </div>
    )
  }

  return (
    <div className="wb-gallery-page">
      <div className="wb-gallery-header">
        <div>
          <div className="wb-gallery-title">Dashboards</div>
          <div className="wb-gallery-sub">{all.length} dashboard{all.length !== 1 ? 's' : ''}</div>
        </div>
      </div>

      <div className="wb-grid">
        {all.map(wb => (
          <div key={wb.id} className={`wb-card${wb.id === newWbId ? ' wb-card-new' : ''}`} onClick={() => { setSelected(wb); setNewWbId(null) }}>
            <div className="wb-card-thumb">
              <WorkbookPreview wb={wb} />
              {wb.builtin && (
                <>
                  <span className="wb-builtin-badge">Voorbeeld</span>
                  <div className="wb-builtin-instelling">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 10v4M12 10v4M16 10v4"/>
                    </svg>
                    {instelling}
                  </div>
                </>
              )}
              {wb.id === newWbId && <span className="wb-new-badge">Nieuw</span>}
            </div>
            <div className="wb-card-body">
              <div className="wb-card-title">{wb.title}</div>
              <div className="wb-card-desc">{wb.description}</div>
              <div className="wb-card-footer">
                {!wb.builtin && <span className="wb-card-date">{formatDate(wb.createdAt)}</span>}
                {!wb.builtin && (
                  <button
                    className="wb-delete-btn"
                    title="Verwijder"
                    onClick={e => { e.stopPropagation(); handleDelete(wb.id) }}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4h6v2" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        <button className="wb-new-card" onClick={() => setShowCreator(true)}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>Nieuw dashboard</span>
          <small>Beschrijf welke data je wilt zien</small>
        </button>
      </div>
    </div>
  )
}

// ─── Workbook preview thumbnails ──────────────────────────────────────────────

function UserWorkbookPreview({ wb }) {
  const answer = wb.messages?.find(m => m.role === 'assistant' && m.content)?.content || ''
  const preview = answer.replace(/[#*`|]/g, '').replace(/\n+/g, ' ').trim().slice(0, 180)
  const hasFigures = (wb.figures?.length ?? 0) > 0
  return (
    <div className="wb-user-preview">
      <div className="wb-user-preview-bars">
        {[40, 65, 55, 80, 70, 50].map((h, i) => (
          <div key={i} className="wb-user-preview-bar" style={{ height: `${h}%`, opacity: 0.15 + i * 0.1 }} />
        ))}
      </div>
      {hasFigures && (
        <div className="wb-user-preview-chart-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
        </div>
      )}
      <p className="wb-user-preview-text">{preview}</p>
    </div>
  )
}

function WorkbookPreview({ wb }) {
  const [loaded, setLoaded] = useState(false)
  const wrapRef = useRef(null)
  const [scale, setScale] = useState(0.25)

  useEffect(() => {
    if (wb.builtin) return
    const el = wrapRef.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => {
      setScale(entry.contentRect.width / 960)
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [wb.builtin])

  if (wb.builtin) return wb.id === '__builtin_arbeidsmarkt__' ? <ArbeidsmarktPreview /> : <BuiltinPreview />

  if (wb.messages) return <UserWorkbookPreview wb={wb} />

  return (
    <div ref={wrapRef} className="wb-preview-wrap">
      {!loaded && <div className="wb-preview-shimmer" />}
      <div
        className="wb-preview-frame-outer"
        style={{ transform: `scale(${scale})`, height: Math.ceil(155 / scale) }}
      >
        <iframe
          srcDoc={wb.htmlContent}
          sandbox="allow-scripts"
          onLoad={() => setLoaded(true)}
          style={{ width: 960, height: '100%', border: 'none' }}
          title={wb.title}
        />
      </div>
    </div>
  )
}

function BuiltinPreview() {
  const bars = [55, 70, 82, 88, 100]
  return (
    <div className="wb-builtin-preview">
      <div className="wb-mini-kpi-row">
        {['#EFF6FF', '#F0FDFA', '#F0FDF4', '#FFF7ED'].map((c, i) => (
          <div key={i} className="wb-mini-kpi" style={{ background: c }}>
            <div className="wb-mini-kpi-val" style={{ background: ['#2563EB','#0D9488','#22C55E','#F59E0B'][i] }} />
          </div>
        ))}
      </div>
      <div className="wb-mini-charts">
        <div className="wb-mini-chart-bar">
          {bars.map((h, i) => (
            <div key={i} className="wb-mini-bar" style={{ height: `${h}%` }} />
          ))}
        </div>
        <div className="wb-mini-line">
          <svg viewBox="0 0 60 40" preserveAspectRatio="none">
            <polyline points="0,38 15,30 30,18 45,10 60,4" fill="rgba(37,99,235,.12)" stroke="#2563EB" strokeWidth="2" />
            <polyline points="0,38 15,34 30,28 45,22 60,16" fill="none" stroke="#14B8A6" strokeWidth="1.5" strokeDasharray="3,2" />
          </svg>
        </div>
        <div className="wb-mini-donut-wrap">
          <div className="wb-mini-donut" />
        </div>
      </div>
    </div>
  )
}

function ArbeidsmarktPreview() {
  const bars = [42, 58, 72, 90, 68]
  return (
    <div className="wb-builtin-preview">
      <div className="wb-mini-kpi-row">
        {['#FFF7ED', '#F0FDFA', '#EFF6FF', '#F0FDF4'].map((c, i) => (
          <div key={i} className="wb-mini-kpi" style={{ background: c }}>
            <div className="wb-mini-kpi-val" style={{ background: ['#F59E0B','#0D9488','#2563EB','#22C55E'][i] }} />
          </div>
        ))}
      </div>
      <div className="wb-mini-charts">
        <div className="wb-mini-chart-bar">
          {bars.map((h, i) => (
            <div key={i} className="wb-mini-bar" style={{ height: `${h}%`, background: ['#F59E0B','#0D9488','#2563EB','#22C55E','#8B5CF6'][i] }} />
          ))}
        </div>
        <div className="wb-mini-line">
          <svg viewBox="0 0 60 40" preserveAspectRatio="none">
            <polyline points="0,32 15,28 30,20 45,14 60,10" fill="rgba(245,158,11,.12)" stroke="#F59E0B" strokeWidth="2" />
            <polyline points="0,36 15,33 30,29 45,25 60,22" fill="none" stroke="#0D9488" strokeWidth="1.5" strokeDasharray="3,2" />
          </svg>
        </div>
        <div className="wb-mini-donut-wrap">
          <div className="wb-mini-donut" style={{ background: 'conic-gradient(#F59E0B 0% 35%, #0D9488 35% 60%, #2563EB 60% 85%, #22C55E 85% 100%)' }} />
        </div>
      </div>
    </div>
  )
}

// ─── Builtin demo dashboard ────────────────────────────────────────────────────

const CHART_OPTS = {
  responsive: true, maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: { x: { grid: { display: false } }, y: { grid: { color: '#F3F4F6' } } },
}

const SECTOR_LABELS = {
  ECONOMIE: 'Economie',
  GEZONDHEIDSZORG: 'Gezondheidszorg',
  TECHNIEK: 'Techniek',
  ONDERWIJS: 'Onderwijs',
  GEDRAG_EN_MAATSCHAPPIJ: 'Gedrag & Mij.',
  TAAL_EN_CULTUUR: 'Taal & Cultuur',
  SECTOROVERSTIJGEND: 'Sectoroverstijgend',
}
const SECTOR_COLORS = ['#2563EB', '#0D9488', '#F59E0B', '#22C55E', '#8B5CF6', '#EC4899', '#94A3B8']

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('nl-NL')
}

function useDashboardData(instelling) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!instelling) return
    setLoading(true)
    setData(null)
    setError(null)
    fetch(`/api/dashboard/instroom?instelling=${encodeURIComponent(instelling)}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [instelling])

  return { data, loading, error }
}

function DashboardShell({ instelling, children, loading, data, error }) {
  if (loading) {
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Data laden…</span>
        </div>
        <div className="db-skeleton-grid">
          {[1,2,3,4].map(i => <div key={i} className="db-skeleton-kpi" />)}
        </div>
        <div className="db-skeleton-grid" style={{ marginTop: 16 }}>
          {[1,2,3,4].map(i => <div key={i} className="db-skeleton-chart" />)}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div className="chart-card" style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
          <div style={{ fontSize: '.85rem', color: '#991B1B' }}>
            Kon geen data ophalen voor <strong>{instelling}</strong>. {error}
          </div>
        </div>
      </div>
    )
  }

  if (!data.gevonden) {
    const suggesties = data.beschikbare_instellingen || []
    return (
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div className="chart-card" style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
          <div style={{ fontSize: '.85rem', color: '#92400E', lineHeight: 1.6 }}>
            <strong>"{instelling}"</strong> niet gevonden in DUO-data.
            {suggesties.length > 0 && (
              <> Bedoel je misschien: {suggesties.slice(0,5).join(', ')}?</>
            )}
            <br />Pas de naam aan via <strong>Instellingen</strong>.
          </div>
        </div>
      </div>
    )
  }

  return children
}

function InlineDashboard({ instelling }) {
  const { data, loading, error } = useDashboardData(instelling)

  const ingesChartData = data?.ingeschrevenen ? (() => {
    const entries = Object.entries(data.ingeschrevenen).sort((a,b) => a[0]-b[0])
    return {
      labels: entries.map(([y]) => String(y)),
      datasets: [{ label: 'Ingeschrevenen', data: entries.map(([,v]) => v), backgroundColor: '#2563EB', borderRadius: 6 }],
    }
  })() : null

  const eerstejaarsChartData = data?.eerstejaars ? (() => {
    const entries = Object.entries(data.eerstejaars).sort((a,b) => a[0]-b[0])
    return {
      labels: entries.map(([y]) => String(y)),
      datasets: [{ label: 'Eerstejaars', data: entries.map(([,v]) => v), backgroundColor: '#0D9488', borderRadius: 6 }],
    }
  })() : null

  const gediplChartData = data?.gediplomeerden ? (() => {
    const entries = Object.entries(data.gediplomeerden).sort((a,b) => a[0]-b[0])
    return {
      labels: entries.map(([y]) => String(y)),
      datasets: [{ label: 'Gediplomeerden', data: entries.map(([,v]) => v), borderColor: '#22C55E', backgroundColor: 'rgba(34,197,94,.08)', fill: true, tension: 0.3, pointRadius: 4 }],
    }
  })() : null

  const sectorChartData = data?.sectoren ? (() => {
    const entries = Object.entries(data.sectoren).sort((a,b) => b[1]-a[1]).slice(0, 7)
    return {
      labels: entries.map(([k]) => SECTOR_LABELS[k] || k),
      datasets: [{ data: entries.map(([,v]) => v), backgroundColor: SECTOR_COLORS, borderWidth: 0 }],
    }
  })() : null

  // KPIs
  const ingesEntries = data?.ingeschrevenen ? Object.entries(data.ingeschrevenen).sort((a,b) => a[0]-b[0]) : []
  const lastInges = ingesEntries.at(-1)
  const prevInges = ingesEntries.at(-2)
  const ingesDelta = lastInges && prevInges ? lastInges[1] - prevInges[1] : null

  const diplEntries = data?.gediplomeerden ? Object.entries(data.gediplomeerden).sort((a,b) => a[0]-b[0]) : []
  const lastDipl = diplEntries.at(-1)
  const prevDipl = diplEntries.at(-2)
  const diplDelta = lastDipl && prevDipl ? lastDipl[1] - prevDipl[1] : null

  const eerstejaarsEntries = data?.eerstejaars ? Object.entries(data.eerstejaars).sort((a,b) => a[0]-b[0]) : []
  const lastEj = eerstejaarsEntries.at(-1)

  const vrouw = data?.geslacht?.VROUW || 0
  const man = data?.geslacht?.MAN || 0
  const totaalGeslacht = vrouw + man
  const pctVrouw = totaalGeslacht > 0 ? ((vrouw / totaalGeslacht) * 100).toFixed(1) : null

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata</span>
        </div>
        <div className="kpi-grid">
          {lastInges && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Ingeschrevenen {lastInges[0]}–{Number(lastInges[0])+1}</span>
                <div className="kpi-icon" style={{ background: '#EFF6FF' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastInges[1])}</div>
              {ingesDelta != null && <div className={`kpi-trend ${ingesDelta >= 0 ? 'up' : 'down'}`}>{ingesDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(ingesDelta))} t.o.v. vorig jaar</div>}
            </div>
          )}
          {lastDipl && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Gediplomeerden {lastDipl[0]}</span>
                <div className="kpi-icon" style={{ background: '#F0FDFA' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#0D9488" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastDipl[1])}</div>
              {diplDelta != null && <div className={`kpi-trend ${diplDelta >= 0 ? 'up' : 'down'}`}>{diplDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(diplDelta))} t.o.v. vorig jaar</div>}
            </div>
          )}
          {lastEj && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Eerstejaars {lastEj[0]}–{Number(lastEj[0])+1}</span>
                <div className="kpi-icon" style={{ background: '#F0FDF4' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#22C55E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastEj[1])}</div>
            </div>
          )}
          {pctVrouw != null && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Aandeel vrouw {data.laatste_jaar}</span>
                <div className="kpi-icon" style={{ background: '#FFF7ED' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                </div>
              </div>
              <div className="kpi-value">{pctVrouw}%</div>
              <div className="kpi-trend">van {fmt(totaalGeslacht)} ingeschrevenen</div>
            </div>
          )}
        </div>
        <div className="charts-grid">
          {ingesChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Ingeschrevenen per jaar</div><div className="chart-sub">{instelling} (DUO p01hoinges)</div></div></div>
              <div style={{ height: 200 }}><Bar data={ingesChartData} options={CHART_OPTS} /></div>
            </div>
          )}
          {sectorChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Verdeling per sector {data.laatste_jaar}</div><div className="chart-sub">Ingeschrevenen naar onderdeel (DUO p01hoinges)</div></div></div>
              <div style={{ height: 200 }}><Doughnut data={sectorChartData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } } }} /></div>
            </div>
          )}
          {eerstejaarsChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Eerstejaars instroom per jaar</div><div className="chart-sub">{instelling} (DUO p02ho1ejrs)</div></div></div>
              <div style={{ height: 200 }}><Bar data={eerstejaarsChartData} options={CHART_OPTS} /></div>
            </div>
          )}
          {gediplChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Gediplomeerden per jaar</div><div className="chart-sub">{instelling} (DUO p04hogdipl)</div></div></div>
              <div style={{ height: 200 }}><Line data={gediplChartData} options={{ ...CHART_OPTS, plugins: { legend: { display: false } } }} /></div>
            </div>
          )}
        </div>
        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://duo.nl/open_onderwijsdata/hoger-onderwijs/ingeschrevenen-wo-hbo/" target="_blank" rel="noreferrer">DUO — Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://duo.nl/open_onderwijsdata/hoger-onderwijs/eerstejaars-wo-hbo/" target="_blank" rel="noreferrer">DUO — Eerstejaars HO per instelling (p02ho1ejrs)</a></li>
            <li><a href="https://duo.nl/open_onderwijsdata/hoger-onderwijs/gediplomeerden-wo-hbo/" target="_blank" rel="noreferrer">DUO — Gediplomeerden HO per instelling (p04hogdipl)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}

function InlineDashboardArbeidsmarkt({ instelling }) {
  const { data, loading, error } = useDashboardData(instelling)

  const gediplChartData = data?.gediplomeerden ? (() => {
    const entries = Object.entries(data.gediplomeerden).sort((a,b) => a[0]-b[0])
    return {
      labels: entries.map(([y]) => String(y)),
      datasets: [{ label: 'Gediplomeerden', data: entries.map(([,v]) => v), borderColor: '#0D9488', backgroundColor: 'rgba(13,148,136,.08)', fill: true, tension: 0.3, pointRadius: 4 }],
    }
  })() : null

  const sectorChartData = data?.sectoren ? (() => {
    const entries = Object.entries(data.sectoren).sort((a,b) => b[1]-a[1]).slice(0, 7)
    return {
      labels: entries.map(([k]) => SECTOR_LABELS[k] || k),
      datasets: [{ label: 'Ingeschrevenen', data: entries.map(([,v]) => v), backgroundColor: SECTOR_COLORS, borderRadius: 6 }],
    }
  })() : null

  const diplEntries = data?.gediplomeerden ? Object.entries(data.gediplomeerden).sort((a,b) => a[0]-b[0]) : []
  const lastDipl = diplEntries.at(-1)
  const prevDipl = diplEntries.at(-2)
  const diplDelta = lastDipl && prevDipl ? lastDipl[1] - prevDipl[1] : null

  const sectorEntries = data?.sectoren ? Object.entries(data.sectoren).sort((a,b) => b[1]-a[1]) : []
  const kpiColors = ['#EFF6FF','#FFF7ED','#F0FDF4']
  const kpiIconColors = ['#2563EB','#F59E0B','#22C55E']

  return (
    <DashboardShell instelling={instelling} loading={loading} data={data} error={error}>
      <div className="dashboard-content" style={{ padding: 24 }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
          <span className="meta-badge instelling">{instelling}</span>
          <span className="meta-badge date">Bron: DUO Open Onderwijsdata</span>
        </div>
        <div className="kpi-grid">
          {lastDipl && (
            <div className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">Gediplomeerden {lastDipl[0]}</span>
                <div className="kpi-icon" style={{ background: '#F0FDFA' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#0D9488" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(lastDipl[1])}</div>
              {diplDelta != null && <div className={`kpi-trend ${diplDelta >= 0 ? 'up' : 'down'}`}>{diplDelta >= 0 ? '↑' : '↓'} {fmt(Math.abs(diplDelta))} t.o.v. vorig jaar</div>}
            </div>
          )}
          {sectorEntries.slice(0, 3).map(([key, val], i) => (
            <div key={key} className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">{SECTOR_LABELS[key] || key} {data.laatste_jaar}</span>
                <div className="kpi-icon" style={{ background: kpiColors[i] }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke={kpiIconColors[i]} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
                </div>
              </div>
              <div className="kpi-value">{fmt(val)}</div>
              <div className="kpi-trend">{i === 0 ? 'grootste sector' : i === 1 ? '2e sector' : '3e sector'}</div>
            </div>
          ))}
        </div>
        <div className="charts-grid">
          {gediplChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Gediplomeerden per jaar</div><div className="chart-sub">{instelling} (DUO p04hogdipl)</div></div></div>
              <div style={{ height: 200 }}><Line data={gediplChartData} options={{ ...CHART_OPTS, plugins: { legend: { display: false } } }} /></div>
            </div>
          )}
          {sectorChartData && (
            <div className="chart-card">
              <div className="chart-header"><div><div className="chart-title">Ingeschrevenen per sector {data.laatste_jaar}</div><div className="chart-sub">Verdeling naar onderdeel (DUO p01hoinges)</div></div></div>
              <div style={{ height: 200 }}><Bar data={sectorChartData} options={{ ...CHART_OPTS, plugins: { legend: { display: false } } }} /></div>
            </div>
          )}
        </div>
        <div className="dashboard-sources">
          <div className="dashboard-sources-title">Bronnen</div>
          <ul className="dashboard-sources-list">
            <li><a href="https://duo.nl/open_onderwijsdata/hoger-onderwijs/ingeschrevenen-wo-hbo/" target="_blank" rel="noreferrer">DUO — Ingeschrevenen HO per instelling (p01hoinges)</a></li>
            <li><a href="https://duo.nl/open_onderwijsdata/hoger-onderwijs/gediplomeerden-wo-hbo/" target="_blank" rel="noreferrer">DUO — Gediplomeerden HO per instelling (p04hogdipl)</a></li>
          </ul>
        </div>
      </div>
    </DashboardShell>
  )
}
