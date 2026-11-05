import { Chart as ChartJS } from 'chart.js'
import { CHART_COLORS } from '../../../constants'
import { fmt } from './getal'

// ─── Chart options & constants ───────────────────────────────────────────────

// Wat elke dashboardgrafiek deelt (#905, #906), als standaard van Chart.js, zodat geen grafiek het vergeet:
// - letters van 13 px: de ondergrens voor leesbare lagen is 12,5 px (#613); Chart.js begint op 12;
// - een tik of muis hoeft niet precies op een punt van 2-4 px (intersect: false): het dichtstbijzijnde punt in de
//   grafiek telt, waar je ook tikt. Het tikdoel is daarmee de hele grafiek, ruim boven de 40 px van HOVER_DISTANCE in
//   de chat (#614). Chart.js luistert passief naar touch, dus een veeg over een grafiek scrolt de pagina;
// - geen animatie bij prefers-reduced-motion (WCAG 2.3.3), en die keuze volgt een wijziging in het systeem;
// - getallen op de assen en in de tooltips in Nederlandse notatie (10.000; 52,3): de locale voor de ticks zonder eigen
//   callback, fmt() in elke callback (#904).
// Een klik op de legenda zet een reeks aan of uit met de standaard van Chart.js; geen eigen onClick (#907): de zes
// kopieën die er waren, lieten een reeks met `hidden: true` bij de eerste klik verborgen.
export const FONT_GROOTTE = 13

export function pasStandaardenToe(defaults, bewegingMedia) {
  defaults.font.size = FONT_GROOTTE
  defaults.locale = 'nl-NL'
  Object.assign(defaults.interaction, { mode: 'nearest', intersect: false, axis: 'xy' })
  const animatie = defaults.animation
  const volg = () => { defaults.animation = bewegingMedia?.matches ? false : animatie }
  volg()
  bewegingMedia?.addEventListener?.('change', volg)
}

pasStandaardenToe(ChartJS.defaults, typeof window !== 'undefined' ? window.matchMedia?.('(prefers-reduced-motion: reduce)') : null)

// Een liggende staaf vangt een tik over de hele rij, niet alleen op de staaf zelf.
export const TIK_LIGGEND = { mode: 'index', axis: 'y', intersect: false }

export function darkColors(dark) {
  return {
    tick: dark ? '#9CA3AF' : '#6B7280',
    grid: dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6',
    label: dark ? '#D1D5DB' : '#374151',
  }
}

// De waardeas van een lijn volgt de eenheid, zoals create_plot in tools/plot.py (#871): een telling begint op 0, anders
// oogt een daling van 2 % als een klif. Een percentage mag afgekapt, maar dan staat dat op de as.
export const AS_NIET_BIJ_NUL = 'as begint niet bij 0'

export function tellingAs(as) {
  return { ...as, beginAtZero: true }
}

// Chart.js laat een verborgen reeks buiten het asbereik; alleen wat bij het openen te zien is telt.
export function afgekapteAs(as, datasets, kleur) {
  const waarden = datasets
    .filter(d => !d.hidden)
    .flatMap(d => d.data)
    .filter(v => typeof v === 'number' && Number.isFinite(v))
  if (!waarden.length || Math.min(...waarden) <= 0) return as
  return { ...as, title: { display: true, text: AS_NIET_BIJ_NUL, color: kleur } }
}

export function buildIndexChartOpts(dark) {
  const { tick, grid, label } = darkColors(dark)
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: { color: label, boxWidth: 20 },
      },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const v = ctx.parsed.y
            return `${ctx.dataset.label}: ${v >= 0 ? '+' : ''}${fmt(v)}%`
          },
        },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick } },
      y: {
        grid: { color: grid },
        ticks: { color: tick, callback: (v) => `${fmt(v)}%` },
        title: { display: true, text: '% verandering t.o.v. het startjaar', color: tick },
      },
    },
  }
}

