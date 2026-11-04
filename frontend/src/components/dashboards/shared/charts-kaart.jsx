import { useMemo, useState } from 'react'
import Plot from '../../LazyPlot'
import KaartTerugval from '../../KaartTerugval'
import WaardenTabel from '../../WaardenTabel'
import { SectionHeader } from './shell'
import { useDarkMode } from './hooks'
import { leesFiguur } from '../../../figuurJson'
import { useBasiskaart } from '../../../hooks/useBasiskaart'
import { KAART_HOOGTE, kaartBeschrijving, kaartData, kaartLayout, kaartTabel, zonderLocatie } from './kaart-figuur'

// ─── Kaart ───────────────────────────────────────────────────────────────────

const KAART_CONFIG = { displayModeBar: false, responsive: true, scrollZoom: false }
const KAART_STIJL = { width: '100%', height: KAART_HOOGTE }

// De kaart van de regio (#906). De basiskaart komt uit de eigen bundel (basiskaart.js), want de CSP houdt cdn.plot.ly
// tegen. Tekent de kaart toch niet (Plotly geeft een fout), dan nemen een melding en de tabel haar plaats in, zoals in
// de chat (KaartTerugval, #632). Wie niet op de kaart past omdat de plaats onbekend is, staat eronder (#628, #642).
export function KaartSection({ figureJson }) {
  const dark = useDarkMode()
  const figuur = useMemo(() => (figureJson ? leesFiguur(figureJson) : null), [figureJson])
  const basiskaart = useBasiskaart(figuur?.layout?.geo)
  const [mislukt, setMislukt] = useState(false)
  const layout = useMemo(() => figuur && kaartLayout(figuur.layout, dark), [figuur, dark])
  const data = useMemo(() => figuur && kaartData(figuur.data, dark), [figuur, dark])
  const tabel = useMemo(() => kaartTabel(figuur), [figuur])

  if (!figuur) return null
  const zonder = zonderLocatie(figuur)

  return (
    <>
      <SectionHeader
        title="Locaties in de regio"
        subtitle="Instellingen in de benchmark-regio (ster = eigen instelling), op benaderde plaatscoördinaten"
      />
      <div className="chart-card">
        {mislukt ? (
          <KaartTerugval figure={figuur} tabel={tabel} />
        ) : (
          <>
            {/* role="img" maakt de kaart één beeld met een naam (#588); de tabel eronder geeft de punten. */}
            <div role="img" aria-label={kaartBeschrijving(figuur)} style={{ minHeight: KAART_HOOGTE }}>
              {basiskaart === 'klaar' && (
                <Plot
                  data={data}
                  layout={layout}
                  config={KAART_CONFIG}
                  style={KAART_STIJL}
                  useResizeHandler
                  onError={() => setMislukt(true)}
                />
              )}
            </div>
            {tabel && <WaardenTabel tabel={tabel} />}
          </>
        )}
        {zonder.length > 0 && (
          <p className="kaart-zonder-locatie">
            Niet op de kaart, want de plaats is onbekend: {zonder.join(', ')}.
          </p>
        )}
      </div>
    </>
  )
}
