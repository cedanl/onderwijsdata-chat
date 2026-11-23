// @vitest-environment jsdom
// #1178: role="dialog" stond direct op een <form>, en ARIA in HTML staat die rol daar niet toe (axe aria-allowed-role).
// In de drie dialogen met een formulier draagt een omhullende <div> de rol, aria-modal en aria-labelledby, en staat de
// <form> erin. Focus naar binnen, Escape en focus terug naar de opener blijven werken (useDialog.test.js).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import axe from 'axe-core'
import AlgemeneFeedbackModal from '../components/AlgemeneFeedbackModal'
import FeedbackModal from '../components/FeedbackModal'
import OnderzoeksvraagDialoog from '../components/OnderzoeksvraagDialoog'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

const VOORSTEL = 'Hoeveel studenten stromen in?'
const DIALOGEN = [
  ['AlgemeneFeedbackModal', () => createElement(AlgemeneFeedbackModal, { onClose: vi.fn() })],
  ['FeedbackModal', () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => [] }))
    return createElement(FeedbackModal, { workbook: { id: 'wb-1', type: 'report', title: 'Instroom' }, onClose: vi.fn(), onSubmitted: vi.fn() })
  }],
  ['OnderzoeksvraagDialoog', () => createElement(OnderzoeksvraagDialoog, {
    voorstel: VOORSTEL, max: 500, checklist: null, onGenereer: vi.fn(), onClose: vi.fn(),
  })],
]

describe.each(DIALOGEN)('%s (#1178)', (_naam, maak) => {
  it('draagt role="dialog" op een div met de form erin, niet op de form zelf', async () => {
    await render(maak())
    const dialogen = document.querySelectorAll('[role="dialog"]')
    expect(dialogen).toHaveLength(1)
    const [dialoog] = dialogen
    expect(dialoog.tagName).toBe('DIV')
    expect(dialoog.getAttribute('aria-modal')).toBe('true')
    expect(document.getElementById(dialoog.getAttribute('aria-labelledby'))).not.toBeNull()
    expect(dialoog.querySelector('form')).not.toBeNull()
    expect(document.querySelector('form[role]')).toBeNull()
  })

  it('geeft de focus aan iets in de dialoog', async () => {
    await render(maak())
    const dialoog = document.querySelector('[role="dialog"]')
    expect(dialoog.contains(document.activeElement)).toBe(true)
  })

  it('heeft geen aria-allowed-role-bevinding van axe', async () => {
    await render(maak())
    const { violations } = await axe.run(document.body, { runOnly: ['aria-allowed-role'] })
    expect(violations.map(v => v.id)).toEqual([])
  })
})
