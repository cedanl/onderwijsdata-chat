// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import WorkbookDownload from '../components/WorkbookDownload'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

describe('WorkbookDownload (#254)', () => {
  let root
  let container

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  function render(workbook, save = vi.fn()) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    act(() => root.render(createElement(WorkbookDownload, { workbook, save })))
    return container.querySelector('button')
  }

  it('downloadt een rapport als zelfstandig HTML-bestand', async () => {
    const save = vi.fn()
    const knop = render({ id: 'r', title: 'Instroom hbo', htmlContent: '<html>rapport</html>' }, save)
    expect(knop.textContent).toBe('Download als HTML')
    await act(async () => knop.click())
    const [blob, naam] = save.mock.calls[0]
    expect(naam).toBe('Instroom_hbo.html')
    expect(blob.type).toBe('text/html;charset=utf-8')
    expect(await blob.text()).toBe('<html>rapport</html>')
  })

  it('heeft geen knop bij een ingebouwd dashboard', () => {
    expect(render({ id: 'b', title: 'Mijn instelling', builtin: true })).toBeNull()
  })
})
