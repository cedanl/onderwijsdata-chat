import { createContext, useContext, useMemo } from 'react'
import { Bar, Line } from 'react-chartjs-2'
import WaardenTabel from '../../WaardenTabel'
import { figuurBeschrijving } from '../../../figuurBeschrijving'
import { figuurTabel } from '../../../figuurTabel'
import { alsFiguur, waardeAsTitel } from './grafiek-figuur'

// De titel van de kaart om een grafiek heen (ChartCard); de grafiek noemt hem in haar beschrijving.
export const GrafiekTitel = createContext(null)

const SOORTEN = { line: Line, bar: Bar }

// Een grafiek van een dashboard (#905), zoals een figuur in de chat (PlotlyFigure.jsx): het canvas heeft al
// role="img" (react-chartjs-2) en krijgt hier zijn naam, een zin met de cijfers (#588); daaronder de waarden als
// ingeklapte tabel (#664), voor wie geen tooltip kan of wil gebruiken. `titel` gaat voor de titel van de kaart;
// `categorie` noemt de labelkolom van de tabel (anders 'Jaar' of 'Categorie').
export function Grafiek({ soort, data, options, hoogte, titel, categorie }) {
  const kaartTitel = useContext(GrafiekTitel)
  const naam = titel ?? kaartTitel
  const waardeAs = waardeAsTitel(options)
  const figuur = useMemo(() => alsFiguur(soort, data, { titel: naam, categorie, waardeAs }), [soort, data, naam, categorie, waardeAs])
  const beschrijving = useMemo(() => figuurBeschrijving(figuur), [figuur])
  const tabel = useMemo(() => figuurTabel(figuur), [figuur])
  const Soort = SOORTEN[soort]
  return (
    <>
      <div style={{ height: hoogte }}>
        <Soort data={data} options={options} aria-label={beschrijving ?? naam ?? 'Grafiek'} />
      </div>
      {tabel && <WaardenTabel tabel={tabel} />}
    </>
  )
}
