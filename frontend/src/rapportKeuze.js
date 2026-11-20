// Which turns with data go into the report (#908), and which figures from the conversation (#993). The server lists
// them (report_checklist); the user switches off what does not belong. Everything starts on and nothing is switched on
// or off on a guess. The choice holds what the user switched off (`beurtenUit`, `figurenUit`), so a list that arrives
// late is on by default. The report shows exactly the figures that are on, at most MAX_FIGUREN; the server checks the
// same limit and recreates each figure from its own record.
//
// A figure can rest on the data of more than one turn (a script that read an earlier table): the server sends those
// turns with each figure (`beurten`, #1045) and pulls them into the report when the figure is chosen. So a figure is
// only on while all of its turns are on, switching it on switches them on, and switching one of them off switches the
// figure off: the report never rests on a turn that the checklist shows as off.

export const MAX_FIGUREN = 4

export const GEEN_KEUZE = Object.freeze({ beurtenUit: new Set(), figurenUit: new Set() })

// The figures of a turn as the server sent them; anything without an id or a title is left out.
export const figurenVan = item =>
  (Array.isArray(item?.figuren) ? item.figuren : []).filter(f => typeof f?.id === 'string' && typeof f.titel === 'string')

// A checklist is only worth showing with a choice to make: two turns with data, or at least one figure.
export const metKeuze = checklist =>
  checklist?.status === 'klaar' && (checklist.items.length >= 2 || checklist.items.some(i => figurenVan(i).length > 0))

export const aanBeurten = (items, keuze) => items.map(i => i.beurt).filter(b => !keuze.beurtenUit.has(b))

// The turns a figure rests on: its own turn and those the server sent along. An older payload without them falls back
// to the figure's own turn.
export function beurtenVanFiguur(item, figuur) {
  const beurten = Array.isArray(figuur?.beurten) ? figuur.beurten.filter(Number.isInteger) : []
  return beurten.includes(item.beurt) ? beurten : [item.beurt, ...beurten]
}

// Every figure of the checklist with its turn and the turns it rests on, in the order of the checklist.
const alleFiguren = items =>
  items.flatMap(item => figurenVan(item).map(figuur => ({ item, figuur, beurten: beurtenVanFiguur(item, figuur) })))

// The ids of the figures that are on, in the order of the checklist: a figure with one of its turns off is off.
export const aanFiguren = (items, keuze) =>
  alleFiguren(items)
    .filter(({ figuur, beurten }) => !keuze.figurenUit.has(figuur.id) && beurten.every(b => !keuze.beurtenUit.has(b)))
    .map(({ figuur }) => figuur.id)

// A turn off switches off every figure that rests on it, its own and those of other turns. A turn on switches its own
// figures on again, as far as their other turns are on; a figure of another turn stays as it is.
export function wisselBeurt(keuze, item, aan, items = [item]) {
  const beurtenUit = new Set(keuze.beurtenUit)
  const figurenUit = new Set(keuze.figurenUit)
  if (aan) {
    beurtenUit.delete(item.beurt)
    for (const figuur of figurenVan(item)) {
      if (beurtenVanFiguur(item, figuur).every(b => !beurtenUit.has(b))) figurenUit.delete(figuur.id)
    }
  } else {
    beurtenUit.add(item.beurt)
    for (const { figuur, beurten } of alleFiguren(items.includes(item) ? items : [...items, item])) {
      if (beurten.includes(item.beurt)) figurenUit.add(figuur.id)
    }
  }
  return { beurtenUit, figurenUit }
}

// A figure on switches all of its turns on (the figure rests on that data); other figures stay as they were.
export function wisselFiguur(keuze, item, id, aan) {
  const beurtenUit = new Set(keuze.beurtenUit)
  const figurenUit = new Set(keuze.figurenUit)
  if (aan) {
    figurenUit.delete(id)
    const figuur = figurenVan(item).find(f => f.id === id)
    for (const b of beurtenVanFiguur(item, figuur)) beurtenUit.delete(b)
  } else {
    figurenUit.add(id)
  }
  return { beurtenUit, figurenUit }
}

// The label of each figure (by id): its title, and a sequence number when another figure has the same title, so two
// figures called "Instroom" are told apart in the list and in the note below.
export function figuurLabels(items) {
  const figuren = items.flatMap(figurenVan)
  const aantal = new Map()
  for (const { titel } of figuren) aantal.set(titel, (aantal.get(titel) ?? 0) + 1)
  const gezien = new Map()
  const labels = new Map()
  for (const { id, titel } of figuren) {
    const n = (gezien.get(titel) ?? 0) + 1
    gezien.set(titel, n)
    labels.set(id, aantal.get(titel) > 1 ? `${titel} (${n})` : titel)
  }
  return labels
}

// "Nodig voor figuur “…”": a turn that a figure of another turn rests on, while that figure is on. Its own figures need
// no note: they sit right below it.
export function nodigVoor(item, items, figurenAan) {
  const labels = figuurLabels(items)
  const nodig = alleFiguren(items)
    .filter(f => f.item.beurt !== item.beurt && f.beurten.includes(item.beurt) && figurenAan.includes(f.figuur.id))
    .map(f => `figuur “${labels.get(f.figuur.id)}”`)
  return nodig.length ? `Nodig voor ${nodig.join(', ')}.` : null
}

const KORT = 60
const kort = tekst => (tekst.length <= KORT ? tekst : `${tekst.slice(0, KORT - 1).trimEnd()}…`)

// "Bouwt voort op “…”": a turn that rests on the data of an earlier one. The source of that data stays in the report
// when the earlier turn is switched off (the data of the later turn comes from it), so the user knows before choosing.
export function voortbouwNotitie(item, items) {
  const vragen = (item.bouwt_voort_op ?? []).map(n => items.find(i => i.beurt === n)?.vraag).filter(Boolean)
  return vragen.length ? `Bouwt voort op “${vragen.map(kort).join('”, “')}”. Die bron blijft vermeld.` : null
}
