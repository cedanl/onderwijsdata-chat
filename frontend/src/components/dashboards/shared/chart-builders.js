import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  Tooltip, Legend, Filler,
} from 'chart.js'
import { SECTOR_LABELS, buildIndexChartOpts } from './chart-opts'
import { CHART_COLORS } from '../../../constants'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip, Legend, Filler)

// ─── Chart data builders ────────────────────────────────────────────────────

// Diplomas vs. vacancies per sector. The backend counts a UWV cluster shared by several sectors
// pro rata (#455), so the vacancy series is its per-sector count, not a sum over clusters.
// Aflopend op gediplomeerden en zonder sector met 0 of zonder waarde; die staan in `weggelaten`. Een sector zonder
// vacaturetelling krijgt geen staaf, geen 0 (#902).
export function buildSupplyDemandData(gediplomeerdenPerSector, vacaturesPerSector) {
  if (!gediplomeerdenPerSector || !vacaturesPerSector) return null
  const alle = Object.keys(gediplomeerdenPerSector)
  const sectors = alle
    .filter(s => gediplomeerdenPerSector[s] > 0)
    .sort((a, b) => gediplomeerdenPerSector[b] - gediplomeerdenPerSector[a])
  if (!sectors.length) return null
  return {
    labels: sectors.map(s => SECTOR_LABELS[s] || s),
    datasets: [
      { label: 'Gediplomeerden', data: sectors.map(s => gediplomeerdenPerSector[s]), backgroundColor: CHART_COLORS[0], borderWidth: 0, borderRadius: 4 },
      { label: 'Vacatures (gerelateerd)', data: sectors.map(s => vacaturesPerSector[s] ?? null), backgroundColor: CHART_COLORS[2], borderWidth: 0, borderRadius: 4 },
    ],
    weggelaten: alle.filter(s => !sectors.includes(s)).map(s => SECTOR_LABELS[s] || s),
  }
}

export function sortedEntries(dict) {
  if (!dict) return []
  return Object.entries(dict).sort((a, b) => a[0] - b[0])
}

export function yearOverYearDelta(entries) {
  const last = entries.at(-1)
  const prev = entries.at(-2)
  return last && prev ? last[1] - prev[1] : null
}

// ─── Groei: één regel voor grafiek, ranking en tabel (#903) ──────────────────
// De groei loopt van een gemeenschappelijk startjaar tot het eindjaar: het laatste van de eerste jaren met een waarde
// over de eigen instelling en de vergeleken reeksen (met minstens twee jaren). Zo heeft elke instelling op een pagina
// hetzelfde groeicijfer, met dezelfde basis; een reeks zonder waarde in het startjaar krijgt geen groei.

const _waarde = (dict, jaar) => dict?.[jaar] ?? dict?.[String(jaar)] ?? null

function _jarenMetWaarde(dict) {
  return Object.keys(dict || {}).map(Number).filter(j => _waarde(dict, j) > 0).sort((a, b) => a - b)
}

export function groeiStartjaar(dicts) {
  const eerste = dicts.map(_jarenMetWaarde).filter(j => j.length >= 2).map(j => j[0])
  return eerste.length ? Math.max(...eerste) : null
}

export function groeiPct(dict, startjaar, eindjaar) {
  if (startjaar == null || eindjaar == null) return null
  const start = _waarde(dict, startjaar)
  const eind = _waarde(dict, eindjaar)
  if (!(start > 0) || eind == null) return null
  return Math.round(((eind - start) / start) * 100)
}

// Elke waarde als % verandering t.o.v. het startjaar; een jaar zonder waarde blijft een gat.
function _index(dict, labels, startjaar) {
  const base = _waarde(dict, startjaar)
  return labels.map(y => {
    const v = _waarde(dict, y)
    return v != null && base > 0 ? Math.round(((v / base) - 1) * 100) : null
  })
}

export function buildPeerLinesData(ownDict, peersDict, ownLabel, ownColor, peerColor) {
  if (!ownDict) return null
  const allYears = new Set(Object.keys(ownDict).map(String))
  for (const d of Object.values(peersDict || {})) Object.keys(d).forEach(y => allYears.add(String(y)))
  const labels = [...allYears].sort((a, b) => Number(a) - Number(b))
  const startjaar = groeiStartjaar([ownDict, ...Object.values(peersDict || {})])
  const toIndex = dict => _index(dict, labels, startjaar)

  const datasets = []
  for (const [naam, data] of Object.entries(peersDict || {})) {
    datasets.push({
      label: naam,
      data: toIndex(data),
      borderColor: peerColor,
      backgroundColor: 'transparent',
      tension: 0.3,
      pointRadius: 2,
      borderWidth: 1.5,
      fill: false,
      pointHoverRadius: 4,
    })
  }
  // Own instelling last so it renders on top
  datasets.push({
    label: ownLabel,
    data: toIndex(ownDict),
    borderColor: ownColor,
    backgroundColor: 'transparent',
    tension: 0.3,
    pointRadius: 4,
    borderWidth: 3,
    fill: false,
    pointHoverRadius: 6,
  })
  return { labels, datasets, startjaar }
}

export function buildPeerLinesOpts(dark, ownLabel) {
  const base = buildIndexChartOpts(dark)
  return {
    ...base,
    plugins: {
      ...base.plugins,
      legend: {
        ...base.plugins.legend,
        labels: {
          ...base.plugins.legend.labels,
          filter: (item) => item.text === ownLabel,
        },
      },
    },
  }
}

export function buildBenchmarkLineData(ownDict, benchDict, ownLabel, benchLabel, ownColor, benchColor) {
  if (!ownDict) return null
  const labels = Object.keys(ownDict).sort((a, b) => a - b).map(String)
  // Eigen instelling en benchmark t.o.v. hetzelfde startjaar (#903); eerder nam elke reeks haar eigen eerste jaar.
  const startjaar = groeiStartjaar(benchDict ? [ownDict, benchDict] : [ownDict])
  const ownData = _index(ownDict, labels, startjaar)

  const datasets = [
    {
      label: ownLabel,
      data: ownData,
      borderColor: ownColor,
      backgroundColor: ownColor + '18',
      fill: true,
      tension: 0.3,
      pointRadius: 4,
      borderWidth: 2,
    },
  ]
  if (benchDict) {
    datasets.push({
      label: benchLabel,
      data: _index(benchDict, labels, startjaar),
      borderColor: benchColor,
      backgroundColor: 'transparent',
      borderDash: [5, 4],
      tension: 0.3,
      pointRadius: 3,
      borderWidth: 2,
      fill: false,
    })
  }
  return { labels, datasets, startjaar }
}
