// De financiën van een bestuur (#935) en het personeel van een universiteit (#936), zoals de eindpunten ze geven;
// gedeeld door dashboardFinancien.test.js en de axe-poort (toegankelijkheidApp.test.js, #973).

// Zoals tools/financien.voor_instelling het geeft (de getallen van tests/test_financien.py).
const jaar = (verslagjaar, variant, extra = {}) => ({
  verslagjaar, variant,
  solvabiliteit_1: { bestuur: 0.69, sector: 0.64, verschil: 0.05 },
  solvabiliteit_2: { bestuur: 0.75, sector: 0.7, verschil: 0.05 },
  liquiditeit: { bestuur: 3.2, sector: 2.1, verschil: 1.1 },
  rentabiliteit_procent: { bestuur: 2.01, sector: 1.5, verschil: 0.51 },
  rijksbijdragen_eur: 197021000, rijksbijdragen_mln_eur: 197,
  liquiditeit_signaleringswaarde: 0.5, signaleringen: [], ...extra,
})
export const FIN = {
  gevonden: true, instelling: 'Hogeschool Dun', sector: 'hbo',
  financien: {
    sleutel: '30000',
    bestuur: { nummer: '30000', naam: 'Stichting Hogeschool Dun', sector: 'hbo', groepering: 'HBO' },
    instelling: { naam: 'Hogeschool Dun', instellingscode: '30DN' },
    eenheden: [{
      eenheid: '30000', naam: 'Stichting Hogeschool Dun',
      reeks: [
        jaar(2024, 'geconsolideerd'),
        jaar(2025, 'enkelvoudig', {
          solvabiliteit_2: { bestuur: 0.25, sector: 0.54, verschil: -0.29 },
          liquiditeit: { bestuur: 0.6, sector: 1.24, verschil: -0.64 },
          rentabiliteit_procent: { bestuur: null, sector: -4.55 },
          liquiditeit_signaleringswaarde: 1.0,
          signaleringen: [
            { kengetal: 'solvabiliteit_2', waarde: 0.25, signaleringswaarde: 0.3 },
            { kengetal: 'liquiditeit', waarde: 0.6, signaleringswaarde: 1.0, trede: 'totale baten van € 3 tot en met € 12 miljoen' },
          ],
        }),
      ],
      melding: 'De variant wisselt binnen de reeks (geconsolideerd 2024, enkelvoudig 2025): een verschil rond de wissel kan door de variant komen in plaats van door de financiële positie.',
    }],
    sectorcijfer: { sector: 'hbo', methode: 'Gewogen', eenheden_per_jaar: { 2024: 35, 2025: 35 } },
    definities: { solvabiliteit_2: 'Solvabiliteit II: (eigen vermogen + voorzieningen) / totaal passiva (definitie DUO).' },
    signaleringswaarden: { solvabiliteit_2: 'onder 0,30', bron: 'Inspectie van het Onderwijs', jaar: 2024 },
    solvabiliteit_2_signaleringswaarde: 0.3,
    voorbehouden: ['Het cijfer geldt voor het hele bestuur (bevoegd gezag), niet voor één instelling.', 'Een signaleringswaarde van de Inspectie is een signaal, geen oordeel.'],
    meldingen: ['Ook Hogeschool Dik valt onder dit bestuur: de cijfers gelden voor het hele bestuur, voor elk van zijn instellingen gelijk.'],
    bron: { editie: 'verslagjaren 2021-2025' },
  },
}

// Zoals tools/wo_personeel.reeks_van het geeft (Universiteit Utrecht op het proefbestand).
export const PERS = {
  gevonden: true, instelling: 'Universiteit Utrecht', sector: 'wo',
  personeel: {
    eenheid: 'fte', gezo: 'excl', instelling: { naam: 'Universiteit Utrecht', brin: '21PD' },
    cijfers: [
      { jaar: 2002, peildatum: '31-12-2002', totaal: 4329.05, obp: 1820.2, wetenschappelijk_personeel: 2508.85, vast: null, tijdelijk: null, aandeel_tijdelijk_procent: null },
      { jaar: 2024, peildatum: '31-12-2024', totaal: 6060.67, obp: 2548.3, wetenschappelijk_personeel: 3512.37, vast: 3800, tijdelijk: 2200, aandeel_tijdelijk_procent: 36.7 },
      { jaar: 2025, peildatum: '31-12-2025', totaal: 6184.36, obp: 2600.31, wetenschappelijk_personeel: 3584.05, vast: 3900, tijdelijk: 2250, aandeel_tijdelijk_procent: 36.6 },
    ],
    definitie: 'Wetenschappelijk personeel (WP) = hoogleraren, … ; OBP = ondersteunend en beheerspersoneel.',
    voorbehouden: ['Peildatum 31 december van elk jaar: personeel in dienst op die dag.', 'fte is geen aantal personen: 1 fte is een volledige werkweek (38 uur).'],
    noot: 'Vast en tijdelijk bestaan vanaf 2003.',
    bron: { regel: 'WOPI 2025, Universiteiten van Nederland, peildatum 31-12-2025, excl. sector Gezondheid' },
  },
}

export const FIN_BRON = {
  bron: 'DUO', dataset: 'financien', titel: 'Financiële verantwoording uit XBRL', url: 'https://duo.nl/x',
  editie: 'verslagjaren 2021-2025', peilmoment: 'editie verslagjaren 2021-2025, versie van 15 september 2026',
  peildatum: '31 december 2025', voorlopig: false, voorlopig_jaren: [], opgehaald_op: '2026-11-06T09:30:00+00:00',
}
export const WOPI_BRON = {
  bron: 'UNL', dataset: 'unl:wopi', titel: 'Universiteiten van Nederland, WOPI-personeelsbestand', url: 'https://unl.nl',
  editie: '2025', peilmoment: 'editie 2025', peildatum: '31-12-2025', voorlopig: false, voorlopig_jaren: [],
  opgehaald_op: '2026-11-06T09:30:00+00:00',
}
