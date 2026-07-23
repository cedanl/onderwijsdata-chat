import { Line, Bar } from 'react-chartjs-2'

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
      borderColor: '#2563EB',
      backgroundColor: '#2563EB18',
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
      borderColor: '#0D9488',
      backgroundColor: '#0D948818',
      fill: true,
      tension: 0.3,
      pointRadius: 4,
      borderWidth: 2.5,
    }],
  }
}

function _ratioLineOpts(dark, tooltipLabel) {
  const tick = dark ? '#9CA3AF' : '#6B7280'
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
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
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header">
          <div>
            <div className="chart-title">Marktaandeel over tijd</div>
            <div className="chart-sub">% van regiototaal ingeschrevenen — verliest of wint de instelling terrein?</div>
          </div>
        </div>
        <div style={{ height: 200 }}>
          <Line data={data} options={_ratioLineOpts(dark, '')} />
        </div>
      </div>
    </div>
  )
}

export function InstroomRatioChart({ data, dark }) {
  if (!data) return null
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header">
          <div>
            <div className="chart-title">Instroom ratio</div>
            <div className="chart-sub">Eerstejaars als % van totaal ingeschrevenen — pipeline-gezondheid (HO)</div>
          </div>
        </div>
        <div style={{ height: 200 }}>
          <Line data={data} options={_ratioLineOpts(dark, '')} />
        </div>
      </div>
    </div>
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
      backgroundColor: entries.map(e => e.eigen ? '#2563EB' : (dark ? '#475569' : '#CBD5E1')),
      borderRadius: 4,
    }],
  }
}

export function buildGroeiRankingData(data, instelling, dark) {
  if (!data?.ingeschrevenen || !data?.benchmark?.peers?.ingeschrevenen) return null

  function groeiPct(dict) {
    const jaren = Object.keys(dict).map(Number).sort((a, b) => a - b)
    if (jaren.length < 2) return null
    const first = dict[jaren[0]]
    const last = dict[jaren[jaren.length - 1]]
    if (!first) return null
    return Math.round((last - first) / first * 100)
  }

  const entries = []
  const g = groeiPct(data.ingeschrevenen)
  if (g != null) entries.push({ naam: instelling, groei: g, eigen: true })

  for (const [naam, jaarData] of Object.entries(data.benchmark.peers.ingeschrevenen)) {
    const pg = groeiPct(jaarData)
    if (pg != null) entries.push({ naam, groei: pg, eigen: false })
  }

  if (entries.length < 2) return null
  entries.sort((a, b) => b.groei - a.groei)

  return {
    labels: entries.map(e => e.naam),
    datasets: [{
      label: 'Groei (%)',
      data: entries.map(e => e.groei),
      backgroundColor: entries.map(e =>
        e.eigen ? '#2563EB' : e.groei >= 0 ? (dark ? '#475569' : '#CBD5E1') : (dark ? '#7F1D1D' : '#FEE2E2')
      ),
      borderRadius: 4,
    }],
  }
}

function _horizontalBarOpts(dark, tooltipSuffix = '') {
  const tick = dark ? '#9CA3AF' : '#6B7280'
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
  return {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: { label: ctx => ` ${ctx.raw.toLocaleString('nl-NL')}${tooltipSuffix}` },
      },
    },
    scales: {
      x: { grid: { color: grid }, ticks: { color: tick, font: { size: 11 } } },
      y: { grid: { display: false }, ticks: { color: tick, font: { size: 11 }, padding: 4 } },
    },
  }
}

export function MarktaandeelChart({ data, jaar, dark }) {
  if (!data) return null
  const h = Math.max(200, data.labels.length * 34 + 40)
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header">
          <div>
            <div className="chart-title">Marktpositie {jaar}</div>
            <div className="chart-sub">Totaal ingeschrevenen per instelling in de regio (eigen instelling blauw)</div>
          </div>
        </div>
        <div style={{ height: h }}>
          <Bar data={data} options={_horizontalBarOpts(dark)} />
        </div>
      </div>
    </div>
  )
}

export function GroeiRankingChart({ data, dark }) {
  if (!data) return null
  const h = Math.max(200, data.labels.length * 34 + 40)
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header">
          <div>
            <div className="chart-title">Groei ranking (totale periode)</div>
            <div className="chart-sub">% verandering eerste→laatste beschikbaar jaar per instelling (eigen instelling blauw)</div>
          </div>
        </div>
        <div style={{ height: h }}>
          <Bar data={data} options={_horizontalBarOpts(dark, '%')} />
        </div>
      </div>
    </div>
  )
}
