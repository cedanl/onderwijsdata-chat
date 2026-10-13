// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createElement, act, useState } from 'react'
import { createRoot } from 'react-dom/client'
import ModelPicker, { modelOptionLabels } from '../components/ModelPicker'
import ChatInputFooter from '../components/ChatInputFooter'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

// Plain labels, provider in a caption (#496, F10).
const FOUNDRY = 'Microsoft Azure AI Foundry'
const SONNET = { id: 'azure_ai/claude-sonnet-5-5', name: 'Sonnet 5.5', description: 'voor de meeste vragen', icon: 'sparkles', provider: FOUNDRY }
const HAIKU = { id: 'anthropic/claude-haiku-4-5-20251001', name: 'Haiku', description: 'snel', icon: 'zap', provider: 'Anthropic' }
const HAIKU_FOUNDRY = { id: 'azure_ai/claude-haiku-4-5', name: 'Haiku', description: 'snel', icon: 'zap', provider: FOUNDRY }

function render(element) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => root.render(element))
  return { container, root }
}

// The parent owns the choice, as ChatPage and DashboardCreator do.
function Controlled({ models, initial, onChange }) {
  const [value, setValue] = useState(initial)
  return createElement(ModelPicker, { models, value, onChange: id => { onChange(id); setValue(id) } })
}

const select = container => container.querySelector('.model-picker select')
const caption = container => container.querySelector('.model-picker .model-picker-provider')
const selectedText = container => select(container).selectedOptions[0].textContent
const optionTexts = container => [...select(container).options].map(o => o.textContent)

function choose(container, id) {
  act(() => {
    select(container).value = id
    select(container).dispatchEvent(new Event('change', { bubbles: true }))
  })
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ModelPicker labels (#496, F10)', () => {
  it('shows "name — description" in a select named Model', () => {
    const { container, root } = render(createElement(ModelPicker, { models: [SONNET], value: SONNET.id, onChange: vi.fn() }))
    expect(select(container).getAttribute('aria-label')).toBe('Model')
    expect(selectedText(container)).toBe('Sonnet 5.5 — voor de meeste vragen')
    act(() => root.unmount())
  })

  it('appends the provider when two models would read the same', () => {
    const models = [SONNET, HAIKU, HAIKU_FOUNDRY]
    const { container, root } = render(createElement(ModelPicker, { models, value: SONNET.id, onChange: vi.fn() }))
    expect(optionTexts(container)).toEqual([
      'Sonnet 5.5 — voor de meeste vragen',
      'Haiku — snel (Anthropic)',
      `Haiku — snel (${FOUNDRY})`,
    ])
    act(() => root.unmount())
  })
})

describe('ModelPicker provider caption (#496, F10)', () => {
  it('names the provider of the selected model and describes the select with it', () => {
    const { container, root } = render(createElement(ModelPicker, { models: [SONNET], value: SONNET.id, onChange: vi.fn() }))
    const el = caption(container)
    expect(el.textContent).toBe(`Via ${FOUNDRY}`)
    expect(el.id).not.toBe('')
    expect(select(container).getAttribute('aria-describedby')).toBe(el.id)
    expect(document.getElementById(el.id)).toBe(el)
    act(() => root.unmount())
  })

  it('follows a change of selection and reports the model id', () => {
    const onChange = vi.fn()
    const models = [HAIKU, HAIKU_FOUNDRY]
    const { container, root } = render(createElement(Controlled, { models, initial: HAIKU.id, onChange }))
    expect(caption(container).textContent).toBe('Via Anthropic')
    choose(container, HAIKU_FOUNDRY.id)
    expect(onChange).toHaveBeenCalledWith(HAIKU_FOUNDRY.id)
    expect(caption(container).textContent).toBe(`Via ${FOUNDRY}`)
    expect(select(container).getAttribute('aria-describedby')).toBe(caption(container).id)
    act(() => root.unmount())
  })

  it('has no caption and no description when the model has no provider', () => {
    const { id, name, description } = SONNET
    for (const model of [{ id, name, description }, { ...SONNET, provider: '' }]) {
      const { container, root } = render(createElement(ModelPicker, { models: [model], value: id, onChange: vi.fn() }))
      expect(caption(container)).toBeNull()
      expect(select(container).hasAttribute('aria-describedby')).toBe(false)
      expect(selectedText(container)).toBe('Sonnet 5.5 — voor de meeste vragen')
      act(() => root.unmount())
    }
  })

  it('has no caption for a value that is not offered', () => {
    const { container, root } = render(createElement(ModelPicker, { models: [SONNET], value: 'ander/model', onChange: vi.fn() }))
    expect(caption(container)).toBeNull()
    act(() => root.unmount())
  })

  it('keeps the picker one footer child after the send button, with the caption inside', () => {
    const { container, root } = render(createElement(ChatInputFooter, {
      connected: true, busy: false, models: [SONNET], selectedModel: SONNET.id,
      onModelChange: vi.fn(), onStop: vi.fn(), onSend: vi.fn(), canSend: true,
    }))
    const footer = container.querySelector('.chat-input-footer')
    expect([...footer.children].map(c => c.className)).toEqual(['ws-reconnecting', 'message-counter', 'send-btn', 'model-picker'])
    expect([...footer.querySelectorAll('button, select')].map(el => el.getAttribute('aria-label'))).toEqual(['Verstuur bericht', 'Model'])
    expect(caption(container).textContent).toBe(`Via ${FOUNDRY}`)
    act(() => root.unmount())
  })

  it('is not hidden by any style rule', () => {
    const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
    const bodies = [...css.matchAll(/([^{}]*\.model-picker[^{}]*)\{([^{}]*)\}/g)].map(m => `${m[1].trim()} { ${m[2].trim()} }`)
    expect(bodies.some(b => b.includes('.model-picker-provider'))).toBe(true)
    const hiding = /display:\s*none|visibility:\s*hidden|opacity:\s*0(?![.\d])|clip(-path)?:|font-size:\s*0(?![.\d])/
    expect(bodies.filter(b => hiding.test(b))).toEqual([])
  })
})

describe('modelOptionLabels', () => {
  it('leaves distinct labels alone and drops an empty description', () => {
    expect(modelOptionLabels([SONNET, { id: 'x/y', name: 'y', description: '' }])).toEqual(['Sonnet 5.5 — voor de meeste vragen', 'y'])
  })

  it('appends only a known provider to a twin', () => {
    const bare = { id: 'x/haiku', name: 'Haiku', description: 'snel', provider: '' }
    expect(modelOptionLabels([HAIKU, bare])).toEqual(['Haiku — snel (Anthropic)', 'Haiku — snel'])
  })

  it('gives no labels for no models', () => {
    expect(modelOptionLabels([])).toEqual([])
  })
})
