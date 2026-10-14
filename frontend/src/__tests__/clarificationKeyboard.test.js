// @vitest-environment jsdom
// #541: the options of a clarification card, found the way a screen reader and a keyboard user meet
// them: by role and accessible name, in tab order, with Enter and Space left to the browser.
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { FakeWebSocket } from './fakeWebSocket'
import ClarificationButtons from '../components/ClarificationButtons'

vi.mock('../api', async importOriginal => ({
  ...await importOriginal(),
  fetchWorkbooks: vi.fn().mockResolvedValue([]),
  putWorkbook: vi.fn().mockResolvedValue({}),
  deleteWorkbookApi: vi.fn().mockResolvedValue({}),
  fetchConversations: vi.fn().mockResolvedValue([]),
  putConversation: vi.fn().mockResolvedValue({}),
  renameConversationApi: vi.fn().mockResolvedValue({}),
  deleteConversationApi: vi.fn().mockResolvedValue({}),
  fetchSettingsConfig: vi.fn().mockResolvedValue({}),
}))
vi.mock('react-plotly.js', () => ({ default: function PlotStub() { return null } }))

import ChatPage from '../pages/ChatPage'

globalThis.IS_REACT_ACT_ENVIRONMENT = true
globalThis.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} }
window.matchMedia ??= q => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })

const VRAAG = 'Hoeveel studenten zitten er in het hbo?'
const TELLING = {
  type: 'clarification',
  vraag: 'Welke telling van studenten bedoel je?',
  opties: [
    { label: 'Ingeschrevenen', beschrijving: 'iedereen met een inschrijving op 1 oktober' },
    { label: 'Eerstejaars', beschrijving: 'nieuw in het hoger onderwijs' },
    'Gediplomeerden',
  ],
}
const LABELS = ['Ingeschrevenen', 'Eerstejaars', 'Gediplomeerden']
const NAMEN = [
  'Ingeschrevenen — iedereen met een inschrijving op 1 oktober',
  'Eerstejaars — nieuw in het hoger onderwijs',
  'Gediplomeerden',
]
const ANDERS = 'Anders formuleren: zet je oorspronkelijke vraag terug in het invoerveld'

// Role and accessible name, the small part of what a screen reader computes that these elements
// need: jsdom has no accessibility tree and the repo has no testing-library. The role comes from
// the `role` attribute, else from the tag; the name from aria-label, else from the text.
const IMPLICIT_ROLES = { BUTTON: 'button' }
const roleOf = el => el.getAttribute('role') ?? IMPLICIT_ROLES[el.tagName] ?? null
const nameOf = el => (el.getAttribute('aria-label') ?? el.textContent).replace(/\s+/g, ' ').trim()
const allByRole = (scope, role, name) =>
  [...scope.querySelectorAll('*')].filter(el => roleOf(el) === role && (name === undefined || nameOf(el) === name))

function getByRole(scope, role, name) {
  const found = allByRole(scope, role, name)
  expect(found, `exactly one ${role} named "${name}"`).toHaveLength(1)
  return found[0]
}

const FOCUSABLE = 'a[href], button, input, select, textarea, [tabindex]'
const focusables = scope => [...scope.querySelectorAll(FOCUSABLE)]

let root
let container

function mount() {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
}

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('ClarificationButtons by role and name (#541)', () => {
  function render(props) {
    mount()
    act(() => root.render(createElement(ClarificationButtons, {
      options: TELLING.opties, onSelect: () => {}, busy: false, answer: { answered: false, choice: null }, ...props,
    })))
  }

  it.each(LABELS.map((label, i) => [NAMEN[i], label]))('finds "%s" and chooses "%s" once', (naam, label) => {
    const onSelect = vi.fn()
    render({ onSelect })
    const optie = getByRole(container, 'button', naam)

    act(() => optie.click())
    act(() => optie.click())

    expect(onSelect).toHaveBeenCalledOnce()
    expect(onSelect).toHaveBeenCalledWith(label)
  })

  it('groups exactly the options under the question; "Anders formuleren" stays outside', () => {
    render({ vraag: TELLING.vraag, onAndersFormuleren: vi.fn() })
    const groep = getByRole(container, 'group', TELLING.vraag)

    expect(allByRole(groep, 'button').map(nameOf)).toEqual(NAMEN)
    expect(groep.contains(getByRole(container, 'button', ANDERS))).toBe(false)
  })

  it.each([['without a question', {}], ['with an empty question', { vraag: '' }]])(
    'names the group "Kies een optie" %s', (_, props) => {
      render(props)
      expect(allByRole(getByRole(container, 'group', 'Kies een optie'), 'button')).toHaveLength(3)
    })

  it('puts the options in tab order as given, then "Anders formuleren" last', () => {
    render({ vraag: TELLING.vraag, onAndersFormuleren: vi.fn() })
    const opties = NAMEN.map(naam => getByRole(container, 'button', naam))
    const anders = getByRole(container, 'button', ANDERS)

    expect(focusables(container)).toEqual([...opties, anders])
    expect(focusables(container).every(el => el.tabIndex >= 0)).toBe(true)
    expect(opties.every(el => !el.disabled)).toBe(true)
  })
})

