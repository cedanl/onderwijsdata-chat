import { useEffect, useRef } from 'react'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Key handlers of the open dialogs, the topmost last. One document listener serves only the topmost,
// so with a dialog opened from another (privacy from settings, #572) Escape closes just the upper one
// and the Tab traps do not fight.
const openDialogs = []

function onDocumentKeyDown(e) {
  openDialogs.at(-1)?.(e)
}

// Modal behaviour for the element the returned ref is attached to: focus moves in on open,
// Tab stays inside, Escape closes, and focus returns to whatever opened it.
export function useDialog(onClose) {
  const ref = useRef(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => { onCloseRef.current = onClose })

  useEffect(() => {
    const dialog = ref.current
    const opener = document.activeElement
    const focusables = () => [...dialog.querySelectorAll(FOCUSABLE)]
    ;(focusables()[0] ?? dialog).focus()

    function onKeyDown(e) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onCloseRef.current?.()
        return
      }
      if (e.key !== 'Tab') return
      const items = focusables()
      if (!items.length) {
        e.preventDefault()
        return
      }
      const first = items[0]
      const last = items[items.length - 1]
      const outside = !dialog.contains(document.activeElement)
      if (e.shiftKey && (outside || document.activeElement === first)) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && (outside || document.activeElement === last)) {
        e.preventDefault()
        first.focus()
      }
    }

    if (!openDialogs.length) document.addEventListener('keydown', onDocumentKeyDown)
    openDialogs.push(onKeyDown)
    return () => {
      openDialogs.splice(openDialogs.indexOf(onKeyDown), 1)
      if (!openDialogs.length) document.removeEventListener('keydown', onDocumentKeyDown)
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus()
    }
  }, [])

  return ref
}
