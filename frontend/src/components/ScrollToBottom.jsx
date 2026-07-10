import { useState, useEffect } from 'react'

/**
 * Floating scroll-to-bottom button.
 * Uses IntersectionObserver on a sentinel element (typically messagesEndRef)
 * to detect whether the user has scrolled away from the bottom.
 */
export default function ScrollToBottom({ sentinelRef, scrollContainerRef }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const sentinel = sentinelRef.current
    const container = scrollContainerRef.current
    if (!sentinel || !container) return

    const observer = new IntersectionObserver(
      ([entry]) => setVisible(!entry.isIntersecting),
      { root: container, threshold: 0 }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [sentinelRef, scrollContainerRef])

  const handleClick = () => {
    sentinelRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  if (!visible) return null

  return (
    <button
      className="scroll-to-bottom-btn"
      onClick={handleClick}
      aria-label="Scroll naar beneden"
      title="Scroll naar beneden"
    >
      <svg
        viewBox="0 0 24 24"
        width="18"
        height="18"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>
  )
}
