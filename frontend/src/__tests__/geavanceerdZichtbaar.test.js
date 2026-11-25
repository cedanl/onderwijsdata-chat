// @vitest-environment jsdom
// #1269, criterium 7: zonder "Geavanceerd" is geen van de functies erachter te zien, met de instelling zijn ze er
// allemaal. Per functie een test in beide standen: de code per stap (smal en breed), de technische key van een getal,
// de data-CSV, de cijfer-CSV, "Vraag opnieuw stellen" na een mislukte download, de modelkiezer en de keuze "Code per stap"
// in de gespreksexport. De CSV van een grafiek staat in beide standen.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ReactMarkdown from 'react-markdown'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { ReasoningPanel } from '../components/MessageContent'
import CitedNumber from '../components/CitedNumber'
import DataExport from '../components/DataExport'
import ChatInputFooter from '../components/ChatInputFooter'
import ConversationExport from '../components/ConversationExport'
import { Message } from '../pages/ChatPage'
import { rehypeCitaties } from '../citations'
import { NARROW_SCREEN } from '../hooks/useMediaQuery'
import { metGeavanceerd } from './helpers/geavanceerd'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let mounted = []

function render(element, aan) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  mounted.push({ root, container })
  act(() => root.render(metGeavanceerd(element, aan)))
  return container
}

function scherm(smal) {
  window.matchMedia = q => ({ matches: smal && q === NARROW_SCREEN, media: q, addEventListener() {}, removeEventListener() {} })
}

afterEach(() => {
  for (const { root, container } of mounted) {
    act(() => root.unmount())
    container.remove()
  }
  mounted = []
  delete window.matchMedia
})

const knoppen = el => [...el.querySelectorAll('button')].map(b => b.textContent.trim())
const STANDEN = [['uit', false], ['aan', true]]

const STAPPEN = [
  { name: 'get_cbs_data', label: 'Data opgehaald', done: true, snippet: 'import pandas as pd\ndf = pd.read_csv("85354NED")' },
  { name: 'query_data', label: 'Data gefilterd', done: true, snippet: 'df = df[df["Perioden"] == "2024SJ00"]' },
]

