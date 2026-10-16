import { topMargin } from './figureMargin'
import { titelOpBreedte } from './figureTitel'

// A chart that brings its own height gets it: horizontal bars grow with the number of
// categories, and the fixed height of the chat or the report squashed 18 of them together.
export function figureHeight(layout, base) {
  const height = layout?.height
  return typeof height === 'number' && height > 0 ? height : base
}

export function figureHeightOfJson(figureJson, base) {
  try {
    return figureHeight(JSON.parse(figureJson)?.layout, base)
  } catch {
    return base
  }
}

// The server puts the legend under the chart. A stored chart from before that, or one without a
// place of its own, gets the same: to the right it took a third of the width, on a phone nearly all.
const LEGEND_BELOW = { orientation: 'h', x: 0, xanchor: 'left', yref: 'container', y: 0, yanchor: 'bottom' }

export function legendBelow(legend) {
  const placed = legend && (legend.x != null || legend.y != null || legend.orientation != null)
  return placed ? legend : { ...LEGEND_BELOW, ...legend }
}

// A stored chart from before the server drew a highlighted bar as one series has a series per
// bar, named after its own bar: its legend only repeats the axis.
export function legendRepeatsAxis(data) {
  return Array.isArray(data) && data.length > 1 &&
    data.every(t => Array.isArray(t.x) && t.x.length === 1 && String(t.name) === String(t.x[0]))
}

const CHART_MARGIN = { l: 48, r: 24, b: 40 }
const MAP_MARGIN = { l: 0, r: 0, b: 0 }
const BASE_TOP_MARGIN = 32
// The title starts at 5% of the width (Plotly's template), above a map that runs to the edge too, so
// it gets the width of a chart's plot area: the room to its right absorbs wider letters (#587).
const TITLE_SIDES = CHART_MARGIN.l + CHART_MARGIN.r

const LIGHT = { bg: '#fff', font: '#374151', legendBg: 'rgba(255,255,255,0.8)', legendBorder: '#ddd' }
const DARK = { bg: '#1E293B', font: '#E2E8F0', legendBg: 'rgba(30,41,59,0.9)', legendBorder: '#475569' }

export function isMapFigure(figure) {
  return Boolean(figure.data?.some(t => t.type?.includes('choropleth')))
}

// The server bakes a dark title (#222) and note (#666) into the figure, and those beat the chat's
// font colour: in the dark theme they get the light colours of darkFigure.js.
function darkTitle(title) {
  if (!title || typeof title !== 'object') return title
  const subtitle = title.subtitle && { ...title.subtitle, font: { ...title.subtitle.font, color: '#9CA3AF' } }
  return { ...title, font: { ...title.font, color: '#F9FAFB' }, ...(subtitle && { subtitle }) }
}

// The layout of a chart in the chat, for the theme and the width the chart really has (0 while that
// is unknown). A long title is broken into lines, with their height added to the top margin; the
// figure itself stays as it is, so the CSV export reads the unbroken title.
export function chatFigureLayout(figure, dark, width) {
  const isMap = isMapFigure(figure)
  const colours = dark ? DARK : LIGHT
  const top = isMap ? BASE_TOP_MARGIN : topMargin(figure.layout, BASE_TOP_MARGIN)
  const { title, extra } = titelOpBreedte(figure.layout?.title, width - TITLE_SIDES, top)
  return {
    ...figure.layout,
    ...(title !== undefined && { title: dark ? darkTitle(title) : title }),
    paper_bgcolor: colours.bg,
    plot_bgcolor: colours.bg,
    margin: { ...(isMap ? MAP_MARGIN : CHART_MARGIN), t: top + extra },
    font: { family: 'system-ui, sans-serif', size: 12, color: colours.font },
    legend: {
      ...legendBelow(figure.layout?.legend),
      bgcolor: colours.legendBg,
      bordercolor: colours.legendBorder,
      font: { color: colours.font },
    },
    ...(legendRepeatsAxis(figure.data) && { showlegend: false }),
    autosize: true,
  }
}
