// De afrondingsnoot van CBS (#352) staat als tekstregel onder de grafiek, niet in de figuur (#651): als ondertitel
// van 11 px was hij niet te selecteren, op een telefoon te klein, en kostte hij bovenmarge. tools/plot.py zet hem in
// layout.meta.afrondingsnoot; een figuur van vóór die wijziging (een bewaard gesprek of dashboard) heeft hem nog als
// layout.title.subtitle. Elke weergave haalt hem hier uit de figuur en toont hem zelf, als tekst.
import { alsTekst } from './figureKop'

const metaNoot = layout => {
  const noot = layout.meta?.afrondingsnoot
  return typeof noot === 'string' ? noot.trim() : ''
}

// { figure, noot }: de figuur zonder ondertitel en de noot als platte tekst. Zonder noot, zonder figuur of zonder
// layout: de figuur zoals hij was en noot ''. Alleen kopieën; de figuur zelf blijft ongemoeid.
export function scheidNoot(figure) {
  const layout = figure?.layout
  if (!layout || typeof layout !== 'object') return { figure, noot: '' }
  const title = layout.title
  const subtitle = title && typeof title === 'object' ? title.subtitle : undefined
  const noot = metaNoot(layout) || alsTekst(subtitle?.text)
  if (!noot) return { figure, noot: '' }
  if (subtitle === undefined) return { figure, noot }
  const { subtitle: _, ...rest } = title
  return { figure: { ...figure, layout: { ...layout, title: rest } }, noot }
}

// Hetzelfde voor het figuurJSON van een rapport of dashboard: { figureJson, noot }. Onleesbaar JSON komt ongewijzigd
// terug, met noot ''.
export function scheidNootJson(figureJson) {
  let figuur
  try {
    figuur = JSON.parse(figureJson)
  } catch {
    return { figureJson, noot: '' }
  }
  const { figure, noot } = scheidNoot(figuur)
  return { figureJson: figure === figuur ? figureJson : JSON.stringify(figure), noot }
}

// De noten die tools/plot.py bij een figuur zet, elk als eigen tekstregel onder de grafiek: een trendbreuk met haar
// bronpassage (#1262), een correctie van de grafiekregels (#1264) en "ondergrens niet per punt bekend" (#1261).
export function figuurNoten(figure) {
  const noten = figure?.layout?.meta?.figuurnoten
  return Array.isArray(noten) ? noten.filter(n => typeof n === 'string' && n.trim()).map(n => n.trim()) : []
}

export function figuurNotenJson(figureJson) {
  try {
    return figuurNoten(JSON.parse(figureJson))
  } catch {
    return []
  }
}

// De bronregel ín de figuur, alleen in afdruk, rapport en Word (#1257): één korte regel boven het plotvlak met de bron
// en "ten minste" als een onderdrukte cel meetelt (layout.meta.bronregel van tools/plot.py). Op het scherm in de chat
// staat hij er niet in (#651): daar staat de herkomst eronder. Een lange regel breekt op "; ".
export const BRONREGEL_NAAM = 'bronregel'
export const BRONREGEL_REGELHOOGTE = 14

export function metBronregel(figure) {
  const regel = figure?.layout?.meta?.bronregel
  if (typeof regel !== 'string' || !regel.trim()) return { figure, extraBoven: 0 }
  // Plotly leest < en > in annotatietekst als opmaak; de bronregel is gewone tekst.
  const regels = regel.replace(/[<>]/g, '').split(/;\s+/)
  const annotatie = {
    name: BRONREGEL_NAAM,
    text: regels.join('<br>'),
    xref: 'paper', x: 0, xanchor: 'left',
    yref: 'paper', y: 1, yanchor: 'bottom', yshift: 2,
    showarrow: false, align: 'left', font: { size: 10 },
  }
  const layout = figure.layout
  const annotations = [...(Array.isArray(layout.annotations) ? layout.annotations : []), annotatie]
  return { figure: { ...figure, layout: { ...layout, annotations } }, extraBoven: regels.length * BRONREGEL_REGELHOOGTE }
}

export function metBronregelJson(figureJson) {
  let figuur
  try {
    figuur = JSON.parse(figureJson)
  } catch {
    return { figureJson, extraBoven: 0 }
  }
  const { figure, extraBoven } = metBronregel(figuur)
  return { figureJson: figure === figuur ? figureJson : JSON.stringify(figure), extraBoven }
}
