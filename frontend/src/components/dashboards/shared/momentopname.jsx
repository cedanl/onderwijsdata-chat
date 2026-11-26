// De UWV-vacatures zijn een momentopname (#900): elk onderdeel dat ze gebruikt, noemt de peildatum uit de payload,
// niet een vaste maand. De arbeidsmarktmatch zegt daarbij wat haar labels betekenen en wat ze niet zeggen; de drempel,
// de jaren en de herkomst van de sectorindeling komen uit `match_duiding` (data/dashboard.py, _match_duiding).
// Hoe oud de peildatum is, zegt de payload ook (#1219: `peildatum_ouderdom_maanden`, `verouderd`); de frontend rekent
// de ouderdom niet zelf uit, hij schrijft haar alleen in woorden.

import { fmt } from './getal'
import { langeDatum } from './datum'

// "2023-05-16" → "16 mei 2023"; meer peildata (komma's, zoals de server ze geeft) elk; iets anders ongewijzigd.
export function peildatumTekst(peildatum) {
  if (!peildatum) return null
  return String(peildatum).split(',').map(d => langeDatum(d)).join(', ')
}

function peildatumOfOnbekend(peildatum) {
  return peildatumTekst(peildatum) ? `peildatum ${peildatumTekst(peildatum)}` : 'peildatum onbekend'
}

// De ouderdom in woorden, met dezelfde regel als de backend (`ouderdom_tekst` in data/arbeidsmarkt.py): onder een maand
// "minder dan een maand", dan maanden, vanaf 12 maanden jaren met "ruim" als er maanden over zijn (42 → "ruim 3 jaar").
// Zonder ouderdom in de payload null.
export function ouderdomTekst(maanden) {
  if (maanden == null || !Number.isFinite(Number(maanden))) return null
  const m = Number(maanden)
  if (m < 1) return 'minder dan een maand'
  if (m < 12) return `${m} ${m === 1 ? 'maand' : 'maanden'}`
  return `${m % 12 ? 'ruim ' : ''}${Math.floor(m / 12)} jaar`
}

// "UWV Open Match, peildatum 16 mei 2023, ruim 3 jaar oud": voor ondertitels die de vacatures noemen. Zonder ouderdom
// in de payload alleen de peildatum.
export function uwvBron(peildatum, ouderdomMaanden) {
  const ouderdom = peildatumTekst(peildatum) ? ouderdomTekst(ouderdomMaanden) : null
  return `UWV Open Match, ${peildatumOfOnbekend(peildatum)}${ouderdom ? `, ${ouderdom} oud` : ''}`
}

// Waar de actuele vacatures per kwartaal staan (#1219, docs/databronnen.md); de app laadt ze niet.
export const UWV_VACATUREMARKT = 'https://www.uwv.nl/nl/arbeidsmarktinformatie/dashboards/dashboard-vacaturemarkt'
export const CBS_VACATURES = 'https://opendata.cbs.nl/#/CBS/nl/dataset/83599NED/table'

// De maand van de jongste peildatum ("mei 2023"): sindsdien werkt UWV de open dataset niet meer bij.
const MAAND_JAAR = new Intl.DateTimeFormat('nl-NL', { month: 'long', year: 'numeric', timeZone: 'UTC' })
function maandVanPeildatum(peildatum) {
  const datums = String(peildatum ?? '').split(',').map(d => d.trim()).filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d)).sort()
  if (!datums.length) return 'de peildatum'
  const [jaar, maand] = datums[datums.length - 1].split('-').map(Number)
  return MAAND_JAAR.format(new Date(Date.UTC(jaar, maand - 1, 1)))
}

function ExterneLink({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={`${children} (opent in een nieuw tabblad)`}>
      {children}
    </a>
  )
}

// [2023, 2024, 2025] → "2023 tot en met 2025"; één jaar is dat jaar; geen jaren is null.
export function jarenTekst(jaren) {
  if (!jaren?.length) return null
  return jaren.length === 1 ? String(jaren[0]) : `${jaren[0]} tot en met ${jaren[jaren.length - 1]}`
}

