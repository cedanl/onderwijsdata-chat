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

  // #1247: Markdown of Jupyter-notebook, standaard Markdown.
  const radio = tekst => [...container.querySelectorAll('input[type="radio"]')].find(r => r.closest('label').textContent.trim() === tekst)

  it('biedt Markdown en Jupyter-notebook als gelabelde keuze, standaard Markdown', () => {
    render(vi.fn())
    act(() => knop('Exporteer gesprek').click())
    const groep = container.querySelector('fieldset')
    expect(groep.querySelector('legend').textContent).toBe('Formaat')
    expect(radio('Markdown').checked).toBe(true)
    expect(radio('Jupyter-notebook (.ipynb)').checked).toBe(false)
    expect(radio('Markdown').name).toBe(radio('Jupyter-notebook (.ipynb)').name)
    expect(container.querySelector('.confirm-message').textContent).toBe('Exporteer dit gesprek als bestand')
  })

  it('bewaart met de notebookkeuze een .ipynb met de code als cel', async () => {
    const save = vi.fn()
    render(save)
    act(() => knop('Exporteer gesprek').click())
    act(() => radio('Jupyter-notebook (.ipynb)').click())
    const [snippets] = container.querySelectorAll('input[type="checkbox"]')
    expect(snippets.disabled).toBe(true)
    expect(snippets.checked).toBe(true)

    act(() => knop('Download').click())
    const [blob, naam] = save.mock.calls[0]
    expect(naam).toBe('Hoeveel_studenten_.ipynb')
    expect(blob.type).toBe('application/x-ipynb+json')
    const notebook = JSON.parse(await blob.text())
    expect(notebook.nbformat).toBe(4)
    expect(notebook.metadata.kernelspec.name).toBe('python3')
    expect(notebook.cells.filter(c => c.cell_type === 'code').map(c => c.source.join(''))).toEqual(['# Stap 1: Data gefilterd\ndf.head()'])
    expect(container.querySelector('[role="dialog"]')).toBeNull()
  })

  it('houdt de codekeuze van Markdown vast als je terugschakelt', async () => {
    const save = vi.fn()
    render(save)
    act(() => knop('Exporteer gesprek').click())
    act(() => container.querySelector('input[type="checkbox"]').click())
    act(() => radio('Jupyter-notebook (.ipynb)').click())
    act(() => radio('Markdown').click())
    expect(container.querySelector('input[type="checkbox"]').checked).toBe(false)
    act(() => knop('Download').click())
    expect(save.mock.calls[0][1]).toBe('Hoeveel_studenten_.md')
    expect(await save.mock.calls[0][0].text()).not.toContain('```python')
  })
})
