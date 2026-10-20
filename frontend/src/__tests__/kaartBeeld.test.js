// #642: met één centrum en zoom 6 viel Nederland op 390 px links en rechts buiten de kaart, en op een breed scherm
// Limburg onderaan. Centrum en zoom volgen nu uit de gebieden en de ruimte van de kaart.
import { describe, it, expect } from 'vitest'
import { kaartPassend, kaartStijl } from '../kaartBeeld'

// Nederland ruwweg: west 3,36, oost 7,23, zuid 50,75, noord 53,55.
const NL = [{ type: 'choroplethmap', geojson: { features: [
  { geometry: { type: 'Polygon', coordinates: [[[3.36, 51.37], [7.23, 53.2], [5.0, 50.75], [6.0, 53.55], [3.36, 51.37]]] } },
] } }]

const mx = lon => (lon + 180) / 360
const my = lat => (1 - Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) / Math.PI) / 2
// Hoeveel px de gebieden bij deze zoom innemen.
const maat = zoom => ({ w: (mx(7.23) - mx(3.36)) * 512 * 2 ** zoom, h: (my(50.75) - my(53.55)) * 512 * 2 ** zoom })

describe('kaartPassend', () => {
  it.each([[390, 448], [1280, 448], [700, 300]])('laat Nederland binnen %i x %i px vallen, kleurenbalk eraf', (b, h) => {
    const { zoom, center } = kaartPassend(NL, b, h)
    expect(maat(zoom).w).toBeLessThanOrEqual(b - 90)
    expect(maat(zoom).h).toBeLessThanOrEqual(h)
    expect(center.lon).toBeCloseTo(5.295, 2)
    expect(center.lat).toBeGreaterThan(52.1)
    expect(center.lat).toBeLessThan(52.25)
  })

  it('zoomt verder in op een breed scherm dan op een telefoon, maar nooit zo ver dat iets wegvalt', () => {
    expect(kaartPassend(NL, 1280, 448).zoom).toBeGreaterThan(kaartPassend(NL, 390, 448).zoom)
    expect(kaartPassend(NL, 390, 448).zoom).toBeLessThan(6)
  })

  it('geeft niets zonder gebieden of zonder bekende maat', () => {
    expect(kaartPassend([{ type: 'choroplethmap' }], 390, 448)).toBeNull()
    expect(kaartPassend(NL, 0, 448)).toBeNull()
  })
})

describe('kaartStijl', () => {
  it('is alleen een achtergrondlaag in de kleur van het thema, zonder tegels van buiten', () => {
    const stijl = kaartStijl('#1E293B')
    expect(stijl.sources).toEqual({})
    expect(stijl.layers).toEqual([{ id: 'achtergrond', type: 'background', paint: { 'background-color': '#1E293B' } }])
  })
})
