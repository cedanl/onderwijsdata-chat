// Een gesprek verwijderen met een korte bedenktijd (#493, UX F06). Na het bevestigen verdwijnt het
// gesprek meteen uit de lijst, maar de DELETE naar de server gaat pas na `wacht` ms; tot die tijd
// zet "Ongedaan maken" het terug. Eén gesprek tegelijk: een tweede verwijdering voert de eerste
// direct uit. De wachttijd is kort en de lijst zonder het gesprek staat al in localStorage, zodat
// verwijderen echt verwijderen blijft (privacy); het open gesprek wordt pas gewist als de tijd om is.
export const UITSTEL_MS = 8000

export function uitgesteldeVerwijdering({ voerUit, wacht = UITSTEL_MS, timers = globalThis } = {}) {
  let lopend = null // { conv, index, timer }

  function afronden() {
    if (!lopend) return null
    const { conv, timer } = lopend
    timers.clearTimeout(timer)
    lopend = null
    voerUit(conv)
    return conv
  }

  return {
    // Plan de verwijdering van `conv` dat op `index` in de lijst stond; een eerdere wordt eerst uitgevoerd.
    plan(conv, index) {
      afronden()
      const timer = timers.setTimeout(afronden, wacht)
      lopend = { conv, index, timer }
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
