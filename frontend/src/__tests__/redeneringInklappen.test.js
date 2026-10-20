// @vitest-environment jsdom
// #609: na een compleet antwoord bleef de kaart "Redenering (N stappen)" open, 380–430 px hoog; op een telefoon
// begon het antwoord daardoor onder de vouw. Op een telefoon klapt de kaart nu in zodra het antwoord begint (#639:
// bij `done` schoof het hele antwoord omhoog); wie hem zelf opende of sloot, houdt zijn stand; desktop blijft zoals
// het was.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { Message } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const smal = { aan: false }
window.matchMedia = q => ({
  matches: smal.aan && q === '(max-width: 1024px)', media: q, addEventListener() {}, removeEventListener() {},
})

let root
let container

afterEach(() => {
  if (root) act(() => root.unmount())
  container?.remove()
  root = null
  smal.aan = false
})

const stappen = [
  { name: 'search_catalog', label: 'Catalogus doorzocht', done: true },
  { name: 'get_cbs_data', label: 'CBS data opgehaald', done: true },
]
const wachtend = { id: 2, role: 'assistant', content: '', tools: stappen, done: false }
const lopend = { ...wachtend, content: 'Er waren' }
const klaar = { ...lopend, content: 'Er waren 475.460 studenten.', done: true, bronnen: [] }

function render(msg) {
  if (!root) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  }
  act(() => root.render(createElement(Message, { msg, settled: msg.done, busy: !msg.done })))
  return container
}

const toggle = () => container.querySelector('.reasoning-toggle')
const open = () => toggle().getAttribute('aria-expanded') === 'true'

describe('de Redenering-kaart na een compleet antwoord', () => {
  it('klapt op een telefoon in zodra de antwoordtekst begint, en blijft dicht als het antwoord compleet is', () => {
    smal.aan = true
    render(wachtend)
    expect(open()).toBe(true)
    render(lopend)
    expect(open()).toBe(false)
    render(klaar)
    expect(open()).toBe(false)
    expect(container.querySelector('.reasoning-content')).toBeNull()
    expect(toggle().textContent).toContain('Redenering (2 stappen)')
  })

  it('blijft open zolang een stap loopt, ook als er al tekst staat', () => {
    smal.aan = true
    render({ ...lopend, tools: [...stappen, { name: 'create_plot', label: 'Grafiek', done: false }] })
    expect(open()).toBe(true)
  })

  it('gaat weer open als na tussentekst een nieuwe stap start (#393)', () => {
    smal.aan = true
    render(wachtend)
    render(lopend)
    expect(open()).toBe(false)
    render({ ...wachtend, tussentekst: ['Er waren'], tools: [...stappen, { name: 'create_plot', label: 'Grafiek', done: false }] })
    expect(open()).toBe(true)
    expect(container.querySelectorAll('.reasoning-step')).toHaveLength(3)
  })

  it('blijft op desktop open zoals voorheen', () => {
    render(lopend)
    render(klaar)
    expect(open()).toBe(true)
  })

  it('respecteert wie de kaart zelf bediende: dicht en weer open blijft open', () => {
    smal.aan = true
    render(wachtend)
    act(() => toggle().click())
    expect(open()).toBe(false)
    act(() => toggle().click())
    expect(open()).toBe(true)
    render(lopend)
    expect(open()).toBe(true)
    render(klaar)
    expect(open()).toBe(true)
  })

  it('laat de kaart na het inklappen weer openen', () => {
    smal.aan = true
    render(lopend)
    render(klaar)
    act(() => toggle().click())
    expect(open()).toBe(true)
    expect(container.querySelectorAll('.reasoning-step')).toHaveLength(2)
  })
})