// De herkomst van de sectorindeling zoals de server haar noemt ("LLM-classificatie, niet van UWV"), zonder afkorting
// die de lezer niet kent (#1133): een taalmodel (AI) deelde de beroepenclusters in.
const HERKOMST_ONBEKEND = 'LLM-classificatie, niet van UWV'
export function herkomstTekst(herkomst) {
  return (herkomst || HERKOMST_ONBEKEND).replace(/LLM-classificatie/i, 'indeling door een taalmodel (AI)')
}

// De banner boven elk onderdeel met UWV-vacatures: peildatum en ouderdom ("peildatum 16 mei 2023 (ruim 3 jaar
// geleden)"). Is de stand verouderd (meer dan 12 maanden, zegt de payload), dan is hij een waarschuwing met de plekken
// waar de actuele kwartaalcijfers staan.
export function MomentopnameBanner({ peildatum, ouderdomMaanden, verouderd }) {
  const ouderdom = peildatumTekst(peildatum) ? ouderdomTekst(ouderdomMaanden) : null
  return (
    <div className={verouderd ? 'db-momentopname db-momentopname--verouderd' : 'db-momentopname'} role="note">
      <p>
        Momentopname: vacatures van UWV Open Match, {peildatumOfOnbekend(peildatum)}{ouderdom && ` (${ouderdom} geleden)`}.
        Geen historische reeks en geen actuele stand: gebruik als indicatie.
      </p>
      {verouderd && (
        <p>
          <strong>Verouderd:</strong> UWV werkt deze open dataset sinds {maandVanPeildatum(peildatum)} niet meer bij.
          UWV en CBS publiceren de actuele vacatures per kwartaal: het{' '}
          <ExterneLink href={UWV_VACATUREMARKT}>UWV-dashboard Vacaturemarkt</ExterneLink> en{' '}
          <ExterneLink href={CBS_VACATURES}>CBS-tabel 83599NED</ExterneLink>. Deze app laadt die cijfers (nog) niet.
        </p>
      )}
    </div>
  )
}

// Onder de aansluiting: bron, peildatum, drempel, de drie labels en wat de indicatie niet zegt.
export function MatchDuiding({ duiding }) {
  if (!duiding) return null
  const drempel = duiding.drempel != null ? fmt(duiding.drempel) : null
  const jaren = jarenTekst(duiding.diplomajaren)
  const mapping = duiding.sectormapping || {}
  const mappingVersie = mapping.mapping_versie && mapping.mapping_versie !== 'onbekend' ? `, versie ${mapping.mapping_versie}` : ''
  const minimum = duiding.min_gediplomeerden != null ? fmt(duiding.min_gediplomeerden) : null
  return (
    <div className="db-match-duiding dashboard-noot" role="note">
      <p>
        Per sector het aandeel in de gerelateerde vacatures ({uwvBron(duiding.vacatures_peildatum, duiding.peildatum_ouderdom_maanden)}) tegenover het
        aandeel in de gediplomeerden van deze instelling (DUO, {jaren ? `gemiddeld over de diplomajaren ${jaren}` : 'gemiddeld per jaar'}).
        Beide aandelen gelden binnen de sectoren van deze instelling.
      </p>
      {drempel && (
        <ul>
          <li><strong>Schaarste</strong>: het vacature-aandeel is meer dan {drempel} keer het diploma-aandeel.</li>
          <li><strong>Overaanbod</strong>: het diploma-aandeel is meer dan {drempel} keer het vacature-aandeel.</li>
          <li><strong>Evenwicht</strong>: geen van beide aandelen is meer dan {drempel} keer het andere.</li>
        </ul>
      )}
      <p>
        Wat deze indicatie niet zegt: de vacatures zijn een bevroren stand van één dag, de gediplomeerden een gemiddelde over
        meer jaren. Teller en noemer zijn dus verschillende grootheden: een voorraad vacatures in de hele provincie
        tegenover een jaarlijkse stroom diploma&apos;s van deze ene instelling; de verhouding zegt niet hoeveel vacatures er
        per gediplomeerde zijn. UWV legt bij vacatures geen opleidingsniveau vast, dus een sector telt ook banen op een
        ander niveau mee. Welke beroepenclusters bij een sector horen, is een indeling van deze app
        ({herkomstTekst(mapping.herkomst)}{mappingVersie}).
        {minimum && ` Een sector met minder dan ${minimum} gediplomeerden per jaar krijgt geen label: daar verschuift één diploma de verhouding te sterk.`}
      </p>
    </div>
  )
}
