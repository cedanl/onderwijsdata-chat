import { Suspense, lazy } from 'react'

// Plotly is 4,7 MB raw / 1,4 MB gzip (#512). Statisch geïmporteerd zat het in de
// gedeelde chunk van /chat en downloadde elk gesprek het, ook zonder één grafiek.
// Lazy laadt de chunk pas bij de eerste figuur.
const Plot = lazy(() => import('react-plotly.js'))

// De plaatsvervanger houdt de hoogte van de figuur vast, zodat de layout niet
// springt terwijl Plotly laadt.
export default function LazyPlot({ style, ...props }) {
  return (
    <Suspense fallback={<div style={style} aria-hidden="true" />}>
      <Plot style={style} {...props} />
    </Suspense>
  )
}
