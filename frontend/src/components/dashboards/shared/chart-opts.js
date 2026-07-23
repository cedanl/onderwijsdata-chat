// ─── Chart options & constants ───────────────────────────────────────────────

export function chartOpts(dark) {
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
  const tick = dark ? '#9CA3AF' : '#6B7280'
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick } },
      y: { grid: { color: grid }, ticks: { color: tick } },
    },
  }
}

export function buildIndexChartOpts(dark) {
  const tick = dark ? '#9CA3AF' : '#6B7280'
  const grid = dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6'
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: { color: dark ? '#D1D5DB' : '#374151', font: { size: 11 }, boxWidth: 20 },
      },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const v = ctx.parsed.y
            return `${ctx.dataset.label}: ${v >= 0 ? '+' : ''}${v}%`
          },
        },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick } },
      y: {
        grid: { color: grid },
        ticks: { color: tick, callback: (v) => `${v}%` },
        title: { display: true, text: '% verandering t.o.v. eerste jaar', color: tick, font: { size: 10 } },
      },
    },
  }
}

const BENCHMARK_COLOR_LIGHT = '#94A3B8'
const BENCHMARK_COLOR_DARK = '#9CA3AF'
export function benchmarkColor(dark) { return dark ? BENCHMARK_COLOR_DARK : BENCHMARK_COLOR_LIGHT }

export function doughnutOpts(dark) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { position: 'right', labels: { color: dark ? '#D1D5DB' : '#374151', font: { size: 11 } } } },
  }
}

export const SECTOR_LABELS = {
  ECONOMIE: 'Economie',
  GEZONDHEIDSZORG: 'Gezondheidszorg',
  TECHNIEK: 'Techniek',
  ONDERWIJS: 'Onderwijs',
  GEDRAG_EN_MAATSCHAPPIJ: 'Gedrag & Mij.',
  TAAL_EN_CULTUUR: 'Taal & Cultuur',
  SECTOROVERSTIJGEND: 'Sectoroverstijgend',
}
// Semantic: each color is fixed to a named sector (Economie→blauw, Gezondheidszorg→teal, …).
// Not a generic sequential palette, so not replaced by CHART_COLORS.
export const SECTOR_COLORS = ['#2563EB', '#0D9488', '#F59E0B', '#22C55E', '#8B5CF6', '#EC4899', '#94A3B8']
