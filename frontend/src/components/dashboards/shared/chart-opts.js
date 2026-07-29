// ─── Chart options & constants ───────────────────────────────────────────────

export function darkColors(dark) {
  return {
    tick: dark ? '#9CA3AF' : '#6B7280',
    grid: dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6',
    label: dark ? '#D1D5DB' : '#374151',
  }
}

function compactNum(n) {
  const abs = Math.abs(n)
  if (abs >= 1_000_000) return (n / 1_000_000).toLocaleString('nl-NL', { maximumFractionDigits: 1 }) + 'M'
  if (abs >= 10_000) return (n / 1_000).toLocaleString('nl-NL', { maximumFractionDigits: 1 }) + 'K'
  return n.toLocaleString('nl-NL')
}

export function chartOpts(dark) {
  const { tick, grid } = darkColors(dark)
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: ctx => ` ${ctx.dataset.label || ''}: ${compactNum(ctx.parsed.y ?? ctx.parsed)}` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: tick } },
      y: { grid: { color: grid }, ticks: { color: tick, callback: v => compactNum(v) } },
    },
  }
}

export function buildIndexChartOpts(dark) {
  const { tick, grid, label } = darkColors(dark)
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: { color: label, font: { size: 11 }, boxWidth: 20 },
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

export const barDataLabelsPlugin = {
  id: 'barDataLabels',
  afterDatasetsDraw(chart) {
    const { ctx } = chart
    chart.data.datasets.forEach((ds, di) => {
      const meta = chart.getDatasetMeta(di)
      if (meta.hidden || meta.type === 'line') return
      meta.data.forEach((el, i) => {
        const val = ds.data[i]
        if (val == null || val === 0) return
        const label = compactNum(val)
        ctx.save()
        ctx.font = '600 10px system-ui, sans-serif'
        ctx.fillStyle = chart.options.plugins?.barDataLabels?.color || '#6B7280'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'bottom'
        ctx.fillText(label, el.x, el.y - 4)
        ctx.restore()
      })
    })
  },
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
  GEDRAG_EN_MAATSCHAPPIJ: 'Gedrag & Maatschappij',
  ONDERWIJS: 'Onderwijs',
  TECHNIEK: 'Techniek',
  NATUUR: 'Natuur',
  TAAL_EN_CULTUUR: 'Taal & Cultuur',
  RECHT: 'Recht',
  LANDBOUW_EN_NATUURLIJKE_OMGEVING: 'Landbouw',
  SECTOROVERSTIJGEND: 'Sectoroverstijgend',
}
// Semantic: each color is fixed to a named sector (Economie→blauw, Gezondheidszorg→teal, …).
// Not a generic sequential palette, so not replaced by CHART_COLORS.
export const SECTOR_COLORS = ['#2563EB', '#0D9488', '#F59E0B', '#22C55E', '#8B5CF6', '#EC4899', '#94A3B8']

export function horizontalBarOpts(dark, tooltipSuffix = '') {
  const { tick, grid } = darkColors(dark)
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
