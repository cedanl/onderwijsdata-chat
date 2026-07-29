import { useState } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import { SECTOR_LABELS, SECTOR_COLORS, darkColors } from './chart-opts'

// ─── Sector trend & Leerweg trend ────────────────────────────────────────────

export function buildSectorTrendData(sectorenTrend) {
  if (!sectorenTrend || Object.keys(sectorenTrend).length === 0) return null
  const sectors = Object.keys(sectorenTrend)
  const allJaren = [...new Set(sectors.flatMap(s => Object.keys(sectorenTrend[s]).map(String)))]
    .sort((a, b) => a - b)
  if (allJaren.length < 2) return null
  return {
    labels: allJaren,
    datasets: sectors.map((sector, i) => ({
      label: SECTOR_LABELS[sector] || sector,
      data: allJaren.map(j => sectorenTrend[sector][j] ?? sectorenTrend[sector][Number(j)] ?? 0),
      backgroundColor: SECTOR_COLORS[i % SECTOR_COLORS.length] + 'BB',
      borderColor: SECTOR_COLORS[i % SECTOR_COLORS.length],
      borderWidth: 1,
      fill: true,
    })),
  }
}

export function buildLeerwegenData(leerwegen) {
  if (!leerwegen || Object.keys(leerwegen).length < 2) return null
  const jaren = Object.keys(leerwegen).sort((a, b) => a - b)
  const tracks = ['BBL', 'BOL voltijd', 'BOL deeltijd']
  const colors = ['#2563EB', '#0D9488', '#F59E0B']
  // Guard: require at least one year with BBL/BOL data
  const hasBblBol = jaren.some(j => tracks.some(t => (leerwegen[j]?.[t] ?? 0) > 0))
  if (!hasBblBol) return null
  return {
    labels: jaren,
    datasets: tracks.map((track, i) => ({
      label: track,
      data: jaren.map(j => leerwegen[j]?.[track] ?? 0),
      backgroundColor: colors[i] + 'CC',
      borderColor: colors[i],
      borderWidth: 1,
      fill: true,
    })),
  }
}

function _normalizeProportional(data) {
  const totals = data.labels.map((_, i) =>
    data.datasets.reduce((sum, ds) => sum + (ds.data[i] ?? 0), 0)
  )
  return {
    ...data,
    datasets: data.datasets.map(ds => ({
      ...ds,
      data: ds.data.map((v, i) => totals[i] > 0 ? Math.round((v / totals[i]) * 1000) / 10 : 0),
    })),
  }
}

function _stackedAreaOpts(dark, proportional = false) {
  const { tick, grid, label } = darkColors(dark)
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true, position: 'top',
        labels: { color: label, font: { size: 11 }, boxWidth: 14 },
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        ...(proportional ? { callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.raw}%` } } : {}),
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick }, stacked: true },
      y: {
        grid: { color: grid },
        ticks: { color: tick, ...(proportional ? { callback: v => `${v}%` } : {}) },
        stacked: true,
        ...(proportional ? { min: 0, max: 100 } : {}),
      },
    },
  }
}

const _toggleBtnStyle = {
  marginLeft: 'auto',
  padding: '2px 10px',
  fontSize: '.75rem',
  fontWeight: 600,
  borderRadius: 4,
  border: '1px solid var(--gray-300, #D1D5DB)',
  background: 'var(--gray-50, #F9FAFB)',
  color: 'var(--gray-600, #4B5563)',
  cursor: 'pointer',
  flexShrink: 0,
}

export function SectorTrendChart({ data, dark }) {
  const [proportional, setProportional] = useState(false)
  if (!data) return null
  const displayData = proportional ? _normalizeProportional(data) : data
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header" style={{ display: 'flex', alignItems: 'flex-start' }}>
          <div>
            <div className="chart-title">Inschrijvingen per sector over tijd</div>
            <div className="chart-sub">Stacked — welke faculteiten groeien of krimpen?</div>
          </div>
          <button style={_toggleBtnStyle} onClick={() => setProportional(p => !p)}>
            {proportional ? 'Abs' : '%'}
          </button>
        </div>
        <div style={{ height: 260 }}>
          <Line data={displayData} options={_stackedAreaOpts(dark, proportional)} />
        </div>
      </div>
    </div>
  )
}

export function SectorkamersChart({ sectorkamers, dark }) {
  if (!sectorkamers || Object.keys(sectorkamers).length === 0) return null
  const entries = Object.entries(sectorkamers).sort((a, b) => b[1] - a[1])
  const colors = ['#2563EB', '#0D9488', '#F59E0B', '#22C55E', '#8B5CF6', '#EC4899', '#94A3B8', '#EF4444']
  const { tick, grid } = darkColors(dark)
  const h = Math.max(160, entries.length * 36)
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header">
          <div>
            <div className="chart-title">Studenten per SBB-sectorkamer</div>
            <div className="chart-sub">MBO eerstejaars per hoofdgroep (DUO instromende-mbo-studenten)</div>
          </div>
        </div>
        <div style={{ height: h }}>
          <Bar
            data={{
              labels: entries.map(([k]) => k),
              datasets: [{
                label: 'Studenten',
                data: entries.map(([, v]) => v),
                backgroundColor: entries.map((_, i) => colors[i % colors.length] + 'CC'),
                borderWidth: 0,
                borderRadius: 4,
              }],
            }}
            options={{
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              plugins: { legend: { display: false } },
              scales: {
                x: { grid: { color: grid }, ticks: { color: tick } },
                y: { grid: { display: false }, ticks: { color: tick, font: { size: 11 } } },
              },
            }}
          />
        </div>
      </div>
    </div>
  )
}

export function LeerwegenChart({ data, dark }) {
  const [proportional, setProportional] = useState(false)
  if (!data) return null
  const displayData = proportional ? _normalizeProportional(data) : data
  return (
    <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
      <div className="chart-card">
        <div className="chart-header" style={{ display: 'flex', alignItems: 'flex-start' }}>
          <div>
            <div className="chart-title">Leerweg-verdeling over tijd</div>
            <div className="chart-sub">MBO leerweg-verdeling: BBL / BOL voltijd / BOL deeltijd per jaar</div>
          </div>
          <button style={_toggleBtnStyle} onClick={() => setProportional(p => !p)}>
            {proportional ? 'Abs' : '%'}
          </button>
        </div>
        <div style={{ height: 260 }}>
          <Line data={displayData} options={_stackedAreaOpts(dark, proportional)} />
        </div>
      </div>
    </div>
  )
}
