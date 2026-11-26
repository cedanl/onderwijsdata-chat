// @vitest-environment jsdom
// #1268: de plankaart met toetsenbord en schermlezer. Een nieuwe kaart krijgt de focus en heeft een naam (haar kop);
// "Klopt, ga door" en "Pas aan" zijn gewone knoppen in een benoemde groep, in die volgorde. Een verlopen kaart (na
// herladen) heeft alleen "Pas aan". Axe vindt op de kaart niets.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import axe from 'axe-core'
import PlanKaart from '../components/PlanKaart'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const PLAN = {
  id: 'plan-1',
  vraag: 'Koppel de mbo-studenten en de ingeschrevenen in het ho per schooljaar',
  bronnen: [
    { titel: 'Mbo; studenten naar niveau, leerweg, herkomst', dataset: '85354NED', versie: 'versie van 09-04-2026', selectie: ['jaren: alle beschikbare jaren', 'vorm: alle'] },
    { titel: 'Ingeschrevenen hoger onderwijs', dataset: 'p01hoinges', versie: 'de nieuwste versie bij het laden', selectie: ['bestand: het standaardbestand'] },
  ],
  sleutel: 'schooljaar',
  duur: 'ongeveer een minuut',
}

let root
let container

async function render(props) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  // Zoals in de chat: de pagina heeft een h1 (ChatPage), de kaart staat eronder.
  const kaart = createElement(PlanKaart, { plan: PLAN, ...props })
  await act(async () => { root.render(createElement('main', null, createElement('h1', null, 'Chat'), kaart)) })
  return container.querySelector('.plan-kaart')
}

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
})

const knoppen = kaart => [...kaart.querySelectorAll('button')].map(b => b.textContent.trim())

describe('PlanKaart', () => {
  it('krijgt de focus als ze open binnenkomt, met haar kop als naam', async () => {
    const kaart = await render({ status: 'open', onBevestig: vi.fn(), onAanpassen: vi.fn() })

    expect(document.activeElement).toBe(kaart)
    expect(kaart.tagName).toBe('SECTION')
    expect(kaart.getAttribute('tabindex')).toBe('-1')
    const kop = document.getElementById(kaart.getAttribute('aria-labelledby'))
    expect(kop.textContent).toBe('Eerst het plan: klopt dit?')
  })

  it('toont per bron titel, dataset, versie en de selectie, en de sleutel en de duur', async () => {
    const kaart = await render({ status: 'open', onBevestig: vi.fn(), onAanpassen: vi.fn() })

    const tekst = kaart.textContent
    for (const bron of PLAN.bronnen) {
      expect(tekst).toContain(bron.titel)
      expect(tekst).toContain(bron.dataset)
      expect(tekst).toContain(bron.versie)
      for (const regel of bron.selectie) expect(tekst).toContain(regel)
    }
    expect(tekst).toContain('Koppelen op schooljaar.')
    expect(tekst).toContain('ongeveer een minuut')
  })

  it('heeft "Klopt, ga door" en "Pas aan" als knoppen in een benoemde groep, in die volgorde', async () => {
    const onBevestig = vi.fn()
    const onAanpassen = vi.fn()
    const kaart = await render({ status: 'open', onBevestig, onAanpassen })

    const groep = kaart.querySelector('[role="group"]')
    expect(groep.getAttribute('aria-label')).toBe('Wat wil je met dit plan?')
    expect(knoppen(groep)).toEqual(['Klopt, ga door', 'Pas aan'])
    for (const knop of groep.querySelectorAll('button')) {
      expect(knop.getAttribute('type')).toBe('button')
      expect(knop.tabIndex).toBe(0)
    }
    const [door, aanpassen] = groep.querySelectorAll('button')
    await act(async () => { door.click() })
    await act(async () => { aanpassen.click() })
    expect(onBevestig).toHaveBeenCalledTimes(1)
    expect(onAanpassen).toHaveBeenCalledTimes(1)
  })

  it('zet "Klopt, ga door" uit terwijl er iets loopt', async () => {
    const kaart = await render({ status: 'open', busy: true, onBevestig: vi.fn(), onAanpassen: vi.fn() })

    expect(kaart.querySelector('.plan-knop-door').disabled).toBe(true)
    expect(kaart.querySelector('.plan-knop-aanpassen').disabled).toBe(false)
  })

  it('een verlopen kaart (na herladen) houdt alleen "Pas aan" en pakt de focus niet', async () => {
    const kaart = await render({ status: 'verlopen', onBevestig: vi.fn(), onAanpassen: vi.fn() })

    expect(knoppen(kaart)).toEqual(['Pas aan'])
    expect(document.activeElement).not.toBe(kaart)
    expect(kaart.querySelector('[role="status"]').textContent).toContain('niet meer open')
  })

  it('een bevestigde kaart heeft geen knoppen meer en zegt wat er gekozen is', async () => {
    const kaart = await render({ status: 'bevestigd', onBevestig: vi.fn(), onAanpassen: vi.fn() })

    expect(knoppen(kaart)).toEqual([])
    expect(kaart.querySelector('[role="status"]').textContent).toContain('Klopt, ga door')
  })

  it('heeft geen axe-bevindingen, open en verlopen', async () => {
    for (const status of ['open', 'verlopen']) {
      const kaart = await render({ status, onBevestig: vi.fn(), onAanpassen: vi.fn() })
      const { violations } = await axe.run(container, { rules: { 'color-contrast': { enabled: false } } })
      expect(violations.map(v => v.id), status).toEqual([])
      await act(async () => root.unmount())
      container.remove()
      root = null
    }
  })
})
