import { useEffect, useState } from 'react'

// The breakpoint below which the chat sidebar is a drawer; keep in step with styles.css.
export const NARROW_SCREEN = '(max-width: 1024px)'

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
