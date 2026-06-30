import { CHART_COLORS } from './constants'

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function parseNum(val) {
  if (!val) return null
  const s = String(val).replace(/[^\d,.\-+]/g, '').replace(',', '.')
  const n = parseFloat(s)
  return isNaN(n) ? null : n
}

function cleanLabel(val) {
  return String(val || '').replace(/[\u{1F300}-\u{1FFFF}]/gu, '').replace(/^\s+/, '').trim()
}

export function parseTables(content) {
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

export function buildChartSpecs(tables) {
  const COLORS = CHART_COLORS
  const ALPHAS = ['rgba(37,99,235,.12)', 'rgba(20,184,166,.12)', 'rgba(245,158,11,.12)']

  return tables.map((tbl, ti) => {
    const { headers, rows } = tbl
    const firstH = (headers[0] || '').toLowerCase()
    const isTimeSeries = /jaar|periode|school/.test(firstH)

    const labels = rows.map(r => escapeHtml(cleanLabel(r[0])))
    const numericCols = headers.slice(1).map((h, ci) => {
      const vals = rows.map(r => parseNum(r[ci + 1]))
      return vals.every(v => v === null) ? null : { label: escapeHtml(cleanLabel(h)), data: vals }
    }).filter(Boolean)

    if (!numericCols.length) return null

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

    const chartType = isTimeSeries ? 'line' : 'bar'
    const horizontal = !isTimeSeries && labels.length > 4

    const primary = numericCols[0].data.filter(v => v !== null)
    const maxI = primary.indexOf(Math.max(...primary))
    const minI = primary.indexOf(Math.min(...primary))
    const kpis = [
      { label: 'Hoogste waarde', value: `${primary[maxI]}`, sub: cleanLabel(labels[maxI]) },
      { label: 'Laagste waarde', value: `${primary[minI]}`, sub: cleanLabel(labels[minI]) },
      numericCols.length > 1
        ? { label: 'Grootste verschil', value: (() => {
              const diff = numericCols[numericCols.length - 1].data
              const maxD = diff.filter(v => v !== null).reduce((a,b) => Math.abs(b) > Math.abs(a) ? b : a, 0)
              return `${maxD > 0 ? '+' : ''}${maxD}`
            })(), sub: (() => {
              const diff = numericCols[numericCols.length - 1]?.data || []
              const maxD = diff.filter(v => v !== null).reduce((a,b) => Math.abs(b) > Math.abs(a) ? b : a, 0)
              return cleanLabel(labels[diff.indexOf(maxD)])
            })() }
        : { label: 'Gemiddelde', value: (primary.reduce((a,b) => a+b, 0) / primary.length).toFixed(1), sub: numericCols[0].label },
      { label: 'Aantal rijen', value: `${rows.length}`, sub: escapeHtml(headers[0]) },
    ]

    return { id: `chart${ti}`, chartType, horizontal, labels, datasets, kpis, tbl }
  }).filter(Boolean)
}

function tableHtml(tbl) {
  const { headers, rows } = tbl
  const hRow = '<tr>' + headers.map(h => `<th>${escapeHtml(cleanLabel(h))}</th>`).join('') + '</tr>'
  const dRows = rows.map(r => '<tr>' + r.map(c => `<td>${escapeHtml(c)}</td>`).join('') + '</tr>').join('')
  return `<table><thead>${hRow}</thead><tbody>${dRows}</tbody></table>`
}

export function buildDashboardHtml(title, content, figures = [], instelling = '') {
  const date = new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
  const tables = parseTables(content)

  const proseRaw = escapeHtml(
    (content || '').replace(/((?:\|.+\|\n?)+)/g, '')
  )
  const proseText = proseRaw
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^\s*[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>')

  const chartSpecs = buildChartSpecs(tables)

  const plotlySection = figures.length
    ? `<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"><\/script>
       ${figures.map((fj, i) => `
         <div class="card"><div id="pf${i}" style="height:360px"></div></div>
         <script>(function(){var f=${fj},_d=window.matchMedia('(prefers-color-scheme:dark)').matches;Plotly.newPlot('pf${i}',f.data,Object.assign({},f.layout,{paper_bgcolor:'transparent',plot_bgcolor:_d?'#111827':'#F9FAFB',margin:{t:48,r:24,b:48,l:60},font:{color:_d?'#D1D5DB':'#374151',family:'system-ui,sans-serif',size:12}}),{responsive:true,displayModeBar:false});})()</script>`
       ).join('\n')}`
    : ''

  const chartJsSection = chartSpecs.length
    ? `<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"><\/script>
       <script>
         (function(){
           var _d=window.matchMedia('(prefers-color-scheme:dark)').matches;
           Chart.defaults.color=_d?'#9CA3AF':'#6B7280';
           Chart.defaults.borderColor=_d?'rgba(255,255,255,0.06)':'#F3F4F6';
         })();
       <\/script>
       ${chartSpecs.map(spec => {
         const kpiHtml = spec.kpis.map((k, i) =>
           `<div class="kpi" style="border-top:3px solid ${ [CHART_COLORS[0], CHART_COLORS[1], CHART_COLORS[2], '#6B7280'][i] }">
             <div class="kpi-val">${escapeHtml(k.value)}</div>
             <div class="kpi-label">${escapeHtml(k.label)}</div>
             <div class="kpi-sub">${escapeHtml(k.sub)}</div>
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
    : ''

  const instellingBadge = instelling
    ? `<div style="display:flex;align-items:center;gap:6px;margin-top:10px;background:#DCFCE7;color:#15803D;font-size:.75rem;font-weight:700;padding:5px 10px;border-radius:6px;width:fit-content">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px;flex-shrink:0"><path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 10v4M12 10v4M16 10v4"/></svg>
        ${escapeHtml(instelling)}
      </div>`
    : ''

  return `<!DOCTYPE html><html lang="nl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(title)}</title>
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
  @media(prefers-color-scheme:dark){
    body{color:#F9FAFB;background:#111827}
    .header{background:#1F2937;border-bottom-color:#374151}
    .header h1{color:#F9FAFB}
    .header .meta{color:#6B7280}
    .card{background:#1F2937}
    .kpi{background:#1F2937}
    .kpi-val{color:#F9FAFB}
    .kpi-label{color:#9CA3AF}
    .kpi-sub{color:#6B7280}
    th{background:#1E3A5F;color:#93C5FD;border-bottom-color:#1D4ED8}
    td{border-bottom-color:#374151}
    tr:nth-child(even) td{background:#111827}
    .prose{color:#D1D5DB}
    .prose h2,.prose h3,.prose strong{color:#F9FAFB}
    .footer{border-top-color:#374151}
  }
</style>
</head><body>
<div class="header">
  <div class="header-top">
    <div>
      <div class="header-label">Dashboard</div>
      <h1>${escapeHtml(title)}</h1>
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