describe('A clarification card on the chat page, by role and name (#541)', () => {
  beforeEach(() => {
    localStorage.clear()
    FakeWebSocket.reset()
    globalThis.WebSocket = FakeWebSocket
  })

  // The real ChatPage with the real useChat: a question goes out, the server answers with a card.
  async function openCard() {
    mount()
    await act(async () => { root.render(createElement(ChatPage, { settings: {}, user: 'gast' })) })
    const ws = FakeWebSocket.last
    await act(async () => { ws.open() })
    const textarea = container.querySelector('textarea.chat-input')
    const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set
    await act(async () => {
      set.call(textarea, VRAAG)
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => {
      textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    })
    await act(async () => { ws.emit(TELLING) })
    return ws
  }

  const choices = ws => ws.sent.filter(m => m.action === 'clarification_choice')

  it('names the group after the question and sends the option clicked by its name', async () => {
    const ws = await openCard()
    const groep = getByRole(container, 'group', TELLING.vraag)
    expect(allByRole(groep, 'button').map(nameOf)).toEqual(NAMEN)
    expect(groep.contains(getByRole(container, 'button', ANDERS))).toBe(false)

    await act(async () => getByRole(groep, 'button', NAMEN[1]).click())

    expect(choices(ws)).toEqual([{ action: 'clarification_choice', choice: 'Eerstejaars' }])
  })

  it('lets Tab reach the options in order and then "Anders formuleren", the last stop in the card', async () => {
    await openCard()
    const opties = NAMEN.map(naam => getByRole(container, 'button', naam))
    const anders = getByRole(container, 'button', ANDERS)
    const kaart = anders.closest('.message-bubble')
    const inKaart = focusables(kaart)

    // Before the options the bubble only has its copy button.
    expect(inKaart.slice(inKaart.indexOf(opties[0]))).toEqual([...opties, anders])
    expect(inKaart.every(el => el.tabIndex >= 0)).toBe(true)
    expect(opties.every(el => !el.disabled)).toBe(true)
  })

  // jsdom does not turn a key into a click, so this only proves that no handler on the page blocks
  // the native activation of a button. Real Enter and Space are covered by the browser probe of #541.
  it.each([
    ['keydown', 'Enter'],
    ['keydown', ' '],
    ['keyup', ' '],
  ])('leaves %s "%s" on an option to the browser', async (type, key) => {
    await openCard()
    const optie = getByRole(container, 'button', NAMEN[0])
    const event = new KeyboardEvent(type, { key, code: key === ' ' ? 'Space' : key, bubbles: true, cancelable: true })

    await act(async () => { optie.dispatchEvent(event) })

    expect(event.defaultPrevented).toBe(false)
  })

  // By design: the finished card is also announced through the polite live region, so a query by
  // text finds the question twice. Queries above use role and name only.
  it('has the question in the bubble and in the live region', async () => {
    await openCard()
    const exact = [...container.querySelectorAll('*')].filter(el =>
      el.textContent === TELLING.vraag && ![...el.children].some(kind => kind.textContent === TELLING.vraag))

    expect(exact).toHaveLength(2)
    expect(exact[0].matches('.sr-only[aria-live="polite"]')).toBe(true)
    expect(exact[1].closest('.message-bubble')).not.toBeNull()
  })
})
