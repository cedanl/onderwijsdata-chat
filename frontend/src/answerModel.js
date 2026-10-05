// Welk model een antwoord gaf (UX-audit P3-4). Het model staat op de vraag (#242);
// het label hoort bij het laatste afgeronde assistentbericht van die beurt.
export function answerModels(messages, models = []) {
  const names = Object.fromEntries(models.map(m => [m.id, m.name]))
  const labels = {}
  let model = null
  messages.forEach((m, i) => {
    if (m.role === 'user') { model = m.model || null; return }
    const lastOfTurn = messages[i + 1]?.role !== 'assistant'
    if (model && lastOfTurn && m.done && !m.isError) labels[m.id] = names[model] || model
  })
  return labels
}
