// Does the report frame show anything (#541)? The report renders in a frame sandboxed with only allow-scripts:
// its origin is opaque, so the page cannot read its document. Never add allow-same-origin to read it: with
// allow-scripts that would let the report lift its own sandbox. postMessage is the one channel out of the
// frame, so a small probe appended to the shown HTML (not to the download) posts one boolean once the frame
// has loaded. The report is untrusted and could post the same message itself: the page only reads that
// boolean to show or hide a notice, so a spoofed message can do no more than that.

export const FRAME_BRON = 'edu-rapport-frame'

// No sign of life within this time means the frame did not load; Plotly is a few MB on a slow link.
export const FRAME_TIMEOUT_MS = 15000

// Elements that show something without text: charts (Plotly draws svg), images, embedded content, tables.
const ZICHTBARE_ELEMENTEN = 'svg, canvas, img, video, iframe, object, embed, table'

// innerText leaves out what is not rendered (scripts, styles, hidden elements), textContent would not.
const PROBE = `<script>window.addEventListener('load', function () {
  var b = document.body
  var zichtbaar = b.innerText.trim() !== '' || b.querySelector('${ZICHTBARE_ELEMENTEN}') !== null
  parent.postMessage({ bron: '${FRAME_BRON}', zichtbaar: zichtbaar }, '*')
})</script>`

// The report HTML with the probe at the end; after </html> the parser still puts the script in the body.
export const metFrameSignaal = html => `${html ?? ''}${PROBE}`

// The boolean from a message of the report frame, or null for any other message.
export function frameSignaal(event, frameWindow) {
  if (!frameWindow || event.source !== frameWindow) return null
  const data = event.data
  if (data?.bron !== FRAME_BRON || typeof data.zichtbaar !== 'boolean') return null
  return data.zichtbaar
}
