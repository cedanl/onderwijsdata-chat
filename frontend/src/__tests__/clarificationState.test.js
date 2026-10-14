import { describe, it, expect } from 'vitest'
import { clarificationAnswer, hasOpenClarification, originalQuestion } from '../clarificationState'
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

// #494: "Anders formuleren" puts the question a card asks about back in the input box.
describe('originalQuestion', () => {
  const typeKaart = { id: 2, role: 'assistant', content: 'Welk onderwijstype?', clarification: ['mbo', { label: 'hbo', beschrijving: 'hoger beroepsonderwijs' }], done: true }
  const jaarKaart = { id: 4, role: 'assistant', content: 'Welk schooljaar?', clarification: ['2023/24', 'Alle jaren'], done: true }
  const keten = [
    { id: 1, role: 'user', content: 'Hoeveel studenten zijn er?' },
    typeKaart,
    { id: 3, role: 'user', content: 'hbo' },
    jaarKaart,
  ]

  it('is the question before the card', () => {
    expect(originalQuestion(gesprek, 1)).toBe('Hoeveel mbo-studenten?')
  })

  it('goes past a choice on an earlier card to the question of the chain', () => {
    expect(originalQuestion(keten, 1)).toBe('Hoeveel studenten zijn er?')
    expect(originalQuestion(keten, 3)).toBe('Hoeveel studenten zijn er?')
  })

  it('takes what was typed instead of an option as the question', () => {
    const getypt = [keten[0], typeKaart, { id: 3, role: 'user', content: 'Nee, ik bedoel het wo' }, jaarKaart]
    expect(originalQuestion(getypt, 3)).toBe('Nee, ik bedoel het wo')
  })

  it('counts an option label as a question when it does not answer a card', () => {
    const los = [...gesprek, { id: 5, role: 'user', content: 'hbo' }, { ...typeKaart, id: 6 }]
    expect(originalQuestion(los, 5)).toBe('hbo')
  })

  it('skips blank and failed user messages', () => {
    const rommel = [keten[0], { id: 7, role: 'user', content: '  ' }, { id: 8, role: 'user', content: 'Kapot', isError: true }, typeKaart]
    expect(originalQuestion(rommel, 3)).toBe('Hoeveel studenten zijn er?')
  })

  it('is null when no question precedes the card', () => {
    expect(originalQuestion([vraag], 0)).toBeNull()
    expect(originalQuestion([{ id: 1, role: 'user', content: ' ' }, vraag], 1)).toBeNull()
    // The conversation starts with the first card of a chain: its choice is no question.
    expect(originalQuestion(keten.slice(1), 2)).toBeNull()
  })

  it('does not fall over on a restored message that is not what it should be', () => {
    expect(originalQuestion([{ id: 1, role: 'user', content: 3 }, vraag], 1)).toBeNull()
    expect(originalQuestion([{ ...vraag, clarification: 'geen lijst' }, { id: 2, role: 'user', content: 'x' }, vraag], 2)).toBe('x')
    expect(originalQuestion([{ ...vraag, clarification: [null] }, { id: 2, role: 'user', content: 'y' }, vraag], 2)).toBe('y')
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
