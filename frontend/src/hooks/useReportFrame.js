import { useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { metEigenPlotly, PLOTLY_URL } from '../plotlyBron'
import { FRAME_TIMEOUT_MS, frameSignaal, metFrameSignaal } from '../reportFrame'
import { GEEN_DIALOGEN_JS, metCsp, metLinkDoorgifte, openRapportLink } from '../rapportSandbox'
import { metThema } from '../reportThema'

// Plotly komt van de eigen server (#486): de enige scriptbron naast inline in de policy van het frame (#634).
const scriptBron = () => new URL(PLOTLY_URL, window.location.href).origin

// Per shown report: did the frame load (onLoad, only for the spinner), what did its probe say, and did the
// timeout pass without a word from it.
const BEGIN = { geladen: false, signaal: null, verlopen: false }

// The state of the sandboxed report frame (#387, #541). `html` is the report HTML, or null when no frame is
// shown. `mode` is the app's theme choice ('light', 'dark' or 'system'), carried into the frame as a class on
// <html> (#568); a change reloads the frame. `probleem` is null, 'leeg' (the frame says it shows nothing) or
// 'niet-geladen' (no word from the frame within FRAME_TIMEOUT_MS); a later word from the frame still counts, so
// a slow report is not failed for good. `printDoc` is the same report for the print frame (WorkbookPrint.jsx):
// without the probe, the links or the theme (printing is light), and without alert/confirm/prompt (#634).
export function useReportFrame(html, mode) {
  const frameRef = useRef(null)
  const srcDoc = useMemo(() => (html
    ? metCsp(metLinkDoorgifte(metFrameSignaal(metEigenPlotly(metThema(html, mode)))), { scriptBron: scriptBron() })
    : null), [html, mode])
  const printDoc = useMemo(() => (html
    ? metCsp(metEigenPlotly(html), { scriptBron: scriptBron(), vooraf: GEEN_DIALOGEN_JS })
    : null), [html])
  const [frame, setFrame] = useState({ srcDoc, ...BEGIN })
  // Another report starts from BEGIN: the state belongs to the srcDoc it was set for.
  const huidig = frame.srcDoc === srcDoc ? frame : BEGIN
  const zet = useCallback(
    wijziging => setFrame(f => ({ ...(f.srcDoc === srcDoc ? f : { srcDoc, ...BEGIN }), ...wijziging })),
    [srcDoc],
  )

  // A layout effect, not a passive one: a small srcdoc can load and post before a passive effect would run.
  useLayoutEffect(() => {
    if (!srcDoc) return undefined
    const onMessage = event => {
      const frameWindow = frameRef.current?.contentWindow
      if (openRapportLink(event, frameWindow)) return
      const zichtbaar = frameSignaal(event, frameWindow)
      if (zichtbaar !== null) zet({ signaal: zichtbaar })
    }
    window.addEventListener('message', onMessage)
    const timer = setTimeout(() => zet({ verlopen: true }), FRAME_TIMEOUT_MS)
    return () => {
      window.removeEventListener('message', onMessage)
      clearTimeout(timer)
    }
  }, [srcDoc, zet])

  const onLoad = useCallback(() => zet({ geladen: true }), [zet])

  let probleem = null
  if (huidig.signaal === false) probleem = 'leeg'
  else if (huidig.signaal === null && huidig.verlopen) probleem = 'niet-geladen'
  // Busy until the frame loads or speaks, but never for good: a shown problem ends it.
  const loading = Boolean(srcDoc) && !probleem && !huidig.geladen && huidig.signaal === null

  return { frameRef, srcDoc, printDoc, onLoad, loading, probleem }
}
