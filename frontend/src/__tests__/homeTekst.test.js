// @vitest-environment jsdom
// #103: de homepage heeft een tekst voor IR-specialisten en een voor bestuursfuncties; de gekozen functie bepaalt welke.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import HomePage from '../pages/HomePage'
import { HOME_TEKST, doelgroepVan } from '../homeTekst'
import { bronnenLijst, zetBronnenLijst } from '../bronnenLijst'

vi.mock('../api', () => ({ fetchCatalogCounts: () => new Promise(() => {}) }))

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

afterEach(() => {
  zetBronnenLijst({})
  if (!root) return
  act(() => root.unmount())
  container.remove()
  root = undefined
})

async function render(functie) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(MemoryRouter, null, createElement(HomePage, { functie }))) })
}

describe('doelgroepVan (#103)', () => {
  it.each(['Bestuurder', 'Directeur'])('geeft %s de bestuurstekst', functie => {
    expect(doelgroepVan(functie)).toBe('bestuur')
  })

  it.each(['IR-specialist', 'Beleidsmedewerker', 'Onderzoeker', 'Docent', 'Anders', '', undefined])(
    'geeft %j de IR-tekst', functie => {
      expect(doelgroepVan(functie)).toBe('ir')
    })
})

describe('homepage per functie (#103)', () => {
  it('toont de IR-tekst voor een IR-specialist', async () => {
    await render('IR-specialist')
    expect(container.querySelector('h1').textContent).toBe(HOME_TEKST.ir.kop(bronnenLijst({})).join(''))
    expect(container.textContent).toContain(HOME_TEKST.ir.voordelenTitel)
    expect(container.textContent).not.toContain(HOME_TEKST.bestuur.voordelenTitel)
  })

  it('toont de bestuurstekst voor een bestuurder', async () => {
    await render('Bestuurder')
    expect(container.querySelector('h1').textContent).toBe(HOME_TEKST.bestuur.kop(bronnenLijst({})).join(''))
    expect(container.textContent).toContain(HOME_TEKST.bestuur.voordelenTitel)
    expect(container.textContent).not.toContain(HOME_TEKST.ir.voordelenTitel)
  })

  it('toont zonder functie de IR-tekst', async () => {
    await render('')
    expect(container.querySelector('h1').textContent).toBe(HOME_TEKST.ir.kop(bronnenLijst({})).join(''))
  })

  it.each(['IR-specialist', 'Bestuurder'])('tekent bij %s vier voordelen met een icoon', async functie => {
    await render(functie)
    const iconen = [...container.querySelectorAll('.benefit-icon svg')]
    expect(iconen).toHaveLength(4)
    for (const svg of iconen) expect(svg.childNodes.length).toBeGreaterThan(0)
  })
})

// #1006: beide intro's noemen de bronnen uit bronnenLijst.js, niet alleen CBS, DUO en RIO.
describe('bronnen in de intro (#1006)', () => {
  const intro = () => container.querySelector('.hero-content p').textContent

  it.each(['ir', 'bestuur'])('%s noemt de vaste bronnen, zonder Studiekeuzedatabase en UNL', doelgroep => {
    const tekst = HOME_TEKST[doelgroep].intro(bronnenLijst({}))
    expect(tekst).toContain('CBS, DUO, RIO, UWV, ROA, de Onderwijsinspectie en wetten.nl (collegegeld)')
    expect(tekst).not.toMatch(/Studiekeuzedatabase|UNL|WOPI/)
  })

  it.each(['ir', 'bestuur'])('%s noemt de Studiekeuzedatabase en UNL waar ze aan staan', doelgroep => {
    expect(HOME_TEKST[doelgroep].intro(bronnenLijst({ studiekeuze: true }))).toContain('de Studiekeuzedatabase (LCSK)')
    expect(HOME_TEKST[doelgroep].intro(bronnenLijst({ wo_personeel: true }))).toContain('UNL (WOPI)')
  })

  it.each([['IR-specialist', 'ir'], ['Bestuurder', 'bestuur']])('de homepage voor %s volgt de lijst uit /api/config', async (functie, doelgroep) => {
    await render(functie)
    expect(intro()).toBe(HOME_TEKST[doelgroep].intro(bronnenLijst({})))
    expect(intro()).not.toContain('Studiekeuzedatabase')
    await act(async () => { zetBronnenLijst({ studiekeuze: true }) })
    expect(intro()).toContain('Studiekeuzedatabase')
  })
})

