// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import DataExport from '../components/DataExport'
import { Message } from '../pages/ChatPage'
import { useChat } from '../hooks/useChat'
import { conversationMessages } from '../conversationStore'
import { BEWIJS_SCHEMA, BEWIJS_SLEUTELS, bewijs, bewijsBestandsnaam, bewijsJson, heeftBewijs } from '../bewijsJson'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

// #1244: "Bewijs (JSON)" naast de downloads van een dataantwoord, gebouwd uit het bericht zelf.
const MANIFEST = {
  model: 'mistral/mistral-medium', model_naam: 'Mistral Medium', prompt_hash: 'ab12cd34', catalogus: '2026-11-20',
  app: '3.1.0', data_as_of: [{ bron: 'duo', dataset: 'p01hoinges', bronhash: ['9f8e'] }], gemaakt_op: '25-11-2026',
}
const VASTE_MAAT = { maat: 'ingeschreven_personen_ho', teldefinitie: 'personen', vastgelegd_in: '#188', vastgelegd_op: '2026-10-14' }
const ARGS = { maat: 'ingeschreven_personen_ho', instelling: 'Hogeschool Utrecht', schooljaren: ['2024/25'] }
const ANTWOORD = {
  role: 'assistant', done: true, content: 'De HU had in 2024/25 38.000 ingeschreven personen.',
  bronnen: ['DUO p01hoinges'], bronlinks: { 'DUO p01hoinges': 'https://duo.nl/open_onderwijsdata/p01' },
  citaties: [{ getal: '38.000', maat: 'AANTAL_INGESCHREVENEN', selectie: 'HU, 2024/25', bron: 'DUO p01hoinges', stap: 1, vastgesteld: true }],
  manifest: MANIFEST, vaste_maat: VASTE_MAAT,
  tools: [
    { name: 'search_catalog', label: 'Catalogus doorzocht', done: true, arguments: { query: 'studenten' }, snippet: null },
    { name: 'get_maat', label: 'Vaste maat opgehaald', done: true, arguments: ARGS, snippet: 'df = maat()', exportKey: 'duo:p01:a', output: '{"rijen":[{"AANTAL":38000}]}' },
    { name: 'query_data', label: 'Data gefilterd', done: true, status: 'empty', statusLabel: 'Filter leverde 0 rijen op', arguments: { data_key: 'x' } },
  ],
}

describe('bewijs (#1244)', () => {
  it('heeft het schema en precies de vaste sleutels, in volgorde', () => {
    const b = bewijs(ANTWOORD)
    expect(Object.keys(b)).toEqual(BEWIJS_SLEUTELS)
    expect(BEWIJS_SLEUTELS).toEqual([
      'schema', 'manifest', 'bronnen', 'bronlinks', 'citaties', 'controle', 'toolstappen', 'vaste_maat', 'antwoord',
    ])
    expect(b.schema).toBe(BEWIJS_SCHEMA)
    expect(BEWIJS_SCHEMA).toBe('onderwijsdata-chat/bewijs/1')
    expect(b).toMatchObject({
      manifest: MANIFEST, bronnen: ANTWOORD.bronnen, bronlinks: ANTWOORD.bronlinks, citaties: ANTWOORD.citaties,
      controle: null, vaste_maat: VASTE_MAAT, antwoord: ANTWOORD.content,
    })
  })

  it('is geldige JSON', () => {
    expect(JSON.parse(bewijsJson(ANTWOORD))).toEqual(bewijs(ANTWOORD))
  })

  it('geeft per geslaagde stap naam, argumenten en code, nooit de ruwe uitvoer', () => {
    const { toolstappen } = bewijs(ANTWOORD)
    expect(toolstappen).toEqual([
      { name: 'search_catalog', arguments: { query: 'studenten' }, snippet: null },
      { name: 'get_maat', arguments: ARGS, snippet: 'df = maat()' },
    ])
    expect(bewijsJson(ANTWOORD)).not.toContain('rijen')
    expect(bewijsJson(ANTWOORD)).not.toContain('Filter leverde')
  })

  it('zet een sleutel die niet van toepassing is op null: een antwoord zonder manifest, links of vaste maat', () => {
    const b = bewijs({ role: 'assistant', done: true, content: 'Tekst.', bronnen: ['CBS 85354NED'], controle: ['let op'] })
    expect(b).toEqual({
      schema: BEWIJS_SCHEMA, manifest: null, bronnen: ['CBS 85354NED'], bronlinks: null, citaties: null,
      controle: ['let op'], toolstappen: null, vaste_maat: null, antwoord: 'Tekst.',
    })
  })

  it('geeft een stap van vóór #1244 zonder argumenten null als argumenten', () => {
    const oud = { ...ANTWOORD, tools: [{ name: 'get_maat', done: true, snippet: 'df = maat()' }] }
    expect(bewijs(oud).toolstappen).toEqual([{ name: 'get_maat', arguments: null, snippet: 'df = maat()' }])
  })
})

