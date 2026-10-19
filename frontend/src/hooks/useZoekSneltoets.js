import { useEffect } from 'react'

// Ctrl+K, or ⌘K on a Mac, opens the search palette on every route (#602). No other shortcut in the app
// uses K; the browser's own Ctrl+K (search bar) gives way to the page.
export function isZoekSneltoets(e) {
  return Boolean(e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key?.toLowerCase() === 'k'
}

// The hint next to the search button: the shortcut as this platform writes it.
export function sneltoetsHint(platform = globalThis.navigator?.platform || '') {
  return /Mac|iPhone|iPad/.test(platform) ? '⌘K' : 'Ctrl K'
}

// `open` null: no shortcut (before login there is nothing to search).
export function useZoekSneltoets(open) {
  useEffect(() => {
    if (!open) return undefined
    function onKeyDown(e) {
      if (!isZoekSneltoets(e)) return
      e.preventDefault()
      open()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open])
}
