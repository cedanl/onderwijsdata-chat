import { useCallback, useState } from 'react'

const roundDown = (width, step) => Math.floor(width / step) * step

// The width of an element, rounded down to `step` pixels and following resizes (a phone turned to
// landscape). Rounded, so a re-render or a pixel's difference gives the same number and nothing that
// depends on it is redone. 0 while unknown: before mounting, or where nothing is laid out (jsdom).
// Returns a callback ref for the element and the width.
export function useElementWidth(step) {
  const [width, setWidth] = useState(0)
  const ref = useCallback(el => {
    if (!el) return
    const measure = w => setWidth(roundDown(w, step))
    measure(el.clientWidth)
    if (typeof ResizeObserver !== 'function') return
    const observer = new ResizeObserver(([entry]) => measure(entry.contentRect.width))
    observer.observe(el)
    return () => observer.disconnect()
  }, [step])
  return [ref, width]
}
