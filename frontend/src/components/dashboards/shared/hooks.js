import { useState, useEffect, useMemo, useCallback } from 'react'
import { useDarkMode } from '../../../hooks/useDarkMode'
import { fetchDashboardData } from '../../../api'
import { CHART_COLORS } from '../../../constants'
import { benchmarkColor, buildIndexChartOpts } from './chart-opts'
import {
  sortedEntries, yearOverYearDelta,
  buildPeerLinesData, buildPeerLinesOpts, buildBenchmarkLineData,
} from './chart-builders'

// ─── Hooks ──────────────────────────────────────────────────────────────────

// Eén implementatie voor de hele app (#834); hier opnieuw geëxporteerd voor de dashboards.
export { useDarkMode }

export function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('nl-NL')
}

// ─── Data hooks ─────────────────────────────────────────────────────────────

// Zo lang wacht een dashboard op de server (#901): ruim boven DASHBOARD_TIMEOUT_S (90 s), zodat de server eerst zijn
// eigen melding geeft. Zonder grens bleef "Data laden…" staan zolang de verbinding hing.
export const DASHBOARD_TIMEOUT_MS = 120_000

const eigenMelding = e => typeof e?.message === 'string' && e.message !== '' && !/^API \d+$/.test(e.message)

// Wat de gebruiker leest als een dashboard niet laadt (#901), en of een nieuwe poging zin heeft. Nooit de ruwe
// "API 500" of "Failed to fetch": een tekst van de server zelf (503 bron niet beschikbaar of druk, 504 tijdsgrens,
// 403 uit) gaat ongewijzigd door, de rest krijgt een vaste zin, zoals een gesprek dat de server niet kreeg (#785).
export function dashboardFout(e, verlopen = false) {
  if (verlopen) return { melding: 'Het dashboard kwam niet op tijd binnen. Probeer het opnieuw.', herstelbaar: true }
  if (e?.status === 401) return { melding: 'Je sessie is verlopen. Log opnieuw in.', herstelbaar: false }
  if (e?.status === 403) return { melding: eigenMelding(e) ? e.message : 'Dashboards zijn niet beschikbaar.', herstelbaar: false }
  if (e?.status === 503 || e?.status === 504) {
    return { melding: eigenMelding(e) ? e.message : 'De server is nu niet bereikbaar. Probeer het over een minuut opnieuw.', herstelbaar: true }
  }
  if (e?.status) return { melding: 'Het dashboard kon niet worden geladen. Probeer het opnieuw.', herstelbaar: true }
  return { melding: 'De server kreeg het verzoek niet. Controleer je verbinding en probeer het opnieuw.', herstelbaar: true }
}

function useDashboardFetch(endpoint, instelling) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [poging, setPoging] = useState(0)

  useEffect(() => {
    if (!instelling) return
    const ac = new AbortController()
    let verlopen = false
    const grens = setTimeout(() => { verlopen = true; ac.abort() }, DASHBOARD_TIMEOUT_MS)
    setLoading(true)
    setData(null)
    setError(null)
    fetchDashboardData(endpoint, instelling, { signal: ac.signal })
      .then(d => { if (!ac.signal.aborted) { setData(d); setLoading(false) } })
      .catch(e => {
        if (ac.signal.aborted && !verlopen) return // een andere instelling of een nieuwe poging nam het over
        setError(dashboardFout(e, verlopen))
        setLoading(false)
      })
      .finally(() => clearTimeout(grens))
    return () => { clearTimeout(grens); ac.abort() }
  }, [endpoint, instelling, poging])

  // Een nieuwe poging: dezelfde aanvraag opnieuw. De server cachet geen mislukte lading (#901).
  const opnieuw = useCallback(() => setPoging(p => p + 1), [])

  return { data, loading, error, opnieuw }
}

export function useRegioDashboardData(instelling) {
  return useDashboardFetch('/api/dashboard/regio', instelling)
}

export function useNationaalDashboardData(instelling) {
  return useDashboardFetch('/api/dashboard/nationaal', instelling)
}

export function useRendementDashboardData(instelling) {
  return useDashboardFetch('/api/dashboard/rendement', instelling)
}

export function useArbeidsmarktmatchDashboardData(instelling) {
  return useDashboardFetch('/api/dashboard/arbeidsmarktmatch', instelling)
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

    const lastDiplEntry = diplEntries.at(-1)
    const lastIngesEntry = ingesEntries.at(-1)
    const sameYear = lastDiplEntry && lastIngesEntry && lastDiplEntry[0] === lastIngesEntry[0]
    const rendement = sameYear && lastIngesEntry[1]
      ? Math.round((lastDiplEntry[1] / lastIngesEntry[1]) * 100)
      : null

    return {
      dark, bmColor, bm, bmLabel, hasPeers,
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
      vrouw, man,
      rendement,
      ingesLineData,
      ejLineData: buildBenchmarkLineData(data?.eerstejaars, bm.eerstejaars, instelling, bmLabel, CHART_COLORS[2], bmColor),
      diplLineData: buildBenchmarkLineData(data?.gediplomeerden, bm.gediplomeerden, instelling, bmLabel, CHART_COLORS[5], bmColor),
    }
  }, [data, instelling, dark])
}
