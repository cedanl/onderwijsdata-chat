// De plankaart vóór een vraag over meer bronnen (#1268), alleen met "Geavanceerd". De server stuurt haar als event
// `plan`, uit code: per bron titel, dataset, versie en de selectie in woorden, de koppelsleutel en een grove duur.
// Wat er van de kaart werd, staat in het gesprek zelf (zoals bij een verduidelijkingskaart, clarificationState.js), zodat
// een heropend gesprek hetzelfde toont.

const tekst = v => (typeof v === 'string' ? v : '')
const lijst = v => (Array.isArray(v) ? v.filter(r => typeof r === 'string' && r.trim()) : [])

// Het plan uit een `plan`-event, alleen met de velden die de kaart toont; null als er geen plan in staat.
export function planUit(ev) {
  if (!ev || typeof ev.id !== 'string' || !ev.id || !Array.isArray(ev.bronnen)) return null
  const bronnen = ev.bronnen
    .filter(b => b && typeof b === 'object' && tekst(b.titel))
    .map(b => ({ titel: b.titel, dataset: tekst(b.dataset), versie: tekst(b.versie), selectie: lijst(b.selectie) }))
  if (bronnen.length < 2) return null
  return { id: ev.id, vraag: tekst(ev.vraag), bronnen, sleutel: tekst(ev.sleutel) || null, duur: tekst(ev.duur) }
}

// Wat er van de kaart op index `index` werd:
// - 'bevestigd': "Klopt, ga door" ging weg;
// - 'aangepast': "Pas aan" zette de vraag terug in het invoerveld;
// - 'voorbij': er kwam een nieuwe vraag zonder dat de kaart gekozen werd;
// - 'open': de server wacht op dit plan (`openPlanId`);
// - 'verlopen': de server kent het plan niet meer (herladen, een nieuwe verbinding): alleen "Pas aan" kan nog.
export function planStatus(messages, index, openPlanId) {
  const kaart = messages[index]
  if (kaart?.planKeuze === 'bevestigd' || kaart?.planKeuze === 'aangepast') return kaart.planKeuze
  if (messages.slice(index + 1).some(m => m.role === 'user' && !m.isError)) return 'voorbij'
  return kaart?.plan?.id && kaart.plan.id === openPlanId ? 'open' : 'verlopen'
}

// De tekst die "Pas aan" in het invoerveld zet: de vraag en de keuzes van het plan, om bij te werken en te versturen.
export function aanpasTekst(plan) {
  if (!plan) return ''
  const bronnen = plan.bronnen.map(b => {
    const selectie = b.selectie.length ? ` (${b.selectie.join('; ')})` : ''
    return `- ${b.titel}${b.dataset && b.dataset !== b.titel ? `, ${b.dataset}` : ''}${selectie}`
  })
  const koppel = plan.sleutel ? `Koppelen op: ${plan.sleutel}.` : 'Naast elkaar, zonder koppeling.'
  return [plan.vraag, '', 'Plan:', ...bronnen, koppel].join('\n').trim()
}
