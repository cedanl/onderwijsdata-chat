// @vitest-environment jsdom
// Dashboardcijfers heten wat ze tellen en tellen op tot hun totaal (#899); ontbreekt is geen 0 (#902); één groeiregel
// en een landelijk getal dat zegt wat het is (#903).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createElement, act } from 'react'
import { createRoot } from 'react-dom/client'

vi.mock('react-chartjs-2', () => ({
  Bar: function BarStub({ data }) { return createElement('pre', { 'data-chart': 'bar' }, JSON.stringify(data)) },
  Line: function LineStub({ data }) { return createElement('pre', { 'data-chart': 'line' }, JSON.stringify(data)) },
}))

import { buildLeerwegenData, buildSectorTrendData, HoofdgroepenChart, LEERWEGEN_MBO } from '../components/dashboards/shared/charts-sector'
import { OndergrensNoot, isOndergrens } from '../components/dashboards/shared/ondergrens'
import { pctVrouwFromGeslacht } from '../components/dashboards/mijn-instelling/gender-section'
import { verdeelCohorten } from '../components/dashboards/mijn-instelling/rendement-section'
import { buildMarktaandeelPerSector, LandelijkDefinitie, studentenTekst } from '../components/dashboards/nationaal/index'
import { buildBenchmarkLineData, buildPeerLinesData, groeiPct, groeiStartjaar } from '../components/dashboards/shared/chart-builders'
import { buildGroeiRankingData, GroeiRankingChart } from '../components/dashboards/shared/charts-markt'
import { PeersTable } from '../components/dashboards/shared/charts-peers'
import { buildIndexChartOpts } from '../components/dashboards/shared/chart-opts'

let container
let root
function render(el) {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root.render(el))
  return container
}
afterEach(() => {
  if (root) act(() => root.unmount())
  container?.remove()
  root = container = undefined
})

describe('mbo-leerwegen (#899)', () => {
  it('tekent Extraneus mee, zodat de leerwegen optellen tot het totaal ingeschrevenen', () => {
    const leerwegen = {
      2024: { BBL: 4000, 'BOL voltijd': 14000, 'BOL deeltijd': 0, Extraneus: 200 },
      2025: { BBL: 4100, 'BOL voltijd': 14100, 'BOL deeltijd': 0, Extraneus: 234 },
    }
    const data = buildLeerwegenData(leerwegen)

    expect(LEERWEGEN_MBO).toContain('Extraneus')
    expect(data.datasets.map(d => d.label)).toEqual(LEERWEGEN_MBO)
    const som2025 = data.datasets.reduce((s, d) => s + d.data[1], 0)
    expect(som2025).toBe(4100 + 14100 + 234)
  })
})

describe('HoofdgroepenChart (#899)', () => {
  it('noemt TOTAAL MBO ingeschrevenen, geen eerstejaars of sectorkamers', () => {
    const el = render(createElement(HoofdgroepenChart, { perHoofdgroep: { 'Zorg en welzijn': 5000, Entree: 300 }, dark: false }))
    const tekst = el.textContent

    expect(tekst).toContain('Ingeschrevenen per hoofdgroep')
    expect(tekst).toContain('Geen eerstejaars')
    expect(tekst).not.toMatch(/sectorkamer/i)
    expect(tekst).not.toMatch(/eerstejaars per hoofdgroep/i)
    const data = JSON.parse(el.querySelector('[data-chart="bar"]').textContent)
    expect(data.datasets[0].label).toBe('Ingeschrevenen')
    expect(data.labels).toEqual(['Zorg en welzijn', 'Entree'])
  })

  it('noemt het schooljaar van het hoofdgroep-bestand, niet "laatste jaar" (#934)', () => {
    const el = render(createElement(HoofdgroepenChart, { perHoofdgroep: { Entree: 300 }, jaar: 2025, soort: 'schooljaar', dark: false }))

    expect(el.textContent).toContain('2025/26')
    expect(el.textContent).not.toMatch(/laatste jaar/i)
  })
})

