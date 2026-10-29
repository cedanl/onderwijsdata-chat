// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import FeedbackModal from '../components/FeedbackModal'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const QUESTIONS = [
  { id: 'nuttig', section: 'Over dit rapport', text: 'Hoe nuttig was dit rapport voor je?', type: 'scale', options: ['1', '2', '3', '4', '5'], labels: ['Niet', 'Zeer'] },
  { id: 'mist', text: 'Mist er iets in dit rapport?', type: 'text' },
  { id: 'dashboardtool', text: 'Welke dashboardtool gebruiken jullie?', type: 'multi', extra: true, section: 'Over jouw instelling', options: ['Power BI', 'Tableau', 'Anders', 'Weet ik niet'] },
  { id: 'contact', text: 'Wil je contactgegevens achter laten?', type: 'text', extra: true },
]
const WORKBOOK = { id: 'wb-1', type: 'report', title: 'Instroom hbo' }

let root
let container

function jsonResponse(status, body) {
  return { ok: status < 400, status, json: async () => body }
}

async function render(props = {}) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root.render(createElement(FeedbackModal, { workbook: WORKBOOK, onClose: vi.fn(), onSubmitted: vi.fn(), ...props }))
  })
}

const submitButton = () => container.querySelector('button[type="submit"]')
// The button that reveals the questions about the institution (#666).
const extraButton = () => [...container.querySelectorAll('button')].find(b => b.textContent.startsWith('Help ons verder'))
const headings = () => [...container.querySelectorAll('h3')].map(h => h.textContent)
const typeText = async (field, text) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(field.constructor.prototype, 'value').set.call(field, text)
    field.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

async function revealExtra() {
  await act(async () => { extraButton().click() })
}

