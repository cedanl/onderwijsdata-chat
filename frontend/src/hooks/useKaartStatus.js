import { useCallback, useEffect, useRef, useState } from 'react'
import { volgKaart } from '../kaartStatus'

// De tekenstatus van een kaart in de chat (#632): 'bezig', 'getekend' of 'mislukt'. Geeft de callbacks voor
// react-plotly mee. Een fout van Plotly (de kaart weigert, bijvoorbeeld omdat de worker niet laadt) is 'mislukt';
// een kaart die getekend is, wordt dat niet meer door een latere fout. Voor een gewone grafiek doet dit niets.
export function useKaartStatus(isMap) {
  const [status, setStatus] = useState('bezig')
  const stopRef = useRef(null)
  useEffect(() => () => stopRef.current?.(), [])

  const zet = useCallback(nieuw => setStatus(oud => (oud === 'getekend' ? oud : nieuw)), [])
  const onInitialized = useCallback((_figuur, gd) => {
    if (!isMap) return
    stopRef.current?.()
    stopRef.current = volgKaart(gd, zet)
  }, [isMap, zet])
  const onError = useCallback(() => {
    if (isMap) zet('mislukt')
  }, [isMap, zet])

  return { status, onInitialized, onError }
}
