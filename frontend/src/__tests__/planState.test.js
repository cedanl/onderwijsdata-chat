// @vitest-environment jsdom
// #1268: de toestand van de plankaart. Een kaart komt binnen als event `plan`; "Klopt, ga door" stuurt plan_bevestigen
// met het id, "Pas aan" zet de vraag met de plankeuzes in het invoerveld en laat niets laden. Na herladen kent de server
// het plan niet meer: de kaart staat er nog, als verlopen, en alleen "Pas aan" kan.
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useChat } from '../hooks/useChat'
import { loadCurrentChat, persistCurrentChat } from '../conversationStore'
import { aanpasTekst, planStatus, planUit } from '../planState'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

class FakeWebSocket {
  static OPEN = 1
  static last = null
  constructor() {
    this.readyState = FakeWebSocket.OPEN
    this.sent = []
    FakeWebSocket.last = this
  }
  send(data) { this.sent.push(JSON.parse(data)) }
  close() {}
  emit(event) { this.onmessage({ data: JSON.stringify(event) }) }
}

const VRAAG = 'Koppel de mbo-studenten en de ingeschrevenen in het ho per schooljaar'
const PLAN = {
  type: 'plan',
  id: 'plan-1',
  vraag: VRAAG,
  tekst: 'Plan voorgelegd: Mbo; studenten (85354NED) en Ingeschrevenen ho (p01hoinges), gekoppeld op schooljaar.',
  bronnen: [
    { titel: 'Mbo; studenten naar niveau, leerweg, herkomst', dataset: '85354NED', versie: 'versie van 09-04-2026', selectie: ['jaren: alle beschikbare jaren', 'vorm: alle'] },
    { titel: 'Ingeschrevenen hoger onderwijs', dataset: 'p01hoinges', versie: 'de nieuwste versie bij het laden', selectie: ['bestand: het standaardbestand'] },
  ],
  sleutel: 'schooljaar',
  duur: 'ongeveer een minuut',
}

let root
let chat

async function openPage(opties = {}) {
  function Harness() {
    chat = useChat(opties)
    return null
  }
  root = createRoot(document.createElement('div'))
  await act(async () => { root.render(createElement(Harness)) })
  return FakeWebSocket.last
}

async function vraagMetKaart(ws) {
  await act(async () => { chat.send(VRAAG) })
  await act(async () => { ws.emit({ type: 'message_start' }) })
  await act(async () => { ws.emit({ type: 'tool_start', name: 'search_catalog', label: 'Catalogus doorzocht' }) })
  await act(async () => { ws.emit({ type: 'tool_end', name: 'search_catalog' }) })
  await act(async () => { ws.emit({ type: 'message_cancel' }) })
  await act(async () => { ws.emit(PLAN) })
  return chat.messages.findIndex(m => m.plan)
}

beforeEach(() => {
  localStorage.clear()
  globalThis.WebSocket = FakeWebSocket
})

afterEach(async () => {
  if (root) await act(async () => root.unmount())
  root = null
})

describe('planUit', () => {
  it('neemt alleen de velden van de kaart over', () => {
    expect(planUit(PLAN)).toEqual({
      id: 'plan-1', vraag: VRAAG, bronnen: PLAN.bronnen, sleutel: 'schooljaar', duur: 'ongeveer een minuut',
    })
  })

  it('is null zonder id of met minder dan twee bronnen', () => {
    expect(planUit({ ...PLAN, id: undefined })).toBeNull()
    expect(planUit({ ...PLAN, bronnen: [PLAN.bronnen[0]] })).toBeNull()
    expect(planUit(null)).toBeNull()
  })
})

describe('aanpasTekst', () => {
  it('zet de vraag en de plankeuzes in één tekst voor het invoerveld', () => {
    const tekst = aanpasTekst(planUit(PLAN))
    expect(tekst.startsWith(VRAAG)).toBe(true)
    expect(tekst).toContain('Mbo; studenten naar niveau, leerweg, herkomst, 85354NED (jaren: alle beschikbare jaren; vorm: alle)')
    expect(tekst).toContain('Ingeschrevenen hoger onderwijs, p01hoinges (bestand: het standaardbestand)')
    expect(tekst).toContain('Koppelen op: schooljaar.')
  })

  it('zegt "naast elkaar" zonder sleutel', () => {
    expect(aanpasTekst(planUit({ ...PLAN, sleutel: null }))).toContain('Naast elkaar, zonder koppeling.')
  })
})

describe('planStatus', () => {
  const kaart = { role: 'assistant', plan: { id: 'p' } }

  it('is open zolang de server op dit plan wacht, anders verlopen', () => {
    expect(planStatus([kaart], 0, 'p')).toBe('open')
    expect(planStatus([kaart], 0, null)).toBe('verlopen')
    expect(planStatus([kaart], 0, 'ander')).toBe('verlopen')
  })

  it('onthoudt de keuze op de kaart, en een nieuwe vraag sluit haar', () => {
    expect(planStatus([{ ...kaart, planKeuze: 'bevestigd' }], 0, null)).toBe('bevestigd')
    expect(planStatus([{ ...kaart, planKeuze: 'aangepast' }], 0, 'p')).toBe('aangepast')
    expect(planStatus([kaart, { role: 'user', content: 'Iets anders' }], 0, 'p')).toBe('voorbij')
  })
})

