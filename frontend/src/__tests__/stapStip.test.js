// @vitest-environment jsdom
// #640 review: the rule for the text of a reasoning step (`.reasoning-step > div { flex: 1 }`, #595) also matched
// the status dot, a <div> as well, and stretched it into a bar. jsdom does no layout, so this test pins the cascade:
// no rule that reaches the dot may grow it; the browser measurement (6 x 6 px) is in the commit message.
import { describe, it, expect, beforeAll, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import ReasoningStep from '../components/ReasoningStep'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const GROEI = ['flex', 'flex-grow', 'min-width']

let container, root

beforeAll(() => {
  const style = document.createElement('style')
  style.textContent = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')
  document.head.appendChild(style)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

function render(children) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  const tool = { name: 'query_cbs', label: 'CBS-data ophalen', done: true, status: 'ok' }
  act(() => root.render(createElement(ReasoningStep, { tool }, children)))
  return container.querySelector('.reasoning-step')
}

// Every style rule (also inside @media) whose selector matches the element; a selector jsdom cannot parse is skipped.
function regelsVoor(el) {
  const regels = []
  const loop = lijst => {
    for (const regel of lijst) {
      if (regel.cssRules) loop(regel.cssRules)
      if (!regel.selectorText) continue
      let raak = false
      try {
        raak = el.matches(regel.selectorText)
      } catch {
        raak = false
      }
      if (raak) regels.push(regel)
    }
  }
  for (const blad of document.styleSheets) loop(blad.cssRules)
  return regels
}

const zet = (regels, eigenschap) => regels.filter(r => r.style.getPropertyValue(eigenschap) !== '')

describe.each([
  ['zonder code', null],
  ['met code', createElement('details', { className: 'reasoning-step-code' }, createElement('summary', null, 'Bekijk code'))],
])('stip van een afgeronde stap %s (#640)', (_naam, children) => {
  it('geen regel die de stip raakt laat hem groeien', () => {
    const stap = render(children)
    const stip = stap.querySelector('.reasoning-step-dot')
    const regels = regelsVoor(stip)

    expect(regels.some(r => r.selectorText.includes('.reasoning-step-dot'))).toBe(true)
    for (const eigenschap of GROEI) {
      expect(zet(regels, eigenschap).map(r => r.selectorText), eigenschap).toEqual([])
    }
  })

  it('de tekst van de stap vult nog steeds de rest van de regel', () => {
    const stap = render(children)
    const tekst = stap.querySelector('.reasoning-step-dot').nextElementSibling
    const flex = zet(regelsVoor(tekst), 'flex')

    expect(flex.length).toBeGreaterThan(0)
    expect(flex.at(-1).style.getPropertyValue('flex')).toMatch(/^1( |$)/)
  })
})
