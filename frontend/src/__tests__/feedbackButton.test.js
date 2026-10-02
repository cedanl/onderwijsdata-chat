// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

// Dashboards pull in Plotly, which jsdom cannot load; this test is about the bar only.
vi.mock('../components/GeneratedDashboard', () => ({ default: () => null }))
vi.mock('../components/InlineDashboards', () => ({
  InlineDashboardMijnInstelling: () => null, InlineDashboardArbeidsmarkt: () => null, InlineDashboardNationaal: () => null,
}))
vi.mock('../components/FeedbackModal', () => ({
  default: ({ onSubmitted }) => createElement('button', { className: 'fake-submit', onClick: onSubmitted }, 'verstuur'),
}))

import WorkbookViewer from '../components/WorkbookViewer'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const WORKBOOK = { id: 'wb-1', type: 'report', title: 'Instroom hbo', htmlContent: '<p>rapport</p>' }

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
    root.render(createElement(WorkbookViewer, {
      workbook: WORKBOOK, onBack: vi.fn(), onUpdate: vi.fn(), feedbackEnabled: true, ...props,
    }))
  })
}

const feedbackButton = () => container.querySelector('.wb-feedback-btn')
const givenBadge = () => container.querySelector('.wb-feedback-given')

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

describe('feedback button in the report viewer', () => {
  it('offers feedback on a report the user has not rated yet', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, ['wb-other'])))
    await render()
    expect(feedbackButton().textContent).toContain('Geef feedback')
    expect(givenBadge()).toBeNull()
  })

  it('shows that feedback was already given on this report', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, ['wb-1'])))
    await render()
    expect(feedbackButton()).toBeNull()
    expect(givenBadge().textContent).toContain('Feedback gegeven')
  })

  it('switches to given right after sending', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, [])))
    await render()
    await act(async () => { feedbackButton().click() })
    await act(async () => { container.querySelector('.fake-submit').click() })
    expect(feedbackButton()).toBeNull()
    expect(givenBadge()).not.toBeNull()
  })

  it('keeps the button when the status cannot be loaded', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(500, {})))
    await render()
    expect(feedbackButton()).not.toBeNull()
  })

  it('does not ask for the status when feedback is off', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    await render({ feedbackEnabled: false })
    expect(fetch).not.toHaveBeenCalled()
    expect(feedbackButton()).toBeNull()
  })
})
