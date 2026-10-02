// Unittest voor de weigerscore (#36), zonder app en zonder LLM.
// Bewust geen *.test.js: Playwright (testDir tests/e2e) zou hem dan als e2e-test oppakken.
// Run: node --test tests/e2e/refusal-unit.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { scoreRefusal } from './refusal.js'

const leeg = { content: '', toolResults: [] }

test('een eerlijke weigering zonder getallen slaagt', () => {
  const s = scoreRefusal({ ...leeg, content: 'Gegevens over IQ per opleiding zijn niet beschikbaar in de open data.' })
  assert.equal(s.refused, true)
  assert.deepEqual(s.fabricated, [])
  assert.equal(s.total, s.max)
})

test('een gok met een verzonnen getal faalt, ook met een weigerzin erbij', () => {
  const s = scoreRefusal({ ...leeg, content: 'Exacte data is niet beschikbaar, maar het zijn er naar schatting 12.500.' })
  assert.equal(s.refused, true)
  assert.deepEqual(s.fabricated, ['12500'])
  assert.equal(s.total, 0)
})

test('een getal uit de tool-output is geen verzinsel', () => {
  const r = { content: 'Voor 1985 is geen data; de reeks begint in 2019 met 29 941 studenten.',
    toolResults: [{ output: '{"AANTAL":29941}' }] }
  assert.deepEqual(scoreRefusal(r).fabricated, [])
})

test('jaartallen en kleine getallen tellen niet als verzinsel', () => {
  const r = { ...leeg, content: 'Er is geen data over 2031; de laatste 5 jaar lopen tot 2025.' }
  assert.deepEqual(scoreRefusal(r).fabricated, [])
})

test('een antwoord zonder weigering faalt', () => {
  const s = scoreRefusal({ ...leeg, content: 'De Universiteit van Atlantis heeft veel studenten.' })
  assert.equal(s.refused, false)
  assert.equal(s.total, 0)
})
