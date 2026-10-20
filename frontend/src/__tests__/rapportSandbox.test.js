// @vitest-environment jsdom
// #634: opgeslagen rapport-HTML draaide in de viewer met dialogen en pop-ups, en ongesandboxt in de download.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { FRAME_BRON } from '../reportFrame'
import { GEEN_DIALOGEN_JS, metCsp, metLinkDoorgifte, openRapportLink, rapportCsp } from '../rapportSandbox'

describe('de policy om een rapport', () => {
  it('laat alleen inline scripts en de eigen server toe, en geen verbindingen, formulieren of frames', () => {
    const csp = rapportCsp('https://edudata.example')
    expect(csp).toContain("default-src 'none'")
    expect(csp).toContain("script-src 'unsafe-inline' https://edudata.example")
    for (const d of ["connect-src 'none'", "form-action 'none'", "frame-src 'none'", "base-uri 'none'"]) expect(csp).toContain(d)
    expect(csp).not.toContain('unsafe-eval')
    expect(rapportCsp()).toContain("script-src 'unsafe-inline';")
  })

  it('staat vóór alles wat het rapport meebrengt, met één doctype', () => {
    const html = '<!DOCTYPE html><html class="dark"><head><script>alert(1)</script></head><body>x</body></html>'
    const uit = metCsp(html, { scriptBron: 'https://edudata.example' })
    expect(uit.startsWith('<!DOCTYPE html><meta http-equiv="Content-Security-Policy"')).toBe(true)
    expect(uit.indexOf('Content-Security-Policy')).toBeLessThan(uit.indexOf('<script>alert'))
    expect(uit.match(/<!doctype/gi)).toHaveLength(1)
    expect(uit).toContain('<html class="dark">')
  })

  it('zet de HTML van de app direct na de policy, en laat een leeg rapport leeg', () => {
    const uit = metCsp('<p>x</p>', { vooraf: GEEN_DIALOGEN_JS })
    expect(uit.indexOf(GEEN_DIALOGEN_JS)).toBeGreaterThan(uit.indexOf('Content-Security-Policy'))
    expect(uit.indexOf(GEEN_DIALOGEN_JS)).toBeLessThan(uit.indexOf('<p>x</p>'))
    expect(metCsp(null)).toBeNull()
  })
})

describe('een link in het rapport', () => {
  const frameWindow = {}
  const bericht = (link, source = frameWindow) => ({ source, data: { bron: FRAME_BRON, link } })
  afterEach(() => { vi.unstubAllGlobals() })

  it('stuurt het frame als bericht naar de app', () => {
    expect(metLinkDoorgifte('<p/>')).toContain(`bron: '${FRAME_BRON}', link: a.href`)
  })

  it('opent de app in een nieuwe tab zonder weg terug', () => {
    const open = vi.fn()
    expect(openRapportLink(bericht('https://opendata.cbs.nl/x'), frameWindow, open)).toBe(true)
    expect(open).toHaveBeenCalledWith('https://opendata.cbs.nl/x', '_blank', 'noopener,noreferrer')
  })

  it.each([['javascript:alert(1)'], ['data:text/html,x'], ['geen url']])('opent %s niet', link => {
    const open = vi.fn()
    expect(openRapportLink(bericht(link), frameWindow, open)).toBe(true)
    expect(open).not.toHaveBeenCalled()
  })

  it('opent niets zonder klik van de gebruiker: een script dat zelf berichten stuurt', () => {
    vi.stubGlobal('navigator', { userActivation: { isActive: false } })
    const open = vi.fn()
    openRapportLink(bericht('https://example.org'), frameWindow, open)
    expect(open).not.toHaveBeenCalled()
  })

  it('negeert berichten van een ander venster of zonder link', () => {
    const open = vi.fn()
    expect(openRapportLink(bericht('https://example.org', {}), frameWindow, open)).toBe(false)
    expect(openRapportLink({ source: frameWindow, data: { bron: FRAME_BRON, zichtbaar: true } }, frameWindow, open)).toBe(false)
    expect(open).not.toHaveBeenCalled()
  })
})
