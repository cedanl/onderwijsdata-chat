// Een dichte uitklap komt niet op papier (#973): de NSE-thema's van Opleidingen en de definities van de kengetallen
// bij de financiën vielen weg uit de afdruk. Een uitklap met `data-afdruk-open` gaat open zolang de browser afdrukt
// (de knop "Afdrukken of als pdf bewaren", maar ook Ctrl+P) en daarna weer dicht; wat de gebruiker zelf opende,
// blijft open. Alleen deze uitklappen: de waarden onder een grafiek staan al in de grafiek op papier.
export const AFDRUK_OPEN = '.dashboard-content details[data-afdruk-open]'

export function openUitklappenBijAfdrukken(win = window) {
  let geopend = []
  const voor = () => {
    geopend = [...win.document.querySelectorAll(AFDRUK_OPEN)].filter(d => !d.open)
    for (const d of geopend) d.open = true
  }
  const na = () => {
    for (const d of geopend) d.open = false
    geopend = []
  }
  win.addEventListener('beforeprint', voor)
  win.addEventListener('afterprint', na)
  return () => {
    win.removeEventListener('beforeprint', voor)
    win.removeEventListener('afterprint', na)
  }
}