describe('ontbrekende waarden blijven een gat (#902)', () => {
  it('tekent een sector zonder waarde in een jaar als gat, niet als val naar 0', () => {
    const data = buildSectorTrendData({ ECONOMIE: { 2023: 100, 2025: 120 }, TECHNIEK: { 2023: 50, 2024: 55, 2025: 60 } })

    expect(data.labels).toEqual(['2023', '2024', '2025'])
    expect(data.datasets[0].data).toEqual([100, null, 120])
  })

  it('tekent een leerweg zonder waarde als gat', () => {
    const data = buildLeerwegenData({ 2023: { BBL: 300, 'BOL voltijd': 2000 }, 2025: { BBL: 310, 'BOL voltijd': 2100, 'BOL deeltijd': 0, Extraneus: 5 } })

    expect(data.datasets.find(d => d.label === 'Extraneus').data).toEqual([null, 5])
    expect(data.datasets.find(d => d.label === 'BOL deeltijd').data).toEqual([null, 0])
  })

  it('geeft geen aandeel vrouw als vrouw of man ontbreekt', () => {
    expect(pctVrouwFromGeslacht({ VROUW: 60 })).toBeNull()
    expect(pctVrouwFromGeslacht({ VROUW: 60, MAN: 40 })).toBe(60)
  })

  it('laat een sector zonder eigen of landelijke waarde weg en noemt hem, aflopend op aandeel', () => {
    const uit = buildMarktaandeelPerSector(
      { ECONOMIE: { 2025: 50 }, TECHNIEK: { 2025: 300 }, ONDERWIJS: { 2024: 10 }, BOLDT: { 2025: 0 } },
      { ECONOMIE: { 2025: 1000 }, TECHNIEK: { 2025: 1000 }, ONDERWIJS: { 2024: 500 }, BOLDT: { 2025: 100 } },
    )

    expect(uit.jaar).toBe(2025)
    expect(uit.data.labels).toEqual(['Techniek', 'Economie'])
    expect(uit.data.datasets[0].data).toEqual([30, 5])
    expect(uit.weggelaten).toEqual(['Onderwijs', 'BOLDT'])
  })

  it('noemt de populatie van de noemer in de reeksnaam van het marktaandeel (#950)', () => {
    const eigen = { RECHT: { 2025: 300 } }
    const landelijk = { RECHT: { 2025: 3000 } }

    expect(buildMarktaandeelPerSector(eigen, landelijk, { soort: 'wo', n: 18 }).data.datasets[0].label)
      .toBe('Aandeel van alle wo-studenten (%)')
    expect(buildMarktaandeelPerSector(eigen, landelijk, { soort: 'hbo', n: 36 }).data.datasets[0].label)
      .toBe('Aandeel van alle hbo-studenten (%)')
    expect(studentenTekst({ soort: 'mbo' })).toBe('alle mbo-studenten')
    expect(studentenTekst(undefined)).toBe('alle studenten')
  })

  it('verdeelt de cohorten in getoond, meer diploma\'s dan instroom en zonder diplomajaar', () => {
    const { rows, teVeel, zonderDiploma } = verdeelCohorten([
      { instroom_jaar: 2019, instroom: 100, gediplomeerden_t3: 60, gediplomeerden_t4: 70, gediplomeerden_t5: null },
      { instroom_jaar: 2020, instroom: 100, gediplomeerden_t3: 140, gediplomeerden_t4: null, gediplomeerden_t5: null },
      { instroom_jaar: 2023, instroom: 100, gediplomeerden_t3: null, gediplomeerden_t4: null, gediplomeerden_t5: null },
    ])

    expect(rows.map(c => c.instroom_jaar)).toEqual([2019])
    expect(teVeel).toEqual([2020])
    expect(zonderDiploma).toEqual([2023])
  })
})

describe('een som over onderdrukte cellen is een ondergrens (#902)', () => {
  it('herkent een jaar met lege cellen, ook met de jaarsleutel als tekst', () => {
    expect(isOndergrens({ 2023: 2 }, 2023)).toBe(true)
    expect(isOndergrens({ 2023: 2 }, '2023')).toBe(true)
    expect(isOndergrens({ 2023: 2 }, 2024)).toBe(false)
    expect(isOndergrens(undefined, 2024)).toBe(false)
  })

  it('zegt "ten minste" met de jaren per reeks, en niets zonder lege cellen', () => {
    const el = render(createElement(OndergrensNoot, { reeksen: [
      { label: 'Ingeschrevenen', onderdrukt: { 2024: 1, 2022: 3 } },
      { label: 'Eerstejaars', onderdrukt: {} },
    ] }))

    expect(el.textContent).toContain('Ingeschrevenen in 2022, 2024: ten minste')
    expect(el.textContent).not.toContain('Eerstejaars')
  })

  it('toont geen noot zonder onderdrukte cellen', () => {
    const el = render(createElement(OndergrensNoot, { reeksen: [{ label: 'Ingeschrevenen', onderdrukt: undefined }] }))

    expect(el.textContent).toBe('')
  })
})

