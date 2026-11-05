import { createContext, createElement, useState, useEffect, useMemo, useCallback, useContext } from 'react'
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

// Eén aanvraag met de tijdsgrens (#901). De belofte faalt nooit: ze geeft { data }, { fout } of { afgebroken } (een
// andere instelling of een nieuwe poging nam het over; niets om te tonen).
function nieuweLading(endpoint, instelling) {
  const ac = new AbortController()
  let verlopen = false
  const grens = setTimeout(() => { verlopen = true; ac.abort() }, DASHBOARD_TIMEOUT_MS)
  const belofte = fetchDashboardData(endpoint, instelling, { signal: ac.signal })
    .then(data => ({ data }), e => (ac.signal.aborted && !verlopen ? { afgebroken: true } : { fout: dashboardFout(e, verlopen) }))
    .finally(() => clearTimeout(grens))
  return { belofte, afbreken: () => ac.abort() }
}

// Op de dashboardpagina delen de miniaturen in de galerij en het dashboard erachter één lading per endpoint en
// instelling (#933): wie een dashboard opent nadat zijn miniatuur laadde, of terwijl die nog laadt, vraagt de server
// niets nieuws. Alleen een geslaagde lading blijft staan; na een fout vraagt een nieuwe poging het opnieuw (#901). De
// ladingen leven zo lang als de pagina, dus wie later terugkomt krijgt verse cijfers. Zonder deze provider laadt elk
// dashboard zelf, zoals voorheen.
const Ladingen = createContext(null)

export function DashboardLadingen({ children }) {
  const [ladingen] = useState(() => new Map())
  return createElement(Ladingen.Provider, { value: ladingen }, children)
}

const sleutel = (endpoint, instelling) => `${endpoint}?${instelling}`

// Een gedeelde lading loopt door als één gebruiker weggaat: een ander wacht er misschien op.
function gedeeldeLading(ladingen, endpoint, instelling) {
  const k = sleutel(endpoint, instelling)
  let lading = ladingen.get(k)
  if (!lading) {
    lading = { ...nieuweLading(endpoint, instelling), afbreken: () => {} }
    ladingen.set(k, lading)
    lading.belofte.then(({ data }) => {
      if (data !== undefined) lading.data = data
      else if (ladingen.get(k) === lading) ladingen.delete(k)
    })
  }
  return lading
}

function useDashboardFetch(endpoint, instelling) {
  const ladingen = useContext(Ladingen)
  // Een lading die er al is, staat er meteen: geen laadscherm tussen de miniatuur en het dashboard.
  const [data, setData] = useState(() => (instelling && ladingen?.get(sleutel(endpoint, instelling))?.data) || null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [poging, setPoging] = useState(0)

  useEffect(() => {
    if (!instelling) return
    const lading = ladingen ? gedeeldeLading(ladingen, endpoint, instelling) : nieuweLading(endpoint, instelling)
    setError(null)
    if (lading.data !== undefined) {
      setData(lading.data)
      setLoading(false)
      return
    }
    let weg = false
    setLoading(true)
    setData(null)
    lading.belofte.then(({ data: d, fout, afgebroken }) => {
      if (weg || afgebroken) return
      if (fout) setError(fout)
      else setData(d)
      setLoading(false)
    })
    return () => { weg = true; lading.afbreken() }
  }, [ladingen, endpoint, instelling, poging])

  // Een nieuwe poging: dezelfde aanvraag opnieuw, ook als de vorige slaagde maar een deel niet kon laden (#901).
  const opnieuw = useCallback(() => {
    if (instelling) ladingen?.delete(sleutel(endpoint, instelling))
    setPoging(p => p + 1)
  }, [ladingen, endpoint, instelling])

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
    // Het soort jaar per reeks uit de payload (#904): schooljaar of diplomajaar.
    const perioden = data?.perioden || {}
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
      ? buildPeerLinesData(data?.ingeschrevenen, peers.ingeschrevenen, instelling, CHART_COLORS[0], bmColor, perioden.ingeschrevenen)
      : buildBenchmarkLineData(data?.ingeschrevenen, bm.ingeschrevenen, instelling, bmLabel, CHART_COLORS[0], bmColor, perioden.ingeschrevenen)

    return {
      dark, bmColor, bm, bmLabel, hasPeers, perioden,
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
      pctVrouw: totaalGeslacht > 0 ? Math.round((vrouw / totaalGeslacht) * 1000) / 10 : null,
      vrouw, man,
      ingesLineData,
      ejLineData: buildBenchmarkLineData(data?.eerstejaars, bm.eerstejaars, instelling, bmLabel, CHART_COLORS[2], bmColor, perioden.eerstejaars),
      diplLineData: buildBenchmarkLineData(data?.gediplomeerden, bm.gediplomeerden, instelling, bmLabel, CHART_COLORS[5], bmColor, perioden.gediplomeerden),
    }
  }, [data, instelling, dark])
}
