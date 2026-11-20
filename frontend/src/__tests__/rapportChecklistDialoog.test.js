// @vitest-environment jsdom
// #908: de dialoog bij "Genereer rapport" toont boven het veld met de onderzoeksvraag een checklist van de beurten met
// data. Alles staat aan; de gebruiker zet uit wat niet in het rapport hoort. Het veld blijft van de gebruiker.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import axe from 'axe-core'
import OnderzoeksvraagDialoog from '../components/OnderzoeksvraagDialoog'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const ITEMS = [
  { beurt: 1, vraag: 'Hoeveel studenten heeft de UU?', bronnen: ['DUO — Ingeschrevenen (p01hoinges)'], bouwt_voort_op: [] },
  { beurt: 2, vraag: 'Even wat anders: het wo-rendement', bronnen: ['CBS — Rendement (83285NED)'], bouwt_voort_op: [] },
  { beurt: 3, vraag: 'Alleen de vrouwen', bronnen: ['DUO — Ingeschrevenen (p01hoinges)'], bouwt_voort_op: [1] },
]
const KLAAR = { status: 'klaar', items: ITEMS }
const VOORSTEL = 'Hoeveel studenten heeft de UU?'

let root
let container
let onGenereer
let onClose

function zetSchermbreedte(isKlein) {
  window.matchMedia = q => ({ matches: isKlein && q.includes('600px'), media: q, addEventListener() {}, removeEventListener() {} })
}

async function toon(checklist) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(OnderzoeksvraagDialoog, { voorstel: VOORSTEL, max: 4000, checklist, onGenereer, onClose }))
  })
}

beforeEach(() => {
  onGenereer = vi.fn()
  onClose = vi.fn()
  zetSchermbreedte(false)
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  container?.remove()
  root = null
  delete window.matchMedia
})

const set = () => container.querySelector('fieldset')
const vakjes = () => [...container.querySelectorAll('input[type="checkbox"]')]
const genereer = () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Genereer')
const veld = () => container.querySelector('textarea')
const klik = el => act(async () => { el.click() })

describe('de checklist in de dialoog (#908)', () => {
  it('is een fieldset met een zichtbare legend, boven het veld', async () => {
    await toon(KLAAR)

    expect(set().querySelector('legend').textContent).toBe('Welke vragen met data horen in het rapport?')
    expect(set().compareDocumentPosition(veld()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('heeft per beurt een vakje met de vraag als naam en de bron als beschrijving', async () => {
    await toon(KLAAR)

    expect(vakjes()).toHaveLength(3)
    const [eerste, , derde] = vakjes()
    expect(eerste.labels[0].textContent).toContain('Hoeveel studenten heeft de UU?')
    const beschrijving = document.getElementById(eerste.getAttribute('aria-describedby')).textContent
    expect(beschrijving).toBe('DUO — Ingeschrevenen (p01hoinges)')
    // Een beurt die voortbouwt zegt dat, en dat die bron blijft staan.
    expect(document.getElementById(derde.getAttribute('aria-describedby')).textContent)
      .toContain('Bouwt voort op “Hoeveel studenten heeft de UU?”. Die bron blijft vermeld.')
  })

  it('zet alles standaard aan en kiest niets op een gok', async () => {
    await toon(KLAAR)

    expect(vakjes().map(v => v.checked)).toEqual([true, true, true])
    expect(container.querySelector('summary').textContent).toBe('Vragen in het rapport: 3 van 3')
  })

  it('de vakjes zijn gewone focusbare invoer: het toetsenbord doet de rest (Tab, Spatie)', async () => {
    await toon(KLAAR)

    for (const v of vakjes()) {
      expect(v.tabIndex).toBe(0)
      expect(v.disabled).toBe(false)
    }
    expect(veld().tabIndex).toBe(0)
  })

  it('de focus blijft in het veld, met de cursor achteraan', async () => {
    await toon(KLAAR)

    expect(document.activeElement).toBe(veld())
    expect(veld().selectionStart).toBe(VOORSTEL.length)
  })

  it('Genereer stuurt de beurten mee die aanstaan, naast de tekst van het veld', async () => {
    await toon(KLAAR)
    await klik(vakjes()[1])

    expect(vakjes().map(v => v.checked)).toEqual([true, false, true])
    expect(container.querySelector('summary').textContent).toBe('Vragen in het rapport: 2 van 3')
    await klik(genereer())

    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [1, 3], [])
  })

  it('alles aan stuurt alle beurten mee (de server leest dat als het hele gesprek)', async () => {
    await toon(KLAAR)

    await klik(genereer())

    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [1, 2, 3], [])
  })

  it('een beurt weer aanzetten kan', async () => {
    await toon(KLAAR)
    await klik(vakjes()[1])
    await klik(vakjes()[1])

    expect(vakjes().map(v => v.checked)).toEqual([true, true, true])
  })

  it('alles uit kan niet worden verstuurd, en de melding zegt waarom', async () => {
    await toon(KLAAR)
    for (const v of vakjes()) await klik(v)

    const melding = container.querySelector('[role="alert"]')
    expect(melding.textContent).toContain('Kies minstens één vraag met data voor het rapport')
    expect(genereer().getAttribute('aria-disabled')).toBe('true')
    expect(genereer().getAttribute('aria-describedby')).toBe(melding.id)
    expect(set().getAttribute('aria-describedby')).toBe(melding.id)

    await klik(genereer())
    expect(onGenereer).not.toHaveBeenCalled()

    // Eén vakje weer aan: de melding is weg en het rapport kan.
    await klik(vakjes()[0])
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(genereer().hasAttribute('aria-disabled')).toBe(false)
    await klik(genereer())
    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [1], [])
  })

  it('Enter in het veld genereert met de gekozen beurten', async () => {
    await toon(KLAAR)
    await klik(vakjes()[2])

    await act(async () => { veld().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })) })
    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [1, 2], [])
  })

  it('het veld wordt niet herschreven door de keuze', async () => {
    await toon(KLAAR)
    await klik(vakjes()[0])
    await klik(vakjes()[1])

    expect(veld().value).toBe(VOORSTEL)
  })

  it('op een telefoon begint de lijst ingeklapt, op een groot scherm open', async () => {
    await toon(KLAAR)
    expect(container.querySelector('details').open).toBe(true)
    await act(async () => root.unmount())
    container.remove()

    zetSchermbreedte(true)
    await toon(KLAAR)
    expect(container.querySelector('details').open).toBe(false)
  })
})

