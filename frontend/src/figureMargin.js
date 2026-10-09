// A chart with a note under its title (the CBS rounding note, #352) brings the top margin
// it needs; the tighter margin of the chat or the export would put title and note over the
// plot area and the top value label (CH-34).
export function topMargin(layout, base) {
  return layout?.title?.subtitle?.text ? Math.max(base, layout.margin?.t ?? 0) : base
}

export function topMarginOfJson(figureJson, base) {
  try {
    return topMargin(JSON.parse(figureJson)?.layout, base)
  } catch {
    return base
  }
}
