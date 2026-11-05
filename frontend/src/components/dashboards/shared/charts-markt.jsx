import { horizontalBarOpts, darkColors, benchmarkColor, DAAL_KLEUR } from './chart-opts'
import { COLOR_EIGEN, COLOR_DIPLOM } from '../../../constants'
import { ChartCard } from './shell'
import { groeiStartjaar, groeiPct } from './chart-builders'
import { Grafiek } from './grafiek'

// ─── Marktaandeel trend & Instroom ratio ─────────────────────────────────────

export function buildMarktaandeelTrendData(data) {
  if (!data?.ingeschrevenen || !data?.benchmark?.totaal_ingeschrevenen) return null
  const eigen = data.ingeschrevenen
  const totaal = data.benchmark.totaal_ingeschrevenen
  const jaren = Object.keys(eigen)
    .filter(j => (totaal[j] ?? totaal[Number(j)]) != null)
    .sort((a, b) => a - b)
  if (jaren.length < 2) return null
  const values = jaren.map(j => {
    const e = eigen[j] ?? eigen[Number(j)]
    const t = totaal[j] ?? totaal[Number(j)]
    return t > 0 ? Math.round((e / (e + t)) * 1000) / 10 : null
  })
  return {
    labels: jaren.map(String),
    datasets: [{
      label: 'Marktaandeel %',
      data: values,
      borderColor: COLOR_EIGEN,
      backgroundColor: COLOR_EIGEN + '18',
      fill: true,
      tension: 0.3,
      pointRadius: 4,
      borderWidth: 2.5,
    }],
  }
}

export function buildInstroomRatioData(data) {
  if (!data?.eerstejaars || !data?.ingeschrevenen) return null
  const jaren = Object.keys(data.eerstejaars)
    .filter(j => (data.ingeschrevenen[j] ?? data.ingeschrevenen[Number(j)]) != null)
    .sort((a, b) => a - b)
  if (jaren.length < 2) return null
  const values = jaren.map(j => {
    const ej = data.eerstejaars[j] ?? data.eerstejaars[Number(j)]
    const ig = data.ingeschrevenen[j] ?? data.ingeschrevenen[Number(j)]
    return ig > 0 ? Math.round((ej / ig) * 1000) / 10 : null
  })
  return {
    labels: jaren.map(String),
    datasets: [{
      label: 'Eerstejaars %',
      data: values,
      borderColor: COLOR_DIPLOM,
      backgroundColor: COLOR_DIPLOM + '18',
      fill: true,
      tension: 0.3,
      pointRadius: 4,
      borderWidth: 2.5,
    }],
  }
}

function _ratioLineOpts(dark, tooltipLabel) {
  const { tick, grid } = darkColors(dark)
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => ` ${ctx.raw}% ${tooltipLabel}` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick } },
      y: {
        min: 0,
        grid: { color: grid },
        ticks: { color: tick, callback: v => `${v}%` },
      },
    },
  }
}

export function MarktaandeelTrendChart({ data, dark }) {
  if (!data) return null
  return (
    <ChartCard
      title="Marktaandeel over tijd"
      subtitle="% van regiototaal ingeschrevenen — verliest of wint de instelling terrein?"
    >
      <Grafiek soort="line" data={data} options={_ratioLineOpts(dark, '')} hoogte={200} />
    </ChartCard>
  )
}

// Eén ondertitel voor mbo en ho; "(HO)" staat er alleen bij ho (#918).
export function instroomRatioOndertitel(type) {
  return `Eerstejaars als % van totaal ingeschrevenen — pipeline-gezondheid${type === 'mbo' ? '' : ' (HO)'}`
}

export function InstroomRatioChart({ data, dark, type }) {
  if (!data) return null
  return (
    <ChartCard
      title="Instroom ratio"
      subtitle={instroomRatioOndertitel(type)}
    >
      <Grafiek soort="line" data={data} options={_ratioLineOpts(dark, '')} hoogte={200} />
    </ChartCard>
  )
}