// De vergelijking (benchmark, concurrenten) in grijs, met 3:1 tegen de kaart in beide thema's (#905): #94A3B8 en
// #CBD5E1 haalden op wit 2,6:1 en 1,5:1, #475569 in het donkere thema 2,1:1.
const BENCHMARK_COLOR_LIGHT = '#64748B'
const BENCHMARK_COLOR_DARK = '#9CA3AF'
export function benchmarkColor(dark) { return dark ? BENCHMARK_COLOR_DARK : BENCHMARK_COLOR_LIGHT }

// Een staafkleur die iets zegt, uit het palet (3:1 in beide thema's): een daling (rood).
export const DAAL_KLEUR = CHART_COLORS[3]

// Tekstkleuren met 4,5:1 tegen de kaart, voor een oordeel (goed, gemiddeld, slecht) of een trend.
const OORDEEL_LICHT = { goed: '#047857', gemiddeld: '#B45309', matig: '#C2410C', slecht: '#B91C1C', neutraal: '#475569' }
const OORDEEL_DONKER = { goed: '#34D399', gemiddeld: '#FBBF24', matig: '#FB923C', slecht: '#F87171', neutraal: '#9CA3AF' }
export const oordeelKleur = (oordeel, dark) => (dark ? OORDEEL_DONKER : OORDEEL_LICHT)[oordeel]

export const SECTOR_LABELS = {
  ECONOMIE: 'Economie',
  GEZONDHEIDSZORG: 'Gezondheidszorg',
  GEDRAG_EN_MAATSCHAPPIJ: 'Gedrag & Maatschappij',
  ONDERWIJS: 'Onderwijs',
  TECHNIEK: 'Techniek',
  NATUUR: 'Natuur',
  TAAL_EN_CULTUUR: 'Taal & Cultuur',
  RECHT: 'Recht',
  LANDBOUW_EN_NATUURLIJKE_OMGEVING: 'Landbouw',
  SECTOROVERSTIJGEND: 'Sectoroverstijgend',
}
// Een sector houdt in elke grafiek dezelfde kleur (#905): de kleur hangt aan de naam, niet aan de plek in de reeks.
// Een bekende sector (code of label uit SECTOR_LABELS) heeft een vaste plek in het palet; andere namen (leerwegen,
// sectorkamers) krijgen de vrije kleuren op alfabet, zodat dezelfde set namen steeds dezelfde kleuren krijgt.
const SECTOR_CODES = Object.keys(SECTOR_LABELS)
const sectorCode = naam => SECTOR_CODES.find(code => code === naam || SECTOR_LABELS[code] === naam)

export function sectorKleuren(namen) {
  const kleuren = CHART_COLORS
  const vast = new Map(namen.map(naam => [naam, sectorCode(naam)]).filter(([, code]) => code)
    .map(([naam, code]) => [naam, kleuren[SECTOR_CODES.indexOf(code) % kleuren.length]]))
  const vrij = kleuren.filter(k => ![...vast.values()].includes(k))
  const rest = [...new Set(namen.filter(naam => !vast.has(naam)))].sort((a, b) => a.localeCompare(b, 'nl'))
  rest.forEach((naam, i) => vast.set(naam, vrij.length ? vrij[i % vrij.length] : kleuren[i % kleuren.length]))
  return vast
}

// Een lang label op de as van een liggende staaf in regels van hoogstens `breedte` tekens (#905). Chart.js geeft die as
// hoogstens de halve grafiek; met 13 px viel op 390 px de voorkant van "Gedrag & Maatschappij" en van lange
// instellingsnamen weg. Een woord langer dan de breedte breekt af met een streepje (#951: van "Informatie- en
// communicatietechnologie" bleef op 390 px "…municatietechnologie" over).
export const LABEL_BREEDTE = 18

function stukken(woord, breedte) {
  if (woord.length <= breedte) return [woord]
  const delen = []
  for (let i = 0; i < woord.length; i += breedte - 1) delen.push(woord.slice(i, i + breedte - 1))
  return delen.map((deel, i) => (i < delen.length - 1 ? `${deel}-` : deel))
}

