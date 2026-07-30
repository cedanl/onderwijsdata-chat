// ─── Public barrel ───────────────────────────────────────────────────────────
// Explicit named exports keep the surface intentional and prevent private
// helpers from leaking when new symbols are added to submodules.

export { darkColors, chartOpts, buildIndexChartOpts, benchmarkColor, SECTOR_LABELS, SECTOR_COLORS, horizontalBarOpts } from './chart-opts'
export { buildSectorChartData, sortedEntries, yearOverYearDelta, buildPeerLinesData, buildPeerLinesOpts, buildBenchmarkLineData } from './chart-builders'
export { useDarkMode, fmt, useRegioDashboardData, useNationaalDashboardData, useRendementDashboardData, useArbeidsmarktmatchDashboardData, useRegioComputed } from './hooks'
export { DashboardShell, Sparkline, SectionHeader, ChartCard, RegioBadges } from './shell'
export { DemografieKpis, InstroomKpis, DiplomeringKpis } from './kpis'
export { BenchmarkLineChart, PeerLinesChart, PeersTable } from './charts-peers'
export { buildMarktaandeelTrendData, buildInstroomRatioData, MarktaandeelTrendChart, InstroomRatioChart, buildMarktaandeelData, buildGroeiRankingData, MarktaandeelChart, GroeiRankingChart } from './charts-markt'
export { RoaSection, PrognoseSection, UwvSection } from './charts-arbeidsmarkt'
export { buildSectorTrendData, buildLeerwegenData, SectorTrendChart, SectorkamersChart, LeerwegenChart } from './charts-sector'
export { buildRendementVergelijkingData, RendementVergelijkingChart } from './charts-rendement'
export { KaartSection } from './charts-kaart'
