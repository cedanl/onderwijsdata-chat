import { useState, useEffect, useMemo } from 'react'
import { CHART_COLORS } from '../../../constants'
import { benchmarkColor, chartOpts, buildIndexChartOpts } from './chart-opts'
import {
  sortedEntries, yearOverYearDelta,
  buildPeerLinesData, buildPeerLinesOpts, buildBenchmarkLineData, buildSectorChartData,
} from './chart-builders'

// ─── Hooks ──────────────────────────────────────────────────────────────────

export function useDarkMode() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const obs = new MutationObserver(() =>
      setDark(document.documentElement.classList.contains('dark'))
    )
    obs.observe(document.documentElement, { attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])
  return dark
}

export function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('nl-NL')
}

// ─── Data hooks ─────────────────────────────────────────────────────────────

function useDashboardFetch(endpoint, instelling) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!instelling) return
    setLoading(true)
    setData(null)
    setError(null)
    fetch(`${endpoint}?instelling=${encodeURIComponent(instelling)}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [endpoint, instelling])

  return { data, loading, error }
}

export function useDashboardData(instelling) {
  return useDashboardFetch('/api/dashboard/instroom', instelling)
}

export function useRegioDashboardData(instelling) {
  return useDashboardFetch('/api/dashboard/regio', instelling)
}

export function useRegioComputed(data, instelling) {
  const dark = useDarkMode()

  return useMemo(() => {
    const bmColor = benchmarkColor(dark)
    const bm = data?.benchmark || {}
    const bmLabel = bm.label || 'Benchmark'
    const peers = bm.peers || {}
    const hasPeers = Object.keys(peers.ingeschrevenen || {}).length > 0

    const ingesEntries = sortedEntries(data?.ingeschrevenen)
    const ejEntries = sortedEntries(data?.eerstejaars)
    const diplEntries = sortedEntries(data?.gediplomeerden)

    const totaalRegioEntry = bm.totaal_ingeschrevenen
      ? Object.entries(bm.totaal_ingeschrevenen).sort((a, b) => a[0] - b[0]).at(-1)
      : null

    const vrouw = data?.geslacht?.VROUW || 0
    const man = data?.geslacht?.MAN || 0
    const totaalGeslacht = vrouw + man

    const ingesLineData = hasPeers
      ? buildPeerLinesData(data?.ingeschrevenen, peers.ingeschrevenen, instelling, CHART_COLORS[0], bmColor)
      : buildBenchmarkLineData(data?.ingeschrevenen, bm.ingeschrevenen, instelling, bmLabel, CHART_COLORS[0], bmColor)

    const lastDiplVal = diplEntries.at(-1)?.[1]
    const lastIngesVal = ingesEntries.at(-1)?.[1]
    const rendement = lastDiplVal && lastIngesVal
      ? Math.round((lastDiplVal / lastIngesVal) * 100)
      : null

    return {
      dark, bmColor, bm, bmLabel, hasPeers,
      opts: chartOpts(dark),
      indexOpts: buildIndexChartOpts(dark),
      peerOpts: buildPeerLinesOpts(dark, instelling),
      ingesEntries,
      lastInges: ingesEntries.at(-1),
      ingesDelta: yearOverYearDelta(ingesEntries),
      ejEntries,
      lastEj: ejEntries.at(-1),
      ejDelta: yearOverYearDelta(ejEntries),
      diplEntries,
      lastDipl: diplEntries.at(-1),
      diplDelta: yearOverYearDelta(diplEntries),
      totaalRegio: totaalRegioEntry?.[1] ?? null,
      totaalRegioJaar: totaalRegioEntry?.[0] ?? data?.laatste_jaar,
      pctVrouw: totaalGeslacht > 0 ? ((vrouw / totaalGeslacht) * 100).toFixed(1) : null,
      totaalGeslacht,
      vrouw, man,
      rendement,
      ingesLineData,
      ejLineData: buildBenchmarkLineData(data?.eerstejaars, bm.eerstejaars, instelling, bmLabel, CHART_COLORS[2], bmColor),
      diplLineData: buildBenchmarkLineData(data?.gediplomeerden, bm.gediplomeerden, instelling, bmLabel, CHART_COLORS[5], bmColor),
      sectorData: buildSectorChartData(data?.sectoren),
      geslachtTrend: data?.geslacht_trend || null,
    }
  }, [data, instelling, dark])
}
