import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  ArcElement, Tooltip, Legend, Filler,
} from 'chart.js'
import { SECTOR_LABELS, SECTOR_COLORS, buildIndexChartOpts } from './chart-opts'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Tooltip, Legend, Filler)

// ─── Chart data builders ────────────────────────────────────────────────────

export function buildBarChartData(dict, label, color) {
  if (!dict) return null
  const entries = Object.entries(dict).sort((a, b) => a[0] - b[0])
  return {
    labels: entries.map(([y]) => String(y)),
    datasets: [{ label, data: entries.map(([, v]) => v), backgroundColor: color, borderRadius: 6 }],
  }
}

export function buildLineChartData(dict, label, borderColor, bgColor) {
  if (!dict) return null
  const entries = Object.entries(dict).sort((a, b) => a[0] - b[0])
  return {
    labels: entries.map(([y]) => String(y)),
    datasets: [{ label, data: entries.map(([, v]) => v), borderColor, backgroundColor: bgColor, fill: true, tension: 0.3, pointRadius: 4 }],
  }
}

export function buildSectorChartData(sectoren, { type = 'doughnut' } = {}) {
  if (!sectoren) return null
  const entries = Object.entries(sectoren).sort((a, b) => b[1] - a[1]).slice(0, 7)
  const dataset = { data: entries.map(([, v]) => v), backgroundColor: SECTOR_COLORS, borderWidth: 0 }
  if (type === 'bar') {
    dataset.label = 'Ingeschrevenen'
    dataset.borderRadius = 6
  }
  return {
    labels: entries.map(([k]) => SECTOR_LABELS[k] || k),
    datasets: [dataset],
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

export function buildPeerLinesData(ownDict, peersDict, ownLabel, ownColor, peerColor) {
  if (!ownDict) return null
  const allYears = new Set(Object.keys(ownDict).map(String))
  for (const d of Object.values(peersDict || {})) Object.keys(d).forEach(y => allYears.add(String(y)))
  const labels = [...allYears].sort((a, b) => Number(a) - Number(b))

  const toIndex = (dict) => {
    const raw = labels.map(y => dict[y] ?? dict[Number(y)] ?? null)
    const base = raw.find(v => v != null && v > 0)
    return raw.map(v => v != null && base > 0 ? Math.round(((v / base) - 1) * 100) : null)
  }

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
  return { labels, datasets }
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
  const ownEntries = Object.entries(ownDict).sort((a, b) => a[0] - b[0])
  const labels = ownEntries.map(([y]) => String(y))
  const ownRaw = ownEntries.map(([, v]) => v)

  const toIndex = (values, base) =>
    values.map(v => v != null && base > 0 ? Math.round(((v / base) - 1) * 100) : null)

  const ownBase = ownRaw.find(v => v != null && v > 0) ?? ownRaw[0]
  const ownData = toIndex(ownRaw, ownBase)

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
    const benchMap = new Map(Object.entries(benchDict).map(([k, v]) => [String(k), v]))
    const benchRaw = labels.map(y => benchMap.get(y) ?? null)
    const benchBase = benchRaw.find(v => v != null)
    datasets.push({
      label: benchLabel,
      data: toIndex(benchRaw, benchBase),
      borderColor: benchColor,
      backgroundColor: 'transparent',
      borderDash: [5, 4],
      tension: 0.3,
      pointRadius: 3,
      borderWidth: 2,
      fill: false,
    })
  }
  return { labels, datasets }
}
