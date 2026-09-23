// @vitest-environment jsdom
import { describe, it, expect, beforeEach } from 'vitest'
import { pickModel, loadModelChoice, saveModelChoice } from '../modelChoice'

const models = [{ id: 'openai/gpt-oss-120b' }, { id: 'anthropic/claude-opus' }]

describe('pickModel', () => {
  it('keeps a stored model that is still offered', () => {
    expect(pickModel(models, 'anthropic/claude-opus', 'openai/gpt-oss-120b')).toBe('anthropic/claude-opus')
  })

  it('falls back to the default when the stored model is gone', () => {
    expect(pickModel(models, 'removed/model', 'openai/gpt-oss-120b')).toBe('openai/gpt-oss-120b')
  })

  it('falls back to the default when nothing is stored', () => {
    expect(pickModel(models, null, 'openai/gpt-oss-120b')).toBe('openai/gpt-oss-120b')
  })
})

describe('model choice storage', () => {
  beforeEach(() => localStorage.clear())

  it('round-trips the chosen model', () => {
    saveModelChoice('anthropic/claude-opus')
    expect(loadModelChoice()).toBe('anthropic/claude-opus')
  })

  it('returns null when nothing was saved', () => {
    expect(loadModelChoice()).toBeNull()
  })
})