describe('de plankaart in het gesprek (useChat)', () => {
  it('komt binnen als kaart uit code en wacht op een keuze', async () => {
    const ws = await openPage()
    const i = await vraagMetKaart(ws)

    expect(i).toBeGreaterThan(0)
    const kaart = chat.messages[i]
    expect(kaart).toMatchObject({ role: 'assistant', content: PLAN.tekst, vast: true, done: true })
    expect(kaart.plan.id).toBe('plan-1')
    expect(chat.openPlanId).toBe('plan-1')
    expect(chat.busy).toBe(false)
    expect(planStatus(chat.messages, i, chat.openPlanId)).toBe('open')
  })

  it('"Klopt, ga door" stuurt plan_bevestigen met het id, zonder nieuwe vraag aan het model', async () => {
    const ws = await openPage()
    const i = await vraagMetKaart(ws)
    const kaart = chat.messages[i]

    let weg
    await act(async () => { weg = chat.sendPlanBevestiging(kaart.id, kaart.plan) })

    expect(weg).toBe(true)
    expect(ws.sent.at(-1)).toEqual({ action: 'plan_bevestigen', id: 'plan-1' })
    expect(chat.busy).toBe(true)
    expect(chat.openPlanId).toBeNull()
    expect(planStatus(chat.messages, i, chat.openPlanId)).toBe('bevestigd')
    expect(chat.messages.at(-1)).toMatchObject({ role: 'user', content: 'Klopt, ga door', planBevestiging: true })
    // Een tweede klik stuurt niets meer.
    await act(async () => { weg = chat.sendPlanBevestiging(kaart.id, kaart.plan) })
    expect(weg).toBe(false)
    expect(ws.sent.filter(f => f.action === 'plan_bevestigen')).toHaveLength(1)
  })

  it('"Pas aan" geeft de vraag met de plankeuzes terug en laadt niets', async () => {
    const ws = await openPage()
    const i = await vraagMetKaart(ws)
    const kaart = chat.messages[i]

    let tekst
    await act(async () => { tekst = chat.planAanpassen(kaart.id, kaart.plan) })

    expect(tekst).toBe(aanpasTekst(kaart.plan))
    expect(tekst).toContain(VRAAG)
    expect(ws.sent.at(-1)).toEqual({ action: 'plan_aanpassen', id: 'plan-1' })
    expect(ws.sent.some(f => f.action === 'plan_bevestigen')).toBe(false)
    expect(chat.busy).toBe(false)
    expect(planStatus(chat.messages, i, chat.openPlanId)).toBe('aangepast')
  })

  it('een gesprek met een open plankaart komt na herladen terug met de kaart als verlopen', async () => {
    const ws = await openPage()
    await vraagMetKaart(ws)
    expect(persistCurrentChat('gesprek-1', chat.messages)).toBe('ok')
    await act(async () => root.unmount())
    root = null

    const { messages } = loadCurrentChat()
    const i = messages.findIndex(m => m.plan)
    expect(i).toBeGreaterThan(0)
    expect(messages[i].plan.bronnen).toHaveLength(2)

    const ws2 = await openPage()
    expect(chat.openPlanId).toBeNull()
    expect(planStatus(messages, i, chat.openPlanId)).toBe('verlopen')
    // Wat de server ziet, als historie: de kaart als tekst uit code, geen leeg bericht.
    expect(chat.sendHistory(messages)).toBe(true)
    const historie = ws2.sent.at(-1).messages
    expect(historie).toContainEqual({ role: 'assistant', content: PLAN.tekst })
    // "Pas aan" kan nog: de tekst, zonder frame naar een server die het plan niet kent.
    let tekst
    await act(async () => { tekst = chat.planAanpassen(messages[i].id, messages[i].plan) })
    expect(tekst).toContain(VRAAG)
    expect(ws2.sent.some(f => f.action === 'plan_aanpassen' || f.action === 'plan_bevestigen')).toBe(false)
  })

  it('stuurt de stand van Geavanceerd mee in de vraag, alleen als die aan staat', async () => {
    const uit = await openPage()
    await act(async () => { chat.send(VRAAG) })
    expect(uit.sent.at(-1)).toEqual({ action: 'message', content: VRAAG })
    await act(async () => root.unmount())

    const aan = await openPage({ geavanceerd: true })
    await act(async () => { chat.send(VRAAG) })
    expect(aan.sent.at(-1)).toEqual({ action: 'message', content: VRAAG, geavanceerd: true })
  })

  it('een nieuwe vraag sluit een open plan', async () => {
    const ws = await openPage()
    const i = await vraagMetKaart(ws)

    await act(async () => { chat.send('Iets anders') })

    expect(chat.openPlanId).toBeNull()
    expect(planStatus(chat.messages, i, chat.openPlanId)).toBe('voorbij')
  })
})