async function submit() {
  await act(async () => { container.querySelector('form').requestSubmit() })
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

describe('FeedbackModal', () => {
  it('shows the questions from the backend and only submits once something is answered', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
    vi.stubGlobal('fetch', fetch)
    await render()
    expect(container.textContent).toContain('Hoe nuttig was dit rapport voor je?')
    expect(container.querySelector('textarea')).not.toBeNull()
    expect(submitButton().disabled).toBe(true)
  })

  it('says what is kept, for how long (#485), and that deleting the conversation does not remove it (#552)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
    await render()
    const intro = [...container.querySelectorAll('[role="dialog"] .feedback-intro')].map(p => p.textContent)
    expect(intro[0]).toBe('Alle vragen zijn optioneel. Je antwoorden helpen ons de rapporten te verbeteren.')
    expect(intro[1]).toBe(
      'We bewaren je antwoorden en de titel van het rapport bij je account, 90 dagen lang. Het gesprek verwijderen wist deze feedback niet.',
    )
  })

  it('names a dashboard a dashboard in the questions, the sections and the intro (#795)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
    await render({ workbook: { ...WORKBOOK, type: 'dashboard' } })
    await revealExtra()
    expect(container.textContent).toContain('Hoe nuttig was dit dashboard voor je?')
    expect(container.textContent).toContain('Mist er iets in dit dashboard?')
    expect(headings()).toEqual(['Over dit dashboard', 'Over jouw instelling'])
    const intro = [...container.querySelectorAll('[role="dialog"] .feedback-intro')].map(p => p.textContent)
    expect(intro[0]).toBe('Alle vragen zijn optioneel. Je antwoorden helpen ons de dashboards te verbeteren.')
    expect(intro[1]).toBe(
      'We bewaren je antwoorden en de titel van het dashboard bij je account, 90 dagen lang. Het gesprek verwijderen wist deze feedback niet.',
    )
    expect(intro[2]).toContain('Na de vragen over het dashboard kun je')
    expect(container.textContent).not.toContain('rapport')
  })

  it('posts the answers with the report context and reports success', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetch)
    const onSubmitted = vi.fn()
    await render({ onSubmitted })

    await act(async () => { container.querySelector('input[value="4"]').click() })
    expect(submitButton().disabled).toBe(false)
    await submit()

    const [url, options] = fetch.mock.calls[1]
    expect(url).toBe('/api/feedback')
    expect(JSON.parse(options.body)).toEqual({
      workbook_id: 'wb-1', report_type: 'report', report_title: 'Instroom hbo', instelling: '', answers: { nuttig: '4' },
    })
    expect(onSubmitted).toHaveBeenCalledOnce()
  })

  it('shows the backend message when sending fails and stays open', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
      .mockResolvedValueOnce(jsonResponse(429, { detail: 'Je hebt net al feedback op dit rapport gegeven.' }))
    vi.stubGlobal('fetch', fetch)
    const onSubmitted = vi.fn()
    await render({ onSubmitted })

    await act(async () => { container.querySelector('input[value="2"]').click() })
    await submit()

    expect(container.querySelector('[role="alert"]').textContent).toContain('Je hebt net al feedback op dit rapport gegeven.')
    expect(onSubmitted).not.toHaveBeenCalled()
    expect(submitButton().disabled).toBe(false)
  })

  it('shows the heading of a section above its first question', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
    await render()
    await revealExtra()
    expect(headings()).toEqual(['Over dit rapport', 'Over jouw instelling'])
  })

  it('names the chosen instelling in the section heading, says it is kept, and posts it along', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetch)
    await render({ instelling: '  Hogeschool Utrecht ' })

    expect(extraButton().textContent).toBe('Help ons verder: vragen over Hogeschool Utrecht (2 vragen)')
    await revealExtra()
    expect(headings()).toEqual(['Over dit rapport', 'Over Hogeschool Utrecht'])
    const intro = [...container.querySelectorAll('[role="dialog"] .feedback-intro')].map(p => p.textContent)
    expect(intro[1]).toBe(
      'We bewaren je antwoorden, de titel van het rapport en je gekozen instelling bij je account, 90 dagen lang. Het gesprek verwijderen wist deze feedback niet.',
    )
    await act(async () => { container.querySelector('input[value="4"]').click() })
    await submit()
    expect(JSON.parse(fetch.mock.calls[1][1].body).instelling).toBe('Hogeschool Utrecht')
  })

  it.each([undefined, null, '', '   '])('keeps the generic heading when no instelling is chosen (%j)', async instelling => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
    await render({ instelling })
    expect(extraButton().textContent).toBe('Help ons verder: vragen over jouw instelling (2 vragen)')
    await revealExtra()
    expect(headings()).toEqual(['Over dit rapport', 'Over jouw instelling'])
  })

  it('leaves a section heading without the placeholder phrase alone', async () => {
    const vragen = [{ ...QUESTIONS[2], section: 'Over het onderzoek' }]
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, vragen)))
    await render({ instelling: 'HAN' })
    await revealExtra()
    expect(headings()).toEqual(['Over het onderzoek'])
  })

  // #665: a long form on a phone says how much there is per section and how far you are.
  describe('progress per section', () => {
    const progress = () => [...container.querySelectorAll('.feedback-voortgang')].map(p => p.textContent)

    it('shows under each heading how many questions it has and how many have an answer', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
      await render()
      expect(progress()).toEqual(['0 van 2 vragen beantwoord'])
      await act(async () => { container.querySelector('input[value="4"]').click() })
      expect(progress()).toEqual(['1 van 2 vragen beantwoord'])
      await typeText(container.querySelector('textarea'), 'meer duiding')
      expect(progress()).toEqual(['2 van 2 vragen beantwoord'])
      await typeText(container.querySelector('textarea'), '   ')
      expect(progress()).toEqual(['1 van 2 vragen beantwoord'])
    })

    it('counts the questions about the institution on their own, once they are shown', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
      await render()
      await revealExtra()
      expect(progress()).toEqual(['0 van 2 vragen beantwoord', '0 van 2 vragen beantwoord'])
      await act(async () => { container.querySelector('input[type="checkbox"][value="Power BI"]').click() })
      expect(progress()).toEqual(['0 van 2 vragen beantwoord', '1 van 2 vragen beantwoord'])
    })

    it('names a single question in the singular, and shows nothing without a section heading', async () => {
      const een = [{ ...QUESTIONS[1], section: 'Over dit rapport' }]
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, een)))
      await render()
      expect(progress()).toEqual(['0 van 1 vraag beantwoord'])
      act(() => root.unmount())
      container.remove()
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, [{ ...QUESTIONS[1] }])))
      await render()
      expect(progress()).toEqual([])
    })
  })

  it('lets a multi question take several options, with free text behind Anders', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
    vi.stubGlobal('fetch', fetch)
    await render()
    await revealExtra()

    const box = value => container.querySelector(`input[type="checkbox"][value="${value}"]`)
    expect(container.querySelector('input[aria-label="Anders, welke?"]')).toBeNull()
    await act(async () => { box('Power BI').click() })
    await act(async () => { box('Tableau').click() })
    await act(async () => { box('Tableau').click() })
    await act(async () => { box('Anders').click() })
    await typeText(container.querySelector('input[aria-label="Anders, welke?"]'), 'Metabase')
    expect(submitButton().disabled).toBe(false)
    await submit()

    expect(JSON.parse(fetch.mock.calls[1][1].body).answers).toEqual({ dashboardtool: ['Power BI', 'Anders: Metabase'] })
  })

  it('does not count a multi question without a choice as an answer', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
    await render()
    await revealExtra()
    const box = container.querySelector('input[type="checkbox"][value="Power BI"]')
    await act(async () => { box.click() })
    expect(submitButton().disabled).toBe(false)
    await act(async () => { box.click() })
    expect(submitButton().disabled).toBe(true)
  })

  // #666: the questions about the institution come only after an explicit choice, below the report questions.
  describe('questions about the institution', () => {
    it('are hidden on opening, behind a button that does not submit the form', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
      await render()
      expect(container.textContent).toContain('Hoe nuttig was dit rapport voor je?')
      expect(container.textContent).toContain('Mist er iets in dit rapport?')
      expect(container.textContent).not.toContain('Welke dashboardtool gebruiken jullie?')
      expect(container.textContent).not.toContain('Wil je contactgegevens achter laten?')
      expect(headings()).toEqual(['Over dit rapport'])
      expect(extraButton().getAttribute('type')).toBe('button')
      // The button comes after the report questions and before the form buttons.
      const order = [...container.querySelectorAll('textarea, button')]
      expect(order.indexOf(extraButton())).toBe(order.indexOf(container.querySelector('textarea')) + 1)
    })

    it('says in the intro that they are optional and come only after the choice', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
      await render()
      const intro = [...container.querySelectorAll('[role="dialog"] .feedback-intro')].map(p => p.textContent)
      expect(intro[2]).toBe(
        'Na de vragen over het rapport kun je ervoor kiezen ook vragen over je instelling te beantwoorden. Ook die zijn optioneel; we bewaren die antwoorden op dezelfde manier.',
      )
    })

    it('leave the button out, and the intro line about them, when the backend flags none', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS.filter(q => !q.extra))))
      await render()
      expect(extraButton()).toBeUndefined()
      expect(container.querySelectorAll('[role="dialog"] .feedback-intro')).toHaveLength(2)
    })

    it('lets a report answer be sent without ever opening them', async () => {
      const fetch = vi.fn()
        .mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
        .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
      vi.stubGlobal('fetch', fetch)
      const onSubmitted = vi.fn()
      await render({ onSubmitted })

      await act(async () => { container.querySelector('input[value="3"]').click() })
      await submit()

      expect(JSON.parse(fetch.mock.calls[1][1].body).answers).toEqual({ nuttig: '3' })
      expect(onSubmitted).toHaveBeenCalledOnce()
    })

    it('appear with their heading after the choice, replace the button and are posted along', async () => {
      const fetch = vi.fn()
        .mockResolvedValueOnce(jsonResponse(200, QUESTIONS))
        .mockResolvedValueOnce(jsonResponse(200, { ok: true }))
      vi.stubGlobal('fetch', fetch)
      await render()

      await act(async () => { container.querySelector('input[value="5"]').click() })
      await revealExtra()
      expect(extraButton()).toBeUndefined()
      expect(headings()).toEqual(['Over dit rapport', 'Over jouw instelling'])
      expect(container.textContent).toContain('Welke dashboardtool gebruiken jullie?')
      expect(container.textContent).toContain('Wil je contactgegevens achter laten?')
      // The report answer given before the choice is kept.
      expect(container.querySelector('input[value="5"]').checked).toBe(true)

      await act(async () => { container.querySelector('input[type="checkbox"][value="Tableau"]').click() })
      const textareas = container.querySelectorAll('textarea')
      await typeText(textareas[textareas.length - 1], 'ik@example.org')
      await submit()

      expect(JSON.parse(fetch.mock.calls[1][1].body).answers).toEqual({
        nuttig: '5', dashboardtool: ['Tableau'], contact: 'ik@example.org',
      })
    })

    it('move focus to their heading, since the button that had it is gone', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
      await render()
      extraButton().focus()
      await revealExtra()
      expect(document.activeElement).toBe([...container.querySelectorAll('h3')].at(-1))
    })

    it('enable sending with only one of them answered', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(200, QUESTIONS)))
      await render()
      await revealExtra()
      expect(submitButton().disabled).toBe(true)
      await act(async () => { container.querySelector('input[type="checkbox"][value="Power BI"]').click() })
      expect(submitButton().disabled).toBe(false)
    })
  })
})
