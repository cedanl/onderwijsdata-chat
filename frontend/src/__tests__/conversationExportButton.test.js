// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ConversationExport from '../components/ConversationExport'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const GESPREK = [
  { role: 'user', content: 'Hoeveel studenten?' },
  { role: 'assistant', content: 'Veel.', done: true, tools: [{ name: 'query_data', label: 'Data gefilterd', done: true, snippet: 'df.head()' }] },
]

describe('ConversationExport (#366)', () => {
  let root
  let container

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  function render(save) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    act(() => root.render(createElement(ConversationExport, { messages: GESPREK, save })))
  }

  const knop = tekst => [...container.querySelectorAll('button')].find(b => b.textContent.includes(tekst))

  it('opent een dialoog met de keuzes en bewaart een markdownbestand', async () => {
    const save = vi.fn()
    render(save)
    act(() => knop('Exporteer gesprek').click())
    const dialoog = container.querySelector('[role="dialog"]')
    const [snippets, fouten] = dialoog.querySelectorAll('input[type="checkbox"]')
    expect(snippets.checked).toBe(true)
    expect(fouten.checked).toBe(false)

    act(() => knop('Download').click())
    const [blob, naam] = save.mock.calls[0]
    expect(naam).toBe('Hoeveel_studenten_.md')
    expect(await blob.text()).toContain('```python\ndf.head()\n```')
    expect(container.querySelector('[role="dialog"]')).toBeNull()
  })

  it('laat de snippets weg als je dat uitvinkt', async () => {
    const save = vi.fn()
    render(save)
    act(() => knop('Exporteer gesprek').click())
    act(() => container.querySelector('input[type="checkbox"]').click())
    act(() => knop('Download').click())
    expect(await save.mock.calls[0][0].text()).not.toContain('```python')
  })
})
