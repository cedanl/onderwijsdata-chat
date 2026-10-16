// Een grafiek als Nederlandse zin, de toegankelijke naam van de figuur (#588): soort, titel, assen, en per
// reeks het aantal punten met de eerste en laatste waarde. Alle getallen komen uit de figuurdata.

import { plotlyArray } from './plotlyArrays'
import { xsOf, ysOf } from './figureCsv'

const MAX_REEKSEN = 5
const GETAL = new Intl.NumberFormat('nl-NL')

// Een titel of aslabel van Plotly: een tekst of {text}, met <br> en andere opmaaktags.
function schoon(waarde) {
  const ruw = typeof waarde === 'object' && waarde !== null ? waarde.text : waarde
  if (typeof ruw !== 'string' && typeof ruw !== 'number') return ''
  return String(ruw).replace(/<br\s*\/?>/gi, ' ').replace(/<[^<>]*>/g, '').replace(/\s+/g, ' ').trim()
}

// Plotly's standaard: zonder type een scatter, zonder mode met lijnen.
function soort(trace) {
  const type = typeof trace.type === 'string' ? trace.type : 'scatter'
  if (type === 'scatter' || type === 'scattergl') {
    return typeof trace.mode !== 'string' || trace.mode.includes('lines') ? 'Lijngrafiek' : 'Spreidingsdiagram'
  }
  if (type === 'bar') return 'Staafdiagram'
  if (type === 'pie') return 'Cirkeldiagram'
  if (type.includes('choropleth')) return 'Kaart'
  return 'Grafiek'
}

const geldig = y => (typeof y === 'number' ? Number.isFinite(y) : typeof y === 'string' && y.trim() !== '')
const waarde = y => (typeof y === 'number' ? GETAL.format(y) : y.trim())
// x is een label (een jaar, een instelling) en blijft zoals hij er staat: 2020 is geen 2.020.
const punt = ([x, y]) => (x == null || x === '' ? waarde(y) : `${x}: ${waarde(y)}`)
const telwoord = (n, enkel, meer) => `${n} ${n === 1 ? enkel : meer}`

function reeks(trace, [enkel, meer]) {
  const xs = xsOf(trace)
  const punten = ysOf(trace).map((y, i) => [xs[i], y]).filter(([, y]) => geldig(y))
  if (!punten.length) return null
  const naam = schoon(trace.name)
  const delen = [telwoord(punten.length, enkel, meer)]
  if (punten.length === 1) delen.push(punt(punten[0]))
  else delen.push(`eerste ${punt(punten[0])}`, `laatste ${punt(punten.at(-1))}`)
  return `${naam ? `${naam}: ` : ''}${delen.join(', ')}`
}

function assen(layout) {
  const tekst = [['X-as', layout.xaxis], ['y-as', layout.yaxis]]
    .map(([as, opmaak]) => [as, schoon(opmaak?.title)])
    .filter(([, label]) => label)
    .map(([as, label]) => `${as}: ${label}`)
    .join(', ')
  return tekst && tekst[0].toUpperCase() + tekst.slice(1)
}

function gebieden(traces) {
  const n = traces.reduce((som, t) => som + (plotlyArray(t.locations ?? t.z)?.length ?? 0), 0)
  return n ? telwoord(n, 'gebied', 'gebieden') : null
}

function reeksen(traces, eenheid) {
  const zinnen = traces.map(t => reeks(t, eenheid)).filter(Boolean)
  const rest = zinnen.length - MAX_REEKSEN
  return rest > 0 ? [...zinnen.slice(0, MAX_REEKSEN), `En nog ${telwoord(rest, 'reeks', 'reeksen')}`] : zinnen
}

function inhoud(naam, traces, layout) {
  if (naam === 'Kaart') return [gebieden(traces)]
  if (naam === 'Cirkeldiagram') return reeksen(traces, ['deel', 'delen'])
  if (naam === 'Grafiek') return [assen(layout)]
  return [assen(layout), ...reeksen(traces, ['punt', 'punten'])]
}

// De zin, of null voor een figuur zonder data: die krijgt geen naam.
export function figuurBeschrijving(figure) {
  const traces = Array.isArray(figure?.data) ? figure.data.filter(t => t && typeof t === 'object') : []
  if (!traces.length) return null
  const layout = figure.layout ?? {}
  const naam = soort(traces[0])
  const titel = schoon(layout.title)
  const kop = titel ? `${naam}: ${titel}` : naam
  return `${[kop, ...inhoud(naam, traces, layout)].filter(Boolean).join('. ')}.`
}
