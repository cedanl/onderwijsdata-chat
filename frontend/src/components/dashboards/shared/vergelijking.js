// Waar de vergelijkingsgroep van "Mijn instelling" woont (#1130): een hogeschool of universiteit zonder genoeg collega's
// in haar regio of provincie vergelijkt met heel Nederland (benchmark.regio_type "nationaal"). Elke titel, ondertitel,
// legenda en alt-tekst die het gebied noemt, haalt het woord hier, zodat "regio" niet blijft staan bij een landelijke groep.

export const isLandelijk = benchmark => benchmark?.regio_type === 'nationaal'

// Het gebied, achter "in": "in de regio", "in heel Nederland".
export const gebiedTekst = landelijk => (landelijk ? 'heel Nederland' : 'de regio')

// Het totaal van de groep, ook als zelfstandig naamwoord achter "het": "het regiototaal", "het landelijke totaal".
export const totaalTekst = landelijk => (landelijk ? 'landelijke totaal' : 'regiototaal')
