// @vitest-environment jsdom
// #778: een verwijdering die niets meer vindt, is gelukt; elke andere fout komt bij de aanroeper.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { deleteConversationApi, deleteWorkbookApi } from '../api'

const antwoord = (status, body = {}) => ({ status, ok: status >= 200 && status < 300, json: async () => body })

describe('verwijderen via de API (#778)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it.each([
    ['gesprek', () => deleteConversationApi('c1')],
    ['werkboek', () => deleteWorkbookApi('wb-1')],
  ])('een 404 voor een %s telt als verwijderd', async (_, verwijder) => {
    vi.stubGlobal('fetch', vi.fn(async () => antwoord(404, { detail: 'Not found' })))
    await expect(verwijder()).resolves.toBeUndefined()
  })

  it.each([
    ['gesprek', () => deleteConversationApi('c1')],
    ['werkboek', () => deleteWorkbookApi('wb-1')],
  ])('een 5xx of netwerkfout voor een %s wijst af', async (_, verwijder) => {
    vi.stubGlobal('fetch', vi.fn(async () => antwoord(503)))
    await expect(verwijder()).rejects.toMatchObject({ status: 503 })
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
    await expect(verwijder()).rejects.toThrow('Failed to fetch')
  })
})
