import { useEffect, useState } from 'react'

function onLineNow() {
  return typeof navigator === 'undefined' || navigator.onLine !== false
}

// Whether the browser thinks it has a network (#532): navigator.onLine at mount, then the
// window's online/offline events.
export function useOnline() {
  const [online, setOnline] = useState(onLineNow)
  useEffect(() => {
    const goOnline = () => setOnline(true)
    const goOffline = () => setOnline(false)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [])
  return online
}
