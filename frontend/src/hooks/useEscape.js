import { useEffect, useRef } from 'react'

// Escape closes something that is open but is not a modal dialog, such as the
// conversation drawer on narrow screens (#400). Dialogs use useDialog instead.
export function useEscape(active, onEscape) {
  const onEscapeRef = useRef(onEscape)
  useEffect(() => { onEscapeRef.current = onEscape })

  useEffect(() => {
    if (!active) return
    function onKeyDown(e) {
      if (e.key === 'Escape') onEscapeRef.current?.()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [active])
}