describe('zonder keuze te maken (#908)', () => {
  it.each([
    ['geen beurten met data', { status: 'klaar', items: [] }],
    ['één beurt met data', { status: 'klaar', items: [ITEMS[0]] }],
    ['nog niet gevraagd', null],
  ])('%s: alleen het veld, en Genereer stuurt geen beurten', async (_naam, checklist) => {
    await toon(checklist)

    expect(set()).toBeNull()
    await klik(genereer())
    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, undefined)
  })

  it('tijdens het laden wacht Genereer, met een melding', async () => {
    await toon({ status: 'laden', items: [] })

    expect(container.querySelector('[role="status"]').textContent).toContain('worden opgehaald')
    expect(genereer().getAttribute('aria-disabled')).toBe('true')
    await klik(genereer())
    expect(onGenereer).not.toHaveBeenCalled()
  })

  it('bij een fout zegt de dialoog dat het hele gesprek wordt gebruikt, zonder figuren, en Genereer werkt', async () => {
    await toon({ status: 'fout', items: [] })

    expect(container.querySelector('[role="status"]').textContent)
      .toBe('De vragen met data konden niet worden opgehaald. Het rapport gebruikt het hele gesprek, zonder figuren.')
    await klik(genereer())
    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, undefined)
  })

  it('de lijst die na het openen binnenkomt staat ook helemaal aan', async () => {
    await toon({ status: 'laden', items: [] })
    await act(async () => {
      root.render(createElement(OnderzoeksvraagDialoog, { voorstel: VOORSTEL, max: 4000, checklist: KLAAR, onGenereer, onClose }))
    })

    expect(vakjes().map(v => v.checked)).toEqual([true, true, true])
    expect(document.activeElement).toBe(veld())
  })
})

