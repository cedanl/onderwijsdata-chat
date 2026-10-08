// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import { SuggestedQuestions } from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function renderIn(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

async function shownQuestions(props) {
  await renderIn(createElement(SuggestedQuestions, { onSend: vi.fn(), busy: false, ...props }))
  for (const btn of container.querySelectorAll('.suggested-category-btn')) await act(async () => btn.click())
  return [...container.querySelectorAll('.suggested-btn')].map(b => b.textContent)
}

// #447: hbo and wo have no student place of residence, so the origin question is mbo-only.
describe('SuggestedQuestions', () => {
  it('shows the origin question to an mbo institution, named', async () => {
    const shown = await shownQuestions({ instelling: 'ROC Midden Nederland', sector: 'mbo' })
    expect(shown.some(q => q.includes('vandaan') && q.includes('ROC Midden Nederland'))).toBe(true)
  })

  it('does not show it to a university of applied sciences', async () => {
    const shown = await shownQuestions({ instelling: 'Hogeschool Utrecht', sector: 'hbo' })
    expect(shown.length).toBeGreaterThan(0)
    expect(shown.filter(q => q.includes('vandaan'))).toEqual([])
  })
})
