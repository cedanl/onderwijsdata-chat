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
