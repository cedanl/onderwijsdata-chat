// ─── Public barrel ───────────────────────────────────────────────────────────
// Explicit named exports keep the surface intentional and prevent private
// helpers from leaking when new symbols are added to submodules.

export { darkColors, buildIndexChartOpts, benchmarkColor, SECTOR_LABELS, SECTOR_COLORS, horizontalBarOpts, tellingAs, afgekapteAs } from './chart-opts'
export { buildSupplyDemandData, sortedEntries, yearOverYearDelta, buildPeerLinesData, buildPeerLinesOpts, buildBenchmarkLineData } from './chart-builders'
export { useDarkMode, fmt, dashboardFout, useRegioDashboardData, useNationaalDashboardData, useRendementDashboardData, useArbeidsmarktmatchDashboardData, useRegioComputed } from './hooks'
export { DashboardShell, NietGeladen, DeelLading, gatenVan, Sparkline, SectionHeader, ChartCard, RegioBadges, DashboardSources, BRONNEN_HO, BRONNEN_MBO, BRONNEN_NATIONAAL, BRONNEN_ARBEIDSMARKT } from './shell'
export { DemografieKpis, InstroomKpis, DiplomeringKpis } from './kpis'
export { BenchmarkLineChart, PeerLinesChart, PeersTable } from './charts-peers'
export { buildMarktaandeelTrendData, buildInstroomRatioData, MarktaandeelTrendChart, InstroomRatioChart, buildMarktaandeelData, buildGroeiRankingData, MarktaandeelChart, GroeiRankingChart } from './charts-markt'
export { RoaSection, PrognoseSection, UwvSection } from './charts-arbeidsmarkt'
export { buildSectorTrendData, buildLeerwegenData, SectorTrendChart, HoofdgroepenChart, LeerwegenChart, LEERWEGEN_MBO } from './charts-sector'
export { buildRendementVergelijkingData, RendementVergelijkingChart } from './charts-rendement'
export { KaartSection } from './charts-kaart'
export { ONDERDRUKT_UITLEG, perJaar, isOndergrens, TenMinste, OndergrensNoot, OndergrensCategorieen, WeggelatenNoot } from './ondergrens'
