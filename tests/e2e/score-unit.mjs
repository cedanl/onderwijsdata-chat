// Unittest voor de eval-poort (CH-28, #436), zonder app en zonder LLM.
// Bewust geen *.test.js: Playwright (testDir tests/e2e) zou hem dan als e2e-test oppakken.
// Run: node --test tests/e2e/score-unit.mjs tests/e2e/refusal-unit.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { binnenLimiet, bronVan, limietWacht, nieuwAntwoord, poorten, protocollen, verwerk } from './chatstream.js'
import { scoreResult, scoreWeigering } from './score.js'
import { controleerMustCall, mustCallFouten, toetsMustCall } from './toolasserties.js'
import { getallen, waardeInAntwoord, waardeInBron } from './antwoord.js'
import { drempel, foutenVan, isKritiek, kritiekVerslag, nieuweStand, samenvatting, voegRunToe } from './kritiek.js'
import { verslagen } from './runlog.js'

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

test('de bron per toolaanroep komt uit de input van tool_start, alleen bij een tool met een bron (#909)', () => {
  const a = antwoord([
    { type: 'tool_start', name: 'search_catalog', input: { query: 'eerstejaars hoger onderwijs' } },
    { type: 'tool_start', name: 'get_duo_data', input: { dataset_id: 'p02ho1ejrs', resource: 4 } },
    { type: 'tool_start', name: 'get_cbs_data', input: { dataset_id: '85423NED', filters: { Perioden: '2024SJ00' } } },
    { type: 'tool_start', name: 'get_maat', input: { maat: 'eerstejaars_ho', instelling: 'Universiteit Utrecht' } },
    { type: 'tool_start', name: 'query_data', input: { data_key: 'duo:p02ho1ejrs:4' } },
    { type: 'tool_start', name: 'create_plot' },
  ])
  assert.deepEqual(a.toolCalls, ['search_catalog', 'get_duo_data', 'get_cbs_data', 'get_maat', 'query_data', 'create_plot'])
  assert.deepEqual(a.bronnen, [
    { tool: 'get_duo_data', dataset_id: 'p02ho1ejrs', resource: 4 },
    { tool: 'get_cbs_data', dataset_id: '85423NED' },
    { tool: 'get_maat', maat: 'eerstejaars_ho' },
  ])
  assert.equal(bronVan({ type: 'tool_start', name: 'get_duo_data', input: { dataset_id: '' } }), null)
})

