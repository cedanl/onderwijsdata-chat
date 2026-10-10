import { useSyncExternalStore } from 'react'

const root = () => document.documentElement

function subscribe(onChange) {
  const observer = new MutationObserver(onChange)
  observer.observe(root(), { attributes: true, attributeFilter: ['class'] })
  return () => observer.disconnect()
}

// Whether the page is in dark mode (theme.js sets the class), following changes. Charts take their
// colours from it, so they redraw on a theme switch and not on every unrelated render.
export function useDarkMode() {
  return useSyncExternalStore(subscribe, () => root().classList.contains('dark'), () => false)
}
