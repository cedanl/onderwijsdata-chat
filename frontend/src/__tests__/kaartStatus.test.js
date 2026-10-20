// #632: of een kaart echt getekend is, gemeten aan de maplibre-kaart achter de Plotly-grafiek. Hier met nagemaakte
// grafiek-divs: getekend, nul gebieden, een fout, een kaart die nooit 'idle' wordt, en geen kaart.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { kaartVan, getekendeGebieden, volgKaart, KAART_WACHTTIJD } from '../kaartStatus'

const vlak = id => ({ id, layer: { type: 'fill' } })
const lijn = id => ({ id, layer: { type: 'line' } })

// Een nagemaakte maplibre-kaart: luisteraars per gebeurtenis en een vaste lijst getekende vormen.
function nepKaart({ vormen = [], geladen = false } = {}) {
  const luisteraars = {}
  return {
    vormen,
    loaded: () => geladen,
    queryRenderedFeatures() { return this.vormen },
    on(naam, f) { (luisteraars[naam] ??= new Set()).add(f) },
    off(naam, f) { luisteraars[naam]?.delete(f) },
    emit(naam) { for (const f of [...(luisteraars[naam] ?? [])]) f() },
    aantal: naam => luisteraars[naam]?.size ?? 0,
  }
}
const grafiek = map => ({ _fullLayout: { _subplots: { map: ['map'] }, map: { _subplot: { map } } } })

afterEach(() => vi.useRealTimers())

describe('kaartVan', () => {
  it('vindt de maplibre-kaart achter de grafiek', () => {
    const map = nepKaart()
    expect(kaartVan(grafiek(map))).toBe(map)
  })

  it('geeft null zonder kaart, zonder layout of met een kapotte layout', () => {
    expect(kaartVan(null)).toBeNull()
    expect(kaartVan({})).toBeNull()
    expect(kaartVan({ _fullLayout: { map: {} } })).toBeNull()
    const kapot = { get _fullLayout() { throw new Error('weg') } }
    expect(kaartVan(kapot)).toBeNull()
  })
})

describe('getekendeGebieden', () => {
  it('telt elk vlak één keer, ook als het over twee tegels ligt, en geen lijnen', () => {
    expect(getekendeGebieden(nepKaart({ vormen: [vlak('PV20'), vlak('PV20'), vlak('PV21'), lijn('PV22')] }))).toBe(2)
  })

  it('herkent een gebied aan zijn eigenschappen, want Plotly geeft elk gebied id 0', () => {
    const plotly = ct => ({ id: 0, properties: { ct, fc: 'rgb(8, 48, 107)' }, layer: { type: 'fill' } })
    expect(getekendeGebieden(nepKaart({ vormen: [plotly([5, 52]), plotly([5, 52]), plotly([6, 53])] }))).toBe(2)
  })

  it('geeft null als de kaart niet kan tellen', () => {
    expect(getekendeGebieden({ queryRenderedFeatures() { throw new Error('geen stijl') } })).toBeNull()
  })
})

describe('volgKaart', () => {
  it('meldt getekend als er na idle gebieden staan, en ruimt dan op', () => {
    const map = nepKaart()
    const meld = vi.fn()
    volgKaart(grafiek(map), meld)
    map.vormen = [vlak('PV20')]
    map.emit('idle')
    expect(meld.mock.calls).toEqual([['getekend']])
    expect(map.aantal('idle')).toBe(0)
    expect(map.aantal('error')).toBe(0)
  })

  it('meldt mislukt als er na idle geen gebied staat, en daarna alsnog getekend', () => {
    const map = nepKaart()
    const meld = vi.fn()
    volgKaart(grafiek(map), meld)
    map.emit('idle')
    expect(meld.mock.calls).toEqual([['mislukt']])
    map.vormen = [vlak('PV20')]
    map.emit('idle')
    expect(meld.mock.calls).toEqual([['mislukt'], ['getekend']])
  })

  it('meldt mislukt bij een fout van de kaart zonder getekend gebied, en stopt', () => {
    const map = nepKaart()
    const meld = vi.fn()
    volgKaart(grafiek(map), meld)
    map.emit('error')
    map.vormen = [vlak('PV20')]
    map.emit('idle')
    expect(meld.mock.calls).toEqual([['mislukt']])
  })

  it('houdt een fout na een getekende kaart voor getekend', () => {
    const map = nepKaart({ vormen: [vlak('PV20')] })
    const meld = vi.fn()
    volgKaart(grafiek(map), meld)
    map.emit('error')
    expect(meld.mock.calls).toEqual([['getekend']])
  })

  it('telt na de wachttijd als de kaart nooit idle wordt', () => {
    vi.useFakeTimers()
    const map = nepKaart()
    const meld = vi.fn()
    volgKaart(grafiek(map), meld)
    vi.advanceTimersByTime(KAART_WACHTTIJD - 1)
    expect(meld).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(meld.mock.calls).toEqual([['mislukt']])
  })

  it('meldt meteen getekend als de kaart al klaar is', () => {
    const meld = vi.fn()
    volgKaart(grafiek(nepKaart({ vormen: [vlak('PV20')], geladen: true })), meld)
    expect(meld.mock.calls).toEqual([['getekend']])
  })

  it('wacht als de kaart al klaar is maar nog niets toont', () => {
    const meld = vi.fn()
    volgKaart(grafiek(nepKaart({ geladen: true })), meld)
    expect(meld).not.toHaveBeenCalled()
  })

  it('meldt niets zonder kaart (jsdom, een gewone grafiek)', () => {
    vi.useFakeTimers()
    const meld = vi.fn()
    const stop = volgKaart({ _fullLayout: {} }, meld)
    vi.advanceTimersByTime(KAART_WACHTTIJD * 2)
    expect(meld).not.toHaveBeenCalled()
    expect(stop).toBeTypeOf('function')
  })

  it('meldt niets meer na opruimen', () => {
    vi.useFakeTimers()
    const map = nepKaart()
    const meld = vi.fn()
    volgKaart(grafiek(map), meld)()
    map.emit('idle')
    map.emit('error')
    vi.advanceTimersByTime(KAART_WACHTTIJD)
    expect(meld).not.toHaveBeenCalled()
  })
})
