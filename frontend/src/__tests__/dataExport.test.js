// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import DataExport from '../components/DataExport'
import { exportKeys, roundSettled } from '../dataExport'
import { finishStep } from '../toolSteps'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const stap = (exportKey, extra = {}) => ({ name: 'query_data', label: 'Data gefilterd', done: true, exportKey, ...extra })

describe('exportKeys (#269)', () => {
  it('neemt de tabel over uit het tool_end-event', () => {
    const klaar = finishStep({ name: 'query_data', done: false }, { export_key: 'duo:x:0:ab' })
    expect(klaar.exportKey).toBe('duo:x:0:ab')
    expect(finishStep({ name: 'search_catalog', done: false }, {}).exportKey).toBeNull()
  })

  it('geeft elke tabel één keer, in volgorde', () => {
    expect(exportKeys([stap('a'), stap(null), stap('b'), stap('a')])).toEqual(['a', 'b'])
  })

  it('slaat een mislukte of lege stap over', () => {
    expect(exportKeys([stap('a', { status: 'empty' }), stap('b', { status: 'error' })])).toEqual([])
    expect(exportKeys(undefined)).toEqual([])
  })
})

describe('roundSettled (#399)', () => {
  // A round with text and tools, then the final round with text only: the server sends
  // message_end only for the last, so the first keeps done=false.
  const turn = [
    { role: 'user', content: 'Hoeveel?' },
    { role: 'assistant', content: 'Ik zoek het op.', tools: [stap('a')], done: false },
    { role: 'assistant', content: 'Het zijn er 36.201.', tools: [], done: true },
  ]

  it('telt een tussenbericht als klaar zodra er een volgende ronde is', () => {
    expect(roundSettled(turn, 1, true)).toBe(true)
  })

  it('telt het bericht dat nog streamt niet als klaar', () => {
    const lopend = [...turn.slice(0, 2)]
    expect(roundSettled(lopend, 1, true)).toBe(false)
  })

  it('telt een ingeladen gesprek als klaar, ook met done=false', () => {
    expect(roundSettled(turn.slice(0, 2), 1, false)).toBe(true)
  })
})

describe('DataExport', () => {
  let root
  let container

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  function render(props) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    act(() => root.render(createElement(DataExport, { settled: true, download: vi.fn(), ...props })))
    return [...container.querySelectorAll('button')]
  }

  it('toont geen knop bij een antwoord zonder tabeldata', () => {
    expect(render({ tools: [{ name: 'search_catalog', done: true, exportKey: null }] })).toEqual([])
  })

  it('toont geen knop zolang het antwoord nog loopt', () => {
    expect(render({ tools: [stap('a')], settled: false })).toEqual([])
  })

  it('downloadt de tabel achter het antwoord', async () => {
    const download = vi.fn().mockResolvedValue(undefined)
    const [knop] = render({ tools: [stap('duo:x:0:ab')], download })
    expect(knop.textContent).toBe('Download data als CSV')
    await act(async () => knop.click())
    expect(download).toHaveBeenCalledWith('duo:x:0:ab')
  })

  it('nummert de tabellen als het antwoord er meer gebruikte', () => {
    const knoppen = render({ tools: [stap('a'), stap('b')] })
    expect(knoppen.map(k => k.textContent)).toEqual(['Tabel 1 als CSV', 'Tabel 2 als CSV'])
  })

  it('zegt het als de data niet meer beschikbaar is', async () => {
    const download = vi.fn().mockRejectedValue(new Error('Deze data is niet meer beschikbaar.'))
    const [knop] = render({ tools: [stap('a')], download })
    await act(async () => knop.click())
    expect(container.querySelector('[role="alert"]').textContent).toContain('Deze data is niet meer beschikbaar.')
  })

  // CH-44 (#466): na een mislukte download bleven alleen de knoppen staan; de foutmelding krijgt een vervolgactie.
  it('biedt na een mislukte download aan de vraag opnieuw te stellen', async () => {
    const download = vi.fn().mockRejectedValue(new Error('Deze data is niet meer beschikbaar.'))
    const onHerhaal = vi.fn()
    const [knop] = render({ tools: [stap('a')], download, onHerhaal })
    await act(async () => knop.click())
    const opnieuw = [...container.querySelectorAll('[role="alert"] button')]
    expect(opnieuw.map(k => k.textContent)).toEqual(['Vraag opnieuw stellen'])
    await act(async () => opnieuw[0].click())
    expect(onHerhaal).toHaveBeenCalledOnce()
  })

  it('toont geen vervolgactie zonder vraag om te herhalen', async () => {
    const download = vi.fn().mockRejectedValue(new Error('x'))
    const [knop] = render({ tools: [stap('a')], download })
    await act(async () => knop.click())
    expect(container.querySelectorAll('[role="alert"] button')).toHaveLength(0)
  })
})

describe('downloadDataCsv', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('haalt de CSV op met het token en bewaart hem onder de naam van de server', async () => {
    const { downloadDataCsv } = await import('../api')
    const fetch = vi.fn().mockResolvedValue(new Response('a;b\n1;2', {
      headers: { 'Content-Disposition': 'attachment; filename="p01hoinges.csv"' },
    }))
    vi.stubGlobal('fetch', fetch)
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    let saved
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { saved = this.download })

    await downloadDataCsv('duo:p01hoinges:0:ab')

    expect(fetch.mock.calls[0][0]).toBe('/api/data/csv?key=duo%3Ap01hoinges%3A0%3Aab')
    expect(saved).toBe('p01hoinges.csv')
    click.mockRestore()
  })

  it('geeft de melding van de server door', async () => {
    const { downloadDataCsv } = await import('../api')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Deze data is niet meer beschikbaar.' }), { status: 404 })))
    await expect(downloadDataCsv('x')).rejects.toThrow('Deze data is niet meer beschikbaar.')
  })
})
