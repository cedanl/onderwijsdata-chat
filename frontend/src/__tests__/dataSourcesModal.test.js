// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../api', () => ({ fetchCatalogCounts: vi.fn() }))

import { fetchCatalogCounts } from '../api'
import DataSourcesModal from '../components/DataSourcesModal'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let host

async function render(counts) {
  fetchCatalogCounts.mockResolvedValue(counts)
  host = document.createElement('div')
  document.body.appendChild(host)
  root = createRoot(host)
  await act(async () => { root.render(createElement(DataSourcesModal, { onClose: () => {} })) })
}

const rows = () => [...host.querySelectorAll('tbody tr')].map(tr => ({
  bron: tr.querySelector('.source-name').textContent,
  inhoud: tr.querySelector('.source-desc').textContent,
  link: tr.querySelector('a'),
}))

afterEach(() => {
  act(() => root.unmount())
  host.remove()
})

describe('DataSourcesModal', () => {
  it('links the CBS and RIO catalogues to the pages of the chat repo, not to the archived package repos (#943)', async () => {
    await render({ CBS: 130, DUO: 15, RIO: 8 })
    const hrefs = Object.fromEntries(rows().map(r => [r.bron, r.link.getAttribute('href')]))
    expect(hrefs).toEqual({
      CBS: 'https://cedanl.github.io/onderwijsdata-chat/catalogus/cbs/',
      RIO: 'https://cedanl.github.io/onderwijsdata-chat/catalogus/rio/',
      DUO: 'https://onderwijsdata.duo.nl',
    })
    expect(host.innerHTML).not.toMatch(/cbs-onderwijsdata|rio-onderwijsdata/)
  })

  it('shows the counts of the catalogue the app searches', async () => {
    await render({ CBS: 130, DUO: 15, RIO: 8 })
    const inhoud = Object.fromEntries(rows().map(r => [r.bron, r.inhoud]))
    expect(inhoud.CBS).toMatch(/^130 datasets/)
    expect(inhoud.DUO).toMatch(/^15 open datasets/)
    expect(inhoud.RIO).toContain('(8 resources)')
  })

  it('opens every catalogue link in a new tab without leaking the opener', async () => {
    await render({})
    for (const { link } of rows()) {
      expect(link.getAttribute('target')).toBe('_blank')
      expect(link.getAttribute('rel')).toContain('noreferrer')
    }
  })

  // #956: a source with a tool of its own gets a row only where /api/catalog/counts names it.
  it('lists UNL only where WOPI answers here', async () => {
    await render({ CBS: 130, DUO: 16, RIO: 8, UWV: 1, ROA: 1, UNL: 1 })
    expect(rows().map(r => r.bron)).toEqual(['CBS', 'RIO', 'DUO', 'UWV', 'ROA', 'UNL'])
    act(() => root.unmount())
    host.remove()
    await render({ CBS: 130, DUO: 15, RIO: 8, UWV: 1, ROA: 1 })
    expect(rows().map(r => r.bron)).not.toContain('UNL')
  })

  // #957: the Studiekeuzedatabase of LCSK only where its key is set (test, playground), with the documentation page of
  // LCSK that the licence asks for.
  it('lists LCSK only where the Studiekeuzedatabase answers here', async () => {
    await render({ CBS: 130, DUO: 16, RIO: 8, UWV: 1, ROA: 1, LCSK: 1 })
    const lcsk = rows().find(r => r.bron === 'LCSK')
    expect(lcsk.inhoud).toContain('Studiekeuzedatabase')
    expect(lcsk.link.getAttribute('href')).toBe('https://lcsk.nl/over-ons/studiekeuzedata-raadplegen/')
    expect(rows().map(r => r.bron)).toEqual(['CBS', 'RIO', 'DUO', 'UWV', 'ROA', 'LCSK'])
    act(() => root.unmount())
    host.remove()
    await render({ CBS: 130, DUO: 16, RIO: 8, UWV: 1, ROA: 1, UNL: 1 })
    expect(rows().map(r => r.bron)).not.toContain('LCSK')
  })
})