describe('figuren in de checklist (#993)', () => {
  const MET_FIGUREN = {
    status: 'klaar',
    items: [
      { ...ITEMS[0], figuren: [{ id: 'f1', titel: 'Instroom UU' }, { id: 'f2', titel: 'Instroom als staven' }] },
      ITEMS[1],
      { ...ITEMS[2], figuren: [{ id: 'f3', titel: 'Vrouwen per jaar' }] },
    ],
  }
  const figuurvakjes = () => [...container.querySelectorAll('.rapport-keuze-figuren input[type="checkbox"]')]
  const vraagvakjes = () => vakjes().filter(v => !v.closest('.rapport-keuze-figuren'))

  it('toont de figuren onder hun vraag, met hun titel als naam, en alles aan', async () => {
    await toon(MET_FIGUREN)

    expect(figuurvakjes().map(v => v.labels[0].textContent)).toEqual([
      'Figuur: Instroom UU', 'Figuur: Instroom als staven', 'Figuur: Vrouwen per jaar',
    ])
    expect(figuurvakjes().every(v => v.checked)).toBe(true)
    expect(container.querySelector('summary').textContent).toBe('Vragen in het rapport: 3 van 3 · figuren: 3 van 3')
    // Het rapport tekent zelf niets meer (besluit 18-11): de dialoog zegt dat alleen de aangevinkte figuren meegaan.
    expect(container.textContent)
      .toContain('Het rapport toont alleen de aangevinkte figuren uit het gesprek en tekent er zelf geen.')
  })

  it('zonder figuren in het gesprek noemt de dialoog geen figuren', async () => {
    await toon(KLAAR)

    expect(container.textContent).not.toContain('figuren')
  })

  it('Genereer stuurt de figuren mee die aanstaan', async () => {
    await toon(MET_FIGUREN)
    await klik(figuurvakjes()[1])

    await klik(genereer())

    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [1, 2, 3], ['f1', 'f3'])
  })

  it('een vraag uit zet haar figuren uit', async () => {
    await toon(MET_FIGUREN)
    await klik(vraagvakjes()[0])

    expect(figuurvakjes().map(v => v.checked)).toEqual([false, false, true])
    await klik(genereer())
    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [2, 3], ['f3'])
  })

  it('een figuur aan zet haar vraag weer aan', async () => {
    await toon(MET_FIGUREN)
    await klik(vraagvakjes()[2])
    expect(vraagvakjes()[2].checked).toBe(false)

    await klik(figuurvakjes()[2])

    expect(vraagvakjes()[2].checked).toBe(true)
    await klik(genereer())
    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [1, 2, 3], ['f1', 'f2', 'f3'])
  })

  it('één vraag met een figuur is al een keuze', async () => {
    await toon({ status: 'klaar', items: [MET_FIGUREN.items[2]] })

    expect(set()).not.toBeNull()
    await klik(genereer())
    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [3], ['f3'])
  })

  it('meer dan vier figuren kan niet worden verstuurd, en de melding zegt het', async () => {
    const vijf = { ...ITEMS[0], figuren: ['a', 'b', 'c', 'd', 'e'].map(id => ({ id, titel: `Figuur ${id}` })) }
    await toon({ status: 'klaar', items: [vijf] })

    const melding = container.querySelector('[role="alert"]')
    expect(melding.textContent)
      .toBe('Kies hoogstens 4 figuren voor het rapport. Nu staan er 5 aan: zet er figuren uit in de lijst.')
    expect(genereer().getAttribute('aria-disabled')).toBe('true')
    expect(genereer().getAttribute('aria-describedby')).toBe(melding.id)
    await klik(genereer())
    expect(onGenereer).not.toHaveBeenCalled()

    await klik(figuurvakjes()[4])
    expect(container.querySelector('[role="alert"]')).toBeNull()
    await klik(genereer())
    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [1], ['a', 'b', 'c', 'd'])
  })

  it('op een telefoon staat de lijst open zolang er te veel figuren aan staan', async () => {
    zetSchermbreedte(true)
    const vijf = { ...ITEMS[0], figuren: ['a', 'b', 'c', 'd', 'e'].map(id => ({ id, titel: `Figuur ${id}` })) }
    await toon({ status: 'klaar', items: [vijf] })

    expect(container.querySelector('details').open).toBe(true)
  })

  it('op een telefoon blijft de lijst dicht als er niets te verhelpen is', async () => {
    zetSchermbreedte(true)
    await toon(MET_FIGUREN)

    expect(container.querySelector('details').open).toBe(false)
  })
})

