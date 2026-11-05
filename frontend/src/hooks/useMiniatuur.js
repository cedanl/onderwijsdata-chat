import { useState, useEffect } from 'react'

// Een miniatuur in een galerijkaart (rapporten #633, dashboards #933): de bovenkant van een pagina van 960 px breed,
// verkleind tot de breedte van de kaart en 155 px hoog.
export const MINIATUUR_BREEDTE = 960
export const MINIATUUR_HOOGTE = 155

// Near the viewport: a card this close to the screen loads its thumbnail before it scrolls in.
const IN_BEELD_MARGE = '300px'

// True while the element is on or near the screen. Without IntersectionObserver (old browser, tests)
// everything counts as in view, as before #633.
export function useInBeeld(ref, aan = true) {
  const [inBeeld, setInBeeld] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    const el = ref.current
    if (!aan || !el || typeof IntersectionObserver === 'undefined') return
    const obs = new IntersectionObserver(([entry]) => setInBeeld(entry.isIntersecting), { rootMargin: IN_BEELD_MARGE })
    obs.observe(el)
    return () => obs.disconnect()
  }, [ref, aan])
  return inBeeld
}

// De schaal van de pagina in de kaart: de breedte van het element gedeeld door MINIATUUR_BREEDTE, ook na een resize.
export function useMiniatuurSchaal(ref, aan = true) {
  const [schaal, setSchaal] = useState(0.25)
  useEffect(() => {
    const el = ref.current
    if (!aan || !el || typeof ResizeObserver === 'undefined') return
    const obs = new ResizeObserver(([entry]) => setSchaal(entry.contentRect.width / MINIATUUR_BREEDTE))
    obs.observe(el)
    return () => obs.disconnect()
  }, [ref, aan])
  return schaal
}