describe.each(STANDEN)('Geavanceerd %s', (_naam, aan) => {
  it(aan ? 'toont de code per stap op een telefoon' : 'toont geen code per stap op een telefoon', () => {
    scherm(true)
    const el = render(createElement(ReasoningPanel, { tools: STAPPEN, isDone: false }), aan)
    expect(el.querySelectorAll('.reasoning-step')).toHaveLength(2) // de stappen zelf staan er altijd
    expect(el.querySelectorAll('.reasoning-step-code')).toHaveLength(aan ? 2 : 0)
    expect(el.textContent.includes('Bekijk code')).toBe(aan)
  })

  it(aan ? 'toont het codeblok onder de stappen op desktop' : 'toont geen codeblok op desktop', () => {
    scherm(false)
    const el = render(createElement(ReasoningPanel, { tools: STAPPEN, isDone: false }), aan)
    expect(el.querySelectorAll('.reasoning-step')).toHaveLength(2)
    expect(el.querySelector('.reasoning-snippets') !== null).toBe(aan)
    expect(el.textContent.includes('read_csv')).toBe(aan)
  })

  it(aan ? 'toont de technische key van een getal' : 'toont geen technische key, wel de herkomst in woorden', () => {
    const citaties = [{
      getal: '378.490', vastgesteld: true, stap: 3, tool: 'query_data', label: 'Data gefilterd',
      bron: 'CBS · Studenten; onderwijssoort', maat: 'Totaal', eenheid: 'aantal',
      selectie: 'Onderwijssoort: Hbo · Perioden: 2024', data_key: 'cbs:85353NED:854e2215',
    }]
    const el = render(createElement(ReactMarkdown, { rehypePlugins: [rehypeCitaties(citaties)], components: { span: CitedNumber } },
      'Er waren 378.490 studenten.'), aan)
    act(() => el.querySelector('.citatie-getal').click())
    const uitleg = el.querySelector('[role="note"]')
    expect(uitleg.textContent).toContain('CBS · Studenten; onderwijssoort')
    expect(uitleg.textContent).toContain('Onderwijssoort: Hbo · Perioden: 2024')
    expect(uitleg.querySelector('.citatie-key') !== null).toBe(aan)
    expect(uitleg.textContent.includes('Technische details')).toBe(aan)
  })

  it(aan ? 'biedt de data-CSV aan' : 'biedt geen data-CSV aan', () => {
    const el = render(createElement(DataExport, { settled: true, tools: [{ name: 'query_data', done: true, exportKey: 'duo:x:0' }] }), aan)
    expect(knoppen(el).includes('Download data als CSV')).toBe(aan)
  })

  it(aan ? 'biedt de cijfer-CSV aan' : 'biedt geen cijfer-CSV aan', () => {
    const citatie = { getal: '36.206', vastgesteld: true, stap: 1, tool: 'compute_kpi', bron: 'DUO · X', maat: 'Aantal' }
    const el = render(createElement(DataExport, { settled: true, tools: [{ name: 'compute_kpi', done: true }], citaties: [citatie] }), aan)
    expect(knoppen(el).includes('Download cijfers als CSV')).toBe(aan)
  })

  it(aan ? 'biedt na een mislukte download "Vraag opnieuw stellen"' : 'heeft geen download, dus ook geen "Vraag opnieuw stellen"', async () => {
    const download = vi.fn().mockRejectedValue(new Error('Deze data is niet meer beschikbaar.'))
    const el = render(createElement(DataExport, {
      settled: true, tools: [{ name: 'query_data', done: true, exportKey: 'duo:x:0' }], download, onHerhaal: vi.fn(),
    }), aan)
    const csv = [...el.querySelectorAll('button')].find(b => b.textContent === 'Download data als CSV')
    if (csv) await act(async () => csv.click())
    expect(knoppen(el).includes('Vraag opnieuw stellen')).toBe(aan)
  })

  it(aan ? 'toont de modelkiezer' : 'toont geen modelkiezer', () => {
    const el = render(createElement(ChatInputFooter, {
      connected: true, busy: false, canSend: true, onSend: vi.fn(), onStop: vi.fn(), onModelChange: vi.fn(),
      models: [{ id: 'a', name: 'Model A' }, { id: 'b', name: 'Model B' }], selectedModel: 'a',
    }), aan)
    expect(el.querySelector('.model-picker') !== null).toBe(aan)
    expect(el.querySelector('.send-btn')).not.toBeNull()
  })

  it(aan ? 'biedt "Code per stap" in de gespreksexport aan' : 'exporteert zonder code en zonder die keuze', () => {
    const save = vi.fn()
    const gesprek = [
      { role: 'user', content: 'Hoeveel?' },
      { role: 'assistant', content: 'Zoveel.', tools: [{ name: 'query_data', label: 'Data gefilterd', snippet: 'df.head()', done: true }] },
    ]
    const el = render(createElement(ConversationExport, { messages: gesprek, save }), aan)
    act(() => el.querySelector('.export-conversation-btn').click())
    const opties = [...el.querySelectorAll('.export-option')].map(o => o.textContent)
    expect(opties.includes('Code per stap (Python, met de bron)')).toBe(aan)
    expect(opties).toContain('Mislukte stappen en foutmeldingen')
    act(() => [...el.querySelectorAll('button')].find(b => b.textContent === 'Download').click())
    return save.mock.calls[0][0].text().then(markdown => expect(markdown.includes('df.head()')).toBe(aan))
  })

  it('houdt de CSV van een grafiek', () => {
    scherm(false)
    const figuur = { data: [{ type: 'bar', x: ['2023', '2024'], y: [518940, 475460] }], layout: { title: { text: 'Mbo-studenten' } } }
    const msg = { id: 1, role: 'assistant', content: '', done: true, figures: [{ label: 'Instroom', json: JSON.stringify(figuur) }] }
    const el = render(createElement(Message, { msg, onSend: vi.fn(), busy: false }), aan)
    expect(el.querySelector('.csv-download-btn')).not.toBeNull()
  })
})