describe('bewijsBestandsnaam (#478)', () => {
  it('neemt de titel uit de vraag, zoals de gespreksexport', () => {
    expect(bewijsBestandsnaam('Hoeveel studenten heeft de HU?')).toBe('bewijs_Hoeveel_studenten_heeft_de_HU.json')
  })

  it('laat een BSN, e-mailadres of telefoonnummer uit de vraag niet in de naam', () => {
    for (const vraag of ['Mijn BSN is 111222333, hoeveel studenten?', 'Mail jan@example.nl de cijfers', 'Bel 0612345678']) {
      const naam = bewijsBestandsnaam(vraag)
      expect(naam).toBe('bewijs_Gesprek_persoonsgegevens_weggelaten.json')
    }
  })

  it('heeft zonder vraag een vaste naam', () => {
    expect(bewijsBestandsnaam(null)).toBe('bewijs_antwoord.json')
  })
})

describe('de knop "Bewijs (JSON)" (#1244)', () => {
  let root
  let container

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  const knop = () => [...container.querySelectorAll('button')].find(b => b.textContent === 'Bewijs (JSON)')

  it('staat naast de CSV-knop en bewaart het bewijs onder de naam uit de vraag', () => {
    const saveJson = vi.fn()
    act(() => root.render(createElement(DataExport, {
      tools: ANTWOORD.tools, citaties: ANTWOORD.citaties, settled: true, bewijsVan: ANTWOORD,
      vraag: 'Hoeveel studenten heeft de HU?', saveJson,
    })))
    const knoppen = [...container.querySelectorAll('.data-export button')].map(b => b.textContent)
    expect(knoppen).toEqual(['Download data als CSV', 'Bewijs (JSON)'])
    act(() => knop().click())
    expect(saveJson).toHaveBeenCalledWith(bewijsJson(ANTWOORD), 'bewijs_Hoeveel_studenten_heeft_de_HU.json')
  })

  it('staat onder een dataantwoord in het exportblok', () => {
    act(() => root.render(createElement(Message, { msg: ANTWOORD })))
    expect(container.querySelector('[data-blok="export"] .bewijs-btn').textContent).toBe('Bewijs (JSON)')
  })

  it('staat ook onder een dataantwoord zonder tabel en zonder citaties', () => {
    const tekst = { role: 'assistant', done: true, content: 'De HU heeft vestigingen in Utrecht.', bronnen: ['RIO'] }
    act(() => root.render(createElement(Message, { msg: tekst })))
    expect(knop()).toBeTruthy()
    expect(container.querySelectorAll('.data-export-btn')).toHaveLength(0)
  })

  it('ontbreekt onder een vast antwoord zonder bronnen', () => {
    const vast = { role: 'assistant', done: true, content: 'Ik beantwoord alleen vragen over mbo, hbo en wo.', bronnen: [], vast: true }
    expect(heeftBewijs(vast)).toBe(false)
    act(() => root.render(createElement(Message, { msg: vast })))
    expect(knop()).toBeUndefined()
  })

  it('ontbreekt zolang het antwoord nog loopt', () => {
    act(() => root.render(createElement(DataExport, { tools: [], settled: false, bewijsVan: ANTWOORD })))
    expect(knop()).toBeUndefined()
  })
})

class FakeWebSocket {
  static OPEN = 1
  static last = null
  constructor() {
    this.readyState = FakeWebSocket.OPEN
    FakeWebSocket.last = this
  }
  send() {}
  close() {}
  emit(event) { this.onmessage({ data: JSON.stringify(event) }) }
}

describe('hetzelfde bewijs na heropenen (#1244)', () => {
  let root

  afterEach(() => act(() => root.unmount()))

  it('bewaart de toolargumenten bij de stap en geeft na heropenen hetzelfde bestand', async () => {
    globalThis.WebSocket = FakeWebSocket
    let chat
    function Harness() {
      chat = useChat()
      return null
    }
    root = createRoot(document.createElement('div'))
    await act(async () => { root.render(createElement(Harness)) })
    await act(async () => {
      const ws = FakeWebSocket.last
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'tool_start', name: 'get_maat', label: 'Vaste maat opgehaald', input: ARGS })
      ws.emit({ type: 'tool_end', name: 'get_maat', output: '{"rijen":[{"AANTAL":38000}]}', snippet: 'df = maat()', export_key: 'duo:p01:a' })
      ws.emit({
        type: 'message_end', content: ANTWOORD.content, bronnen: ANTWOORD.bronnen, bronlinks: ANTWOORD.bronlinks,
        citaties: ANTWOORD.citaties, manifest: MANIFEST, vaste_maat: VASTE_MAAT,
      })
    })
    const live = chat.messages.find(m => m.role === 'assistant')
    expect(live.tools[0].arguments).toEqual(ARGS)
    expect(live.tools[0]).not.toHaveProperty('output')

    // Zoals ChatPage het gesprek bewaart (PUT /api/conversations/{id}) en weer opent.
    const heropend = conversationMessages({ messages: JSON.stringify([{ role: 'user', content: 'Hoeveel?' }, live]) })
    expect(bewijsJson(heropend[1])).toBe(bewijsJson(live))
    expect(bewijs(heropend[1]).toolstappen).toEqual([{ name: 'get_maat', arguments: ARGS, snippet: 'df = maat()' }])
  })
})

