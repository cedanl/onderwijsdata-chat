import { describe, it, expect } from 'vitest'
import { clarificationAnswer, hasOpenClarification } from '../clarificationState'
import { buildHistory } from '../hooks/useChat'

// #109: after a reload the chosen option was gone and every option was clickable again.
// What was chosen is in the conversation itself: the first question after the card.
const vraag = { id: 2, role: 'assistant', content: 'Welk schooljaar bedoel je?', clarification: ['2023/24', 'Alle jaren'], done: true }
const gesprek = [
  { id: 1, role: 'user', content: 'Hoeveel mbo-studenten?' },
  vraag,
  { id: 3, role: 'user', content: '2023/24' },
  { id: 4, role: 'assistant', content: 'In 2023/24 waren er …', done: true },
]

describe('clarificationAnswer', () => {
  it('finds the option the user chose', () => {
    expect(clarificationAnswer(gesprek, 1)).toEqual({ answered: true, choice: '2023/24' })
  })

  it('counts a typed question after the card as an answer too', () => {
    const ander = [gesprek[0], vraag, { id: 3, role: 'user', content: 'Laat maar, toon hbo' }]
    expect(clarificationAnswer(ander, 1)).toEqual({ answered: true, choice: 'Laat maar, toon hbo' })
  })

  it('is open while nothing came after the card', () => {
    expect(clarificationAnswer(gesprek.slice(0, 2), 1)).toEqual({ answered: false, choice: null })
  })
})

describe('hasOpenClarification', () => {
  it('is true when the conversation ends on a card', () => {
    expect(hasOpenClarification(gesprek.slice(0, 2))).toBe(true)
  })

  it('is false once it was answered', () => {
    expect(hasOpenClarification(gesprek)).toBe(false)
    expect(hasOpenClarification([])).toBe(false)
  })
})

describe('buildHistory', () => {
  it('keeps the clarification question, so the server knows what the choice answers', () => {
    expect(buildHistory(gesprek.slice(0, 3))).toEqual([
      { role: 'user', content: 'Hoeveel mbo-studenten?' },
      { role: 'assistant', content: 'Welk schooljaar bedoel je?' },
      { role: 'user', content: '2023/24' },
    ])
  })
})
