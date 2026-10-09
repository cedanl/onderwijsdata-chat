// A workbook as one standalone HTML file, to share with someone without an account (#254).
// A report already is one; a generated dashboard is built here from its spec, with
// Plotly from the CDN as in the report, so the file needs no server of ours.
import { escapeHtml, PLOTLY_CDN_VERSION } from './reportHtml'
import { scriptSafe } from './scriptSafe'

const asJson = fig => (typeof fig === 'string' ? fig : JSON.stringify(fig))

function kpiHtml(kpi) {
  const trend = kpi.trend ? `${kpi.trendDirection === 'down' ? '↓' : '↑'} ${escapeHtml(kpi.trend)} ` : ''
  const sub = kpi.sub ? `<span class="sub">${escapeHtml(kpi.sub)}</span>` : ''
  return `<div class="card kpi">
    <div class="kpi-label">${escapeHtml(kpi.label || '')}</div>
    <div class="kpi-value">${escapeHtml(kpi.value ?? '')}</div>
    ${trend || sub ? `<div class="kpi-trend ${kpi.trendDirection === 'down' ? 'down' : ''}">${trend}${sub}</div>` : ''}
  </div>`
}

function figureHtml(fig, i) {
  return `<div class="card"><div id="fig${i}" style="height:320px"></div></div>
<script>(function(){var f=${scriptSafe(asJson(fig))},d=window.matchMedia('(prefers-color-scheme:dark)').matches;Plotly.newPlot('fig${i}',f.data||[],Object.assign({},f.layout,{paper_bgcolor:'transparent',plot_bgcolor:'transparent',margin:{t:48,r:24,b:48,l:60},font:{color:d?'#D1D5DB':'#374151',family:'system-ui,sans-serif',size:12}}),{responsive:true,displayModeBar:false});})()</script>`
}

// narrativeHtml: the narrative already rendered as safe HTML (see workbookHtml).
export function buildDashboardHtml(spec, { title, instelling = '', narrativeHtml = '' }) {
  const kpis = spec?.kpis || []
  const figures = spec?.figures_json || []
  const sources = spec?.sources || []
  return `<!DOCTYPE html><html lang="nl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(title || 'Dashboard')}</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,-apple-system,sans-serif;font-size:14px;color:#111827;background:#F3F4F6}
  header{background:#fff;border-bottom:1px solid #E5E7EB;padding:24px 32px}
  header h1{font-size:1.3rem;font-weight:800}
  .badge{display:inline-block;margin-top:8px;background:#DCFCE7;color:#15803D;font-size:.75rem;font-weight:700;padding:4px 10px;border-radius:6px}
  main{padding:24px 32px;max-width:1100px;margin:0 auto}
  .card{background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:16px;overflow-x:auto}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px}
  .charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,440px),1fr));gap:16px}
  .kpi-label{font-size:.8rem;color:#6B7280}
  .kpi-value{font-size:1.6rem;font-weight:800;margin:6px 0}
  .kpi-trend{font-size:.8rem;color:#15803D}.kpi-trend.down{color:#B91C1C}
  .sub{color:#6B7280}
  .prose{line-height:1.7}.prose p,.prose ul,.prose table{margin:.5em 0}.prose li{margin-left:1.4em}
  .prose table{border-collapse:collapse}.prose th,.prose td{border:1px solid #E5E7EB;padding:4px 10px;text-align:left}
  .label{font-size:.7rem;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}
  .bronnen{margin-left:20px;color:#4B5563}
  footer{text-align:center;color:#9CA3AF;font-size:.72rem;padding:20px 32px 32px}
  @media(max-width:640px){header,main{padding:16px}}
  @media(prefers-color-scheme:dark){
    body{color:#F9FAFB;background:#111827}
    header,.card{background:#1F2937}header{border-bottom-color:#374151}
    .kpi-label,.sub,.label,.bronnen{color:#9CA3AF}
    .prose th,.prose td{border-color:#374151}
  }
</style>
${figures.length ? `<script src="https://cdn.plot.ly/plotly-${PLOTLY_CDN_VERSION}.min.js"></script>` : ''}
</head><body>
<header>
  <h1>${escapeHtml(title || 'Dashboard')}</h1>
  ${instelling ? `<div class="badge">${escapeHtml(instelling)}</div>` : ''}
</header>
<main>
  ${kpis.length ? `<div class="grid">${kpis.map(kpiHtml).join('')}</div>` : ''}
  ${figures.length ? `<div class="charts">${figures.map(figureHtml).join('')}</div>` : ''}
  ${narrativeHtml ? `<div class="card prose">${narrativeHtml}</div>` : ''}
  ${sources.length ? `<div class="card"><div class="label">Bronnen</div><ol class="bronnen">${sources.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ol></div>` : ''}
</main>
<footer>Gegenereerd door openEDUdata+ · Gebaseerd op open onderwijsdata</footer>
</body></html>`
}

// The narrative through the same markdown renderer as the app: tables work, raw HTML
// stays text. Loaded on demand, so the download costs the first load nothing.
async function narrativeToHtml(narrative) {
  if (!narrative) return ''
  const [{ createElement }, { renderToStaticMarkup }, { default: ReactMarkdown }, { default: remarkGfm }] = await Promise.all([
    import('react'), import('react-dom/server'), import('react-markdown'), import('remark-gfm'),
  ])
  return renderToStaticMarkup(createElement(ReactMarkdown, { remarkPlugins: [remarkGfm] }, narrative))
}

// The HTML of a workbook, or null for a built-in dashboard: that one is live app code.
export async function workbookHtml(workbook, { instelling = '' } = {}) {
  if (workbook.builtin) return null
  const spec = workbook.dashboardSpec
  if (spec) {
    return buildDashboardHtml(spec, { title: workbook.title, instelling, narrativeHtml: await narrativeToHtml(spec.narrative) })
  }
  return workbook.htmlContent || null
}

export const workbookFilename = workbook => (workbook.title || 'dashboard').replace(/[^a-zA-Z0-9]/g, '_') + '.html'
