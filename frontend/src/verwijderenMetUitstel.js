// Een gesprek verwijderen met een korte bedenktijd (#493, UX F06). Na het bevestigen verdwijnt het
// gesprek meteen uit de lijst, maar de DELETE naar de server gaat pas na `wacht` ms; tot die tijd
// zet "Ongedaan maken" het terug. Eén gesprek tegelijk: een tweede verwijdering voert de eerste
// direct uit. De wachttijd is kort en de lijst zonder het gesprek staat al in localStorage, zodat
// verwijderen echt verwijderen blijft (privacy); het open gesprek wordt pas gewist als de tijd om is.
// Zolang de melding met "Ongedaan maken" muis of toetsenbord heeft, staat de tijd stil (#776, WCAG 2.2.1).
export const UITSTEL_MS = 8000

export function uitgesteldeVerwijdering({ voerUit, wacht = UITSTEL_MS, timers = globalThis, klok = () => Date.now() } = {}) {
  let lopend = null // { conv, index, timer, eind, rest }: rest is de resterende tijd zolang er gepauzeerd is

  function afronden() {
    if (!lopend) return null
    const { conv, timer } = lopend
    timers.clearTimeout(timer)
    lopend = null
    voerUit(conv)
    return conv
  }

  return {
    // Plan de verwijdering van `conv` dat op `index` stond (een getal, of de plaatsen in meer lijsten);
    // ongedaan() geeft `index` ongewijzigd terug. Een eerdere verwijdering wordt eerst uitgevoerd.
    plan(conv, index) {
      afronden()
      const timer = timers.setTimeout(afronden, wacht)
      lopend = { conv, index, timer, eind: klok() + wacht, rest: null }
    },
    // De tijd stilzetten en later de rest laten lopen; dubbel pauzeren of hervatten telt als één keer.
    pauzeer() {
      if (!lopend || lopend.rest !== null) return
      timers.clearTimeout(lopend.timer)
      lopend.rest = Math.max(0, lopend.eind - klok())
    },
    hervat() {
      if (!lopend || lopend.rest === null) return
      lopend.eind = klok() + lopend.rest
      lopend.timer = timers.setTimeout(afronden, lopend.rest)
      lopend.rest = null
    },
    // Het geplande gesprek met zijn plaats in de lijst, of null als er niets te herstellen is.
    ongedaan() {
      if (!lopend) return null
      const { conv, index, timer } = lopend
      timers.clearTimeout(timer)
      lopend = null
      return { conv, index }
    },
    // Voer een geplande verwijdering nu uit (tab sluiten, navigeren): het gesprek, of null.
    nu: afronden,
    get lopend() { return lopend ? lopend.conv : null },
  }
}

// De lijst met `conv` terug op zijn plaats.
export function terugInLijst(list, conv, index) {
  const zonder = list.filter(c => String(c.id) !== String(conv.id))
  const plek = Math.min(Math.max(index, 0), zonder.length)
  return [...zonder.slice(0, plek), conv, ...zonder.slice(plek)]
}
