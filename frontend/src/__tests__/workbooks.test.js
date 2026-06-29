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
vi.stubGlobal('crypto', { randomUUID: () => 'test-uuid-1234' })

const { saveWorkbook, getWorkbooks, deleteWorkbook } = await import('../workbooks.js')

beforeEach(() => {
  localStorageMock.clear()
  vi.clearAllMocks()
})

describe('saveWorkbook', () => {
  it('saves a workbook and returns ok with workbook', () => {
    const result = saveWorkbook({ title: 'Test', description: 'Desc' })
    expect(result.ok).toBe(true)
    expect(result.workbook).toMatchObject({ id: 'test-uuid-1234', title: 'Test' })
    expect(result.workbook.createdAt).toBeTruthy()
  })

  it('persists to localStorage', () => {
    saveWorkbook({ title: 'Test', description: 'Desc' })
    const stored = JSON.parse(localStorageMock.setItem.mock.calls[0][1])
    expect(stored).toHaveLength(1)
    expect(stored[0].title).toBe('Test')
  })

  it('strips messages to only role+content to save space', () => {
    const messages = [
      { id: 123, role: 'user', content: 'hello', done: true, tools: [] },
      { id: 456, role: 'assistant', content: 'world', done: true, toolLabel: 'zoeken', isError: false },
    ]
    saveWorkbook({ title: 'T', description: 'D', messages })
    const stored = JSON.parse(localStorageMock.setItem.mock.calls[0][1])
    const savedMsgs = stored[0].messages
    expect(savedMsgs[0]).toEqual({ role: 'user', content: 'hello' })
    expect(savedMsgs[1]).toEqual({ role: 'assistant', content: 'world' })
    expect(savedMsgs[0].done).toBeUndefined()
    expect(savedMsgs[1].toolLabel).toBeUndefined()
  })

  it('returns { ok: false } when localStorage throws', () => {
    localStorageMock.setItem.mockImplementation(() => { throw new DOMException('quota') })
    const result = saveWorkbook({ title: 'Big', description: 'D', messages: [], figures: [] })
    expect(result.ok).toBe(false)
    expect(result.error).toBeTruthy()
  })

  it('retries without figures on quota error', () => {
    let callCount = 0
    localStorageMock.setItem.mockImplementation((k, v) => {
      callCount++
      if (callCount === 1) throw new DOMException('quota')
      storage[k] = v
    })
    const result = saveWorkbook({
      title: 'T', description: 'D',
      messages: [{ role: 'assistant', content: 'x' }],
      figures: ['big-figure-json'],
    })
    expect(result.ok).toBe(true)
    const stored = JSON.parse(storage.edudata_workbooks)
    expect(stored[0].figures).toEqual([])
  })
})

describe('getWorkbooks', () => {
  it('returns empty array when nothing stored', () => {
    expect(getWorkbooks()).toEqual([])
  })

  it('returns stored workbooks', () => {
    storage.edudata_workbooks = JSON.stringify([{ id: 'a', title: 'A' }])
    expect(getWorkbooks()).toEqual([{ id: 'a', title: 'A' }])
  })

  it('returns empty array on corrupt data', () => {
    storage.edudata_workbooks = 'not-json'
    expect(getWorkbooks()).toEqual([])
  })
})

describe('deleteWorkbook', () => {
  it('removes a workbook by id', () => {
    storage.edudata_workbooks = JSON.stringify([
      { id: 'a', title: 'A' },
      { id: 'b', title: 'B' },
    ])
    deleteWorkbook('a')
    const remaining = JSON.parse(storage.edudata_workbooks)
    expect(remaining).toHaveLength(1)
    expect(remaining[0].id).toBe('b')
  })
})
