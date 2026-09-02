function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function mdToHtml(src) {
  return String(src)
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^\s*[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>')
}

function bullets(items) {
  return items.map(item => `<li>${escapeHtml(item)}</li>`).join('')
}

function plotlyHtml(figureJson, id) {
  return `<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <div class="card"><div id="${id}" style="height:360px"></div></div>
    <script>(function(){var f=${figureJson},_d=window.matchMedia('(prefers-color-scheme:dark)').matches;Plotly.newPlot('${id}',f.data,Object.assign({},f.layout,{paper_bgcolor:'transparent',plot_bgcolor:_d?'#111827':'#F9FAFB',margin:{t:48,r:24,b:48,l:60},font:{color:_d?'#D1D5DB':'#374151',family:'system-ui,sans-serif',size:12}}),{responsive:true,displayModeBar:false});})()</script>`
}

export function buildReportHtml(spec, { instelling = '' } = {}) {
  const s = spec || {}
  const datum = s.datum || new Date().toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })
  const auteur = s.auteur || 'onbekend'

  const definitionHtml = (s.definities || []).map(d =>
    `<div class="def">
       <span class="def-term">${escapeHtml(d.begrip || '')}</span>
       <span class="def-desc">${escapeHtml(d.definitie || d || '')}</span>
     </div>`
  ).join('')

  const beantwoordt = (s.beantwoordt || []).length
    ? `<div class="scope-col">
        <div class="scope-title scope-yes">Wat dit rapport wel beantwoordt</div>
        <ul>${bullets(s.beantwoordt)}</ul>
      </div>`
    : ''

  const beantwoordtNiet = (s.beantwoordt_niet || []).length
    ? `<div class="scope-col">
        <div class="scope-title scope-no">Wat dit rapport niet beantwoordt</div>
        <ul>${bullets(s.beantwoordt_niet)}</ul>
      </div>`
    : ''

  const scopeHtml = (beantwoordt || beantwoordtNiet)
    ? `<div class="card">
        <div class="section-label">Reikwijdte</div>
        <div class="scope-row">${beantwoordt}${beantwoordtNiet}</div>
      </div>`
    : ''

  const visualisaties = (s.visualisaties || []).map((v, i) =>
    `<div class="vis">
       <div class="vis-title">${escapeHtml(v.titel || `Visualisatie ${i + 1}`)}</div>
       ${plotlyHtml(v.figure_json, `rp${i}`)}
       ${v.toelichting ? `<p class="vis-note">${escapeHtml(v.toelichting)}</p>` : ''}
     </div>`
  ).join('')

  const conclusieProse = mdToHtml(escapeHtml(s.conclusie || ''))
  const conclusieHtml = conclusieProse
    ? `<div class="card conf">
        <div class="section-label">Conclusie</div>
        <div class="prose"><p>${conclusieProse}</p></div>
      </div>`
    : ''

  const bronnen = (s.bronnen || [])
  const bronnenHtml = bronnen.length
    ? `<div class="card">
        <div class="section-label">Bronnen</div>
        <ol class="bronnen">${bronnen.map(b => `<li>${escapeHtml(b)}</li>`).join('')}</ol>
      </div>`
    : ''

  const instellingBadge = instelling
    ? `<div class="instelling-badge">${escapeHtml(instelling)}</div>`
    : ''

  return `<!DOCTYPE html><html lang="nl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(s.title || 'Rapport')}</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,-apple-system,sans-serif;font-size:14px;color:#111827;background:#F3F4F6;min-height:100vh}
  .header{background:#fff;border-bottom:1px solid #E5E7EB;padding:28px 32px}
  .header-top{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
  .header-label{font-size:.7rem;font-weight:700;color:#2563EB;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
  .header h1{font-size:1.35rem;font-weight:800;color:#111827;line-height:1.3}
  .meta{margin-top:8px;display:flex;flex-wrap:wrap;gap:14px;align-items:center}
  .meta-chip{font-size:.74rem;color:#6B7280}
  .meta-chip b{color:#374151;font-weight:600}
  .instelling-badge{display:flex;align-items:center;gap:6px;background:#DCFCE7;color:#15803D;font-size:.75rem;font-weight:700;padding:5px 10px;border-radius:6px;width:fit-content;flex-shrink:0}
  .body{padding:28px 32px;max-width:1100px;margin:0 auto}
  .card{background:#fff;border-radius:10px;padding:24px;box-shadow:0 1px 3px rgba(0,0,0,.07);margin-bottom:20px}
  .section-label{font-size:.7rem;font-weight:700;color:#6B7280;text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px}
  .vraag{border-left:4px solid #2563EB;background:#EFF6FF;border-radius:0 10px 10px 0;padding:20px 24px;margin-bottom:20px}
  .vraag .section-label{color:#1D4ED8;margin-bottom:6px}
  .vraag .vraag-text{font-size:1.05rem;font-weight:700;color:#1E3A8A;line-height:1.5}
  .scope-row{display:grid;grid-template-columns:1fr 1fr;gap:24px}
  .scope-col ul{list-style:none}
  .scope-col li{position:relative;padding:8px 0 8px 24px;border-bottom:1px solid #F3F4F6;font-size:.9rem;color:#4B5563}
  .scope-col li:last-child{border-bottom:none}
  .scope-col li::before{content:'';position:absolute;left:4px;top:14px;width:7px;height:7px;border-radius:50%}
  .scope-title{font-size:.8rem;font-weight:700;margin-bottom:4px}
  .scope-yes{color:#15803D}.scope-yes::before{content:'✓ '}
  .scope-no{color:#B91C1C}.scope-no::before{content:'✗ '}
  .scope-col.yes li::before{background:#22C55E}.scope-col.no li::before{background:#EF4444}
  .def{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #F3F4F6}
  .def:last-child{border-bottom:none}
  .def-term{flex:0 0 34%;font-weight:700;color:#111827;font-size:.92rem}
  .def-desc{flex:1;color:#4B5563;font-size:.9rem;line-height:1.5}
  .vis-title{font-size:1.05rem;font-weight:700;color:#111827;margin-bottom:12px}
  .vis-note{margin-top:14px;color:#4B5563;line-height:1.6;font-size:.92rem;background:#F9FAFB;border-left:3px solid #DBEAFE;padding:12px 16px;border-radius:0 6px 6px 0}
  .conf{background:#fff}
  .prose{line-height:1.7;color:#374151}
  .prose h1,.prose h2,.prose h3{font-weight:700;margin:1em 0 .4em;color:#111827}
  .prose li{margin:.3em 0 .3em 1.4em}
  .prose strong{color:#111827}
  .prose p{margin:.5em 0}
  .bronnen{margin-left:20px}
  .bronnen li{color:#4B5563;font-size:.88rem;line-height:1.6;margin:.3em 0}
  .footer{text-align:center;color:#9CA3AF;font-size:.72rem;padding:20px 32px 32px;border-top:1px solid #F3F4F6;margin-top:8px}
  @media(max-width:640px){.scope-row{grid-template-columns:1fr}.body{padding:16px}.header{padding:20px 16px}.def{flex-direction:column;gap:4px}}
  @media(prefers-color-scheme:dark){
    body{color:#F9FAFB;background:#111827}
    .header{background:#1F2937;border-bottom-color:#374151}
    .header h1{color:#F9FAFB}
    .meta-chip,.meta-chip b{color:#9CA3AF}
    .card{background:#1F2937}
    .vraag{background:#1E3A5F;border-left-color:#3B82F6}
    .vraag .vraag-text{color:#DBEAFE}
    .vraag .section-label{color:#93C5FD}
    .section-label{color:#9CA3AF}
    .def-term,.vis-title,.prose h1,.prose h2,.prose h3,.prose strong{color:#F9FAFB}
    .def-desc,.vis-note,.scope-col li,.prose,.bronnen li{color:#D1D5DB}
    .scope-col li{border-bottom-color:#374151}
    .def{border-bottom-color:#374151}
    .vis-note{background:#111827;border-left-color:#1D4ED8}
    .footer{border-top-color:#374151}
  }
</style>
</head><body>
<div class="header">
  <div class="header-top">
    <div>
      <div class="header-label">Rapport</div>
      <h1>${escapeHtml(s.title || 'Rapport')}</h1>
      <div class="meta">
        <span class="meta-chip">Gegenereerd op <b>${escapeHtml(datum)}</b></span>
        <span class="meta-chip">Auteur <b>${escapeHtml(auteur)}</b></span>
      </div>
    </div>
    ${instellingBadge}
  </div>
</div>
<div class="body">
  <div class="vraag">
    <div class="section-label">Onderzoeksvraag</div>
    <div class="vraag-text">${escapeHtml(s.onderzoeksvraag || '')}</div>
  </div>
  ${scopeHtml}
  ${definitionHtml ? `<div class="card"><div class="section-label">Gekozen definities</div>${definitionHtml}</div>` : ''}
  ${visualisaties ? `<div class="card"><div class="section-label">Visualisaties</div>${visualisaties}</div>` : ''}
  ${conclusieHtml}
  ${bronnenHtml}
</div>
<div class="footer">Gegenereerd door openEDUdata+ · Gebaseerd op open onderwijsdata</div>
</body></html>`
}