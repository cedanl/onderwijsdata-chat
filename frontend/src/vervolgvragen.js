// De vervolgvragen van een antwoord (#364): alleen tekst, hoogstens drie. Ook bij het tonen: een bericht uit
// localStorage of de gespreksopslag houdt elk veld, kan er iets anders in hebben, en React kan een object niet tonen.
export const MAX_VERVOLGVRAGEN = 3

export function vervolgvragenTekst(vragen) {
  if (!Array.isArray(vragen)) return []
  return vragen.filter(q => typeof q === 'string' && q.trim()).slice(0, MAX_VERVOLGVRAGEN)
}