// #1010: met de Studiekeuzedatabase (gelicentieerd) aan zei de homepage nog "open onderwijsdata" en "100% Open
// onderwijsdata", tegen de intro en de privacytekst in. Kop, voordelen, cta, cijfers en voetlink volgen de lijst.
describe('"open" volgt de lijst (#1010)', () => {
  const stats = () => [...container.querySelectorAll('.hero-stats > div')].map(d => ({
    waarde: d.querySelector('.hero-stat-value').textContent,
    label: d.querySelector('.hero-stat-label').textContent,
  }))
  const voetlink = () => container.querySelector('footer .sources-link').textContent

  it.each([['IR-specialist', 'ir'], ['Bestuurder', 'bestuur']])('%s: zonder licentiebron staat alles er als op main', async (functie, doelgroep) => {
    await render(functie)
    expect(container.querySelector('h1').textContent).toBe(
      doelgroep === 'ir' ? 'Van open onderwijsdata naar reproduceerbare inzichten' : 'Van open onderwijsdata naar onderbouwde besluiten')
    expect(container.querySelector('.cta-section p').textContent).toBe(doelgroep === 'ir'
      ? 'Stel je eerste vraag aan openEDUdata+ en ontdek wat gekoppelde open onderwijsdata voor jouw analyses betekent.'
      : 'Stel je eerste vraag aan openEDUdata+ en zie wat open onderwijsdata voor jouw besluiten betekent.')
    if (doelgroep === 'bestuur') expect(container.textContent).toContain('naast landelijke open data, als houvast')
    expect(stats()).toEqual([
      { waarde: '6', label: 'Open bronnen gekoppeld' },
      { waarde: '–', label: 'Datasets doorzoekbaar' },
      { waarde: '100%', label: 'Open onderwijsdata' },
    ])
    expect(voetlink()).toBe('Gebaseerd op open onderwijsdata')
  })

  it.each(['IR-specialist', 'Bestuurder'])('%s: met de Studiekeuzedatabase aan zegt de pagina nergens "open"', async functie => {
    await render(functie)
    await act(async () => { zetBronnenLijst({ studiekeuze: true }) })
    expect(container.textContent).not.toMatch(/\bopen\b/i)
    expect(container.querySelector('h1').textContent).toMatch(/^Van onderwijsdata naar /)
    expect(container.querySelector('.cta-section p').textContent).toContain(' onderwijsdata voor jouw ')
    expect(stats()).toEqual([
      { waarde: '7', label: 'Bronnen gekoppeld' },
      { waarde: '–', label: 'Datasets doorzoekbaar' },
      { waarde: '100%', label: 'Met bronvermelding' },
    ])
    expect(voetlink()).toBe('Gebaseerd op onderwijsdata')
  })

  it('zegt de bestuurder "landelijke data" met de Studiekeuzedatabase aan', async () => {
    await render('Bestuurder')
    await act(async () => { zetBronnenLijst({ studiekeuze: true }) })
    expect(container.textContent).toContain('naast landelijke data, als houvast')
  })

  it.each([
    [{}, '6'], [{ studiekeuze: true }, '7'], [{ wo_personeel: true }, '7'], [{ studiekeuze: true, wo_personeel: true }, '8'],
  ])('telt bij %j %s gekoppelde bronnen, al vóór de catalogustellingen er zijn', async (bronnen, aantal) => {
    await render('IR-specialist')
    await act(async () => { zetBronnenLijst(bronnen) })
    expect(stats()[0].waarde).toBe(aantal)
  })

  it('UNL alleen haalt "open" niet weg: dat is geen gelicentieerde bron', async () => {
    await render('IR-specialist')
    await act(async () => { zetBronnenLijst({ wo_personeel: true }) })
    expect(stats()[0].label).toBe('Open bronnen gekoppeld')
    expect(voetlink()).toBe('Gebaseerd op open onderwijsdata')
  })
})
