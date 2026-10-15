// A figure with the light colours tools/plot.py bakes in (#567): title with subtitle, grid,
// axis lines, legend, and black series in every place a trace colour can sit. Shared by the
// report and dashboard dark-mode tests.
const axis = { showgrid: true, gridcolor: '#f0f0f0', linecolor: '#ccc', zeroline: false }

export const layout = {
  title: {
    text: 'Instroom per jaar', font: { size: 16, color: '#222' }, yref: 'container', y: 0.98,
    subtitle: { text: 'Afgerond op 10-tallen', font: { size: 11, color: '#666' } },
  },
  xaxis: { ...axis, title: { text: 'Jaar' }, type: 'category' },
  yaxis: { ...axis, title: { text: 'Aantal' }, tickformat: ',d' },
  legend: { bgcolor: 'rgba(255,255,255,0.8)', bordercolor: '#ddd', borderwidth: 1, orientation: 'h' },
  margin: { t: 100 },
}

export const data = [
  { type: 'bar', name: 'A', x: ['2023'], y: [1], marker: { color: '#0072B2' } },
  { type: 'bar', name: 'B', x: ['2023'], y: [2], marker: { color: '#000000' } },
  { type: 'scatter', name: 'C', x: ['2023'], y: [3], line: { color: '#000000', width: 2 } },
  { type: 'bar', name: 'D', x: ['2023'], y: [4], marker: { color: ['#B0B0B0', '#000', 'black'] } },
  { type: 'pie', labels: ['p', 'q', 'r'], values: [1, 2, 3], marker: { colors: ['#0072B2', '#F0E442', '#000000'] } },
]
