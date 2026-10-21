// @vitest-environment jsdom
// #626: een brede tabel in een antwoord maakte de hele berichtenlijst breder dan het scherm (op 390 px
// scrollWidth 792). De tabel staat nu in een eigen scrollcontainer; de lijst blijft zo breed als het scherm.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { Message } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')

const TABEL = '| Instelling | Studenten |\n|---|---|\n| HvA | 12.345 |\n| UvA | 23.456 |'
const antwoord = { id: 1, role: 'assistant', content: `Zo staat het erbij:\n\n${TABEL}\n\nKlaar.`, done: true }

let mounted = []

afterEach(() => {
  for (const { root, container } of mounted) {
    act(() => root.unmount())
    container.remove()
  }
  mounted = []
})

function render(msg) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  mounted.push({ root, container })
  act(() => root.render(createElement(Message, { msg })))
  return container
}

describe('tabel in een antwoord (#626)', () => {
  it('staat in een scrollcontainer die met het toetsenbord te bereiken is', () => {
    const tabel = render(antwoord).querySelector('.message-bubble table')
    const wrap = tabel.parentElement
    expect(wrap.classList.contains('tabel-scroll')).toBe(true)
    expect(wrap.getAttribute('role')).toBe('region')
    expect(wrap.getAttribute('aria-label')).toBe('Tabel')
    expect(wrap.tabIndex).toBe(0)
  })

  it('houdt de cellen en de kolomkoppen zoals ze waren', () => {
    const el = render(antwoord)
    expect([...el.querySelectorAll('th')].map(th => th.textContent)).toEqual(['Instelling', 'Studenten'])
    expect([...el.querySelectorAll('td')].map(td => td.textContent)).toEqual(['HvA', '12.345', 'UvA', '23.456'])
  })

  it('laat een antwoord zonder tabel ongemoeid', () => {
    expect(render({ ...antwoord, content: 'Alleen tekst.' }).querySelector('.tabel-scroll')).toBeNull()
  })

  it('laat de container zijwaarts scrollen zonder breder te worden dan de tekstkolom', () => {
    const regel = css.match(/\.tabel-scroll\s*\{([^}]*)\}/)
    expect(regel).not.toBeNull()
    expect(regel[1]).toMatch(/overflow-x:\s*auto\s*;/)
    expect(regel[1]).toMatch(/max-width:\s*100%\s*;/)
  })
})

// #657 (spec van #611, rood na #626): de scrollbox knipt ook verticaal (overflow-y wordt auto), dus de open herkomst van een getal in de
// tabel viel onderaan weg en scrolde binnen de tabel. Hij hangt nu buiten de box en schuift met de tabel mee.
describe('herkomst van een getal in een tabel (#657)', () => {
  const regel = kiezer => css.match(new RegExp(`${kiezer.replace(/[.]/g, '\\.')}\\s*\\{([^}]*)\\}`))?.[1] ?? ''

  it('hangt de uitleg buiten de scrollbox, op zijn plek onder het getal', () => {
    expect(regel('.tabel-scroll .citatie')).toMatch(/position:\s*static\s*;/)
    const uitleg = regel('.tabel-scroll .citatie-uitleg')
    expect(uitleg).toMatch(/top:\s*auto\s*;/)
    expect(uitleg).toMatch(/left:\s*auto\s*;/)
    expect(uitleg).toMatch(/translate:\s*calc\(-1 \* var\(--tabel-scroll-x, 0px\)\) calc\(-1 \* var\(--tabel-scroll-y, 0px\)\)/)
  })

  it('geeft de scrollpositie van de tabel door, zodat de uitleg meeschuift', () => {
    const wrap = render(antwoord).querySelector('.tabel-scroll')
    Object.defineProperty(wrap, 'scrollLeft', { configurable: true, value: 60 })
    Object.defineProperty(wrap, 'scrollTop', { configurable: true, value: 3 })
    act(() => { wrap.dispatchEvent(new Event('scroll')) })
    expect(wrap.style.getPropertyValue('--tabel-scroll-x')).toBe('60px')
    expect(wrap.style.getPropertyValue('--tabel-scroll-y')).toBe('3px')
  })
})
