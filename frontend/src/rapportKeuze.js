// Which turns with data go into the report (#908). The server lists them (report_checklist); the user switches off what
// does not belong. Everything starts on and nothing is switched on or off on a guess. `uit` is the set of turn numbers
// the user switched off, so a list that arrives late is on by default.

// A checklist is only worth showing with a choice to make: one turn with data cannot be left out.
export const metKeuze = checklist => checklist?.status === 'klaar' && checklist.items.length >= 2

export const aanBeurten = (items, uit) => items.map(i => i.beurt).filter(b => !uit.has(b))

const KORT = 60
const kort = tekst => (tekst.length <= KORT ? tekst : `${tekst.slice(0, KORT - 1).trimEnd()}…`)

// "Bouwt voort op “…”": a turn that rests on the data of an earlier one. The source of that data stays in the report
// when the earlier turn is switched off (the data of the later turn comes from it), so the user knows before choosing.
export function voortbouwNotitie(item, items) {
  const vragen = (item.bouwt_voort_op ?? []).map(n => items.find(i => i.beurt === n)?.vraag).filter(Boolean)
  return vragen.length ? `Bouwt voort op “${vragen.map(kort).join('”, “')}”. Die bron blijft vermeld.` : null
}