export function labelRegels(label, breedte = LABEL_BREEDTE) {
  const tekst = String(label ?? '')
  if (tekst.length <= breedte) return tekst
  const regels = []
  for (const woord of tekst.split(/\s+/).flatMap(w => stukken(w, breedte))) {
    const laatste = regels.at(-1)
    if (laatste != null && `${laatste} ${woord}`.length <= breedte) regels[regels.length - 1] = `${laatste} ${woord}`
    else regels.push(woord)
  }
  return regels
}

// Ticks voor de categorie-as van een liggende staaf: het label, afgebroken in regels, en elk label op de as. Chart.js
// sloeg bij veel categorieën elk tweede label over (autoSkip): Gediplomeerden vs. vacatures, Beroepencluster,
// Rendement vergelijking, Ingeschrevenen per hoofdgroep (#951). Daarom staat autoSkip hier uit, voor elke liggende
// staaf, en geeft staafHoogte elke categorie de ruimte voor haar regels.
export function categorieTicks(kleur, breedte = LABEL_BREEDTE) {
  return {
    color: kleur,
    padding: 4,
    autoSkip: false,
    callback(waarde) { return labelRegels(this.getLabelForValue(waarde), breedte) },
  }
}

// De hoogte van een liggende staafgrafiek: elke categorie krijgt ten minste `perRij` px en ruimte voor de regels van
// haar label (labelRegels), plus `kader` voor legenda en waardeas. Chart.js geeft elke categorie even veel ruimte, dus
// de naam met de meeste regels bepaalt de rij. Zonder die ruimte schuiven labels zonder autoSkip over elkaar.
const REGEL_PX = 17

export function staafHoogte(labels, { perRij = 34, kader = 40, minimum = 160, breedte = LABEL_BREEDTE } = {}) {
  const regels = Math.max(1, ...labels.map(l => [labelRegels(l, breedte)].flat().length))
  return Math.max(minimum, kader + labels.length * Math.max(perRij, regels * REGEL_PX + 8))
}

// Stippellijnen dwars over de waardeas van een liggende staaf, op de waarden in `options.plugins.drempellijnen.waarden`
// (#949: de drempels van de arbeidsmarktmatch). Chart.js heeft geen annotatie zonder extra pakket; dit is een
// inline-plugin voor <Grafiek plugins={[DREMPELLIJNEN]}>. De lijn is een extra: de grafiek noemt de drempel ook in tekst.
export const DREMPELLIJNEN = {
  id: 'drempellijnen',
  afterDatasetsDraw(chart, _args, opties) {
    const { waarden = [], kleur = '#475569' } = opties || {}
    const { ctx, chartArea, scales } = chart
    const as = scales?.x
    if (!as || !chartArea) return
    ctx.save()
    ctx.strokeStyle = kleur
    ctx.lineWidth = 1.5
    ctx.setLineDash([5, 4])
    for (const waarde of waarden) {
      const x = as.getPixelForValue(waarde)
      if (!(x >= chartArea.left && x <= chartArea.right)) continue
      ctx.beginPath()
      ctx.moveTo(x, chartArea.top)
      ctx.lineTo(x, chartArea.bottom)
      ctx.stroke()
    }
    ctx.restore()
  },
}

// `opmaak` zet de waarde in de tooltip om: fmt, of fmtProcent voor een aandeel met een vast aantal decimalen.
export function horizontalBarOpts(dark, tooltipSuffix = '', opmaak = fmt) {
  const { tick, grid } = darkColors(dark)
  return {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    interaction: TIK_LIGGEND,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: { label: ctx => ` ${opmaak(ctx.raw)}${tooltipSuffix}` },
      },
    },
    scales: {
      x: { grid: { color: grid }, ticks: { color: tick } },
      y: { grid: { display: false }, ticks: categorieTicks(tick) },
    },
  }
}
