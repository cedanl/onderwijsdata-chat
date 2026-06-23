export const SOURCES = [
  { label: 'DUO Open Data' },
  { label: '1cijferHO' },
  { label: 'CBS StatLine' },
  { label: 'UWV Arbeidsmarkt' },
  { label: 'ROA / SBB' },
]

export const SUGGESTED = [
  {
    category: 'Arbeidsmarkt',
    questions: [
      'Welk percentage van de bevolking in mijn regio neemt deel aan LLO?',
      'Wat is in mijn regio het opleidingsniveau van werkzoekenden?',
      'Hoeveel vacatures zijn er in mijn regio voor ons onderwijsaanbod?',
    ],
  },
  {
    category: 'Uitstroom',
    questions: [
      'Hoeveel gediplomeerden levert ons onderwijsaanbod op ten opzichte van andere instellingen in de regio?',
      'Wat verdienen gediplomeerden van onze instelling gemiddeld in de regio?',
      'Hoe groot is het aandeel voortijdig schoolverlaters dat werk heeft gevonden in mijn regio?',
    ],
  },
  {
    category: 'Instroom',
    questions: [
      'Waar komen mijn lerenden vandaan en met welke instellingen in de regio concurreer ik om dezelfde doelgroep?',
      'Hoeveel instromers komen rechtstreeks vanuit een andere opleiding uit de regio?',
      'Hoe heeft de deelname aan voltijdonderwijs bij ons zich ontwikkeld?',
    ],
  },
]