describe('één groeiregel voor grafiek, ranking en tabel (#903)', () => {
  // Peer B begint pas in 2022; het gemeenschappelijke startjaar is dan 2022 voor iedereen.
  const DATA = {
    laatste_jaar: 2025,
    ingeschrevenen: { 2021: 1000, 2022: 1100, 2023: 1150, 2025: 1210 },
    benchmark: {
      peers: {
        ingeschrevenen: {
          'Peer A': { 2021: 500, 2022: 400, 2025: 600 },
          'Peer B': { 2022: 200, 2023: 210, 2025: 300 },
        },
      },
    },
  }

  it('kiest het laatste van de eerste jaren met een waarde, en negeert een reeks van één jaar', () => {
    expect(groeiStartjaar([DATA.ingeschrevenen, ...Object.values(DATA.benchmark.peers.ingeschrevenen)])).toBe(2022)
    expect(groeiStartjaar([{ 2021: 1, 2022: 2 }, { 2025: 9 }])).toBe(2021)
    expect(groeiPct({ 2022: 200, 2025: 300 }, 2022, 2025)).toBe(50)
    expect(groeiPct({ 2023: 200, 2025: 300 }, 2022, 2025)).toBeNull()
  })

  it('geeft in de lijnen, de ranking en de tabel hetzelfde groeicijfer per instelling', () => {
    const lijnen = buildPeerLinesData(DATA.ingeschrevenen, DATA.benchmark.peers.ingeschrevenen, 'Eigen', '#000', '#999')
    const ranking = buildGroeiRankingData(DATA, 'Eigen', false)
    const laatste = lijnen.labels.indexOf('2025')
    const lijnGroei = Object.fromEntries(lijnen.datasets.map(d => [d.label, d.data[laatste]]))
    const rankingGroei = Object.fromEntries(ranking.labels.map((naam, i) => [naam, ranking.datasets[0].data[i]]))

    expect(lijnen.startjaar).toBe(2022)
    expect(ranking.startjaar).toBe(2022)
    expect(rankingGroei).toEqual({ Eigen: 10, 'Peer A': 50, 'Peer B': 50 })
    expect(lijnGroei).toEqual(rankingGroei)

    const el = render(createElement(PeersTable, { data: DATA, instelling: 'Eigen' }))
    expect(el.textContent).toContain('Groei (2022–2025)')
    const tabelGroei = Object.fromEntries([...el.querySelectorAll('tbody tr')].map(tr => {
      const cellen = [...tr.querySelectorAll('td')].map(td => td.textContent)
      return [cellen[1].replace(' ★', ''), Number(cellen[3].replace('%', ''))]
    }))
    expect(tabelGroei).toEqual(rankingGroei)
  })

  it('zet het startjaar in de kop van de groeiranking', () => {
    const el = render(createElement(GroeiRankingChart, { data: buildGroeiRankingData(DATA, 'Eigen', false), dark: false }))

    expect(el.textContent).toContain('Groei ingeschrevenen 2022–2025')
    expect(el.textContent).not.toContain('eerste')
  })

  it('noemt op de as het startjaar, niet het eerste jaar van elke reeks', () => {
    expect(buildIndexChartOpts(false).scales.y.title.text).toBe('% verandering t.o.v. het startjaar')
  })

  it('rekent eigen instelling en benchmark t.o.v. hetzelfde jaar', () => {
    const data = buildBenchmarkLineData({ 2021: 100, 2022: 110, 2023: 121 }, { 2022: 50, 2023: 55 }, 'Eigen', 'Regio', '#000', '#999')

    expect(data.startjaar).toBe(2022)
    expect(data.datasets[0].data).toEqual([-9, 0, 10])
    expect(data.datasets[1].data).toEqual([null, 0, 10])
  })
})

describe('een peer zonder gegevens (#925)', () => {
  it('staat in de concurrententabel met "geen gegevens", onderaan en zonder rang', () => {
    const data = {
      laatste_jaar: 2025,
      ingeschrevenen: { 2024: 1000, 2025: 1100 },
      benchmark: {
        peers: { ingeschrevenen: { 'Peer A': { 2024: 500, 2025: 600 } } },
        geen_gegevens: { ingeschrevenen: ['BBO de Schalm'] },
      },
    }

    const el = render(createElement(PeersTable, { data, instelling: 'Eigen' }))
    const rijen = [...el.querySelectorAll('tbody tr')].map(tr => [...tr.querySelectorAll('td')].map(td => td.textContent))

    expect(rijen.map(r => r[1])).toEqual(['Eigen ★', 'Peer A', 'BBO de Schalm'])
    expect(rijen[2]).toEqual(['—', 'BBO de Schalm', 'geen gegevens', '—'])
    expect(el.textContent).toContain('3 instellingen in de benchmark-regio')
  })
})

describe('landelijk zegt wat het telt (#903)', () => {
  it('noemt de DUO-som en de CBS-tabel van de chat', () => {
    const el = render(createElement(LandelijkDefinitie, { landelijk: {
      definitie: 'de som van DUO p01hoinges over alle universiteiten',
      verschil_met_chat: 'De chat geeft het landelijke aantal uit de CBS-tabel 85423NED.',
    } }))

    expect(el.textContent).toContain('Landelijk is hier de som van DUO p01hoinges')
    expect(el.textContent).toContain('85423NED')
  })
})