// #1256 en #1259 naast #1244: de regels onder het antwoord komen uit stappen van code na de modelronde. Die stappen
// sturen dezelfde events als een modelstap (tool_start met input, tool_end), de regels staan in de tekst van
// message_end en hun getallen in de citaties (tests/test_kruiscontrole.py toetst die events aan de serverkant).
describe('de regels onder het antwoord in het bewijs (#1256, #1259)', () => {
  let root

  afterEach(() => act(() => root.unmount()))

  const MAAT = { maat: 'mbo_studenten_landelijk', schooljaren: ['2024/25'] }
  const ALTERNATIEF = { ...MAAT, vorm: 'zonder_extranei' }
  const PAAR = { bronpaar: 'mbo-studenten-landelijk', schooljaar: '2024/25' }
  const DEFINITIES = '**Andere definities:** in 2024/25 telt dit antwoord 475.460; zonder extranei 465.820 (-2,0%).'
  const KRUIS = "**Ter controle:** DUO 'Mbo-studenten per instelling' telt in 2024/25 476.079 (alle instellingen): 619 meer dan CBS 85354NED (475.460), +0,1%."
  const TEKST = `In 2024/25 waren er 475.460 mbo-studenten.\n\n${DEFINITIES}\n\n${KRUIS}`
  const CITATIES = [
    { getal: '475.460', stap: 1, bron: 'CBS 85354NED', vastgesteld: true },
    { getal: '465.820', stap: 2, bron: 'CBS 85354NED', vastgesteld: true },
    { getal: '476.079', stap: 3, bron: "DUO 'Mbo-studenten per instelling'", vastgesteld: true },
  ]
  const VM = { maat: 'mbo_studenten_landelijk', teldefinitie: 'mbo-studenten landelijk; Leerweg: Totaal mbo (incl. extranei)', vastgelegd_in: '#805', vastgelegd_op: '2026-10-29' }

  it('zet de regels in het antwoord, de stappen van code met hun argumenten en hun getallen in de citaties', async () => {
    globalThis.WebSocket = FakeWebSocket
    let chat
    function Harness() {
      chat = useChat()
      return null
    }
    root = createRoot(document.createElement('div'))
    await act(async () => { root.render(createElement(Harness)) })
    await act(async () => {
      const ws = FakeWebSocket.last
      ws.emit({ type: 'message_start' })
      ws.emit({ type: 'tool_start', name: 'get_maat', label: 'Vaste maat opgehaald', input: MAAT })
      ws.emit({ type: 'tool_end', name: 'get_maat', output: '{}', snippet: 'df = maat()' })
      ws.emit({ type: 'tool_start', name: 'get_maat', label: 'Andere definitie berekend: zonder extranei', input: ALTERNATIEF })
      ws.emit({ type: 'tool_end', name: 'get_maat', output: '{}', snippet: 'df = maat(vorm="zonder_extranei")' })
      ws.emit({ type: 'tool_start', name: 'kruiscontrole', label: 'Kruiscontrole met de andere bron', input: PAAR })
      ws.emit({ type: 'tool_end', name: 'kruiscontrole', output: '{}', data_key: 'duo:mbo:som' })
      ws.emit({
        type: 'message_end', content: TEKST, bronnen: ['CBS 85354NED', "DUO 'Mbo-studenten per instelling'"],
        citaties: CITATIES, manifest: MANIFEST, vaste_maat: VM,
      })
    })
    const live = chat.messages.find(m => m.role === 'assistant')
    const b = bewijs(live)
    expect(Object.keys(b)).toEqual(BEWIJS_SLEUTELS)
    expect(b.antwoord).toContain(DEFINITIES)
    expect(b.antwoord).toContain(KRUIS)
    expect(b.toolstappen).toEqual([
      { name: 'get_maat', arguments: MAAT, snippet: 'df = maat()' },
      { name: 'get_maat', arguments: ALTERNATIEF, snippet: 'df = maat(vorm="zonder_extranei")' },
      { name: 'kruiscontrole', arguments: PAAR, snippet: null },
    ])
    // Hier wijst elke citatie naar haar stap in het bestand: de stappen van code komen na die van het model.
    expect(b.citaties.map(c => b.toolstappen[c.stap - 1].name)).toEqual(['get_maat', 'get_maat', 'kruiscontrole'])
    expect(b.vaste_maat).toEqual(VM)

    const heropend = conversationMessages({ messages: JSON.stringify([{ role: 'user', content: 'Hoeveel?' }, live]) })
    expect(bewijsJson(heropend[1])).toBe(bewijsJson(live))
  })
})
