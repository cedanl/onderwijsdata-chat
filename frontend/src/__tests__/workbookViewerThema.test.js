// @vitest-environment jsdom
// #568: the report frame follows the app's theme choice; 'system' leaves the OS preference in charge.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('../components/GeneratedDashboard', () => ({ default: () => null }))
vi.mock('../components/InlineDashboards', () => ({
  InlineDashboardMijnInstelling: () => null, InlineDashboardArbeidsmarkt: () => null, InlineDashboardNationaal: () => null,
}))

import WorkbookViewer from '../components/WorkbookViewer'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const RAPPORT = {
  id: 'wb-1', type: 'report', title: 'Instroom hbo',
  htmlContent: '<!DOCTYPE html><html lang="nl"><head></head><body><p>rapport</p></body></html>',
}

let root
let container

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  container = null
  root = null
})

async function render(props) {
  if (!container) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  }
  await act(async () => {
    root.render(createElement(WorkbookViewer, { workbook: RAPPORT, onBack: vi.fn(), onUpdate: vi.fn(), ...props }))
  })
}

const srcdoc = () => container.querySelector('iframe.wb-iframe').getAttribute('srcdoc')

describe('report frame and the app theme (#568)', () => {
  it.each([['dark'], ['light']])('zet de app-keuze %s als klasse op <html> in het frame', async mode => {
    await render({ mode })
    expect(srcdoc()).toContain(`<html lang="nl" class="${mode}">`)
    expect(srcdoc()).toContain('<p>rapport</p>')
  })

  it.each([['system'], [undefined]])('laat <html> zonder klasse bij modus %j', async mode => {
    await render({ mode })
    expect(srcdoc()).toContain('<html lang="nl"><head>')
    expect(srcdoc()).not.toContain('class="')
  })

  it('volgt een gewijzigde keuze zonder het rapport te verliezen', async () => {
    await render({ mode: 'light' })
    expect(srcdoc()).toContain('class="light"')
    await render({ mode: 'dark' })
    expect(srcdoc()).toContain('class="dark"')
    expect(srcdoc()).not.toContain('light')
    await render({ mode: 'system' })
    expect(srcdoc()).not.toContain('class="')
  })
})
