// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'
import ChatInputFooter from '../components/ChatInputFooter'
import { MAX_MESSAGE_CHARS } from '../constants'

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

describe('ChatInputFooter tekenteller (#481)', () => {
  const props = text => ({
    connected: true,
    busy: false,
    models,
    selectedModel: 'openai/gpt-oss-120b',
    onModelChange: vi.fn(),
    onStop: vi.fn(),
    onSend: vi.fn(),
    canSend: true,
    text,
  })
  const counter = container => container.querySelector('.message-counter')

  it('blijft verborgen onder 80% van het maximum', () => {
    const { container, root } = renderFooter(props('x'.repeat(Math.ceil(MAX_MESSAGE_CHARS * 0.8) - 1)))
    expect(counter(container)).toBeNull()
    act(() => root.unmount())
  })

  it('toont vanaf 80% "n / max", beleefd aangekondigd', () => {
    const n = Math.ceil(MAX_MESSAGE_CHARS * 0.8)
    const { container, root } = renderFooter(props('x'.repeat(n)))
    const el = counter(container)
    expect(el.textContent).toContain(`${n} / ${MAX_MESSAGE_CHARS}`)
    expect(el.getAttribute('role')).toBe('status')
    expect(el.getAttribute('aria-live')).toBe('polite')
    expect(el.classList.contains('message-counter--limit')).toBe(false)
    act(() => root.unmount())
  })

  it('krijgt de waarschuwingsstijl op de grens', () => {
    const { container, root } = renderFooter(props('x'.repeat(MAX_MESSAGE_CHARS)))
    const el = counter(container)
    expect(el.classList.contains('message-counter--limit')).toBe(true)
    expect(el.classList.contains('message-counter--over')).toBe(false)
    act(() => root.unmount())
  })

  it('toont een te lange tekst als te lang', () => {
    const { container, root } = renderFooter(props('x'.repeat(MAX_MESSAGE_CHARS + 5)))
    const el = counter(container)
    expect(el.classList.contains('message-counter--over')).toBe(true)
    expect(el.textContent).toContain(`${MAX_MESSAGE_CHARS + 5} / ${MAX_MESSAGE_CHARS}`)
    expect(el.textContent).toMatch(/te lang/i)
    act(() => root.unmount())
  })

  it('houdt de verzendknop vóór de modelpicker in de tab-volgorde', () => {
    const { container, root } = renderFooter(props('x'.repeat(MAX_MESSAGE_CHARS)))
    expect(focusableOrder(container)).toEqual(['Verstuur bericht', 'Model'])
    act(() => root.unmount())
  })
})
