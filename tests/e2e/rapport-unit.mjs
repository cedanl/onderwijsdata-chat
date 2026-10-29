// Unittest voor de rapporteval (#752), zonder app en zonder LLM.
// Bewust geen *.test.js: Playwright (testDir tests/e2e) zou hem dan als e2e-test oppakken.
// Run: node --test tests/e2e/rapport-unit.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { gesprekFouten, rapportFouten, rapportVerslag, reekslabels, voorstel } from './rapportscore.js'

const SCENARIOS = JSON.parse(readFileSync(new URL('./rapportscenarios.json', import.meta.url), 'utf-8')).scenarios
const BIJSTURING = SCENARIOS.find(s => s.label === 'rapport-bijsturing-wo')
const LAATSTE = SCENARIOS.find(s => s.label === 'rapport-laatste-antwoord')

const WO = 'Hoe ontwikkelt de instroom in de wo-bachelors B Computing Science, B Informatica en B Computer Science zich?'
const WO_BRON = {
  bron: 'DUO',
  dataset: 'p02ho1ejrs',
  tekst: 'DUO · Eerstejaars (p02ho1ejrs), bestand Eerstejaarsingeschrevenen wetenschappelijk onderwijs niveau opleiding',
  url: 'https://onderwijsdata.duo.nl/datasets/p02ho1ejrs/resources/abc',
}
const HBO_BRON = { ...WO_BRON, tekst: WO_BRON.tekst.replace('wetenschappelijk onderwijs', 'hoger beroepsonderwijs') }

const geldig = content => ({ content, einde: 'geldig', toolCalls: [], toolResults: [] })
const grafiek = (namen, bron = WO_BRON) => ({
  titel: 'Instroom',
  figure_json: JSON.stringify({ data: namen.map(name => ({ name, x: ['2021/22', '2022/23'], y: [10, 12] })) }),
  bron,
})
const spec = extra => ({ title: WO, onderzoeksvraag: WO, visualisaties: [grafiek(['B Informatica', 'B Computing Science'])], ...extra })

test('het voorstel is de regel Onderzoeksvraag van het laatste antwoord dat er een heeft, zoals in de app', () => {
  const beurten = [
    { vraag: BIJSTURING.berichten[0], antwoord: geldig('**Onderzoeksvraag:** Hoe ontwikkelt de instroom in wo en hbo zich?') },
    { vraag: BIJSTURING.berichten[1], antwoord: geldig(`**Onderzoeksvraag:** ${WO}\n\nAlleen het wo.`) },
    { vraag: 'Genereer een rapport dat ingaat op je laatste antwoord', antwoord: geldig('Gebruik de knop.') },
  ]
  assert.equal(voorstel(beurten), WO)
  // Een afgebroken antwoord telt niet: de regel kan een halve zin zijn.
  beurten[1].antwoord = { ...beurten[1].antwoord, einde: 'afgebroken' }
  assert.equal(voorstel(beurten), 'Hoe ontwikkelt de instroom in wo en hbo zich?')
})

test('een rapport dat de bijsturing volgt, slaagt', () => {
  assert.deepEqual(rapportFouten({ spec: spec() }, BIJSTURING.verwachting, WO), [])
})

test('een grafiek uit het hbo-bestand of met een hbo- of verwante reeks faalt, met de reden', () => {
  const hbo = rapportFouten({ spec: spec({ visualisaties: [grafiek(['B Informatica'], HBO_BRON)] }) }, BIJSTURING.verwachting, WO)
  assert.ok(hbo.some(f => f.includes('bron /hoger beroepsonderwijs/')), hbo.join('\n'))

  const reeksen = rapportFouten(
    { spec: spec({ visualisaties: [grafiek(['B Informatica', 'B HBO-ICT', 'B Technische Informatica'])] }) },
    BIJSTURING.verwachting,
    WO,
  )
  assert.ok(reeksen.some(f => f.includes('HBO-ICT')), reeksen.join('\n'))
  assert.ok(reeksen.some(f => f.includes('Technische Informatica')), reeksen.join('\n'))
})

