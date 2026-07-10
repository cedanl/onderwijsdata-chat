import { describe, it, expect, beforeEach, vi } from 'vitest'

// localStorage mock
const storage = {}
const localStorageMock = {
  getItem: vi.fn((key) => storage[key] ?? null),
  setItem: vi.fn((key, val) => { storage[key] = val }),
  removeItem: vi.fn((key) => { delete storage[key] }),
  clear: vi.fn(() => { for (const k in storage) delete storage[k] }),
}
vi.stubGlobal('localStorage', localStorageMock)

const STORAGE_KEY = 'edudata_conversations'

function loadConversationHistory() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') } catch { return [] }
}

function persistConversationHistory(list) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
}

beforeEach(() => {
  localStorageMock.clear()
  vi.clearAllMocks()
})

describe('loadConversationHistory', () => {
  it('returns empty array when nothing stored', () => {
    expect(loadConversationHistory()).toEqual([])
  })

  it('returns stored conversations', () => {
    storage[STORAGE_KEY] = JSON.stringify([{ id: 1, title: 'Test' }])
    expect(loadConversationHistory()).toEqual([{ id: 1, title: 'Test' }])
  })

  it('returns empty array on corrupt data', () => {
    storage[STORAGE_KEY] = 'not-json'
    expect(loadConversationHistory()).toEqual([])
  })
})

describe('deleteConversation from history', () => {
  it('removes a conversation by id and persists', () => {
    const history = [
      { id: 1, title: 'First', timestamp: 100, messages: [] },
      { id: 2, title: 'Second', timestamp: 200, messages: [] },
      { id: 3, title: 'Third', timestamp: 300, messages: [] },
    ]
    const updated = history.filter(c => c.id !== 2)
    persistConversationHistory(updated)

    const result = loadConversationHistory()
    expect(result).toHaveLength(2)
    expect(result.map(c => c.id)).toEqual([1, 3])
  })

  it('handles deleting non-existent id gracefully', () => {
    const history = [{ id: 1, title: 'Only', timestamp: 100, messages: [] }]
    const updated = history.filter(c => c.id !== 999)
    persistConversationHistory(updated)

    expect(loadConversationHistory()).toHaveLength(1)
  })
})

describe('renameConversation in history', () => {
  it('updates the title of a conversation by id and persists', () => {
    const history = [
      { id: 1, title: 'Old title', timestamp: 100, messages: [] },
      { id: 2, title: 'Other', timestamp: 200, messages: [] },
    ]
    const updated = history.map(c => c.id === 1 ? { ...c, title: 'New title' } : c)
    persistConversationHistory(updated)

    const result = loadConversationHistory()
    expect(result[0].title).toBe('New title')
    expect(result[1].title).toBe('Other')
  })

  it('does not change anything when id not found', () => {
    const history = [{ id: 1, title: 'Unchanged', timestamp: 100, messages: [] }]
    const updated = history.map(c => c.id === 999 ? { ...c, title: 'X' } : c)
    persistConversationHistory(updated)

    expect(loadConversationHistory()[0].title).toBe('Unchanged')
  })

  it('trims whitespace from new title', () => {
    const history = [{ id: 1, title: 'Old', timestamp: 100, messages: [] }]
    const newTitle = '  Trimmed Title  '.trim()
    const updated = history.map(c => c.id === 1 ? { ...c, title: newTitle } : c)
    persistConversationHistory(updated)

    expect(loadConversationHistory()[0].title).toBe('Trimmed Title')
  })
})
