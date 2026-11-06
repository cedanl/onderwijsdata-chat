import { useMemo } from 'react'
import { CHART_COLORS } from '../../../constants'
import { SectionHeader, ChartCard, Grafiek, fmt, fmtProcent, darkColors } from '../shared/index'

// Personeel van een universiteit (#936): de payload van /api/dashboard/personeel, met de uitkomst van
// tools/wo_personeel.py (`reeks_van`): fte zonder GEZO per jaar (peildatum 31 december). Alleen voor wo; een hbo- of
// mbo-instelling krijgt geen kaart. De pagina rekent niets; een jaar zonder vast/tijdelijk is null, geen 0.

const NOOT = { fontSize: '12.5px', color: 'var(--muted-text)' }
const TITEL = 'Personeel (wo)'

function Kpis({ laatste }) {
  const tegels = [
    ['Totaal', `${fmt(laatste.totaal)} fte`],
    ['Wetenschappelijk personeel', `${fmt(laatste.wetenschappelijk_personeel)} fte`],
    ['Ondersteunend en beheer (OBP)', `${fmt(laatste.obp)} fte`],
    ['Aandeel tijdelijk', laatste.aandeel_tijdelijk_procent == null ? '—' : `${fmtProcent(laatste.aandeel_tijdelijk_procent)}%`],
  ]
  return (
    <div className="kpi-grid">
      {tegels.map(([label, waarde]) => (
        <div key={label} className="kpi-card">
          <div className="kpi-label">{label}</div>
          <div className="kpi-value">{waarde}</div>
          <div className="kpi-sub">peildatum {laatste.peildatum}</div>
        </div>
      ))}
    </div>
  )
}

function lijn(label, data, kleur, extra = {}) {
  return { label, data, borderColor: kleur, backgroundColor: kleur + '33', borderWidth: 2, tension: 0.2, ...extra }
}

function opties(dark, eenheid) {
  const { tick, grid, label } = darkColors(dark)
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { display: true, position: 'top', labels: { color: label, boxWidth: 14 } },
      tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.raw == null ? '—' : `${fmt(ctx.raw)}${eenheid}`}` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick } },
      y: { beginAtZero: true, grid: { color: grid }, ticks: { color: tick, callback: v => `${fmt(v)}${eenheid}` } },
    },
  }
}

function FteChart({ cijfers, dark }) {
  const data = useMemo(() => ({
    labels: cijfers.map(r => String(r.jaar)),
    datasets: [
      lijn('Wetenschappelijk personeel', cijfers.map(r => r.wetenschappelijk_personeel ?? null), CHART_COLORS[0], { borderWidth: 3 }),
      lijn('OBP', cijfers.map(r => r.obp ?? null), CHART_COLORS[1]),
    ],
  }), [cijfers])
  return (
    <ChartCard title="Fte per jaar" subtitle="Wetenschappelijk personeel en OBP, zonder GEZO, peildatum 31 december">
      <Grafiek soort="line" data={data} hoogte={260} categorie="Jaar" options={opties(dark, ' fte')} />
    </ChartCard>
  )
}

function TijdelijkChart({ cijfers, dark }) {
  const data = useMemo(() => {
    const metAandeel = cijfers.filter(r => r.aandeel_tijdelijk_procent != null)
    return {
      labels: metAandeel.map(r => String(r.jaar)),
      datasets: [lijn('Aandeel tijdelijk', metAandeel.map(r => r.aandeel_tijdelijk_procent), CHART_COLORS[2])],
    }
  }, [cijfers])
  if (data.labels.length < 2) return null
  return (
    <ChartCard title="Aandeel tijdelijk per jaar" subtitle="Tijdelijk als deel van vast plus tijdelijk, in fte; vanaf 2003">
      <Grafiek soort="line" data={data} hoogte={240} categorie="Jaar" options={opties(dark, '%')} />
    </ChartCard>
  )
}

export function PersoneelSection({ data, dark }) {
  if (!data?.gevonden || data.sector !== 'wo') return null
  if (data.melding) {
    return (
      <>
        <SectionHeader title={TITEL} />
        <p className="dashboard-noot" role="note" style={{ ...NOOT, margin: '0 0 16px' }}>{data.melding}</p>
      </>
    )
  }
  const pers = data.personeel
  if (!pers?.cijfers?.length) return null // niet geladen: de melding staat bovenaan (niet_beschikbaar)
  const cijfers = [...pers.cijfers].sort((a, b) => a.jaar - b.jaar)
  return (
    <>
      <SectionHeader title={TITEL} subtitle={`In fte, zonder GEZO; ${pers.bron?.regel || 'WOPI, Universiteiten van Nederland'}`} />
      <Kpis laatste={cijfers.at(-1)} />
      <FteChart cijfers={cijfers} dark={dark} />
      <TijdelijkChart cijfers={cijfers} dark={dark} />
      <div className="dashboard-noot" role="note" style={{ ...NOOT, margin: '0 0 16px' }}>
        <ul style={{ margin: '0 0 4px', paddingLeft: 18 }}>{(pers.voorbehouden || []).map(v => <li key={v}>{v}</li>)}</ul>
        {pers.definitie && <p style={{ margin: '0 0 4px' }}>{pers.definitie}</p>}
        {pers.noot && <p style={{ margin: 0 }}>{pers.noot}</p>}
      </div>
    </>
  )
}
