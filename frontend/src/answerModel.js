// Welk model een antwoord gaf (UX-audit P3-4). Het model staat op de vraag (#242);
// het label hoort bij het laatste afgeronde assistentbericht van die beurt. Een vast antwoord
// uit code (`vast`: scope-uitleg, weigering, sentinelantwoord) schreef geen model: geen label (#565).
// Het label staat onder de bubbel en schuift dus mee met alles wat erboven groeit. Het komt daarom pas als elk
// bericht van de beurt klaar is: een grafiek komt als los, al afgerond bericht binnen terwijl de tekst nog stroomt
// (#661).
export function answerModels(messages, models = []) {
  const names = Object.fromEntries(models.map(m => [m.id, m.name]))
  const labels = {}
  let model = null
  let beurtKlaar = true
  messages.forEach((m, i) => {
    if (m.role === 'user') { model = m.model || null; beurtKlaar = true; return }
    beurtKlaar = beurtKlaar && !!m.done
    const lastOfTurn = messages[i + 1]?.role !== 'assistant'
    if (model && lastOfTurn && beurtKlaar && !m.isError && !m.vast) labels[m.id] = names[model] || model
  })
  return labels
}
