// Een grafiek komt van de server als een eigen bericht ná het antwoord (het figure-event in useChat); de
// gespreksopslag, de geschiedenis voor het model en de rapportlogica rekenen daarop. Op het scherm hoort hij
// bij het antwoord: in dezelfde bubbel, tussen de tekst en de vaste blokken eronder (#610). Als los bericht
// stond hij ónder het antwoord en schoof hij op een telefoon 360 px omlaag zodra de blokken (citaties,
// telling, export, bronnen), de vervolgvragen en de feedbackknoppen aan het eind van het antwoord landden:
// de grootste layout-shift in de eerste 15 s van een antwoord. In de bubbel landt dat alles ónder de grafiek.

export const isFiguurBericht = m =>
  !!m && m.role === 'assistant' && m.figures?.length > 0 &&
  !m.content && !m.tools?.length && !m.clarification && !m.vervangen?.length && !m.isError

// De berichten zoals ze getoond worden: elk grafiekbericht direct na een antwoord gaat op in dat antwoord.
// `index` is de plaats van het antwoord in de lijst (voor vervolgvragen, feedback en herhalen); `laatsteId`
// is het laatste bericht van de groep, waar answerModels het modeletiket van de beurt aan hangt.
export function groepeerFiguren(messages) {
  const rijen = []
  messages.forEach((m, i) => {
    const vorige = rijen.at(-1)
    const sluitAan = vorige && vorige.index + vorige.gevouwen === i - 1
    if (isFiguurBericht(m) && sluitAan && vorige.msg.role === 'assistant' && !isFiguurBericht(vorige.msg)) {
      vorige.figures = [...vorige.figures, ...m.figures]
      vorige.gevouwen += 1
      vorige.laatsteId = m.id
      return
    }
    rijen.push({ msg: m, index: i, figures: m.figures || [], gevouwen: 0, laatsteId: m.id })
  })
  return rijen
}
