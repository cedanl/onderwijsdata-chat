import { useEffect, useRef } from 'react'

// Binnen deze afstand tot de onderkant staat de gebruiker nog 'onderaan'.
const NEAR_BOTTOM_PX = 80

const isNearBottom = (el) => el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_PX

/**
 * Houdt de berichtenlijst onderaan terwijl een antwoord binnenstroomt (#243).
 *
 * Elk tekstfragment levert een nieuwe `messages` op; een smooth-scroll per fragment
 * start tientallen animaties per seconde die elkaar afbreken, en dat springt. Daarom
 * direct scrollen, hooguit één keer per frame, en alleen als de gebruiker onderaan
 * stond. Een eigen vraag zet de lijst weer onderaan vast.
 */
export default function useAutoScroll(containerRef, messages) {
  const pinnedRef = useRef(true)
  const frameRef = useRef(0)
  const countRef = useRef(messages.length)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onScroll = () => { pinnedRef.current = isNearBottom(el) }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      el.removeEventListener('scroll', onScroll)
      cancelAnimationFrame(frameRef.current)
      frameRef.current = 0
    }
  }, [containerRef])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const added = messages.length > countRef.current
    countRef.current = messages.length
    if (added && messages.at(-1)?.role === 'user') pinnedRef.current = true
    if (!pinnedRef.current || frameRef.current) return
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = 0
      // De gebruiker kan net vóór dit frame omhoog zijn gescrold.
      if (pinnedRef.current) el.scrollTop = el.scrollHeight
    })
  }, [containerRef, messages])
}
