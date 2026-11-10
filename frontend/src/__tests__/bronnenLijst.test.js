// @vitest-environment jsdom
// #1006: de welkomst-, home- en privacytekst noemden alleen "CBS, DUO en RIO". Eén lijst in bronnenLijst.js noemt de
// bronnen die de app echt bevraagt: de vaste, plus wat /api/config `bronnen` hier aan meldt (tools/beschikbaarheid.py).
import { describe, it, expect, afterEach } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { bronnenLijst, bronnamen, opsomming, zetBronnenLijst, useBronnenLijst } from '../bronnenLijst'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const VAST = ['CBS', 'DUO', 'RIO', 'UWV', 'ROA', 'de Onderwijsinspectie', 'wetten.nl (collegegeld)']
const namen = bronnen => bronnenLijst(bronnen).map(b => b.naam)

describe('opsomming', () => {
  it.each([
    [[], ''],
    [['CBS'], 'CBS'],
    [['CBS', 'DUO'], 'CBS en DUO'],
    [['CBS', 'DUO', 'RIO'], 'CBS, DUO en RIO'],
  ])('%j wordt %j', (lijst, zin) => {
    expect(opsomming(lijst)).toBe(zin)
  })
})

describe('bronnenLijst (#1006)', () => {
  it.each([[undefined], [null], [{}], ['geen object']])('noemt bij %j alleen de vaste bronnen', bronnen => {
    expect(namen(bronnen)).toEqual(VAST)
  })

  it('voegt de Studiekeuzedatabase van LCSK toe met studiekeuze aan', () => {
    expect(namen({ studiekeuze: true })).toEqual([...VAST.slice(0, 6), 'de Studiekeuzedatabase (LCSK)', VAST[6]])
  })

  it('voegt UNL (WOPI) toe met wo_personeel aan', () => {
    expect(namen({ wo_personeel: true })).toEqual([...VAST.slice(0, 6), 'UNL (WOPI)', VAST[6]])
  })

  it('voegt voor de financiën niets toe: dat is data van DUO', () => {
    expect(namen({ financien: true })).toEqual(VAST)
  })

  it('telt alleen true als aan', () => {
    expect(namen({ studiekeuze: 'true', wo_personeel: 1 })).toEqual(VAST)
    expect(namen({ studiekeuze: false, wo_personeel: false })).toEqual(VAST)
  })

  it('zet alles in een zin', () => {
    expect(bronnamen(bronnenLijst({ studiekeuze: true, wo_personeel: true }))).toBe(
      'CBS, DUO, RIO, UWV, ROA, de Onderwijsinspectie, de Studiekeuzedatabase (LCSK), UNL (WOPI) en wetten.nl (collegegeld)')
  })

  it('markeert alleen wetten.nl als bron zonder opvraag, en alleen de Studiekeuzedatabase als gelicentieerd', () => {
    const lijst = bronnenLijst({ studiekeuze: true, wo_personeel: true })
    expect(lijst.filter(b => b.opvraag === false).map(b => b.naam)).toEqual(['wetten.nl (collegegeld)'])
    expect(lijst.filter(b => b.gelicentieerd).map(b => b.naam)).toEqual(['de Studiekeuzedatabase (LCSK)'])
  })
})

describe('de lijst staat één keer in de bron', () => {
  it('alleen bronnenLijst.js noemt de Studiekeuzedatabase (LCSK) en wetten.nl (collegegeld)', () => {
    const src = join(__dirname, '..')
    const files = readdirSync(src, { recursive: true })
      .filter(f => /\.jsx?$/.test(f) && !f.includes('__tests__'))
      .filter(f => /Studiekeuzedatabase \(LCSK\)|wetten\.nl \(collegegeld\)|CBS, DUO en RIO/.test(readFileSync(join(src, f), 'utf8')))
    expect(files).toEqual(['bronnenLijst.js'])
  })
})

describe('useBronnenLijst', () => {
  let root
  let container
  let gezien
  function Toon() {
    gezien = useBronnenLijst().map(b => b.naam)
    return null
  }

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    zetBronnenLijst({})
  })

  it('geeft de vaste bronnen tot /api/config antwoordt, en volgt dan de configuratie', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => { root.render(createElement(Toon)) })
    expect(gezien).toEqual(VAST)
    await act(async () => { zetBronnenLijst({ studiekeuze: true }) })
    expect(gezien).toContain('de Studiekeuzedatabase (LCSK)')
    await act(async () => { zetBronnenLijst(undefined) })
    expect(gezien).toEqual(VAST)
  })
})
