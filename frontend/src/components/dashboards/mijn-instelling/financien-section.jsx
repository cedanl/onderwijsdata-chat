import { useMemo } from 'react'
import TabelScroll from '../../TabelScroll'
import { CHART_COLORS } from '../../../constants'
import { SectionHeader, ChartCard, Grafiek, fmt, darkColors, benchmarkColor } from '../shared/index'

// Financiën van het bestuur (#935): de payload van /api/dashboard/financien, met de uitkomst van tools/financien.py
// (`voor_instelling`). De pagina rekent niets: elk getal, verschil en signaal komt uit de payload. Een waarde die in de
// bron ontbreekt, is null en staat er als "—", nooit als 0. Een signaal is geen oordeel; geen ranking van besturen.

const NOOT = { fontSize: '12.5px', color: 'var(--muted-text)' }
const CEL = { textAlign: 'right', padding: '5px 8px', verticalAlign: 'top' }

// De kengetallen in de volgorde van de tabel; `signaal`: de Inspectie heeft er een signaleringswaarde voor.
export const KENGETALLEN = [
  { sleutel: 'solvabiliteit_1', naam: 'Solvabiliteit I' },
  { sleutel: 'solvabiliteit_2', naam: 'Solvabiliteit II', signaal: true },
  { sleutel: 'liquiditeit', naam: 'Liquiditeit', signaal: true },
  { sleutel: 'rentabiliteit_procent', naam: 'Rentabiliteit', procent: true },
]
const NAAM = Object.fromEntries(KENGETALLEN.map(k => [k.sleutel, k.naam]))

const metEenheid = (waarde, procent) => (waarde == null ? '—' : `${fmt(waarde)}${procent ? '%' : ''}`)

// De signaleringswaarde per verslagjaar: bij solvabiliteit II één grens, bij de liquiditeit een per trede van de baten.
export function grensPerJaar(fin, reeks, sleutel) {
  if (sleutel === 'solvabiliteit_2') return reeks.map(() => fin.solvabiliteit_2_signaleringswaarde ?? null)
  if (sleutel === 'liquiditeit') return reeks.map(j => j.liquiditeit_signaleringswaarde ?? null)
  return null
}

// "2025: Solvabiliteit II 0,25 onder de signaleringswaarde 0,3": per verslagjaar de signalen uit de payload, nieuwste eerst.
export function signaalRegels(reeks) {
  return [...reeks]
    .sort((a, b) => b.verslagjaar - a.verslagjaar)
    .filter(j => j.signaleringen?.length)
    .map(j => `${j.verslagjaar}: ${j.signaleringen.map(s => (
      `${NAAM[s.kengetal] ?? s.kengetal} ${fmt(s.waarde)} onder de signaleringswaarde ${fmt(s.signaleringswaarde)}${s.trede ? ` (${s.trede})` : ''}`
    )).join('; ')}`)
}

