// Unittest voor de eval-poort (CH-28, #436), zonder app en zonder LLM.
// Bewust geen *.test.js: Playwright (testDir tests/e2e) zou hem dan als e2e-test oppakken.
// Run: node --test tests/e2e/score-unit.mjs tests/e2e/refusal-unit.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { nieuwAntwoord, poorten, protocollen, verwerk } from './chatstream.js'
import { scoreResult } from './score.js'
import { getallen, waardeInAntwoord, waardeInBron } from './antwoord.js'

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
const BRON = '[{"jaar":2022,"aantal":30280},{"jaar":2023,"aantal":29941},{"jaar":2024,"aantal":29620}]'

function goed(extra = {}) {
  return {
    ...antwoord([
      { type: 'tool_start', name: 'search_catalog' },
      { type: 'tool_start', name: 'get_duo_data' },
      { type: 'tool_start', name: 'create_plot' },
      { type: 'tool_start', name: 'query_data' },
      { type: 'tool_end', name: 'get_duo_data', output: '{"data_key":"duo:01.-ingeschrevenen-ho:0"}' },
      { type: 'tool_end', name: 'query_data', output: BRON },
      { type: 'message_end', content: 'Hogeschool Utrecht, voltijd: 30.280 (2022), 29.941 (2023), 29.620 (2024).' },
    ]),
    ...extra,
  }
}

