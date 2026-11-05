// Een schooljaar zoals chat en rapport het schrijven (tools/periode.label): startjaar 2024 is "2024/25" (#920).
export function schooljaarLabel(startjaar) {
  const start = Number(startjaar)
  return `${start}/${String((start + 1) % 100).padStart(2, '0')}`
}

// Een jaar van een dashboardreeks zoals de bron het bedoelt (#904). Het soort jaar komt uit de payload (`perioden`,
// data/dashboard.PERIODEN): een schooljaar heet "2025/26"; een ander soort jaar blijft een jaartal met zijn naam
// ("diplomajaar 2024"), want DUO legt niet vast of een diplomajaar een kalender- of studiejaar is (CH-41). Zonder
// soort blijft het jaartal kaal: dan beweert het label niets.
export function jaarLabel(jaar, soort) {
  if (jaar == null) return ''
  if (soort === 'schooljaar') return schooljaarLabel(jaar)
  return soort ? `${soort} ${jaar}` : String(jaar)
}

// Een jaar op een as of in een tabelkolom die het soort al noemt: een schooljaar als "2025/26", anders het jaartal.
export function asJaar(jaar, soort) {
  return soort === 'schooljaar' ? schooljaarLabel(jaar) : String(jaar)
}
