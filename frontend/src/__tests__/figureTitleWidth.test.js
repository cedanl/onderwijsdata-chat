// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

// Every layout the chart is drawn with, in order: a new one is a Plotly redraw.
const layouts = vi.hoisted(() => [])
vi.mock('react-plotly.js', () => ({ default: function PlotStub({ layout }) { layouts.push(layout); return null } }))

import { Message } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

// jsdom has no ResizeObserver; this one lets the test say how wide the chart wrapper became.
const observers = []
class FakeResizeObserver {
  constructor(callback) { this.callback = callback; observers.push(this) }
  observe(el) { this.el = el }
  disconnect() { this.disconnected = true }
}
async function resize(width) {
  const live = observers.filter(o => !o.disconnected)
  await act(async () => { live.forEach(o => o.callback([{ target: o.el, contentRect: { width } }])) })
}

const ISSUE = 'Mbo-studenten totaal (incl. extranei), 2020/2021 – 2024/2025'
const figure = JSON.stringify({
  data: [{ type: 'bar', x: ['2020/2021', '2024/2025'], y: [512340, 491230] }],
  layout: { title: { text: ISSUE, font: { size: 16, color: '#222' } }, margin: { t: 60 } },
})
const msg = { role: 'assistant', done: true, content: '', figures: [{ json: figure, label: 'Studenten' }] }

let root
let container

async function renderFigure() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(createElement(Message, { msg })) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  layouts.length = 0
  observers.length = 0
  vi.unstubAllGlobals()
})

// #587: the chart title is broken for the width the chart wrapper really has.
describe('the title of a chart in the chat', () => {
  it('stays as it is while the width is unknown', async () => {
    vi.stubGlobal('ResizeObserver', undefined)
    await renderFigure()
    expect(layouts.at(-1).title.text).toBe(ISSUE)
    expect(layouts.at(-1).margin.t).toBe(32)
  })

  it('is broken on a phone, re-broken when it turns, and not redrawn for the same width', async () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    await renderFigure()
    expect(observers.at(-1).el.classList.contains('plotly-figure-wrap')).toBe(true)

    await resize(342)
    const portrait = layouts.at(-1)
    expect(portrait.title.text).toContain('<br>')
    expect(portrait.margin.t).toBeGreaterThan(32)

    const draws = layouts.length
    await resize(340)
    expect(layouts.length).toBe(draws)

    await resize(796)
    expect(layouts.at(-1).title.text).toBe(ISSUE)
    expect(layouts.at(-1).margin.t).toBe(32)
  })

  it('stops following the width once the chart is gone', async () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    await renderFigure()
    const observer = observers.at(-1)
    act(() => root.unmount())
    expect(observer.disconnected).toBe(true)
    root = createRoot(container)
  })
})
