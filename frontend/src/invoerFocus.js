// Op een telefoon verdwijnt de vaste tabbalk zolang het invoerveld focus heeft: met het toetsenbord open krijgt
// de chat die hoogte terug (#527). Die wissel verschuift het hele invoergebied. Een tik verplaatst de focus bij
// mousedown, en mouseup en click volgen daarna op dezelfde plek. Deed CSS de wissel meteen
// (`body:has(.chat-input:focus)`), dan landde de mouseup op de disclaimer en kwam 'Verstuur bericht' niet aan
// (#584); hetzelfde gold voor de stopknop, de modelkiezer en elke tik buiten het veld.
//
// Daarom zet dit een klasse op body, pas na de lopende tik: een timeout van 0 loopt na de mouseup en click van
// dezelfde tik, en zolang er een vinger of muisknop is ingedrukt, wacht het op de pointerup.

export const INVOER_ACTIEF = 'invoer-actief'

const isInvoer = el => Boolean(el?.classList?.contains('chat-input'))

// Volgt de focus vanaf nu; geeft de functie terug die ermee stopt.
export function volgInvoerFocus(doc = document) {
  const win = doc.defaultView
  let timer = null
  let ingedrukt = false

  const bijwerken = () => {
    timer = null
    if (!ingedrukt) doc.body.classList.toggle(INVOER_ACTIEF, isInvoer(doc.activeElement))
  }
  const later = () => {
    if (timer === null) timer = win.setTimeout(bijwerken, 0)
  }
  const neer = () => { ingedrukt = true }
  const los = () => {
    ingedrukt = false
    later()
  }

  const luisteraars = [['focusin', later], ['focusout', later], ['pointerdown', neer], ['pointerup', los], ['pointercancel', los]]
  for (const [type, fn] of luisteraars) doc.addEventListener(type, fn, true)
  later()

  return () => {
    for (const [type, fn] of luisteraars) doc.removeEventListener(type, fn, true)
    if (timer !== null) win.clearTimeout(timer)
    doc.body.classList.remove(INVOER_ACTIEF)
  }
}
