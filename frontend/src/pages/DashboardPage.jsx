import { Bar, Line, Doughnut } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement, LineElement, PointElement,
  ArcElement, Title, Tooltip, Legend, Filler,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Title, Tooltip, Legend, Filler)

const CHART_OPTS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: { x: { grid: { display: false } }, y: { grid: { color: '#F3F4F6' } } },
}

const KPI_DATA = [
  { label: 'Totaal inschrijvingen', value: '4.832', trend: '+6,3%', dir: 'up', color: '#EFF6FF', iconColor: '#2563EB' },
  { label: 'Diplomarendement 4jr', value: '71,4%', trend: '+2,1 pp', dir: 'up', color: '#F0FDFA', iconColor: '#0D9488' },
  { label: 'VSV-percentage', value: '3,8%', trend: '-0,4 pp', dir: 'up', color: '#F0FDF4', iconColor: '#22C55E' },
  { label: 'Arbeidsmarktplaatsing', value: '84,2%', trend: '+1,8 pp', dir: 'up', color: '#FFF7ED', iconColor: '#F59E0B' },
]

const instroom = {
  labels: ['2020', '2021', '2022', '2023', '2024'],
  datasets: [{
    data: [3912, 4087, 4398, 4545, 4832],
    backgroundColor: '#2563EB',
    borderRadius: 6,
  }],
}

const rendement = {
  labels: ['Informatica', 'Verpleegkunde', 'Bedrijfskunde', 'Werktuigbouwkunde', 'Communicatie'],
  datasets: [
    { label: 'Uw instelling', data: [68.3, 74.2, 64.8, 71.4, 72.1], backgroundColor: '#2563EB', borderRadius: 4 },
    { label: 'Regionaal gem.', data: [65.1, 71.8, 67.3, 69.2, 70.4], backgroundColor: '#DBEAFE', borderRadius: 4 },
  ],
}

const rendementOpts = {
  ...CHART_OPTS,
  plugins: { legend: { display: true, position: 'top' } },
}

const herkomst = {
  labels: ['Groot-Amsterdam', 'Noord-Holland', 'Flevoland', 'Utrecht', 'Buitenland'],
  datasets: [{
    data: [52.4, 21.3, 11.2, 8.7, 6.4],
    backgroundColor: ['#2563EB', '#3B82F6', '#93C5FD', '#DBEAFE', '#EFF6FF'],
    borderWidth: 0,
  }],
}

const herkomstOpts = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'right', labels: { font: { size: 11 } } } },
}

const trend = {
  labels: ['2020', '2021', '2022', '2023', '2024'],
  datasets: [{
    label: 'Voltijd',
    data: [3241, 3389, 3618, 3724, 3901],
    borderColor: '#2563EB', backgroundColor: 'rgba(37,99,235,.08)',
    fill: true, tension: 0.3, pointRadius: 4,
  }, {
    label: 'Deeltijd',
    data: [487, 501, 538, 561, 612],
    borderColor: '#14B8A6', backgroundColor: 'transparent',
    fill: false, tension: 0.3, pointRadius: 4,
  }],
}

const trendOpts = {
  ...CHART_OPTS,
  plugins: { legend: { display: true, position: 'top' } },
}

export default function DashboardPage() {
  return (
    <div className="dashboard-layout">
      <div className="dashboard-topbar">
        <span className="dashboard-title">Dashboard</span>
        <span className="meta-badge live">● Live</span>
        <span className="meta-badge date">Peildatum: 1 okt 2024</span>
      </div>

      <div className="dashboard-content">
        {/* KPI's */}
        <div className="kpi-grid">
          {KPI_DATA.map(k => (
            <div key={k.label} className="kpi-card">
              <div className="kpi-card-header">
                <span className="kpi-label">{k.label}</span>
                <div className="kpi-icon" style={{ background: k.color }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke={k.iconColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
                  </svg>
                </div>
              </div>
              <div className="kpi-value">{k.value}</div>
              <div className={`kpi-trend ${k.dir}`}>↑ {k.trend} t.o.v. vorig jaar</div>
            </div>
          ))}
        </div>

        {/* Charts */}
        <div className="charts-grid">
          <div className="chart-card">
            <div className="chart-header">
              <div>
                <div className="chart-title">Instroom per jaar</div>
                <div className="chart-sub">Totaal inschrijvingen 2020–2024</div>
              </div>
            </div>
            <div style={{ height: 200 }}>
              <Bar data={instroom} options={CHART_OPTS} />
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-header">
              <div>
                <div className="chart-title">Herkomst instroom</div>
                <div className="chart-sub">Regio van herkomst 2024</div>
              </div>
            </div>
            <div style={{ height: 200 }}>
              <Doughnut data={herkomst} options={herkomstOpts} />
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-header">
              <div>
                <div className="chart-title">Diplomarendement per opleiding</div>
                <div className="chart-sub">Binnen 4 jaar, cohort 2020</div>
              </div>
            </div>
            <div style={{ height: 200 }}>
              <Bar data={rendement} options={rendementOpts} />
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-header">
              <div>
                <div className="chart-title">Deelname voltijd vs. deeltijd</div>
                <div className="chart-sub">Ontwikkeling 2020–2024</div>
              </div>
            </div>
            <div style={{ height: 200 }}>
              <Line data={trend} options={trendOpts} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