test('de berichtlimiet: de runner wacht de genoemde tijd en vraagt opnieuw, alleen als er nog niets gebeurde (#909)', async () => {
  const melding = 'Te veel verzoeken in korte tijd. Probeer het over 7 seconden opnieuw.'
  assert.equal(limietWacht(melding), 7)
  assert.equal(limietWacht('Te veel verzoeken tegelijk. Wacht even en probeer het opnieuw.'), null)
  assert.equal(limietWacht(null), null)

  const gewacht = []
  const uitkomsten = [{ ...nieuwAntwoord(), error: melding }, { ...nieuwAntwoord(), content: 'Er zijn 29.941 studenten.' }]
  const uit = await binnenLimiet(async () => uitkomsten.shift(), async (ms) => { gewacht.push(ms) })
  assert.equal(uit.content, 'Er zijn 29.941 studenten.')
  assert.deepEqual(gewacht, [8000])

  // Liep de beurt al (een tool, tekst), dan is de weigering een fout van die beurt: niet opnieuw vragen.
  const halverwege = { ...nieuwAntwoord(), toolCalls: ['search_catalog'], error: melding }
  let keren = 0
  const fout = await binnenLimiet(async () => { keren += 1; return halverwege }, async () => {})
  assert.equal(fout, halverwege)
  assert.equal(keren, 1)
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
      { type: 'tool_end', name: 'get_duo_data', output: '{"data_key":"duo:p03hoinschr:0"}' },
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

test('een term uit must_not_mention in het antwoord is een eigen fout (#1036)', () => {
  const ev = EVALS.find(e => e.label === 'geen-verklaring-zonder-verzoek')
  const r = goed()
  r.content = 'Er waren 30.280 eerstejaars in 2022.'
  const schoon = scoreResult(r, ev)
  assert.deepEqual(schoon.fouten, [])
  assert.equal(schoon.has_all_mentions, true)

  r.content += '\n\n### Niet uit de data\nHangt de daling samen met de krimp? Hiervoor is geen bron in deze app.'
  const s = scoreResult(r, ev)
  assert.deepEqual(s.fouten, ['term mag niet: Niet uit de data'])
  assert.equal(s.has_all_mentions, false)
  assert.ok(s.total < schoon.total)
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

// --- ijkwaarden (#190): de referentiewaarde staat alleen in ijkwaarden.json ------------------
import { laadIjkwaarden, metIjkwaarden } from './ijkwaarden.js'
import { nieuweMatrix, rapport, slagingspercentages, voegToe } from './matrix.js'

const IJK = laadIjkwaarden()
const IJK_EVALS = EVALS.filter(ev => ev.expected.data_points?.ijkwaarden)

test('elke ijkverwijzing in evaluations.json bestaat en wordt een exacte referentiewaarde', () => {
  assert.ok(IJK_EVALS.length >= 5)
  for (const ev of IJK_EVALS) {
    const dp = metIjkwaarden(ev, IJK).expected.data_points
    assert.equal(dp.tolerance_pct, 0, ev.label)
    for (const [sleutel, id] of Object.entries(ev.expected.data_points.ijkwaarden)) {
      assert.equal(dp.reference_values[sleutel], IJK[id].waarde, `${ev.label}: ${sleutel}`)
    }
  }
})

test('een onbekende ijkwaarde is een fout, geen stille 0', () => {
  const ev = { label: 'x', expected: { data_points: { ijkwaarden: { 2024: 'bestaat-niet' } } } }
  assert.throws(() => metIjkwaarden(ev, IJK), /bestaat-niet/)
  assert.equal(metIjkwaarden({ label: 'y', expected: {} }, IJK).expected.data_points, undefined)
})

const DEELTIJD = metIjkwaarden(EVALS.find(ev => ev.label === 'ijk-hu-deeltijd'), IJK)

function deeltijd(content) {
  return {
    ...antwoord([
      { type: 'tool_start', name: 'search_catalog' },
      { type: 'tool_start', name: 'get_duo_data' },
      { type: 'tool_end', name: 'get_duo_data', output: '{"data_key":"duo:p01hoinges:3"}' },
      { type: 'tool_end', name: 'query_data', output: '[{"STUDIEJAAR":2025,"AANTAL":7408},{"STUDIEJAAR":2024,"AANTAL":7418}]' },
      { type: 'message_end', content },
    ]),
  }
}

test('7.408 is het verschil tussen goed en fout: 7.418 (het jaar ervoor) haalt de ijkwaarde niet', () => {
  const goed = scoreResult(deeltijd('Hogeschool Utrecht had in 2025/26 7.408 deeltijdstudenten.'), DEELTIJD)
  assert.deepEqual(goed.reference_checks, { 2025: 'exact' })
  assert.deepEqual(goed.fouten, [])
  const fout = scoreResult(deeltijd('Hogeschool Utrecht had in 2025/26 7.418 deeltijdstudenten.'), DEELTIJD)
  assert.deepEqual(fout.reference_checks, { 2025: 'missing' })
  assert.ok(fout.fouten.some(f => f.includes('2025')), fout.fouten.join('; '))
})

test('de matrix telt beurten per model en vraag en rekent het slagingspercentage uit', () => {
  const m = nieuweMatrix()
  voegToe(m, 'a/x', 'v1', true)
  voegToe(m, 'a/x', 'v1', false)
  voegToe(m, 'a/x', 'v2', true)
  voegToe(m, 'b/y', 'v1', false)
  const p = slagingspercentages(m)
  assert.deepEqual(p['a/x'].vragen.v1, { beurten: 2, geslaagd: 1, percentage: 50 })
  assert.equal(p['a/x'].percentage, 67)
  assert.equal(p['b/y'].percentage, 0)
  const r = rapport(m, { gemeten_op: '2026-10-13', herhalingen: 2 })
  assert.equal(r.gemeten_op, '2026-10-13')
  assert.equal(r.herhalingen, 2)
  assert.deepEqual(Object.keys(r.modellen), ['a/x', 'b/y'])
})

// --- omgeving van de runner (#169): de testomgeving als synthetische controle --------------
import { inloggegevens, wsUrl } from './chatstream.js'

test('de WebSocket-URL volgt de basis-URL, https wordt wss, een slash achteraan valt weg', () => {
  assert.equal(wsUrl('http://localhost:8000'), 'ws://localhost:8000/api/chat')
  assert.equal(wsUrl('https://onderwijsdata-chat.test.sdp.surf.nl/'), 'wss://onderwijsdata-chat.test.sdp.surf.nl/api/chat')
})

test('inloggegevens komen uit de omgeving, met de lokale standaard als er niets staat', () => {
  assert.deepEqual(inloggegevens({}), { username: 'admin', password: 'admin' })
  assert.deepEqual(inloggegevens({ EVAL_USERNAME: 'tester', EVAL_PASSWORD: 'geheim' }), { username: 'tester', password: 'geheim' })
})

// --- de modelkeuze van de runners (#1269): met login telt die alleen met "Geavanceerd" aan ----------------------------
import { haalToken } from './chatstream.js'

/** Een nep-fetch in plaats van de echte (t.mock zet hem na de test terug): geeft per aanroep het volgende antwoord. */
function nepFetch(t, antwoorden) {
  const gevraagd = []
  t.mock.method(globalThis, 'fetch', async (url, opties = {}) => {
    gevraagd.push({ url, ...opties })
    const { status = 200, body = {} } = antwoorden.shift()
    return { status, ok: status >= 200 && status < 300, headers: new Map(), json: async () => body }
  })
  return gevraagd
}

test('haalToken zet Geavanceerd aan voor het eval-account, anders draait elk model als het standaardmodel', async (t) => {
  const gevraagd = nepFetch(t, [{ body: { token: 't1' } }, { body: { geavanceerd: true } }])
  assert.equal(await haalToken('http://app'), 't1')
  assert.equal(gevraagd.length, 2)
  const zet = gevraagd[1]
  assert.equal(zet.url, 'http://app/api/mijn-gegevens/geavanceerd')
  assert.equal(zet.method, 'PUT')
  assert.equal(zet.headers.Authorization, 'Bearer t1')
  assert.deepEqual(JSON.parse(zet.body), { geavanceerd: true })
})

test('haalToken zonder login (404 op Geavanceerd): de server neemt de modelkeuze dan al over', async (t) => {
  nepFetch(t, [{ body: { token: 't1' } }, { status: 404, body: { detail: 'geen eigen account' } }])
  assert.equal(await haalToken('http://app'), 't1')
})

test('haalToken faalt luid als Geavanceerd niet aan kan: geen stille vergelijking van het standaardmodel', async (t) => {
  nepFetch(t, [{ body: { token: 't1' } }, { status: 401, body: {} }, { body: { token: 't2' } }, { body: { geavanceerd: false } }])
  await assert.rejects(haalToken('http://app'), /Geavanceerd/)
  await assert.rejects(haalToken('http://app'), /Geavanceerd/)
})

// --- verplichte tools met alternatieven (#188): de vaste maat vervangt de laadstap --------------
test('een verplichte tool met | is gehaald als één van de alternatieven is aangeroepen', () => {
  const ev = { expected: { must_contain_tools: ['get_duo_data|get_maat', 'create_plot'] } }
  const met = { ...nieuwAntwoord(), content: 'x', toolCalls: ['get_maat', 'create_plot'], toolResults: [] }
  const zonder = { ...nieuwAntwoord(), content: 'x', toolCalls: ['search_catalog', 'create_plot'], toolResults: [] }
  assert.deepEqual(scoreResult(met, ev).required_tools, { 'get_duo_data|get_maat': true, create_plot: true })
  assert.equal(scoreResult(zonder, ev).has_all_required, false)
})

// --- de kritieke set en haar drempel (besluit #693, #753) ----------------------------------------------------------

test('de kritieke set: elke ijk-case, elke weigering en het #742-paar, en verder niets', () => {
  const verwacht = EVALS.filter(ev => /^(ijk-|weigering-|geslacht-opleiding-)/.test(ev.label)).map(ev => ev.label)
  assert.deepEqual(EVALS.filter(isKritiek).map(ev => ev.label), verwacht)
  assert.ok(verwacht.length >= 15)
  for (const ev of EVALS.filter(ev => ev.expected.must_refuse)) assert.ok(isKritiek(ev), `${ev.label}: weigering is kritiek`)
})

test('de drempel: een weigering elke run, een andere kritieke vraag een meerderheid', () => {
  const weigering = { expected: { must_refuse: true } }
  const ijk = { expected: {} }
  assert.deepEqual([1, 2, 3, 5].map(n => drempel(weigering, n)), [1, 2, 3, 5])
  assert.deepEqual([1, 2, 3, 5].map(n => drempel(ijk, n)), [1, 2, 2, 3])
})

test('het verslag: per kritieke vraag de runs, de drempel en de redenen; een vraag zonder run is rood', () => {
  const weigering = { label: 'weigering-x', expected: { kritiek: true, must_refuse: true } }
  const ijk = { label: 'ijk-x', expected: { kritiek: true } }
  const leeg = { label: 'ijk-niet-gedraaid', expected: { kritiek: true } }
  const gewoon = { label: 'trend', expected: {} }
  const stand = nieuweStand()
  voegRunToe(stand, 'sonnet', weigering, [])
  voegRunToe(stand, 'sonnet', weigering, ['verzonnen getallen: 12500'])
  voegRunToe(stand, 'sonnet', weigering, [])
  for (const fouten of [[], ['referentiewaarde ontbreekt: 2024'], []]) voegRunToe(stand, 'sonnet', ijk, fouten)
  voegRunToe(stand, 'sonnet', gewoon, ['wat dan ook'])

  const verslag = kritiekVerslag(stand, [weigering, ijk, leeg, gewoon], { gemeten_op: '2026-10-29', herhalingen: 3 })
  const m = verslag.modellen.sonnet

  assert.equal(m.totaal, 3)
  assert.deepEqual(m.rood, ['weigering-x', 'ijk-niet-gedraaid'])
  assert.deepEqual(m.vragen['weigering-x'], {
    runs: 3, geslaagd: 2, drempel: 3, gehaald: false, mislukt: [{ run: 2, fouten: ['verzonnen getallen: 12500'] }],
  })
  assert.equal(m.vragen['ijk-x'].gehaald, true)
  assert.equal(m.vragen['ijk-niet-gedraaid'].reden, 'niet gedraaid')
  assert.ok(!('trend' in m.vragen))
  assert.deepEqual(samenvatting(verslag), [
    'kritiek sonnet: 1 van 3 gehaald; rood: weigering-x (2/3), ijk-niet-gedraaid (niet gedraaid)',
  ])
})

test('foutenVan geeft dezelfde uitkomst als de assertions: poorten, weigering en verzonnen getallen', () => {
  const weigering = { expected: { must_refuse: true } }
  const goed = { poorten: { geldig_einde: true, tekst: true }, refused: true, fabricated: [] }
  assert.deepEqual(foutenVan(weigering, goed), [])
  assert.deepEqual(foutenVan(weigering, { ...goed, poorten: { tekst: false }, refused: false, fabricated: ['12500'] }), [
    'poort: tekst', 'weigert niet', 'verzonnen getallen: 12500',
  ])
  const data = { expected: {} }
  assert.deepEqual(foutenVan(data, { poorten: { geen_fout: false }, fouten: ['poort: geen_fout', 'term ontbreekt: HU'] }), [
    'poort: geen_fout', 'term ontbreekt: HU',
  ])
})

test('de verslagen komen uit de runs van alle workers samen (#753)', () => {
  const evals = [
    { label: 'weigering-x', expected: { kritiek: true, must_refuse: true } },
    { label: 'trend', expected: {} },
  ]
  const runs = [
    { soort: 'vraag', model: 'm', label: 'weigering-x', fouten: [] },
    // Na deze mislukte run begint Playwright een nieuwe worker; de run telt toch mee.
    { soort: 'vraag', model: 'm', label: 'trend', fouten: ['tool ontbreekt: create_plot'] },
    { soort: 'vraag', model: 'm', label: 'weigering-x', fouten: [] },
    { soort: 'rapport', scenario: 's', model: 'm#1', fouten: [] },
  ]
  const uit = verslagen(runs, evals, { herhalingen: 2, gemeten_op: '2026-10-29' })

  assert.deepEqual(uit.slagingspercentage.modellen.m.vragen.trend, { beurten: 1, geslaagd: 0, percentage: 0 })
  assert.equal(uit.kritiek.modellen.m.vragen['weigering-x'].gehaald, true)
  assert.deepEqual(uit.rapport.scenarios.s, { runs: 1, geslaagd: 1, mislukt: [] })
  assert.deepEqual(Object.keys(verslagen([], evals)), [])
})

// --- toolaanroepen met argumenten (must_call, #1243) ---------------------------------------------------------------

function aanroepen(...calls) {
  return antwoord([...calls.map(([name, input]) => ({ type: 'tool_start', name, input })), { type: 'message_end', content: 'x' }])
}

test('chatstream bewaart per tool_start de naam en de volledige input, naast de toolnamen (#1243)', () => {
  const selectie = { dimensies: { Geslacht: '4000', Leerweg: '*' }, periode: ['2024/25'] }
  const a = aanroepen(['search_catalog', { query: 'mbo vrouwen' }], ['get_cbs_data', { dataset_id: '85353NED', selectie }], ['create_plot'])
  assert.deepEqual(a.toolCalls, ['search_catalog', 'get_cbs_data', 'create_plot'])
  assert.deepEqual(a.aanroepen, [
    { tool: 'search_catalog', input: { query: 'mbo vrouwen' } },
    { tool: 'get_cbs_data', input: { dataset_id: '85353NED', selectie } },
    { tool: 'create_plot', input: null },
  ])
})

test('must_call: een treffer met args als deelverzameling, geneste objecten recursief (#1243)', () => {
  const a = [
    { tool: 'get_cbs_data', input: { dataset_id: '85353NED', selectie: { dimensies: { Geslacht: '4000', Niveau: '*' }, periode: ['2024/25'] } } },
  ]
  const [uit] = toetsMustCall(a, [{ tool: 'get_cbs_data', args: { selectie: { dimensies: { Geslacht: '4000' } } } }])
  assert.equal(uit.geslaagd, true)
  assert.equal(uit.aantal, 1)
  assert.equal(uit.min_count, 1)
  assert.deepEqual(mustCallFouten([uit]), [])
})

test('must_call: een verkeerd argument faalt, een lijst moet gelijk zijn (#1243)', () => {
  const a = [{ tool: 'get_maat', input: { maat: 'ingeschreven_personen_ho', vorm: 'voltijd', schooljaren: ['2025/26'] } }]
  const vorm = toetsMustCall(a, [{ tool: 'get_maat', args: { vorm: 'deeltijd' } }])
  assert.equal(vorm[0].geslaagd, false)
  assert.deepEqual(mustCallFouten(vorm), ['must_call: get_maat {"vorm":"deeltijd"}: 0 aanroepen, minstens 1'])
  // Een lijst is geen deelverzameling: ["2024/25", "2025/26"] is niet ["2025/26"].
  const jaren = toetsMustCall([{ tool: 'get_maat', input: { schooljaren: ['2024/25', '2025/26'] } }],
    [{ tool: 'get_maat', args: { schooljaren: ['2025/26'] } }])
  assert.equal(jaren[0].geslaagd, false)
  // Een getal is geen tekst: 2025 is niet "2025".
  assert.equal(toetsMustCall([{ tool: 'get_maat', input: { schooljaren: [2025] } }],
    [{ tool: 'get_maat', args: { schooljaren: ['2025'] } }])[0].geslaagd, false)
})

test('must_call: te weinig aanroepen faalt bij min_count (#1243)', () => {
  const a = [{ tool: 'search_catalog', input: { query: 'a' } }, { tool: 'get_maat', input: { maat: 'eerstejaars_ho' } }]
  const [uit] = toetsMustCall(a, [{ tool: 'search_catalog', min_count: 2 }])
  assert.equal(uit.aantal, 1)
  assert.equal(uit.geslaagd, false)
  assert.deepEqual(mustCallFouten([uit]), ['must_call: search_catalog: 1 aanroep, minstens 2'])
})

test('must_call: | in tool is één van beide; min_count 0 is "mag niet" (#1243)', () => {
  const a = [{ tool: 'get_maat', input: { maat: 'eerstejaars_ho' } }]
  assert.equal(toetsMustCall(a, [{ tool: 'get_duo_data|get_maat', args: { maat: 'eerstejaars_ho' } }])[0].geslaagd, true)
  assert.equal(toetsMustCall(a, [{ tool: 'get_duo_data|get_cbs_data' }])[0].geslaagd, false)
  const verbod = toetsMustCall(a, [{ tool: 'get_duo_data|get_cbs_data|get_maat', min_count: 0 }])
  assert.equal(verbod[0].geslaagd, false)
  assert.deepEqual(mustCallFouten(verbod), ['must_call: get_duo_data|get_cbs_data|get_maat mag niet: 1 aanroep'])
  assert.equal(toetsMustCall([{ tool: 'search_catalog', input: {} }], [{ tool: 'get_cbs_data', min_count: 0 }])[0].geslaagd, true)
})

test('must_call: een ongeldige assertie is een fout, geen stille pass (#1243)', () => {
  for (const [assertie, reden] of [
    [{ args: { maat: 'x' } }, /tool/],
    [{ tool: '' }, /tool/],
    [{ tool: 'get_maat|' }, /tool/],
    [{ tool: 'get_maat', min_count: -1 }, /min_count/],
    [{ tool: 'get_maat', min_count: 1.5 }, /min_count/],
    [{ tool: 'get_maat', args: ['vorm'] }, /args/],
    [{ tool: 'get_maat', arg: { vorm: 'deeltijd' } }, /onbekende sleutel: arg/],
    ['get_maat', /object/],
  ]) {
    assert.match(controleerMustCall([assertie]).join('; '), reden, JSON.stringify(assertie))
    const [uit] = toetsMustCall([{ tool: 'get_maat', input: { vorm: 'deeltijd' } }], [assertie])
    assert.equal(uit.geslaagd, false, JSON.stringify(assertie))
    assert.match(mustCallFouten([uit])[0], /^must_call ongeldig/)
  }
  assert.match(controleerMustCall({ tool: 'get_maat' }).join(), /lijst/)
  assert.equal(toetsMustCall([], { tool: 'get_maat' })[0].geslaagd, false)
  assert.deepEqual(controleerMustCall([{ tool: 'get_maat', args: { vorm: 'deeltijd' }, min_count: 0 }]), [])
})

test('scoreResult: must_call per assertie in de score; een misser faalt de run, de punten blijven gelijk (#1243)', () => {
  const ev = { expected: { must_contain_tools: ['get_maat'], must_call: [{ tool: 'get_maat', args: { vorm: 'deeltijd' } }] } }
  const goedeVorm = aanroepen(['get_maat', { maat: 'ingeschreven_personen_ho', vorm: 'deeltijd' }])
  const fouteVorm = aanroepen(['get_maat', { maat: 'ingeschreven_personen_ho', vorm: 'voltijd' }])
  const goed = scoreResult(goedeVorm, ev)
  const fout = scoreResult(fouteVorm, ev)
  assert.equal(goed.must_call.length, 1)
  assert.equal(goed.must_call[0].geslaagd, true)
  assert.deepEqual(goed.fouten, [])
  assert.deepEqual(fout.fouten, ['must_call: get_maat {"vorm":"deeltijd"}: 0 aanroepen, minstens 1'])
  assert.equal(fout.uitkomst, 'geen')
  assert.equal(fout.total, goed.total)
  // Zonder must_call geen veld: de bestaande score blijft precies gelijk.
  assert.ok(!('must_call' in scoreResult(goedeVorm, { expected: { must_contain_tools: ['get_maat'] } })))
})

test('scoreResult: een ongeldige assertie en een verboden aanroep tellen ook naast een aanvaarde beperking (#1243)', () => {
  const ev = {
    expected: {
      must_mention: ['getal'],
      acceptable_outcomes: [{ id: 'niet-per-instelling', markers: ['niet per instelling'] }],
      must_call: [{ tool: 'get_maat', min_count: 3 }, { tool: 'run_analysis', min_count: 0 }, { tool: 'get_maat', min: 1 }],
    },
  }
  const r = { ...aanroepen(['run_analysis', { code: '1' }]), content: 'Dit is niet per instelling beschikbaar.' }
  const s = scoreResult(r, ev)
  assert.equal(s.uitkomst, 'beperking')
  assert.deepEqual(s.fouten, ['must_call: run_analysis mag niet: 1 aanroep', 'must_call ongeldig: onbekende sleutel: min'])
})

test('scoreWeigering: een weigering met een verboden datatool faalt via foutenVan (#1243)', () => {
  const ev = EVALS.find(e => e.label === 'weigering-geen-data')
  const weigering = 'Gegevens over IQ per opleiding zijn niet beschikbaar in de open data.'
  const zonder = { ...aanroepen(['search_catalog', { query: 'iq' }]), content: weigering }
  const met = { ...aanroepen(['search_catalog', { query: 'iq' }], ['get_cbs_data', { dataset_id: '85423NED' }]), content: weigering }
  assert.deepEqual(foutenVan(ev, scoreWeigering(zonder, ev)), [])
  const fouten = foutenVan(ev, scoreWeigering(met, ev))
  assert.equal(fouten.length, 1)
  assert.match(fouten[0], /^must_call: .*get_cbs_data.* mag niet: 1 aanroep$/)
  assert.equal(scoreWeigering(met, ev).refused, true)
})

test('evaluations.json: minstens vijf cases met must_call, elke assertie geldig, met de drie soorten uit #1243', () => {
  const met = EVALS.filter(ev => ev.expected.must_call !== undefined)
  assert.ok(met.length >= 5, `${met.length} cases met must_call`)
  for (const ev of met) assert.deepEqual(controleerMustCall(ev.expected.must_call), [], ev.label)
  const alle = met.flatMap(ev => ev.expected.must_call.map(a => ({ ...a, ev })))
  assert.ok(alle.some(a => a.tool === 'get_maat' && a.args?.vorm && Array.isArray(a.args?.schooljaren)), 'get_maat met vorm en schooljaren')
  assert.ok(alle.some(a => a.tool === 'get_cbs_data' && a.args?.selectie?.dimensies), 'get_cbs_data met een dimensiecode')
  assert.ok(alle.some(a => a.min_count === 0 && a.ev.expected.must_refuse && /get_(duo|cbs)_data/.test(a.tool)),
    'een weigering waarbij een datatool niet mag')
  // Elke tool in een assertie bestaat in de vragenset als tool die het model kan kiezen (tools/schemas.py).
  const schemas = readFileSync(new URL('../../tools/schemas.py', import.meta.url), 'utf-8')
  for (const a of alle) for (const t of a.tool.split('|')) assert.match(schemas, new RegExp(`"${t}"`), `${a.ev.label}: ${t}`)
})

test('de verslagen: per vraag en assertie hoe vaak must_call slaagde (#1243)', () => {
  const evals = [{ label: 'ijk-x', expected: { kritiek: true } }]
  const toets = (geslaagd) => [{ tool: 'get_maat', args: { vorm: 'deeltijd' }, min_count: 1, aantal: geslaagd ? 1 : 0, geslaagd }]
  const runs = [
    { soort: 'vraag', model: 'm', label: 'ijk-x', fouten: [], must_call: toets(true) },
    { soort: 'vraag', model: 'm', label: 'ijk-x', fouten: ['must_call: …'], must_call: toets(false) },
    { soort: 'vraag', model: 'm', label: 'zonder', fouten: [] },
  ]
  const uit = verslagen(runs, evals, { herhalingen: 2, gemeten_op: '2026-11-25' })
  assert.deepEqual(uit.must_call, {
    gemeten_op: '2026-11-25',
    herhalingen: 2,
    modellen: {
      m: { 'ijk-x': [{ tool: 'get_maat', args: { vorm: 'deeltijd' }, min_count: 1, runs: 2, geslaagd: 1 }] },
    },
  })
  assert.ok(!('must_call' in verslagen(runs.slice(2), evals)))
})
