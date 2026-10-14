// #541: the report frame is sandboxed without allow-same-origin, so the page cannot read it; a probe in the
// frame posts one boolean (does the report show anything?) and the page only accepts it from that frame.
import { describe, it, expect } from 'vitest'
import { JSDOM } from 'jsdom'
import { FRAME_BRON, FRAME_TIMEOUT_MS, metFrameSignaal, frameSignaal } from '../reportFrame'

const telVoorkomens = (tekst, deel) => tekst.split(deel).length - 1

describe('metFrameSignaal', () => {
  it('appends the probe once and keeps the report as it was', () => {
    const html = '<html><head></head><body><h1>Instroom</h1></body></html>'
    const metProbe = metFrameSignaal(html)
    expect(metProbe.startsWith(html)).toBe(true)
    expect(telVoorkomens(metProbe, FRAME_BRON)).toBe(1)
    expect(telVoorkomens(metProbe, '<script>')).toBe(1)
  })

  it('waits 15 seconds for a slow report before it calls the frame not loaded', () => {
    expect(FRAME_TIMEOUT_MS).toBe(15000)
  })
})

// Runs the probe in a real parsed document, as the frame does. jsdom has no layout and so no innerText:
// the text without scripts and styles stands in for it.
function probeerIn(html) {
  const dom = new JSDOM(metFrameSignaal(html), {
    runScripts: 'dangerously',
    beforeParse(window) {
      Object.defineProperty(window.HTMLElement.prototype, 'innerText', {
        get() {
          const kopie = this.cloneNode(true)
          kopie.querySelectorAll('script, style').forEach(el => el.remove())
          return kopie.textContent
        },
      })
    },
  })
  // A top-level jsdom window is its own parent, so the probe posts to itself.
  return new Promise(resolve => dom.window.addEventListener('message', e => { resolve(e.data); dom.window.close() }))
}

describe('the probe in the frame', () => {
  it.each([
    ['an empty body', '<html><head></head><body></body></html>', false],
    ['only whitespace', '<html><body>  \n </body></html>', false],
    ['only a script', '<html><body><script>var x = "tekst"</script></body></html>', false],
    ['text', '<html><body><h1>Instroom hbo</h1></body></html>', true],
    ['a chart (svg)', '<html><body><div><svg width="10" height="10"></svg></div></body></html>', true],
    ['a table without text', '<html><body><table><tr><td></td></tr></table></body></html>', true],
  ])('posts zichtbaar for %s', async (_, html, zichtbaar) => {
    expect(await probeerIn(html)).toEqual({ bron: FRAME_BRON, zichtbaar })
  })
})

describe('frameSignaal', () => {
  const frame = {}
  const bericht = (data, source = frame) => ({ data, source })

  it('reads the boolean from the report frame', () => {
    expect(frameSignaal(bericht({ bron: FRAME_BRON, zichtbaar: true }), frame)).toBe(true)
    expect(frameSignaal(bericht({ bron: FRAME_BRON, zichtbaar: false }), frame)).toBe(false)
  })

  it.each([
    ['another source', bericht({ bron: FRAME_BRON, zichtbaar: false }, {})],
    ['no source', bericht({ bron: FRAME_BRON, zichtbaar: false }, null)],
    ['another bron', bericht({ bron: 'iets-anders', zichtbaar: false })],
    ['a string zichtbaar', bericht({ bron: FRAME_BRON, zichtbaar: 'false' })],
    ['no zichtbaar', bericht({ bron: FRAME_BRON })],
    ['a string as data', bericht(FRAME_BRON)],
    ['no data', bericht(null)],
  ])('ignores a message with %s', (_, event) => {
    expect(frameSignaal(event, frame)).toBeNull()
  })

  it('ignores every message while there is no frame', () => {
    expect(frameSignaal(bericht({ bron: FRAME_BRON, zichtbaar: false }, undefined), undefined)).toBeNull()
  })
})
