// ─── Public barrel ───────────────────────────────────────────────────────────
// Explicit named exports keep the surface intentional and prevent private
// helpers from leaking when new symbols are added to submodules.

export { darkColors, buildIndexChartOpts, benchmarkColor, SECTOR_LABELS, sectorKleuren, oordeelKleur, horizontalBarOpts, tellingAs, afgekapteAs } from './chart-opts'
export { Grafiek } from './grafiek'
export { buildSupplyDemandData, sortedEntries, yearOverYearDelta, buildPeerLinesData, buildPeerLinesOpts, buildBenchmarkLineData, groeiStartjaar, groeiPct } from './chart-builders'
export { useDarkMode, fmt, dashboardFout, useRegioDashboardData, useNationaalDashboardData, useRendementDashboardData, useArbeidsmarktmatchDashboardData, useRegioComputed } from './hooks'
export { DemografieKpis, InstroomKpis, DiplomeringKpis, JaarNoot, eerstejaarsNoot, gediplomeerdenNoot } from './kpis'
export { DashboardShell, NietGeladen, DeelLading, gatenVan, Sparkline, SectionHeader, ChartCard, RegioBadges, DashboardSources, POPULATIE_NATIONAAL, ROA_AIS, ROA_SIS, bronnenVan, bronBadge, roaPeilmoment } from './shell'
export { BenchmarkLineChart, PeerLinesChart, PeersTable } from './charts-peers'
export { buildMarktaandeelTrendData, buildInstroomRatioData, MarktaandeelTrendChart, InstroomRatioChart, buildMarktaandeelData, buildGroeiRankingData, MarktaandeelChart, GroeiRankingChart } from './charts-markt'
export { RoaSection, PrognoseSection, UwvSection } from './charts-arbeidsmarkt'
export { buildSectorTrendData, buildLeerwegenData, SectorTrendChart, HoofdgroepenChart, LeerwegenChart, LEERWEGEN_MBO } from './charts-sector'
export { buildRendementVergelijkingData, RendementVergelijkingChart } from './charts-rendement'
export { diplomaRatio } from './diploma-ratio'
export { KaartSection } from './charts-kaart'
export { ONDERDRUKT_UITLEG, perJaar, isOndergrens, TenMinste, OndergrensNoot, OndergrensCategorieen, WeggelatenNoot } from './ondergrens'
