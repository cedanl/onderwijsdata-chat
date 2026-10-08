// Unittest voor de eval-poort (CH-28, #436), zonder app en zonder LLM.
// Bewust geen *.test.js: Playwright (testDir tests/e2e) zou hem dan als e2e-test oppakken.
// Run: node --test tests/e2e/score-unit.mjs tests/e2e/refusal-unit.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { nieuwAntwoord, poorten, protocollen, verwerk } from './chatstream.js'
import { scoreResult } from './score.js'

const EVALS = JSON.parse(readFileSync(new URL('./evaluations.json', import.meta.url), 'utf-8')).evaluations
const DATA_EVALS = EVALS.filter(ev => !ev.expected.must_refuse)

function antwoord(events) {
  const a = nieuwAntwoord()
  for (const e of events) verwerk(a, e)
  return a
}

test('een leeg, mislukt resultaat scoort 0 en faalt in elke case (de proef uit de audit)', () => {
  const r = { ...nieuwAntwoord(), error: 'Authentication rejected' }
  assert.ok(DATA_EVALS.length >= 13)
  for (const ev of DATA_EVALS) {
    const s = scoreResult(r, ev)
    assert.equal(s.total, 0, ev.label)
    assert.ok(s.fouten.includes('poort: geen_fout'), ev.label)
    assert.ok(s.fouten.includes('poort: tekst'), ev.label)
  }
})

test('een antwoord zonder message_end of met een afgebroken einde is geen geldig einde', () => {
  assert.equal(poorten(antwoord([{ type: 'text_delta', content: 'Er zijn 29.941 studenten.' }])).geldig_einde, false)
  assert.equal(poorten(antwoord([{ type: 'message_end', content: 'x', aborted: true }])).geldig_einde, false)
  assert.equal(poorten(antwoord([{ type: 'message_end', content: 'x', partial: true }])).geldig_einde, false)
  assert.deepEqual(poorten(antwoord([{ type: 'message_end', content: 'x' }])), {
    geldig_einde: true, tekst: true, geen_fout: true, geen_timeout: true,
  })
})

test('ingetrokken tekst telt niet mee', () => {
  const a = antwoord([
    { type: 'text_delta', content: 'Er zijn 99.999 studenten.' },
    { type: 'message_cancel' },
    { type: 'text_delta', content: 'Er zijn 29.941 ' },
    { type: 'text_delta', content: 'studenten.' },
  ])
  assert.equal(a.delen.join(''), 'Er zijn 29.941 studenten.')
  assert.equal(a.ingetrokken, 1)
})

test('het eindantwoord is de content van message_end, niet de som van de deltas', () => {
  const a = antwoord([
    { type: 'text_delta', content: 'Er zijn 99.999 studenten.' },
    { type: 'message_end', content: 'Er zijn 29.941 studenten.' },
  ])
  assert.equal(a.content, 'Er zijn 29.941 studenten.')
})

test('het token gaat als subprotocol mee, niet in de URL', () => {
  assert.deepEqual(protocollen('abc'), ['bearer', 'abc'])
})

const TREND = EVALS.find(ev => ev.label === 'trend-analyse')

function goed(extra = {}) {
  return {
    ...antwoord([
      { type: 'tool_start', name: 'search_catalog' },
      { type: 'tool_start', name: 'get_duo_data' },
      { type: 'tool_start', name: 'create_plot' },
      { type: 'tool_end', name: 'get_duo_data', output: '{"data_key":"duo:01.-ingeschrevenen-ho:0"}' },
      { type: 'message_end', content: 'Hogeschool Utrecht, voltijd: 30.280 (2022), 29.941 (2023), 29.620 (2024).' },
    ]),
    ...extra,
  }
}

test('een volledig antwoord haalt alle eisen', () => {
  assert.deepEqual(scoreResult(goed(), TREND).fouten, [])
})

test('elke eis faalt apart, ook als de totaalscore hoog blijft', () => {
  const r = goed()
  r.content = 'Hogeschool Utrecht, voltijd: 12.345 (2022), 12.346 (2023), 12.347 (2024).'
  const s = scoreResult(r, TREND)
  assert.deepEqual(s.fouten, [2022, 2023, 2024].map(j => `referentiewaarde ontbreekt: ${j}`))
  assert.ok(s.total >= 30)  // de oude grens had dit goedgekeurd

  const zonderPlot = goed()
  zonderPlot.toolCalls = ['search_catalog', 'get_duo_data']
  assert.deepEqual(scoreResult(zonderPlot, TREND).fouten, ['tool ontbreekt: create_plot', 'grafiek ontbreekt'])
})
