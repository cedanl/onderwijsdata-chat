// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ChatInputFooter from '../components/ChatInputFooter'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const models = [{ id: 'openai/gpt-oss-120b', name: 'GPT-OSS' }]

function renderFooter(props) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => root.render(createElement(ChatInputFooter, props)))
  return { container, root }
}

function focusableOrder(container) {
  return [...container.querySelectorAll('.chat-input-footer button, .chat-input-footer select')]
    .map(el => el.getAttribute('aria-label') || el.title || '')
}

function childOrder(container) {
  return [...container.querySelector('.chat-input-footer').children]
    .map(c => c.className || c.title)
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ChatInputFooter tab-volgorde', () => {
  it('plaatst de verzendknop in DOM-volgorde vóór de modelpicker', () => {
    const { container, root } = renderFooter({
      connected: true,
      busy: false,
      models,
      selectedModel: 'openai/gpt-oss-120b',
      onModelChange: vi.fn(),
      onStop: vi.fn(),
      onSend: vi.fn(),
      canSend: true,
    })
    expect(focusableOrder(container)).toEqual(['Verstuur bericht', 'Model'])
    act(() => root.unmount())
  })

  it('toont eerst de verbindingsstatus, dan verzenden, dan de modelpicker', () => {
    const { container, root } = renderFooter({
      connected: false,
      busy: false,
      models,
      selectedModel: 'openai/gpt-oss-120b',
      onModelChange: vi.fn(),
      onStop: vi.fn(),
      onSend: vi.fn(),
      canSend: true,
    })
    expect(childOrder(container)).toEqual(['ws-reconnecting', 'send-btn', 'model-picker'])
    act(() => root.unmount())
  })

  it('houdt de stopknop in DOM-volgorde vóór de modelpicker', () => {
    const { container, root } = renderFooter({
      connected: true,
      busy: true,
      models,
      selectedModel: 'openai/gpt-oss-120b',
      onModelChange: vi.fn(),
      onStop: vi.fn(),
      onSend: vi.fn(),
      canSend: true,
    })
    expect(focusableOrder(container)).toEqual(['Stop genereren', 'Model'])
    act(() => root.unmount())
  })
})