function KengetalChart({ fin, eenheid, kengetal, dark }) {
  const { tick, grid, label } = darkColors(dark)
  const sector = fin.sectorcijfer?.sector
  const reeks = eenheid.reeks
  const data = useMemo(() => {
    const waarde = rol => reeks.map(j => j[kengetal.sleutel]?.[rol] ?? null)
    const datasets = [
      { label: fin.bestuur?.naam || 'Bestuur', data: waarde('bestuur'), borderColor: CHART_COLORS[0], backgroundColor: CHART_COLORS[0] + '33', borderWidth: 3, tension: 0.2 },
      { label: `Sector ${sector} (gewogen, Inspectie)`, data: waarde('sector'), borderColor: benchmarkColor(dark), backgroundColor: benchmarkColor(dark) + '33', borderWidth: 2, borderDash: [5, 4], tension: 0.2 },
    ]
    const grens = grensPerJaar(fin, reeks, kengetal.sleutel)
    if (grens?.some(g => g != null)) {
      datasets.push({ label: 'Signaleringswaarde Inspectie', data: grens, borderColor: tick, backgroundColor: 'transparent', borderWidth: 1.5, borderDash: [2, 3], pointRadius: 0, stepped: 'middle' })
    }
    return { labels: reeks.map(j => String(j.verslagjaar)), datasets }
  }, [fin, reeks, kengetal.sleutel, sector, dark, tick])
  const eenheidTekst = kengetal.procent ? '%' : ''
  return (
    <ChartCard title={kengetal.naam} subtitle={`Per verslagjaar — bestuur vs. sectorcijfer ${sector}${kengetal.signaal ? '; stippellijn: signaleringswaarde van de Inspectie' : ''}`}>
      <Grafiek soort="line" data={data} hoogte={240} categorie="Verslagjaar" options={{
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: 'top', labels: { color: label, boxWidth: 14 } },
          tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${metEenheid(ctx.raw, kengetal.procent)}` } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: tick } },
          y: { grid: { color: grid }, ticks: { color: tick, callback: v => `${fmt(v)}${eenheidTekst}` } },
        },
      }} />
    </ChartCard>
  )
}

// Eén cel: het bestuur, daaronder het sectorcijfer; een signaal staat er in woorden bij, niet alleen als kleur.
function KengetalCel({ jaar, kengetal }) {
  const waarde = jaar[kengetal.sleutel] || {}
  const signaal = jaar.signaleringen?.find(s => s.kengetal === kengetal.sleutel)
  return (
    <td style={CEL}>
      <div>{metEenheid(waarde.bestuur, kengetal.procent)}</div>
      <div style={NOOT}>sector {metEenheid(waarde.sector, kengetal.procent)}</div>
      {signaal && <div style={{ ...NOOT, fontWeight: 600 }}>onder {fmt(signaal.signaleringswaarde)}</div>}
    </td>
  )
}

function KengetallenTabel({ fin, eenheid, dark }) {
  const { tick } = darkColors(dark)
  const titel = `Kengetallen ${eenheid.naam}`
  return (
    <ChartCard title="Kengetallen per verslagjaar" subtitle={`Bestuur, met het gewogen sectorcijfer ${fin.sectorcijfer?.sector} van de Inspectie eronder`}>
      <TabelScroll label={titel} style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem', color: tick }}>
        <caption className="sr-only">{`${titel}: per verslagjaar het bestuur en het sectorcijfer`}</caption>
        <thead>
          <tr style={{ borderBottom: '2px solid var(--gray-200)' }}>
            <th scope="col" style={{ textAlign: 'left', padding: '6px 8px' }}>Verslagjaar</th>
            {KENGETALLEN.map(k => <th key={k.sleutel} scope="col" style={{ textAlign: 'right', padding: '6px 8px' }}>{k.naam}{k.procent ? ' (%)' : ''}</th>)}
            <th scope="col" style={{ textAlign: 'right', padding: '6px 8px' }}>Rijksbijdragen (mln €)</th>
          </tr>
        </thead>
        <tbody>
          {[...eenheid.reeks].sort((a, b) => b.verslagjaar - a.verslagjaar).map(j => (
            <tr key={j.verslagjaar} style={{ borderBottom: '1px solid var(--gray-100)' }}>
              <th scope="row" style={{ textAlign: 'left', padding: '5px 8px', fontWeight: 400, verticalAlign: 'top' }}>
                {j.verslagjaar}
                <div style={NOOT}>{j.variant}</div>
              </th>
              {KENGETALLEN.map(k => <KengetalCel key={k.sleutel} jaar={j} kengetal={k} />)}
              <td style={CEL}>{fmt(j.rijksbijdragen_mln_eur)}</td>
            </tr>
          ))}
        </tbody>
      </TabelScroll>
      <p style={{ ...NOOT, margin: '8px 0 0' }}>— : de waarde ontbreekt in de bron (geen 0). De variant staat onder het verslagjaar.</p>
    </ChartCard>
  )
}

function Signalen({ fin, eenheid }) {
  const regels = signaalRegels(eenheid.reeks)
  const waarden = fin.signaleringswaarden || {}
  const bron = waarden.bron ? `${waarden.bron}${waarden.jaar ? ` (${waarden.jaar})` : ''}` : 'de Inspectie'
  return (
    <div className="dashboard-noot" role="note" style={{ ...NOOT, margin: '0 0 16px' }}>
      <p style={{ margin: '0 0 4px' }}><strong>Signalen (geen oordeel).</strong> Signaleringswaarden: {bron}.</p>
      {regels.length
        ? <ul style={{ margin: 0, paddingLeft: 18 }}>{regels.map(r => <li key={r}>{r}.</li>)}</ul>
        : <p style={{ margin: 0 }}>In deze verslagjaren ligt geen kengetal onder een signaleringswaarde.</p>}
    </div>
  )
}

function Voorbehouden({ fin }) {
  return (
    <div className="dashboard-noot" role="note" style={{ ...NOOT, margin: '0 0 16px' }}>
      <p style={{ margin: '0 0 4px' }}><strong>Voorbehouden</strong></p>
      <ul style={{ margin: '0 0 8px', paddingLeft: 18 }}>{(fin.voorbehouden || []).map(v => <li key={v}>{v}</li>)}</ul>
      <details>
        <summary>Wat de kengetallen meten</summary>
        <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>{Object.entries(fin.definities || {}).map(([k, d]) => <li key={k}>{d}</li>)}</ul>
      </details>
    </div>
  )
}

function Eenheid({ fin, eenheid, dark }) {
  return (
    <>
      {eenheid.melding && <p className="dashboard-noot" role="note" style={{ ...NOOT, margin: '0 0 12px' }}>{eenheid.melding}</p>}
      <Signalen fin={fin} eenheid={eenheid} />
      <KengetallenTabel fin={fin} eenheid={eenheid} dark={dark} />
      {KENGETALLEN.filter(k => k.sleutel !== 'solvabiliteit_1').map(k => (
        <KengetalChart key={k.sleutel} fin={fin} eenheid={eenheid} kengetal={k} dark={dark} />
      ))}
    </>
  )
}

const TITEL = 'Financiën van het bestuur'

export function FinancienSection({ data, dark }) {
  if (!data?.gevonden) return null
  if (data.melding) {
    return (
      <>
        <SectionHeader title={TITEL} />
        <p className="dashboard-noot" role="note" style={{ ...NOOT, margin: '0 0 16px' }}>{data.melding}</p>
      </>
    )
  }
  const fin = data.financien
  if (!fin) return null // niet geladen: de melding staat bovenaan (niet_beschikbaar)
  const bestuur = fin.bestuur || {}
  const jaren = fin.bron?.editie ? `, ${fin.bron.editie}` : ''
  return (
    <>
      <SectionHeader title={TITEL} subtitle={`${bestuur.naam} (bestuur ${bestuur.nummer})${jaren}; DUO, financiële verantwoording uit XBRL`} />
      {(fin.meldingen || []).map(m => <p key={m} className="dashboard-noot" role="note" style={{ ...NOOT, margin: '0 0 8px' }}>{m}</p>)}
      {(fin.eenheden || []).map(e => <Eenheid key={e.eenheid} fin={fin} eenheid={e} dark={dark} />)}
      <Voorbehouden fin={fin} />
    </>
  )
}
