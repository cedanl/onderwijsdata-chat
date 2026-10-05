import { describe, it, expect } from 'vitest'
import { answerModels } from '../answerModel'

const MODELS = [{ id: 'claude-sonnet', name: 'Sonnet' }, { id: 'gpt-oss-120b', name: 'gpt-oss' }]

describe('answerModels', () => {
  it('labels the last finished answer of each turn with the model of its question', () => {
    const messages = [
      { id: 1, role: 'user', model: 'claude-sonnet' },
      { id: 2, role: 'assistant', done: true, content: 'tekst' },
      { id: 3, role: 'assistant', done: true, figures: [{}] },
      { id: 4, role: 'user', model: 'gpt-oss-120b' },
      { id: 5, role: 'assistant', done: true, content: 'ander antwoord' },
    ]
    expect(answerModels(messages, MODELS)).toEqual({ 3: 'Sonnet', 5: 'gpt-oss' })
  })

  it('labels nothing while the answer is still coming, on an error, or without a model', () => {
    expect(answerModels([{ id: 1, role: 'user', model: 'claude-sonnet' }, { id: 2, role: 'assistant', done: false }], MODELS)).toEqual({})
    expect(answerModels([{ id: 1, role: 'user', model: 'claude-sonnet' }, { id: 2, role: 'assistant', done: true, isError: true }], MODELS)).toEqual({})
    expect(answerModels([{ id: 1, role: 'user' }, { id: 2, role: 'assistant', done: true }], MODELS)).toEqual({})
  })

  it('falls back to the model id when the model is no longer offered', () => {
    expect(answerModels([{ id: 1, role: 'user', model: 'oud-model' }, { id: 2, role: 'assistant', done: true }], MODELS)).toEqual({ 2: 'oud-model' })
  })
})
