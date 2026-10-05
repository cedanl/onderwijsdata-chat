// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import DataExport from '../components/DataExport'
import { exportKeys } from '../dataExport'
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
    act(() => root.render(createElement(DataExport, { done: true, download: vi.fn(), ...props })))
    return [...container.querySelectorAll('button')]
  }

  it('toont geen knop bij een antwoord zonder tabeldata', () => {
    expect(render({ tools: [{ name: 'search_catalog', done: true, exportKey: null }] })).toEqual([])
  })

  it('toont geen knop zolang het antwoord nog loopt', () => {
    expect(render({ tools: [stap('a')], done: false })).toEqual([])
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
    expect(container.querySelector('[role="alert"]').textContent).toBe('Deze data is niet meer beschikbaar.')
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
