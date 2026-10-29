import { memo, useMemo } from 'react'
import Plot from './LazyPlot'
import KaartTerugval from './KaartTerugval'
import WaardenTabel from './WaardenTabel'
import { chatFigureLayout, figureHeight, isMapFigure } from '../figureLayout'
import { KAART_HOOGTE } from '../kaartBeeld'
import { useDarkMode } from '../hooks/useDarkMode'
import { useElementWidth } from '../hooks/useElementWidth'
import { useKaartStatus } from '../hooks/useKaartStatus'
import { figureToCsv, figureCsvProblem, figureCsvFilename } from '../figureCsv'
import { figuurBeschrijving } from '../figuurBeschrijving'
import { figuurTabel } from '../figuurTabel'
import { scheidNoot } from '../figuurNoot'
import { saveFile } from '../saveFile'

// Een grafiek in een antwoord, met haar CSV-download en de tabel als alternatief. Uit ChatPage.jsx gehaald (#696).

function downloadCsv(csv, filename) {
  saveFile(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }), filename)
}

function parseFigure(figureJson) {
  try {
    return typeof figureJson === 'string' ? JSON.parse(figureJson) : figureJson
  } catch {
    return null
  }
}

const NO_TRACES = []

const PLOT_CONFIG = { responsive: true, displayModeBar: false }

// The chart's width in steps of 16 px: its title is broken again when a phone turns (#587), not
// for every pixel.
const WIDTH_STEP = 16

// react-plotly redraws when data, layout or config change by reference, and a redraw is costly. So
// everything handed to <Plot> is derived once per figure, theme and width step, not once per render.
export const PlotlyFigure = memo(function PlotlyFigure({ figureJson, label }) {
  const dark = useDarkMode()
  const [wrapRef, width] = useElementWidth(WIDTH_STEP)
  // De afrondingsnoot als tekstregel onder de grafiek, niet in de figuur (#651).
  const { figure, noot } = useMemo(() => scheidNoot(parseFigure(figureJson)), [figureJson])
  const layout = useMemo(() => figure && chatFigureLayout(figure, dark, width), [figure, dark, width])
  const csv = useMemo(() => figure && figureToCsv(figure), [figure])
  const csvProblem = useMemo(() => figure && figureCsvProblem(figure), [figure])
  const beschrijving = useMemo(() => figure && figuurBeschrijving(figure), [figure])
  const tabel = useMemo(() => figuurTabel(figure), [figure])
  const isMap = Boolean(figure && isMapFigure(figure))
  const kaart = useKaartStatus(isMap)
  if (!figure) return null
  // Een kaart die niet getekend is, heet niet "Kaart aangemaakt" (#632): de melding en de tabel nemen haar plaats in.
  const kaartMislukt = isMap && kaart.status === 'mislukt'
  return (
    <div ref={wrapRef} style={{ margin: '8px 0', position: 'relative' }} className="plotly-figure-wrap">
      {label && <div style={{ fontSize: 'var(--font-klein)', color: 'var(--gray-500)', marginBottom: 4 }}>{kaartMislukt ? 'Kaart niet getekend' : label}</div>}
      {kaartMislukt && <KaartTerugval figure={figure} />}
      {csvProblem && (
        <div role="alert" style={{ fontSize: 'var(--font-klein)', color: 'var(--danger, #b42318)', marginBottom: 4 }}>
          Deze grafiek is niet te exporteren: {csvProblem}. Controleer de cijfers in het antwoord.
        </div>
      )}
      {csv && (
        <button type="button"
          className="csv-download-btn"
          title="Download als CSV"
          onClick={() => downloadCsv(csv, figureCsvFilename(figure, label || 'data'))}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          CSV
        </button>
      )}
      {/* The chart's accessible name (#588), on the chart only: role="img" makes its children
          presentational, and the CSV button above must stay a button. */}
      <div hidden={kaartMislukt} {...(beschrijving && { role: 'img', 'aria-label': beschrijving })}>
        <Plot
          data={figure.data || NO_TRACES}
          layout={layout}
          config={PLOT_CONFIG}
          useResizeHandler
          onInitialized={kaart.onInitialized}
          onError={kaart.onError}
          style={{ width: '100%', height: isMap ? KAART_HOOGTE : figureHeight(figure.layout, 340) }}
        />
      </div>
      {noot && <p className="figuur-noot">{noot}</p>}
      {/* Een kaart die niet getekend is, toont haar tabel al in KaartTerugval. */}
      {tabel && !kaartMislukt && <WaardenTabel tabel={tabel} />}
    </div>
  )
})
