import { useEffect, useState } from 'react'
import { flushSync } from 'react-dom'
import { NPULS, NPULS_LETTER, NPULS_LOGO_SVG, NPULS_PRODUCTNAAM } from '../npulsHuisstijl'

// De printkop van een vast dashboard (#1127), dezelfde als die van de rapport-PDF (#1037): logo en productnaam, de naam van
// het dashboard in oranje, roze chips met de instelling en de datum, een oranje lijn eronder, zwart in de Npuls-letter.
// Kleuren, letter en logo komen uit npulsHuisstijl.js, geen eigen opmaak. Op het scherm staat hij uit (`.db-printkop` in
// styles.css) en op papier staat hij boven de inhoud.

const datumNl = datum => datum.toLocaleDateString('nl-NL', { day: 'numeric', month: 'long', year: 'numeric' })

// Zoals de datum in het rapport: "20 november 2026".
export const afdrukDatum = (nu = new Date()) => datumNl(nu)

const STIJL = {
  kop: { fontFamily: NPULS_LETTER, color: NPULS.zwart, borderBottom: `2px solid ${NPULS.oranje}`, paddingBottom: 16, marginBottom: 16 },
  merk: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, fontSize: 14, fontWeight: 600, color: NPULS.zwart },
  label: { color: NPULS.blauw, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 6 },
  titel: { fontSize: 24, fontWeight: 600, color: NPULS.oranje, lineHeight: 1.3 },
  chips: { display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 },
  chip: {
    background: NPULS.roze, color: NPULS.zwart, padding: '2px 8px', borderRadius: 4, fontSize: 12,
    WebkitPrintColorAdjust: 'exact', printColorAdjust: 'exact',
  },
}

export default function DashboardPrintkop({ titel, instelling }) {
  const [datum, setDatum] = useState(afdrukDatum)
  // De datum is die van het afdrukken, niet van het openen: een dashboard kan dagen openstaan. flushSync, want de browser
  // drukt direct na dit event af en wacht niet op een geplande render.
  useEffect(() => {
    const voor = () => flushSync(() => setDatum(afdrukDatum()))
    window.addEventListener('beforeprint', voor)
    return () => window.removeEventListener('beforeprint', voor)
  }, [])

  return (
    <div className="db-printkop" style={STIJL.kop}>
      <div data-onderdeel="merk" style={STIJL.merk}>
        <span style={{ display: 'flex' }} dangerouslySetInnerHTML={{ __html: NPULS_LOGO_SVG }} />
        <span>{NPULS_PRODUCTNAAM}</span>
      </div>
      <div style={STIJL.label}>Dashboard</div>
      <div data-onderdeel="titel" style={STIJL.titel}>{titel}</div>
      <div style={STIJL.chips}>
        {instelling && <span data-onderdeel="instelling" style={STIJL.chip}>{instelling}</span>}
        <span style={STIJL.chip}>Afgedrukt op {datum}</span>
      </div>
    </div>
  )
}
