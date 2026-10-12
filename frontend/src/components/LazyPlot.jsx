import { Component, Suspense, lazy } from 'react'

// Plotly is 4,7 MB raw / 1,4 MB gzip (#512). Statisch geïmporteerd zat het in de
// gedeelde chunk van /chat en downloadde elk gesprek het, ook zonder één grafiek.
// Lazy laadt de chunk pas bij de eerste figuur.
const Plot = lazy(() => import('react-plotly.js'))

// Hoogte van de plaatsvervanger als de aanroeper geen hoogte meegeeft; gelijk aan de
// maxHeight van de kaart (charts-kaart.jsx), zodat die niet verspringt als Plotly laadt.
const STANDAARD_HOOGTE = 340

const PLAATSHOUDER_STIJL = {
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontSize: '.75rem', color: 'var(--muted-text)',
}

function plaatshouderStijl(style) {
  return { ...PLAATSHOUDER_STIJL, ...style, minHeight: style?.height ?? STANDAARD_HOOGTE }
}

// Een mislukte chunk (oud tabblad na een deploy: de gehashte chunk geeft 404) mag niet
// via de ErrorBoundary van de app de hele route vervangen; alleen deze grafiek valt weg.
class GrafiekGrens extends Component {
  constructor(props) {
    super(props)
    this.state = { mislukt: false }
  }
  static getDerivedStateFromError() { return { mislukt: true } }
  componentDidCatch(error) {
    console.error('[LazyPlot] grafiek laden mislukt', error)
  }
  render() {
    if (this.state.mislukt) {
      return (
        <div role="alert" style={plaatshouderStijl(this.props.style)}>
          De grafiek kon niet worden geladen; vernieuw de pagina.
        </div>
      )
    }
    return this.props.children
  }
}

// De plaatsvervanger houdt de hoogte van de figuur vast, zodat de layout niet
// springt terwijl Plotly laadt.
export default function LazyPlot({ style, ...props }) {
  return (
    <GrafiekGrens style={style}>
      <Suspense fallback={<div role="status" aria-busy="true" style={plaatshouderStijl(style)}>Grafiek wordt geladen…</div>}>
        <Plot style={style} {...props} />
      </Suspense>
    </GrafiekGrens>
  )
}
