// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../api', () => ({ fetchCatalogCounts: vi.fn(), fetchVersion: vi.fn() }))

import { fetchCatalogCounts, fetchVersion } from '../api'
import DataSourcesModal from '../components/DataSourcesModal'
import { bronnenLijst, zetBronnenLijst } from '../bronnenLijst'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let host

const VERSIE = {
  arbeidsmarkt: [
    { bron: 'UWV', dataset: 'uwv-open-match-data', periode: '…' },
    { bron: 'ROA', dataset: 'ais2030', periode: '…', editie: '2026', sis: 'SIS 2025' },
  ],
}

async function render(counts, versie = VERSIE) {
  fetchCatalogCounts.mockResolvedValue(counts)
  fetchVersion.mockResolvedValue(versie)
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
  zetBronnenLijst({})
})

const opnieuw = async (counts, versie) => {
  act(() => root.unmount())
  host.remove()
  await render(counts, versie)
}

const ALLES = { studiekeuze: true, wo_personeel: true }
const VAST = ['CBS', 'DUO', 'RIO', 'UWV', 'ROA', 'de Onderwijsinspectie', 'wetten.nl (collegegeld)']

describe('DataSourcesModal', () => {
  it('links the CBS and RIO catalogues to the pages of the chat repo, not to the archived package repos (#943)', async () => {
    await render({ CBS: 130, DUO: 15, RIO: 8 })
    const hrefs = Object.fromEntries(rows().map(r => [r.bron, r.link.getAttribute('href')]))
    expect(hrefs).toMatchObject({
      CBS: 'https://cedanl.github.io/onderwijsdata-chat/catalogus/cbs/',
      RIO: 'https://cedanl.github.io/onderwijsdata-chat/catalogus/rio/',
      DUO: 'https://onderwijsdata.duo.nl',
    })
    expect(host.innerHTML).not.toMatch(/cbs-onderwijsdata|rio-onderwijsdata/)
  })

  it('shows the counts of the catalogue the app searches, RIO in bestanden (#1150)', async () => {
    await render({ CBS: 130, DUO: 15, RIO: 8 })
    const inhoud = Object.fromEntries(rows().map(r => [r.bron, r.inhoud]))
    expect(inhoud.CBS).toMatch(/^130 datasets/)
    expect(inhoud.DUO).toMatch(/^15 open datasets/)
    expect(inhoud.RIO).toContain('(8 bestanden)')
    expect(host.textContent).not.toMatch(/resources/i)
  })

  it('opens every link in a new tab without leaking the opener', async () => {
    zetBronnenLijst(ALLES)
    await render({})
    expect(rows()).toHaveLength(bronnenLijst(ALLES).length)
    for (const { link } of rows()) {
      expect(link.getAttribute('target')).toBe('_blank')
      expect(link.getAttribute('rel')).toContain('noreferrer')
    }
  })

  // #1150: a link says what it does, not a path or a bare domain.
  it('gives every link a text that says what it does', async () => {
    zetBronnenLijst(ALLES)
    await render({ CBS: 130, DUO: 15, RIO: 8 })
    const teksten = Object.fromEntries(rows().map(r => [r.bron, r.link.textContent]))
    expect(teksten.CBS).toBe('Bekijk de CBS-catalogus')
    expect(teksten.RIO).toBe('Bekijk de RIO-catalogus')
    expect(teksten.DUO).toBe('Bekijk de DUO-catalogus')
    for (const tekst of Object.values(teksten)) {
      expect(tekst).toMatch(/^Bekijk /)
      expect(tekst).not.toMatch(/\//)
      expect(tekst).not.toMatch(/^[\w.-]+\.(nl|org|io)$/)
    }
  })

  // #1149: the rows follow bronnenLijst(), the list of the welcome text, with and without the sources behind a key or
  // flag; the counts no longer decide which rows show.
  it.each([
    ['no flags', {}],
    ['the Studiekeuzedatabase key', { studiekeuze: true }],
    ['the WOPI flag', { wo_personeel: true }],
    ['both', ALLES],
  ])('names the same sources as bronnenLijst() with %s', async (_naam, bronnen) => {
    zetBronnenLijst(bronnen)
    await render({ CBS: 130, DUO: 16, RIO: 8, UWV: 1, ROA: 1, UNL: 1, LCSK: 1 })
    expect(rows().map(r => r.bron)).toEqual(bronnenLijst(bronnen).map(b => b.naam))
  })

  // #1091: the ROA row names the edition and SIS year the app loads (from /api/version), not a fixed SIS 2024.
  it('names the ROA edition and SIS year of the loaded file', async () => {
    await render({})
    const roa = rows().find(r => r.bron === 'ROA')
    expect(roa.inhoud).toBe('Schoolverlaters (SIS 2025) en arbeidsmarktprognoses tot 2030, editie 2026')
    expect(host.textContent).not.toContain('SIS 2024')
    await opnieuw({}, { arbeidsmarkt: [{ bron: 'ROA', dataset: 'ais2030', editie: '2027', sis: 'SIS 2026' }] })
    expect(rows().find(r => r.bron === 'ROA').inhoud).toContain('(SIS 2026) en arbeidsmarktprognoses tot 2030, editie 2027')
  })

  it('names no year in the ROA row when the version is not there', async () => {
    fetchVersion.mockRejectedValue(new Error('weg'))
    fetchCatalogCounts.mockResolvedValue({})
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
    await act(async () => { root.render(createElement(DataSourcesModal, { onClose: () => {} })) })
    expect(rows().find(r => r.bron === 'ROA').inhoud).toBe('Schoolverlaters en arbeidsmarktprognoses tot 2030')
  })

  it('always lists the Inspectie and wetten.nl, also when the counts fail', async () => {
    fetchCatalogCounts.mockRejectedValue(new Error('weg'))
    fetchVersion.mockResolvedValue(VERSIE)
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
    await act(async () => { root.render(createElement(DataSourcesModal, { onClose: () => {} })) })
    expect(rows().map(r => r.bron)).toEqual(VAST)
    const wetten = rows().find(r => r.bron === 'wetten.nl (collegegeld)')
    expect(wetten.inhoud).toContain('vaste tabel')
    expect(wetten.link.getAttribute('href')).toMatch(/^https:\/\/wetten\.overheid\.nl\//)
    expect(rows().find(r => r.bron === 'de Onderwijsinspectie').link.getAttribute('href')).toMatch(/onderwijsinspectie\.nl/)
  })

  // #957: the Studiekeuzedatabase of LCSK only where its key is set (test, playground), with the documentation page of
  // LCSK that the licence asks for.
  it('lists LCSK only where the Studiekeuzedatabase key is set', async () => {
    zetBronnenLijst({ studiekeuze: true })
    await render({ CBS: 130, DUO: 16, RIO: 8, UWV: 1, ROA: 1, LCSK: 1 })
    const lcsk = rows().find(r => r.bron === 'de Studiekeuzedatabase (LCSK)')
    expect(lcsk.inhoud).toContain('Studiekeuzedatabase')
    expect(lcsk.link.getAttribute('href')).toBe('https://lcsk.nl/over-ons/studiekeuzedata-raadplegen/')
    zetBronnenLijst({})
    await opnieuw({ CBS: 130, DUO: 16, RIO: 8, UWV: 1, ROA: 1, LCSK: 1 })
    expect(rows().map(r => r.bron)).not.toContain('de Studiekeuzedatabase (LCSK)')
  })
})
