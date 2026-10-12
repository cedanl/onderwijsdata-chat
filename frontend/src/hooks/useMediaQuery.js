import { useEffect, useState } from 'react'

// The breakpoint below which the chat sidebar is a drawer; keep in step with styles.css.
export const NARROW_SCREEN = '(max-width: 1024px)'

// Wie het systeem op minder beweging zet (WCAG 2.3.3, #517); houd gelijk met de reduced-motion-regel in styles.css.
export const REDUCED_MOTION = '(prefers-reduced-motion: reduce)'

function matches(query) {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(query).matches
}

// Whether a CSS media query matches now, following changes (rotate, resize).
export function useMediaQuery(query) {
  const [match, setMatch] = useState(() => matches(query))
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const mql = window.matchMedia(query)
    const onChange = () => setMatch(mql.matches)
    onChange()
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [query])
  return match
}

// Het scrollgedrag dat bij de voorkeur van de gebruiker past: geen glijdende scroll bij minder beweging.
// Een functie, geen hook: de voorkeur wordt gelezen op het moment van scrollen, zonder te hertekenen.
export function scrollGedrag() {
  return matches(REDUCED_MOTION) ? 'auto' : 'smooth'
}
