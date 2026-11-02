// ─── Chart options & constants ───────────────────────────────────────────────

export function darkColors(dark) {
  return {
    tick: dark ? '#9CA3AF' : '#6B7280',
    grid: dark ? 'rgba(255,255,255,0.06)' : '#F3F4F6',
    label: dark ? '#D1D5DB' : '#374151',
  }
}

// De waardeas van een lijn volgt de eenheid, zoals create_plot in tools/plot.py (#871): een telling begint op 0, anders
// oogt een daling van 2 % als een klif. Een percentage mag afgekapt, maar dan staat dat op de as.
export const AS_NIET_BIJ_NUL = 'as begint niet bij 0'

export function tellingAs(as) {
  return { ...as, beginAtZero: true }
}

// Chart.js laat een verborgen reeks buiten het asbereik; alleen wat bij het openen te zien is telt.
export function afgekapteAs(as, datasets, kleur) {
  const waarden = datasets
    .filter(d => !d.hidden)
    .flatMap(d => d.data)
    .filter(v => typeof v === 'number' && Number.isFinite(v))
  if (!waarden.length || Math.min(...waarden) <= 0) return as
  return { ...as, title: { display: true, text: AS_NIET_BIJ_NUL, color: kleur, font: { size: 10 } } }
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
        onClick: (e, legendItem, legend) => {
          const index = legendItem.datasetIndex
          const chart = legend.chart
          const meta = chart.getDatasetMeta(index)
          meta.hidden = !meta.hidden
          chart.update()
        },
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
// Palet voor de sector-, leerweg- en sectorkamergrafieken (charts-sector.jsx). De kleur hangt aan de positie in de
// reeks (`i % SECTOR_COLORS.length`), niet aan een sectorcode: met 8 kleuren voor 10 sectoren delen sommige sectoren een
// kleur, en een sector kan per grafiek een andere kleur krijgen.
export const SECTOR_COLORS = ['#2563EB', '#0D9488', '#F59E0B', '#22C55E', '#8B5CF6', '#EC4899', '#94A3B8', '#EF4444']

export function horizontalBarOpts(dark, tooltipSuffix = '') {
  const { tick, grid } = darkColors(dark)
  return {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
        onClick: (e, legendItem, legend) => {
          const index = legendItem.datasetIndex
          const chart = legend.chart
          const meta = chart.getDatasetMeta(index)
          meta.hidden = !meta.hidden
          chart.update()
        },
      },
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