test('een volledig antwoord haalt alle eisen', () => {
  const s = scoreResult(goed(), TREND)
  assert.deepEqual(s.fouten, [])
  assert.deepEqual(s.reference_checks, { 2022: 'exact', 2023: 'exact', 2024: 'exact' })
  assert.deepEqual(s.bron_gevonden, { 2022: true, 2023: true, 2024: true })
  assert.equal(s.uitkomst, 'data')
  assert.equal(s.total, s.max)
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

// Antwoordcorrectheid (#463): alleen het eindantwoord bewijst een referentiewaarde.

/** Een resultaat met alle tools goed en de juiste bron, met `content` als eindantwoord. */
function metAntwoord(content, bron = BRON) {
  const r = goed()
  r.content = content
  r.toolResults = r.toolResults.map(t => (t.name === 'query_data' ? { ...t, output: bron } : t))
  return r
}

const HU = 'Hogeschool Utrecht, voltijd:'

test('de proef uit het issue: een goede fetch bewijst geen fout antwoord', () => {
  const ev = { label: 'proef', expected: { data_points: { reference_values: { totaal: 36201 } } } }
  const r = antwoord([
    { type: 'tool_start', name: 'get_duo_data' },
    { type: 'tool_end', name: 'get_duo_data', output: '{"totaal": 36201}' },
    { type: 'message_end', content: 'Er zijn 99.999 studenten.' },
  ])
  const s = scoreResult(r, ev)
  assert.equal(s.reference_checks.totaal, 'missing')
  assert.ok(s.fouten.includes('referentiewaarde ontbreekt: totaal'))
  assert.equal(s.bron_gevonden.totaal, true)
  assert.ok(!s.fouten.some(f => f.startsWith('bron:')))
})

test('een fout eindantwoord met alle tools en de bron goed scoort minder dan 100 en faalt', () => {
  const s = scoreResult(metAntwoord(`${HU} 12.345 (2022), 12.346 (2023), 12.347 (2024).`), TREND)
  assert.deepEqual(s.bron_gevonden, { 2022: true, 2023: true, 2024: true })
  assert.ok(s.total < 100, `total ${s.total}`)
  assert.deepEqual(s.fouten, [2022, 2023, 2024].map(j => `referentiewaarde ontbreekt: ${j}`))
})

test('bronophaal is een aparte uitkomst: antwoord goed en bron mist geeft alleen bronfouten', () => {
  const s = scoreResult(metAntwoord(`${HU} 30.280 (2022), 29.941 (2023), 29.620 (2024).`, '{"rijen":0}'), TREND)
  assert.deepEqual(s.reference_checks, { 2022: 'exact', 2023: 'exact', 2024: 'exact' })
  assert.deepEqual(s.bron_gevonden, { 2022: false, 2023: false, 2024: false })
  assert.deepEqual(s.fouten, [2022, 2023, 2024].map(j => `bron: waarde niet in tooluitvoer: ${j}`))
})

test('getallen matchen op getalgrenzen', () => {
  const check = tekst => scoreResult(metAntwoord(tekst), TREND).reference_checks['2023']
  assert.equal(check(`${HU} 30.280 (2022), 129.941 (2023), 29.620 (2024).`), 'missing')
  assert.equal(check(`${HU} 30.280 (2022), 29.9411 (2023), 29.620 (2024).`), 'missing')
  assert.equal(check(`${HU} 30.280 (2022), 29.941 (2023), 29.620 (2024).`), 'exact')
  assert.equal(check(`${HU} 30 280 (2022), 29 941 (2023), 29 620 (2024).`), 'exact')
  assert.equal(check(`${HU} 30280 (2022), 29941 (2023), 29620 (2024).`), 'exact')
})

test('een verwachte 0 matcht "0" en niet "10"; tolerance_pct 0 blijft 0', () => {
  const ev = { label: 'nul', expected: { data_points: { reference_values: { 2024: 0 } } } }
  const r = c => ({ ...goed(), content: c, toolResults: [{ name: 'query_data', output: '{"2024": 0}' }] })
  assert.equal(scoreResult(r('In 2024 waren er 10 studenten.'), ev).reference_checks['2024'], 'missing')
  assert.equal(scoreResult(r('In 2024 waren er 0 studenten.'), ev).reference_checks['2024'], 'exact')
  assert.equal(scoreResult(r('In 2024 waren er 0 studenten.'), ev).bron_gevonden['2024'], true)

  const streng = structuredClone(TREND)
  streng.expected.data_points.tolerance_pct = 0
  const s = scoreResult(metAntwoord(`${HU} 30.280 (2022), 29.950 (2023), 29.620 (2024).`), streng)
  assert.equal(s.reference_checks['2023'], 'missing')
})

test('een waarde telt alleen bij haar eigen jaar en instelling', () => {
  const checks = tekst => scoreResult(metAntwoord(tekst), TREND).reference_checks
  assert.equal(checks('Utrecht 2023: 12.345; Amsterdam 2022: 30.280')['2022'], 'missing')
  assert.equal(checks('Hogeschool Utrecht 2023: 12.345; Universiteit van Amsterdam 2022: 30.280')['2022'], 'missing')
  // juiste waarden, verwisselde jaren
  assert.deepEqual(checks(`${HU} 29.941 (2022), 30.280 (2023), 29.620 (2024).`),
    { 2022: 'missing', 2023: 'missing', 2024: 'exact' })
  // juiste waarden, andere instelling
  assert.deepEqual(checks('Universiteit Utrecht, voltijd: 30.280 (2022), 29.941 (2023), 29.620 (2024).'),
    { 2022: 'missing', 2023: 'missing', 2024: 'missing' })
})

test('lopende tekst, lijst en tabel binden waarde, jaar en instelling', () => {
  const alleExact = { 2022: 'exact', 2023: 'exact', 2024: 'exact' }
  const checks = tekst => scoreResult(metAntwoord(tekst), TREND).reference_checks
  assert.deepEqual(checks(
    'In 2022 had de Hogeschool Utrecht 30.280 voltijdstudenten, in 2023 waren dat er 29.941. ' +
    'In 2024, het laatste jaar, telde de Hogeschool Utrecht er 29.620.'), alleExact)
  assert.deepEqual(checks(
    'De Hogeschool Utrecht telde 30.280 voltijdstudenten in 2022, 29.941 in 2023 en 29.620 in 2024.'), alleExact)
  assert.deepEqual(checks('Voltijd bij de Hogeschool Utrecht:\n\n- 2022: 30.280\n- 2023: 29.941\n- 2024: 29.620'),
    alleExact)
  assert.deepEqual(checks(
    'Voltijdinschrijvingen Hogeschool Utrecht:\n\n| Jaar | Voltijd |\n|---|---|\n' +
    '| 2022 | 30.280 |\n| 2023 | 29.941 |\n| 2024 | 29.620 |'), alleExact)
  assert.deepEqual(checks(
    '| Instelling | 2022 | 2023 | 2024 |\n|:--|--:|--:|--:|\n' +
    '| Hogeschool Utrecht | 30.280 | 29.941 | 29.620 |\n| Universiteit Utrecht | 1 | 2 | 3 |'), alleExact)
  // dezelfde lijst onder een andere instelling telt niet
  assert.deepEqual(checks('Voltijd bij de Universiteit Utrecht:\n\n- 2022: 30.280\n- 2023: 29.941\n- 2024: 29.620'),
    { 2022: 'missing', 2023: 'missing', 2024: 'missing' })
})

test('close is gebonden, blijft een fout en is nooit exact', () => {
  const s = scoreResult(metAntwoord(`${HU} 30.000 (2022), 29.941 (2023), 29.620 (2024).`), TREND)
  assert.equal(s.reference_checks['2022'], 'close')
  assert.deepEqual(s.fouten, ['referentiewaarde ontbreekt: 2022'])
  assert.ok(s.total < 100)
  // 30.000 hoort bij 2023: voor 2022 is er geen gebonden getal in de buurt
  const los = scoreResult(metAntwoord('Hogeschool Utrecht, voltijd: 30.000 (2023).'), TREND)
  assert.equal(los.reference_checks['2022'], 'missing')
  assert.equal(los.reference_checks['2023'], 'close')
})

const ARBEID = EVALS.find(ev => ev.label === 'arbeidsmarkt-aansluiting')

function zonderData(content) {
  return antwoord([
    { type: 'tool_start', name: 'search_catalog' },
    { type: 'message_end', content },
  ])
}

test('een kale "niet beschikbaar" zonder het gevraagde onderwerp is geen aanvaarde uitkomst', () => {
  const s = scoreResult(zonderData('Die gegevens zijn niet beschikbaar voor deze instelling, eerlijk gezegd.'), ARBEID)
  assert.equal(s.uitkomst, 'geen')
  assert.ok(s.fouten.includes('tool ontbreekt: get_cbs_data'))
})

test('een vastgelegde beperking met alle markers vervangt de data-eisen', () => {
  const s = scoreResult(zonderData(
    'De arbeidsmarktpositie van afgestudeerden is niet per instelling beschikbaar. ' +
    'Ik kan wel het landelijke hbo-beeld geven.'), ARBEID)
  assert.equal(s.uitkomst, 'beperking')
  assert.equal(s.uitkomst_id, 'landelijk-niveau')
  assert.deepEqual(s.fouten, [])

  const half = scoreResult(zonderData('De arbeidsmarktpositie is landelijk bekend.'), ARBEID)
  assert.equal(half.uitkomst, 'geen')
})

test('een beperking die een getal noemt dat de referentie tegenspreekt, telt niet', () => {
  const ev = structuredClone(TREND)
  ev.expected.acceptable_outcomes = [{ id: 'niet-per-jaar', markers: ['Hogeschool Utrecht', 'niet per jaar'] }]
  const r = c => ({ ...zonderData(c), toolCalls: ['search_catalog', 'get_duo_data'] })
  const beperking = 'Voor de Hogeschool Utrecht is voltijd niet per jaar te geven'
  assert.equal(scoreResult(r(`${beperking}.`), ev).uitkomst, 'beperking')
  const tegen = scoreResult(r(`${beperking}, maar in 2022 waren het er ca. 12.000.`), ev)
  assert.equal(tegen.uitkomst, 'geen')
  assert.ok(tegen.fouten.includes('referentiewaarde ontbreekt: 2022'))
})

test('elke acceptable_outcome in evaluations.json is structureel vastgelegd', () => {
  const uitkomsten = EVALS.flatMap(ev => ev.expected.acceptable_outcomes || [])
  assert.ok(uitkomsten.length >= 5)
  for (const u of uitkomsten) {
    assert.equal(typeof u.id, 'string', JSON.stringify(u))
    assert.ok(Array.isArray(u.markers) && u.markers.length >= 2, u.id)
    for (const m of u.markers) new RegExp(m, 'i')
  }
})

test('getallen leest Nederlandse notatie op getalgrenzen', () => {
  const waarden = tekst => getallen(tekst).map(g => g.waarde)
  assert.deepEqual(waarden('2022: 30.280; 29 941 en 29941'), [2022, 30280, 29941, 29941])
  assert.deepEqual(waarden('129.941, 29.9411 en 29,5%'), [129941, 29.9411, 29.5])
  assert.deepEqual(waarden('1.234.567,8'), [1234567.8])
})

test('waardeInAntwoord en waardeInBron toetsen los van elkaar', () => {
  const ctx = { sleutel: '2022', sleutels: ['2022'], verwacht: 30280, entiteit: 'Hogeschool Utrecht' }
  assert.equal(waardeInAntwoord('Hogeschool Utrecht had in 2022 30.280 studenten.', ctx), 'exact')
  assert.equal(waardeInAntwoord('In 2022 had zij 30.280 studenten.', ctx), 'missing')
  const zin = 'Hogeschool Utrecht had in 2022 30.280 studenten.'
  assert.equal(waardeInAntwoord(zin, { ...ctx, maat: 'deeltijd' }), 'missing')
  assert.equal(waardeInAntwoord(`${zin} Dat is voltijd.`, { ...ctx, maat: 'voltijd' }), 'missing')
  const voltijd = { ...ctx, maat: 'voltijd' }
  assert.equal(waardeInAntwoord('Hogeschool Utrecht had in 2022 30.280 voltijdstudenten.', voltijd), 'exact')
  assert.equal(waardeInBron(['{"aantal": 30280}'], 30280), true)
  assert.equal(waardeInBron(['2022,30280'], 30280), true)
  assert.equal(waardeInBron(['{"aantal": 130280}'], 30280), false)
  assert.equal(waardeInBron([], 0), false)
})
