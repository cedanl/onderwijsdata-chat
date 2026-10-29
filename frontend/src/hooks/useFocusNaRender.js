import { useCallback, useEffect, useRef, useState } from 'react'
import { focusEerste } from '../focusNa'

// Focus op een element dat pas na de volgende render bestaat of als enige overblijft (#776): het
// teruggezette gesprek na Ongedaan maken, het volgende rapport na verwijderen. `focusNa(...kiezers)`
// onthoudt de kiezers; na de render krijgt het eerste element dat de focus aanneemt hem. Het effect
// draait na het opruimen van een sluitende dialoog, dus wint van diens terugzetten van de focus.
export function useFocusNaRender() {
  const doel = useRef(null)
  const [, tik] = useState(0)
  useEffect(() => {
    if (!doel.current) return
    const kiezers = doel.current
    doel.current = null
    focusEerste(...kiezers)
  })
  return useCallback((...kiezers) => {
    doel.current = kiezers
    tik(n => n + 1)
  }, [])
}
