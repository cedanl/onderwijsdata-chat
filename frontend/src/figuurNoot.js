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