test('een onderzoeksvraag die niet de bevestigde is, of geen wo noemt, faalt', () => {
  const fouten = rapportFouten({ spec: spec({ onderzoeksvraag: 'Hoe ontwikkelt de instroom zich?' }) }, BIJSTURING.verwachting, WO)
  assert.ok(fouten.some(f => f.startsWith('onderzoeksvraag is niet de bevestigde')), fouten.join('\n'))
  assert.ok(fouten.some(f => f.startsWith('onderzoeksvraag noemt /')), fouten.join('\n'))
})

test('het laatste antwoord: de bron van de tweede vraag moet in een grafiek staan', () => {
  const uu = 'Hoe ontwikkelde het aantal eerstejaars bij de Universiteit Utrecht zich van 2021/22 tot en met 2025/26?'
  const goed = { spec: { onderzoeksvraag: uu, visualisaties: [grafiek(['Universiteit Utrecht'])] } }
  assert.deepEqual(rapportFouten(goed, LAATSTE.verwachting, uu), [])

  const p01 = { ...WO_BRON, dataset: 'p01hoinges', tekst: 'DUO · Ingeschrevenen (p01hoinges)', url: '' }
  const fout = { spec: { onderzoeksvraag: uu, visualisaties: [grafiek(['Hogeschool Utrecht'], p01)] } }
  assert.deepEqual(rapportFouten(fout, LAATSTE.verwachting, uu), ['geen grafiek met bron /p02ho1ejrs/'])
})

test('geen rapport, een fout of een time-out is altijd niet geslaagd', () => {
  assert.deepEqual(rapportFouten({ timeout: true }, BIJSTURING.verwachting, WO), ['rapport: time-out'])
  assert.deepEqual(rapportFouten({ error: 'De cijfers klopten niet' }, BIJSTURING.verwachting, WO), ['rapport: De cijfers klopten niet'])
  assert.ok(rapportFouten({ spec: spec({ visualisaties: [] }) }, BIJSTURING.verwachting, WO)[0].startsWith('0 grafieken'))
})

test('een mislukte beurt is een fout van het gesprek, vóór het rapport', () => {
  const beurten = [
    { vraag: 'a', antwoord: geldig('ok') },
    { vraag: 'b', antwoord: { ...geldig(''), einde: null, error: 'verbinding gesloten (1006)' } },
  ]
  assert.deepEqual(gesprekFouten(beurten), ['beurt 2 ("b"): verbinding gesloten (1006)'])
})

test('de reekslabels komen uit namen en categorieën, ook uit een figure_json als object', () => {
  const vis = { figure_json: { data: [{ name: 'B Informatica', x: ['Universiteit Leiden', 2021], y: [1, 2] }] } }
  assert.deepEqual(reekslabels(vis), ['B Informatica', 'Universiteit Leiden'])
  assert.deepEqual(reekslabels({ figure_json: 'geen json' }), [])
})

test('het verslag telt per scenario de geslaagde runs en bewaart de redenen', () => {
  const verslag = rapportVerslag(
    [
      { scenario: 's', model: 'm#1', fouten: [] },
      { scenario: 's', model: 'm#2', fouten: ['rapport: time-out'] },
    ],
    { gemeten_op: '2026-10-29', herhalingen: 2 },
  )
  assert.deepEqual(verslag, {
    gemeten_op: '2026-10-29',
    herhalingen: 2,
    scenarios: { s: { runs: 2, geslaagd: 1, mislukt: [{ model: 'm#2', fouten: ['rapport: time-out'] }] } },
  })
})

test('elk scenario is een gesprek met een verwachting die de controles kennen', () => {
  const bekend = new Set([
    'min_visualisaties', 'onderzoeksvraag_is_voorstel', 'onderzoeksvraag_noemt', 'onderzoeksvraag_niet',
    'bron_wel', 'bron_niet', 'reeksen_niet',
  ])
  assert.ok(SCENARIOS.length >= 2)
  for (const s of SCENARIOS) {
    assert.ok(s.label && s.description, JSON.stringify(s))
    assert.ok(s.berichten.length >= 2, s.label)
    for (const [sleutel, waarde] of Object.entries(s.verwachting)) {
      assert.ok(bekend.has(sleutel), `${s.label}: onbekende verwachting ${sleutel}`)
      if (Array.isArray(waarde)) for (const p of waarde) new RegExp(p, 'i')
    }
  }
})
