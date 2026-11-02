// @vitest-environment jsdom
// #835: de privacy- en feedbackteksten noemen de termijnen die de backend toepast (via /api/config), niet vaste
// getallen. Zonder /api/config of bij een ontbrekende waarde blijven de backenddefaults staan.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../api', () => ({ postAlgemeneFeedback: vi.fn() }))

import PrivacyInhoud from '../components/PrivacyInhoud'
import AlgemeneFeedbackModal from '../components/AlgemeneFeedbackModal'
import { zetTermijnen, STANDAARD_TERMIJNEN } from '../termijnen'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

async function render(element) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => { root.render(element) })
}

const tekst = () => document.body.textContent.replace(/\s+/g, ' ')

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  zetTermijnen({})
})

describe('termijnen in de teksten (#835)', () => {
  it('noemt zonder /api/config de standaardtermijnen', async () => {
    await render(createElement(PrivacyInhoud))
    expect(STANDAARD_TERMIJNEN).toEqual({ gesprekkenDagen: 90, rapportenDagen: 365, sessieUren: 8, sessieMaxUren: 24 })
    expect(tekst()).toContain('tot 90 dagen na je laatste bericht')
    expect(tekst()).toContain('dat je 365 dagen niet hebt geopend')
    expect(tekst()).toContain('Een sessie duurt 8 uur en wordt bij gebruik verlengd tot ten hoogste 24 uur')
  })

  it('volgt de termijnen uit /api/config in de privacytekst', async () => {
    zetTermijnen({ bewaartermijn_gesprekken_dagen: 30, bewaartermijn_rapporten_dagen: 180, sessie_uren: 2, sessie_max_uren: 12.5 })
    await render(createElement(PrivacyInhoud))
    const t = tekst()
    expect(t).toContain('tot 30 dagen na je laatste bericht')
    expect(t).toContain('dat je 180 dagen niet hebt geopend')
    expect(t).toContain('Feedback wordt 30 dagen nadat je hem gaf verwijderd')
    expect(t).toContain('je gesprekken 30 dagen na je laatste bericht erin, je feedback 30 dagen nadat je hem gaf')
    expect(t).toContain('rapporten en dashboards 180 dagen nadat')
    expect(t).toContain('Een sessie duurt 2 uur en wordt bij gebruik verlengd tot ten hoogste 12,5 uur')
    expect(t).toContain('(ten hoogste 12,5 uur)')
    expect(t).not.toMatch(/\b(90|365) dagen|\b(8|24) uur/)
  })

  it('volgt de termijn in de algemene feedback, en een ontbrekende waarde houdt de standaard', async () => {
    zetTermijnen({ bewaartermijn_gesprekken_dagen: 45, bewaartermijn_rapporten_dagen: null })
    await render(createElement(AlgemeneFeedbackModal, { onClose: vi.fn() }))
    expect(tekst()).toContain('en bewaart het 45 dagen.')
    act(() => root.unmount())
    container.remove()
    await render(createElement(PrivacyInhoud))
    expect(tekst()).toContain('dat je 365 dagen niet hebt geopend')
  })
})
