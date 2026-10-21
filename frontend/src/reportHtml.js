import { figureHeightOfJson } from './figureLayout'
import { zonderDubbeleTitel } from './figureKop'
import { scheidNootJson } from './figuurNoot'
import { scriptSafe } from './scriptSafe'
import { plotlyScript } from './plotlyBron'
import { DARK_FIGURE_JS } from './darkFigure'
import { veiligeBronUrl } from './bronLink'

export function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

// Koppen in de conclusie vallen onder de sectiekop (h2), dus allemaal h3: één h1 per rapport (#424).
function mdToHtml(src) {
  return String(src)
    .replace(/^#{1,3} (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^\s*[-*] (.+)$/gm, '<li>$1</li>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>')
}

function bullets(items) {
  return items.map(item => `<li>${escapeHtml(item)}</li>`).join('')
}

// De bronregel onder een grafiek (#569): bron, titel, dataset-ID, periode en status uit code, met de link
// naar de open-databron. Zonder herleidbare bron zegt de regel dat, en gokt niet. Alleen een http(s)-adres
// wordt een link (bronLink.js): de regel komt uit de store en de catalogus, maar wat in een spec staat is tekst.
function bronregelHtml(bron) {
  if (!bron || !bron.tekst) return '<p class="vis-bron">Bron niet vastgesteld</p>'
  const url = veiligeBronUrl(bron.url)
  const link = url
    ? ` · <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Bekijk de bron${bron.bron ? ` bij ${escapeHtml(bron.bron)}` : ''}</a>`
    : ''
  return `<p class="vis-bron">Bron: ${escapeHtml(bron.tekst)}${link}</p>`
}

// De donkere regels, één keer. De themakeuze van de app wint van de OS-voorkeur (#568), zoals styles.css dat
// voor de app doet: de viewer zet `dark` of `light` op <html> (reportThema.js), zonder klasse (modus 'systeem',
// de download, een ouder rapport in een oudere viewer) volgt het rapport prefers-color-scheme.
const DARK_RULES = [
  ['body', 'color:#F9FAFB;background:#111827'],
  ['.header', 'background:#1F2937;border-bottom-color:#374151'],
  ['.header h1', 'color:#F9FAFB'],
  ['.meta-chip,.meta-chip b', 'color:#9CA3AF'],
  ['.card', 'background:#1F2937'],
  ['.vraag', 'background:#1E3A5F;border-left-color:#3B82F6'],
  ['.vraag .vraag-text', 'color:#DBEAFE'],
  ['.vraag .section-label', 'color:#93C5FD'],
  ['.section-label', 'color:#9CA3AF'],
  ['.def-term,.vis-title,.prose h1,.prose h2,.prose h3,.prose strong', 'color:#F9FAFB'],
  ['.def-desc,.vis-note,.scope-col li,.prose,.bronnen li', 'color:#D1D5DB'],
  ['.vis-bron', 'color:#9CA3AF'],
  ['.vis-noot', 'color:#9CA3AF'],
  ['.vis-bron a', 'color:#60A5FA'],
  ['.scope-col li', 'border-bottom-color:#374151'],
  ['.def', 'border-bottom-color:#374151'],
  ['.vis-note', 'background:#111827;border-left-color:#1D4ED8'],
  ['.manifest,.footer', 'border-top-color:#374151'],
]

// Elke selector in een lijst krijgt het voorvoegsel: `.a,.b` wordt `html.dark .a,html.dark .b`.
const metVoorvoegsel = (voorvoegsel, selector) => selector.split(',').map(s => `${voorvoegsel} ${s}`).join(',')
const darkCss = voorvoegsel => DARK_RULES.map(([sel, decl]) => `${metVoorvoegsel(voorvoegsel, sel)}{${decl}}`).join('\n    ')

// Op een telefoon (#571, gemeten op 390 px): de figuurtitel viel rechts weg, de legendatitel naast de items
// maakte de legenda breder dan de figuur, en bij liggende staven lieten de namen op de y-as 64 px plotvlak
// over. Hieronder NARROW_PX: de titel afgebroken in regels en kleiner (de marge erboven groeit mee), de
// legendatitel boven de items, kleinere tick- en legendaletters, en de namen op de y-as van liggende staven
// afgebroken. De titel van een figuur van vóór #651 met noot hangt aan de bovenrand (CH-34); afgebroken stak zijn
// eerste regel 4 px boven de figuur uit (gemeten), vandaar 10 px padding erboven.
// Daarna (#579): jaartallen op een categorie-as kantelden 90° zodra ze niet naast elkaar pasten; dan staat om de
// zoveel jaar een label, het laatste jaar altijd (_nx, de breedte geschat op 6,5 px per teken van 11 px). Namen
// slaan niets over: elke naam hoort bij zijn staaf. Waardelabels krijgen de lettergrootte van de ticks (_nd). En na
// het tekenen groeit de figuur zo veel als het plotvlak tekortkomt (_ng): titel, ticks en een legenda van zes
// reeksen lieten 160 px over, en een rij liggende staven met een naam van twee regels liet 1 px tussen de namen.
// _fullLayout._size is de maat van het plotvlak; Plotly rekent zelf de rijen gelijk, dus elke rij krijgt de ruimte
// van de langste naam.
// Alleen kopieën, zoals DARK_FIGURE_JS (darkFigure.js); _o en _w van daar.
const NARROW_PX = 640
const NARROW_FIGURE_JS = `function _wr(s,n){var r=[],c='';String(s).split(' ').forEach(function(x){if(c&&(c+' '+x).length>n){r.push(c);c=x}else c=c?c+' '+x:x});if(c)r.push(c);return r.join('<br>')}
function _tf(a){return _w(a,{tickfont:_w(a.tickfont,{size:11})})}
function _nl(l){l=_w(l);var t=l.title;if(_o(t)&&typeof t.text==='string'&&t.text.indexOf('<br>')<0){var s=_wr(t.text,42),n=s.split('<br>').length;l.title=_w(t,{text:s,font:_w(t.font,{size:14})});if(n>1){l.margin=_w(l.margin,{t:(l.margin&&l.margin.t||48)+17*(n-1)});if(t.yref==='container'&&t.yanchor==='top')l.title.pad=_w(t.pad,{t:10})}}
if(_o(l.legend)){var lt=l.legend.title;l.legend=_w(l.legend,{font:_w(l.legend.font,{size:11})});if(_o(lt)&&lt.text||typeof lt==='string')l.legend.title=_w(_o(lt)?lt:{text:lt},{side:'top'})}
Object.keys(l).forEach(function(k){if(/^[xy]axis\\d*$/.test(k)&&_o(l[k]))l[k]=_tf(l[k])});return l}
function _ny(l,d){var y=_o(l.yaxis)?l.yaxis:{},c=[];if(y.tickvals||!Array.isArray(d)||!d.some(function(t){return _o(t)&&t.type==='bar'&&t.orientation==='h'}))return{layout:l,rij:0};
d.forEach(function(t){if(_o(t)&&Array.isArray(t.y))t.y.forEach(function(v){if(typeof v==='string'&&c.indexOf(v)<0)c.push(v)})});
var tt=c.map(function(v){return _wr(v,24)}),r=Math.max.apply(null,[1].concat(tt.map(function(v){return v.split('<br>').length})));if(r<2)return{layout:l,rij:0};
return{layout:_w(l,{yaxis:_w(y,{tickvals:c,ticktext:tt})}),rij:c.length*(r*14+4)}}
function _nx(l,d,w){var a=l.xaxis,c=[];if(!_o(a)||a.type!=='category'||a.tickvals||a.dtick||!Array.isArray(d))return l;
d.forEach(function(t){if(_o(t)&&t.orientation!=='h'&&Array.isArray(t.x))t.x.forEach(function(v){v=String(v);if(c.indexOf(v)<0)c.push(v)})});
if(c.length<3||!c.every(function(v){return /^\\d{4}/.test(v)}))return l;
var m=l.margin||{},p=Math.max(w-(m.l||60)-(m.r||24),1),n=Math.max.apply(null,c.map(function(v){return v.length})),k=Math.min(Math.ceil(c.length*(n*6.5+10)/p),c.length-1);
return k>1?_w(l,{xaxis:_w(a,{tickmode:'linear',tick0:(c.length-1)%k,dtick:k})}):l}
function _nd(d){return Array.isArray(d)?d.map(function(t){return _o(t)&&t.text!=null?_w(t,{textfont:_w(t.textfont,{size:11})}):t}):d}
function _ng(e,rij){var s=e._fullLayout&&e._fullLayout._size,tekort=s&&s.h>0?Math.max(220,rij)-s.h:0;if(tekort<1)return;var h=Math.round(e.getBoundingClientRect().height+tekort);e.style.height=h+'px';return Plotly.relayout(e,{height:h})}`

// Plotly zelf staat één keer in de head (plotlyBron.js, #486); hier alleen de grafiek. Een figuur die haar
// eigen hoogte meebrengt (liggende staven) houdt die; de andere krijgen de basishoogte uit de CSS (.plot-auto),
// op een telefoon hoger, zodat titel, ticklabels en legenda het plotvlak niet opeten (#571).
// Zonder titel (de kop erboven zegt het al, #579) is boven het plotvlak alleen ruimte nodig voor de bovenste tick.
const TOP_ZONDER_TITEL = 16

function plotlyHtml(figureJson, id, { titelWeg = false } = {}) {
  const eigen = figureHeightOfJson(figureJson, 0)
  const div = eigen ? `<div id="${id}" class="plot" style="height:${eigen}px">` : `<div id="${id}" class="plot plot-auto">`
  const boven = titelWeg ? TOP_ZONDER_TITEL : 48
  return `<div class="card">${div}</div></div>
    <script>(function(){${DARK_FIGURE_JS}
${NARROW_FIGURE_JS}
var f=${scriptSafe(figureJson)},_h=document.documentElement.classList,_d=_h.contains('dark')||(!_h.contains('light')&&window.matchMedia('(prefers-color-scheme:dark)').matches),_n=window.innerWidth<=${NARROW_PX},_e=document.getElementById('${id}'),_l=Object.assign({},f.layout,{paper_bgcolor:'transparent',plot_bgcolor:_d?'#111827':'#F9FAFB',margin:{t:${boven},r:24,b:48,l:60},font:{color:_d?'#D1D5DB':'#374151',family:'system-ui,sans-serif',size:12}}),_data=_d?_dd(f.data):f.data,_rij=0;if(_d)_l=_dl(_l);if(_n){var _y=_ny(_nl(_l),_data);_l=_nx(_y.layout,_data,_e.getBoundingClientRect().width||window.innerWidth-32);_rij=_y.rij;_data=_nd(_data)}var _p=Plotly.newPlot(_e,_data,_l,{responsive:true,displayModeBar:false});if(_n&&_p&&typeof _p.then==='function')_p.then(function(){return _ng(_e,_rij)});})()</script>`
}

// Afdrukken als PDF (#622): de browser drukt af, het rapport zorgt dat het op A4 past. Licht thema (de
// printhandler zet de klasse), geen schaduwen of achtergrond, elke kaart en grafiek op één pagina, grafieken
// op de breedte van een A4-kolom (de handler hieronder tekent ze daarop over vóór het afdrukken).
export const PRINT_BREEDTE = 680
export const PRINT_CSS = `@media print{
    @page{size:A4;margin:14mm}
    html,body{background:#fff!important;min-height:0}
    body{font-size:12px}
    .header{padding:0 0 16px;border-bottom:1px solid #E5E7EB;break-after:avoid}
    .body{padding:16px 0 0;max-width:none}
    .card,.vraag,.header{box-shadow:none;break-inside:avoid;page-break-inside:avoid}
    .vis{break-inside:avoid;page-break-inside:avoid}
    .vis .card{margin:0;padding:0}
    .card{border:1px solid #E5E7EB}
    .plot,.plot-auto{max-height:330px}
    .scope-row{grid-template-columns:1fr 1fr}
    .manifest,.footer{break-inside:avoid}
    a{color:inherit}
  }`
// Het bericht van de app ('edudata:print', WorkbookPrint.jsx): het rapport staat in een sandbox-frame met een
// opaque origin, dus de app kan print() niet zelf aanroepen. Alleen een bericht van de app zelf telt (#634). Vóór het afdrukken: licht thema en grafieken op
// A4-breedte; erna alles terug. Een rapport van vóór deze build kent het bericht niet: de app toont dan geen knop.
export const PRINT_BERICHT = 'edudata:print'
export const PRINT_JS = `(function(){
  var H=document.documentElement,B=document.body;
  function plots(){return Array.prototype.slice.call(document.querySelectorAll('.js-plotly-plot'))}
  function voorbereiden(){
    H.setAttribute('data-print-thema',H.classList.contains('dark')?'dark':H.classList.contains('light')?'light':'');
    H.classList.remove('dark');H.classList.add('light');
    B.style.width='${PRINT_BREEDTE}px';
    if(window.Plotly)plots().forEach(function(e){Plotly.relayout(e,{width:${PRINT_BREEDTE},height:Math.min(e.getBoundingClientRect().height||330,330)})});
  }
  function herstellen(){
    var t=H.getAttribute('data-print-thema');H.classList.remove('light');if(t)H.classList.add(t);H.removeAttribute('data-print-thema');
    B.style.width='';
    if(window.Plotly)plots().forEach(function(e){Plotly.relayout(e,{width:null,height:null,autosize:true})});
  }
  window.__edudataPrint={voorbereiden:voorbereiden,herstellen:herstellen};
  window.addEventListener('afterprint',herstellen);
  window.addEventListener('message',function(ev){if(ev.source!==window.parent||ev.data!=='${PRINT_BERICHT}')return;voorbereiden();setTimeout(function(){window.print()},150)});
})()`

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
        <h3 class="scope-title scope-yes">Wat dit rapport wel beantwoordt</h3>
        <ul>${bullets(s.beantwoordt)}</ul>
      </div>`
    : ''

  const beantwoordtNiet = (s.beantwoordt_niet || []).length
    ? `<div class="scope-col">
        <h3 class="scope-title scope-no">Wat dit rapport niet beantwoordt</h3>
        <ul>${bullets(s.beantwoordt_niet)}</ul>
      </div>`
    : ''

  const scopeHtml = (beantwoordt || beantwoordtNiet)
    ? `<div class="card">
        <h2 class="section-label">Reikwijdte</h2>
        <div class="scope-row">${beantwoordt}${beantwoordtNiet}</div>
      </div>`
    : ''

  const visualisaties = (s.visualisaties || []).map((v, i) => {
    const kop = v.titel || `Visualisatie ${i + 1}`
    // De afrondingsnoot als tekstregel onder de grafiek, vóór de bronregel (#651).
    const { figureJson, noot } = scheidNootJson(v.figure_json)
    const figuur = zonderDubbeleTitel(figureJson, kop)
    return `<div class="vis">
       <h3 class="vis-title">${escapeHtml(kop)}</h3>
       ${plotlyHtml(figuur.figureJson, `rp${i}`, figuur)}
       ${noot ? `<p class="vis-noot">${escapeHtml(noot)}</p>` : ''}
       ${bronregelHtml(v.bron)}
       ${v.toelichting ? `<p class="vis-note">${escapeHtml(v.toelichting)}</p>` : ''}
     </div>`
  }).join('')

  const conclusieProse = mdToHtml(escapeHtml(s.conclusie || ''))
  const conclusieHtml = conclusieProse
    ? `<div class="card conf">
        <h2 class="section-label">Conclusie</h2>
        <div class="prose"><p>${conclusieProse}</p></div>
      </div>`
    : ''

  const verantwoording = manifestHtml(s.manifest)

  const bronnen = (s.bronnen || [])
  const bronnenHtml = bronnen.length
    ? `<div class="card">
        <h2 class="section-label">Bronnen</h2>
        <ol class="bronnen">${bronnen.map(b => `<li>${escapeHtml(b)}</li>`).join('')}</ol>
      </div>`
    : ''

  const instellingBadge = instelling
    ? `<div class="instelling-badge">${escapeHtml(instelling)}</div>`
    : ''

  return `<!DOCTYPE html><html lang="nl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(s.title || 'Rapport')}</title>
${(s.visualisaties || []).length ? plotlyScript() : ''}
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
  .plot-auto{height:360px}
  .vis-noot{margin-top:8px;color:#6B7280;font-size:.8rem;line-height:1.45}
  .vis-bron{margin-top:8px;color:#6B7280;font-size:.8rem;line-height:1.5}
  .vis-bron a{color:#2563EB;text-decoration:underline}
  .vis-note{margin-top:14px;color:#4B5563;line-height:1.6;font-size:.92rem;background:#F9FAFB;border-left:3px solid #DBEAFE;padding:12px 16px;border-radius:0 6px 6px 0}
  .conf{background:#fff}
  .prose{line-height:1.7;color:#374151}
  .prose h1,.prose h2,.prose h3{font-weight:700;margin:1em 0 .4em;color:#111827}
  .prose li{margin:.3em 0 .3em 1.4em}
  .prose strong{color:#111827}
  .prose p{margin:.5em 0}
  .bronnen{margin-left:20px}
  .bronnen li{color:#4B5563;font-size:.88rem;line-height:1.6;margin:.3em 0}
  .manifest{color:#9CA3AF;font-size:.7rem;line-height:1.6;padding:12px 32px 0;border-top:1px solid #F3F4F6;margin-top:8px}
  .footer{text-align:center;color:#9CA3AF;font-size:.72rem;padding:20px 32px 32px;border-top:1px solid #F3F4F6;margin-top:8px}
  .header h1,.vraag-text,.scope-col li,.def-desc,.vis-note,.vis-noot,.vis-bron,.prose,.bronnen li,.manifest{overflow-wrap:anywhere}
  @media(max-width:640px){.scope-row{grid-template-columns:1fr}.body{padding:16px}.header{padding:20px 16px}.header-top{flex-direction:column}.def{flex-direction:column;gap:4px}.card{padding:16px}.vis .card{padding:0;margin:0 -16px}.plot-auto{height:420px}.header-label,.section-label,.manifest,.footer{font-size:.75rem}}
  ${PRINT_CSS}
  ${darkCss('html.dark')}
  @media(prefers-color-scheme:dark){
    ${darkCss('html:not(.light)')}
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
    <h2 class="section-label">Onderzoeksvraag</h2>
    <div class="vraag-text">${escapeHtml(s.onderzoeksvraag || '')}</div>
  </div>
  ${scopeHtml}
  ${definitionHtml ? `<div class="card"><h2 class="section-label">Gekozen definities</h2>${definitionHtml}</div>` : ''}
  ${visualisaties ? `<div class="card"><h2 class="section-label">Visualisaties</h2>${visualisaties}</div>` : ''}
  ${conclusieHtml}
  ${bronnenHtml}
</div>
${verantwoording}
<div class="footer">Gegenereerd door openEDUdata+ · Gebaseerd op open onderwijsdata</div>
<script>${PRINT_JS}</script>
</body></html>`
}

// Het model zoals de gebruiker het kent (BEV-10): de naam uit het manifest, of bij een ouder
// rapport zonder model_naam het id zonder provider (azure_ai/claude-sonnet-5-5 -> claude-sonnet-5-5).
const zonderProvider = id => String(id).split('/').pop()
const modelNaam = m => m.model_naam || zonderProvider(m.model)

// Herkomst van het rapport (#345), compact onder de bronnen: model, prompt-, catalogus-,
// app- en dataversie, en of seed/temperature het model echt bereikten.
function manifestHtml(manifest) {
  if (!manifest || !manifest.model) return ''
  const m = manifest
  const toegepast = v => (v === true ? 'toegepast' : v === false ? 'niet toegepast' : 'onbekend')
  const delen = [
    `model ${modelNaam(m)}${m.model_versie ? ` (${zonderProvider(m.model_versie)})` : ''}`,
    m.sampling ? `seed ${toegepast(m.sampling.seed_toegepast)}` : '',
    m.prompt_hash ? `prompt ${m.prompt_hash}` : '',
    m.catalogus ? `catalogus ${m.catalogus}` : '',
    m.app ? `app ${m.app}` : '',
  ].filter(Boolean)
  const data = (m.data_as_of || []).map(d => {
    const extra = [
      d.laatste_update ? `bijgewerkt ${d.laatste_update}` : '',
      d.periodestatus?.length ? `status ${d.periodestatus.join('/')}` : '',
      d.herladen_op ? `herladen ${d.herladen_op}` : '',
      d.peilmoment || '',
    ].filter(Boolean).join(', ')
    return `${d.bron.toUpperCase()} ${d.dataset}${extra ? ` (${extra})` : ''}`
  })
  return `<div class="manifest">
    <div>Verantwoording: ${escapeHtml(delen.join(' · '))}</div>
    ${data.length ? `<div>Dataversie: ${escapeHtml(data.join(' · '))}</div>` : ''}
  </div>`
}