describe('restpunten van de checklist (#1045)', () => {
  const figuurvakjes = () => [...container.querySelectorAll('.rapport-keuze-figuren input[type="checkbox"]')]
  const vraagvakjes = () => vakjes().filter(v => !v.closest('.rapport-keuze-figuren'))
  const beschrijving = vakje => document.getElementById(vakje.getAttribute('aria-describedby'))?.textContent ?? ''
  const metFiguren = (aantal, eigen = {}) => ({
    status: 'klaar',
    items: [{ ...ITEMS[0], figuren: Array.from({ length: aantal }, (_, i) => ({ id: `f${i}`, titel: `Figuur ${i}` })), ...eigen }],
  })

  it('op een telefoon (375 px) blijft de lijst open als je van vijf naar vier figuren gaat', async () => {
    zetSchermbreedte(true)
    await toon(metFiguren(5))
    expect(container.querySelector('details').open).toBe(true)

    await klik(figuurvakjes()[4])

    expect(figuurvakjes().filter(v => v.checked)).toHaveLength(4)
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelector('details').open).toBe(true)
  })

  it('op een telefoon met vier figuren begint de lijst nog steeds dicht, op een groot scherm open', async () => {
    zetSchermbreedte(true)
    await toon(metFiguren(4))
    expect(container.querySelector('details').open).toBe(false)
    await act(async () => root.unmount())
    container.remove()

    zetSchermbreedte(false)
    await toon(metFiguren(4))
    expect(container.querySelector('details').open).toBe(true)
  })

  const MEER = {
    status: 'klaar',
    items: [
      ITEMS[0],
      { ...ITEMS[1], figuren: [{ id: 'samen', titel: 'Rendement naast instroom', beurten: [1, 2] }] },
      ITEMS[2],
    ],
  }

  it('een figuur met data uit beurt 1 en 2 vinkt beide aan, en ze gaan allebei mee', async () => {
    await toon(MEER)
    await klik(vraagvakjes()[0])
    await klik(vraagvakjes()[1])
    expect(vraagvakjes().map(v => v.checked)).toEqual([false, false, true])
    expect(figuurvakjes()[0].checked).toBe(false)

    await klik(figuurvakjes()[0])

    expect(vraagvakjes().map(v => v.checked)).toEqual([true, true, true])
    await klik(genereer())
    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [1, 2, 3], ['samen'])
  })

  it('de meegetrokken beurt zegt voor welke figuur ze nodig is, alleen zolang die figuur aanstaat', async () => {
    await toon(MEER)

    expect(beschrijving(vraagvakjes()[0])).toContain('Nodig voor figuur “Rendement naast instroom”.')
    expect(beschrijving(vraagvakjes()[1])).not.toContain('Nodig voor')
    expect(beschrijving(vraagvakjes()[2])).not.toContain('Nodig voor')

    await klik(figuurvakjes()[0])
    expect(beschrijving(vraagvakjes()[0])).not.toContain('Nodig voor')
  })

  it('de meegetrokken beurt uitzetten zet de figuur uit: het rapport rust nooit op een beurt die uit staat', async () => {
    await toon(MEER)

    await klik(vraagvakjes()[0])

    expect(figuurvakjes()[0].checked).toBe(false)
    await klik(genereer())
    expect(onGenereer).toHaveBeenCalledExactlyOnceWith(VOORSTEL, [2, 3], [])
  })

  it('een ouder antwoord zonder beurten bij de figuur valt terug op haar eigen beurt', async () => {
    await toon({ status: 'klaar', items: [ITEMS[0], { ...ITEMS[1], figuren: [{ id: 'oud', titel: 'Oud' }] }] })
    await klik(vraagvakjes()[0])
    await klik(vraagvakjes()[1])

    await klik(figuurvakjes()[0])

    expect(vraagvakjes().map(v => v.checked)).toEqual([false, true])
    expect(container.textContent).not.toContain('Nodig voor')
  })

  it('twee figuren met dezelfde titel hebben een ander label; een unieke titel niet', async () => {
    await toon({
      status: 'klaar',
      items: [
        { ...ITEMS[0], figuren: [{ id: 'a', titel: 'Instroom' }, { id: 'b', titel: 'Uitval' }] },
        { ...ITEMS[1], figuren: [{ id: 'c', titel: 'Instroom' }] },
      ],
    })

    expect(figuurvakjes().map(v => v.labels[0].textContent))
      .toEqual(['Figuur: Instroom (1)', 'Figuur: Uitval', 'Figuur: Instroom (2)'])
  })
})

describe('toegankelijkheid van de dialoog (#908)', () => {
  // jsdom rekent geen layout, dus axe meet hier geen contrast; wat het wel ziet (namen, rollen, labels, fieldset,
  // legend, beschrijvingen, aria) faalt op serious en critical, zoals in toegankelijkheidApp.test.js.
  async function bevindingen() {
    const { violations } = await axe.run(container, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
      rules: { region: { enabled: false }, 'html-has-lang': { enabled: false } },
    })
    return violations.map(v => `${v.id}: ${v.nodes.map(n => n.target.join(' ')).join(', ')}`)
  }

  it.each([
    ['met de checklist, open', () => KLAAR, false],
    ['met de checklist, ingeklapt op een telefoon', () => KLAAR, true],
    ['met alles uitgezet en de melding', () => KLAAR, false, true],
    ['met figuren (#993)', () => ({ status: 'klaar', items: [{ ...ITEMS[0], figuren: [{ id: 'f1', titel: 'T' }] }, ITEMS[1]] }), false],
    ['met een meegetrokken beurt (#1045)', () => ({ status: 'klaar', items: [ITEMS[0], { ...ITEMS[1], figuren: [{ id: 'f1', titel: 'T', beurten: [1, 2] }] }] }), false],
    ['tijdens het laden', () => ({ status: 'laden', items: [] }), false],
    ['bij een fout', () => ({ status: 'fout', items: [] }), false],
    ['zonder checklist', () => ({ status: 'klaar', items: [] }), false],
  ])('heeft geen bevindingen %s', async (_naam, checklist, smal, allesUit = false) => {
    zetSchermbreedte(smal)
    await toon(checklist())
    if (allesUit) for (const v of vakjes()) await klik(v)

    expect(await bevindingen()).toEqual([])
  })
})
