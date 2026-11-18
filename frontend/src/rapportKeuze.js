// Which turns with data go into the report (#908), and which figures from the conversation (#993). The server lists
// them (report_checklist); the user switches off what does not belong. Everything starts on and nothing is switched on
// or off on a guess. The choice holds what the user switched off (`beurtenUit`, `figurenUit`), so a list that arrives
// late is on by default. The report shows exactly the figures that are on, at most MAX_FIGUREN; the server checks the
// same limit and recreates each figure from its own record.

export const MAX_FIGUREN = 4

export const GEEN_KEUZE = Object.freeze({ beurtenUit: new Set(), figurenUit: new Set() })

// The figures of a turn as the server sent them; anything without an id or a title is left out.
export const figurenVan = item =>
  (Array.isArray(item?.figuren) ? item.figuren : []).filter(f => typeof f?.id === 'string' && typeof f.titel === 'string')

// A checklist is only worth showing with a choice to make: two turns with data, or at least one figure.
export const metKeuze = checklist =>
  checklist?.status === 'klaar' && (checklist.items.length >= 2 || checklist.items.some(i => figurenVan(i).length > 0))

export const aanBeurten = (items, keuze) => items.map(i => i.beurt).filter(b => !keuze.beurtenUit.has(b))

// The ids of the figures that are on, in the order of the checklist: a figure of a turn that is off is off.
export const aanFiguren = (items, keuze) =>
  items.filter(i => !keuze.beurtenUit.has(i.beurt)).flatMap(figurenVan).map(f => f.id).filter(id => !keuze.figurenUit.has(id))

// A turn off switches its figures off; a turn on switches them on again.
export function wisselBeurt(keuze, item, aan) {
  const beurtenUit = new Set(keuze.beurtenUit)
  const figurenUit = new Set(keuze.figurenUit)
  if (aan) beurtenUit.delete(item.beurt)
  else beurtenUit.add(item.beurt)
  for (const { id } of figurenVan(item)) {
    if (aan) figurenUit.delete(id)
    else figurenUit.add(id)
  }
  return { beurtenUit, figurenUit }
}

// A figure on switches its turn on (the figure rests on that data); its other figures stay as they were.
export function wisselFiguur(keuze, item, id, aan) {
  const beurtenUit = new Set(keuze.beurtenUit)
  const figurenUit = new Set(keuze.figurenUit)
  if (aan) {
    figurenUit.delete(id)
    beurtenUit.delete(item.beurt)
  } else {
    figurenUit.add(id)
  }
  return { beurtenUit, figurenUit }
}

const KORT = 60
const kort = tekst => (tekst.length <= KORT ? tekst : `${tekst.slice(0, KORT - 1).trimEnd()}…`)

// "Bouwt voort op “…”": a turn that rests on the data of an earlier one. The source of that data stays in the report
// when the earlier turn is switched off (the data of the later turn comes from it), so the user knows before choosing.
export function voortbouwNotitie(item, items) {
  const vragen = (item.bouwt_voort_op ?? []).map(n => items.find(i => i.beurt === n)?.vraag).filter(Boolean)
  return vragen.length ? `Bouwt voort op “${vragen.map(kort).join('”, “')}”. Die bron blijft vermeld.` : null
}
