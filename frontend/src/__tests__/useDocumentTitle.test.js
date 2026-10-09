// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import { useDocumentTitle, pageTitle, APP_NAME } from '../hooks/useDocumentTitle'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

let root
let container

function Probe({ title }) {
  useDocumentTitle(title)
  return null
}

async function render(title) {
  await act(async () => { root.render(createElement(Probe, { title })) })
}

beforeEach(() => {
  document.title = 'vorige'
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

// #491: every route has its own tab title, so tabs and screen readers can tell pages apart.
describe('useDocumentTitle', () => {
  it('sets the document title', async () => {
    await render('Chat — openEDUdata+')
    expect(document.title).toBe('Chat — openEDUdata+')
  })

  it('follows a change of the title', async () => {
    await render('Rapporten — openEDUdata+')
    await render('Instroom hbo — openEDUdata+')
    expect(document.title).toBe('Instroom hbo — openEDUdata+')
  })

  it('leaves the title alone for an empty or non-string value', async () => {
    for (const value of ['', null, undefined, 42]) {
      await render(value)
      expect(document.title).toBe('vorige')
    }
  })

  it('keeps the title after unmount, so the next page does not flash the old one', async () => {
    await render('Chat — openEDUdata+')
    act(() => root.unmount())
    root = createRoot(container)
    expect(document.title).toBe('Chat — openEDUdata+')
  })
})

describe('pageTitle', () => {
  it('ends a page name with the app name after an em dash', () => {
    expect(APP_NAME).toBe('openEDUdata+')
    expect(pageTitle('Rapporten')).toBe('Rapporten — openEDUdata+')
  })
})