// ─── Marktaandeel & Groei helpers ───────────────────────────────────────────

export function buildMarktaandeelData(data, instelling, dark) {
  if (!data?.ingeschrevenen || !data?.benchmark?.peers?.ingeschrevenen) return null
  const jaar = data.laatste_jaar
  const jaarStr = String(jaar)
  const entries = []

  const ownVal = data.ingeschrevenen[jaar] ?? data.ingeschrevenen[jaarStr]
  if (ownVal != null) entries.push({ naam: instelling, waarde: ownVal, eigen: true })

  for (const [naam, jaarData] of Object.entries(data.benchmark.peers.ingeschrevenen)) {
    const val = jaarData[jaar] ?? jaarData[jaarStr] ??
      jaarData[Object.keys(jaarData).sort((a, b) => b - a)[0]]
    if (val != null) entries.push({ naam, waarde: val, eigen: false })
  }

  if (entries.length < 2) return null
  entries.sort((a, b) => b.waarde - a.waarde)

  return {
    labels: entries.map(e => e.naam),
    datasets: [{
      label: 'Ingeschrevenen',
      data: entries.map(e => e.waarde),
      backgroundColor: entries.map(e => e.eigen ? COLOR_EIGEN : benchmarkColor(dark)),
      borderRadius: 4,
    }],
  }
}

// Groei per instelling met de ene groeiregel van chart-builders (#903): hetzelfde startjaar als de lijnen en de tabel.
export function buildGroeiRankingData(data, instelling, dark) {
  if (!data?.ingeschrevenen || !data?.benchmark?.peers?.ingeschrevenen) return null
  const peers = data.benchmark.peers.ingeschrevenen
  const startjaar = groeiStartjaar([data.ingeschrevenen, ...Object.values(peers)])
  const eindjaar = data.laatste_jaar

  const entries = []
  const g = groeiPct(data.ingeschrevenen, startjaar, eindjaar)
  if (g != null) entries.push({ naam: instelling, groei: g, eigen: true })

  for (const [naam, jaarData] of Object.entries(peers)) {
    const pg = groeiPct(jaarData, startjaar, eindjaar)
    if (pg != null) entries.push({ naam, groei: pg, eigen: false })
  }

  if (entries.length < 2) return null
  entries.sort((a, b) => b.groei - a.groei)

  return {
    startjaar,
    eindjaar,
    labels: entries.map(e => e.naam),
    datasets: [{
      label: 'Groei (%)',
      data: entries.map(e => e.groei),
      backgroundColor: entries.map(e =>
        e.eigen ? COLOR_EIGEN : e.groei >= 0 ? benchmarkColor(dark) : DAAL_KLEUR
      ),
      borderRadius: 4,
    }],
  }
}


export function MarktaandeelChart({ data, jaar, dark }) {
  if (!data) return null
  const h = Math.max(200, data.labels.length * 34 + 40)
  return (
    <ChartCard
      title={`Marktpositie ${jaar}`}
      subtitle="Totaal ingeschrevenen per instelling in de regio (eigen instelling blauw)"
    >
      <Grafiek soort="bar" data={data} options={horizontalBarOpts(dark)} hoogte={h} categorie="Instelling" />
    </ChartCard>
  )
}

export function GroeiRankingChart({ data, dark }) {
  if (!data) return null
  const { startjaar, eindjaar, ...barData } = data
  const h = Math.max(200, barData.labels.length * 34 + 40)
  return (
    <ChartCard
      title={`Groei ingeschrevenen ${startjaar}–${eindjaar}`}
      subtitle={`% verandering van ${startjaar} tot ${eindjaar}, voor elke instelling vanaf hetzelfde jaar (eigen instelling blauw, daling rood)`}
    >
      <Grafiek soort="bar" data={barData} options={horizontalBarOpts(dark, '%')} hoogte={h} categorie="Instelling" />
    </ChartCard>
  )
}
