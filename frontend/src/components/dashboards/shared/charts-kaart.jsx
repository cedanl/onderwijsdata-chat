import { useMemo } from 'react'
import Plot from 'react-plotly.js'
import { SectionHeader } from './shell'

// ─── Kaart ───────────────────────────────────────────────────────────────────

export function KaartSection({ figureJson }) {
  const figure = useMemo(() => {
    if (!figureJson) return null
    try {
      return typeof figureJson === 'string' ? JSON.parse(figureJson) : figureJson
    } catch {
      return null
    }
  }, [figureJson])

  if (!figure) return null

  return (
    <>
      <SectionHeader
        title="Locaties in de regio"
        subtitle="Geografisch overzicht van instellingen in de benchmark-regio (ster = eigen instelling)"
      />
      <div className="chart-card" style={{ overflow: 'hidden', padding: 0, maxHeight: 240 }}>
        <Plot
          data={figure.data}
          layout={{ ...figure.layout, autosize: true }}
          config={{ displayModeBar: false, responsive: true, scrollZoom: false }}
          style={{ width: '100%' }}
          useResizeHandler
        />
      </div>
    </>
  )
}
