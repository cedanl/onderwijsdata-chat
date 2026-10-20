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

const api = vi.hoisted(() => ({
  putWorkbook: vi.fn(() => Promise.resolve({})),
  deleteWorkbookApi: vi.fn(() => Promise.resolve({})),
  fetchWorkbooks: vi.fn(() => Promise.resolve([])),
  fetchWorkbook: vi.fn(),
}))
vi.mock('../api', () => api)

const { saveWorkbook, saveWorkbookWithSync, updateWorkbook, getWorkbooks, deleteWorkbook, loadWorkbook, loadWorkbooksFromServer, isVolledig } = await import('../workbooks.js')

beforeEach(() => {
  localStorageMock.clear()
  vi.clearAllMocks()
  // clearAllMocks keeps implementations: a test that makes setItem throw would leak.
  localStorageMock.setItem.mockImplementation((key, val) => { storage[key] = val })
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

describe('saveWorkbookWithSync', () => {
  // #189: the report opened before its PUT landed; the gallery, which reads the
  // server list, then showed it missing or empty.
  it('resolves only after the server has the workbook', async () => {
    let landed = false
    api.putWorkbook.mockImplementation(() => new Promise(resolve => setTimeout(() => { landed = true; resolve({}) }, 0)))
    const result = await saveWorkbookWithSync({ title: 'Rapport', htmlContent: '<p>x</p>', type: 'report' })
    expect(landed).toBe(true)
    expect(result.ok).toBe(true)
    expect(api.putWorkbook).toHaveBeenCalledWith('test-uuid-1234', expect.objectContaining({ htmlContent: '<p>x</p>' }))
  })

  it('is not ok when the server rejects the workbook', async () => {
    api.putWorkbook.mockImplementation(() => Promise.reject(new Error('HTTP 500')))
    const result = await saveWorkbookWithSync({ title: 'Rapport', htmlContent: '<p>x</p>', type: 'report' })
    expect(result.ok).toBe(false)
    expect(result.error).toContain('HTTP 500')
  })

  it('is ok when the server has it, even if the local copy did not fit', async () => {
    api.putWorkbook.mockImplementation(() => Promise.resolve({}))
    localStorageMock.setItem.mockImplementation(() => { throw new DOMException('quota') })
    const result = await saveWorkbookWithSync({ title: 'Groot', htmlContent: '<p>x</p>', type: 'report' })
    expect(result.ok).toBe(true)
  })
})

describe('updateWorkbook', () => {
  const rapport = { id: 'r1', title: 'Oud', htmlContent: '<p>x</p>', type: 'report', createdAt: '2026-09-26T10:00:00Z' }

  // #176: direct na het genereren stond het rapport niet in localStorage; de titel
  // leek opgeslagen, maar er ging geen PUT naar de server.
  it('saves to the server even when the workbook is not in the local cache', async () => {
    api.putWorkbook.mockImplementation(() => Promise.resolve({}))
    const updated = await updateWorkbook(rapport, { title: 'Nieuw' })
    expect(updated.title).toBe('Nieuw')
    expect(api.putWorkbook).toHaveBeenCalledWith('r1', expect.objectContaining({ title: 'Nieuw', htmlContent: '<p>x</p>' }))
  })

  it('updates the local cache when the workbook is in it', async () => {
    api.putWorkbook.mockImplementation(() => Promise.resolve({}))
    storage.edudata_workbooks = JSON.stringify([rapport])
    await updateWorkbook(rapport, { title: 'Nieuw' })
    expect(JSON.parse(storage.edudata_workbooks)[0].title).toBe('Nieuw')
  })

  it('rejects when the server does not save it', async () => {
    api.putWorkbook.mockImplementation(() => Promise.reject(new Error('HTTP 500')))
    await expect(updateWorkbook(rapport, { title: 'Nieuw' })).rejects.toThrow('HTTP 500')
  })
})

// #633: the list carries no content; a report's HTML comes per workbook, once.
describe('loadWorkbooksFromServer', () => {
  const kaart = { id: 'r1', title: 'Rapport', description: '', instelling: null, created_at: '2026-10-19T10:00:00Z', type: 'report' }
  beforeEach(() => {
    api.fetchWorkbooks.mockReset()
    api.putWorkbook.mockReset().mockResolvedValue({})
  })

  it('asks the server for the list once and marks each row as a summary', async () => {
    api.fetchWorkbooks.mockResolvedValue([kaart])
    const lijst = await loadWorkbooksFromServer()
    expect(api.fetchWorkbooks).toHaveBeenCalledTimes(1)
    expect(lijst).toEqual([expect.objectContaining({ id: 'r1', createdAt: '2026-10-19T10:00:00Z', samenvatting: true })])
    expect(isVolledig(lijst[0])).toBe(false)
  })

  it('puts workbooks saved only in this browser on an empty server, then reads the list again', async () => {
    storage.edudata_workbooks = JSON.stringify([{ id: 'oud', title: 'Oud', htmlContent: '<p/>' }])
    api.fetchWorkbooks.mockResolvedValueOnce([]).mockResolvedValueOnce([{ ...kaart, id: 'oud' }])
    const lijst = await loadWorkbooksFromServer()
    expect(api.putWorkbook).toHaveBeenCalledWith('oud', expect.objectContaining({ htmlContent: '<p/>' }))
    expect(lijst.map(w => w.id)).toEqual(['oud'])
  })

  it('never puts a summary back: it has no content', async () => {
    storage.edudata_workbooks = JSON.stringify([{ ...kaart, samenvatting: true }])
    api.fetchWorkbooks.mockResolvedValue([])
    expect(await loadWorkbooksFromServer()).toEqual([])
    expect(api.putWorkbook).not.toHaveBeenCalled()
  })
})

describe('loadWorkbook', () => {
  it('fetches a workbook once and parses its content', async () => {
    api.fetchWorkbook.mockResolvedValue({ id: 'r2', title: 'R', html_content: '<p>r</p>', dashboard_spec: null, messages: null, created_at: 'x' })
    const [a, b] = await Promise.all([loadWorkbook('r2'), loadWorkbook('r2')])
    expect(api.fetchWorkbook).toHaveBeenCalledTimes(1)
    expect(a).toBe(b)
    expect(a).toMatchObject({ htmlContent: '<p>r</p>', createdAt: 'x' })
    expect(isVolledig(a)).toBe(true)
  })

  it('tries again after a failed fetch', async () => {
    api.fetchWorkbook.mockRejectedValueOnce(new Error('API 503')).mockResolvedValueOnce({ id: 'r3', html_content: '<p/>' })
    await expect(loadWorkbook('r3')).rejects.toThrow('API 503')
    await expect(loadWorkbook('r3')).resolves.toMatchObject({ htmlContent: '<p/>' })
  })

  it('fetches a deleted workbook again rather than serving it from memory', async () => {
    api.fetchWorkbook.mockResolvedValue({ id: 'r4', html_content: '<p/>' })
    await loadWorkbook('r4')
    deleteWorkbook('r4')
    await loadWorkbook('r4')
    expect(api.fetchWorkbook).toHaveBeenCalledTimes(2)
  })
})

describe('updateWorkbook with a summary', () => {
  // The PUT replaces the row: a summary from the list would save the report without its HTML.
  it('refuses, and sends nothing', async () => {
    await expect(updateWorkbook({ id: 'r1', title: 'R', samenvatting: true }, { title: 'Nieuw' })).rejects.toThrow()
    expect(api.putWorkbook).not.toHaveBeenCalled()
  })
})
