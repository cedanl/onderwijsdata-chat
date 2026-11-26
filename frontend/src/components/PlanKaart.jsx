import { useEffect, useId, useRef } from 'react'

// De plankaart (#1268): vóór een vraag over meer bronnen laat de app eerst zien wat ze gaat laden, uit code. "Klopt, ga
// door" laadt precies dit plan; "Pas aan" zet de vraag met de plankeuzes terug in het invoerveld, zonder te laden.
// Een kaart die net binnenkwam (status 'open') krijgt de focus, zodat een schermlezer haar meteen voorleest en het
// toetsenbord bij de knoppen is. Wat er van de kaart werd (planStatus in planState.js) blijft na herladen staan.
const STATUSREGEL = {
  bevestigd: 'Je koos "Klopt, ga door": de app laadt dit plan.',
  aangepast: 'Je koos "Pas aan": je vraag en het plan staan in het invoerveld.',
  voorbij: 'Je stelde een nieuwe vraag; dit plan is niet uitgevoerd.',
  verlopen: 'Dit plan is niet meer open. Kies "Pas aan" om je vraag opnieuw te stellen.',
}

export default function PlanKaart({ plan, status = 'open', onBevestig = null, onAanpassen = null, busy = false }) {
  const kopId = useId()
  const ref = useRef(null)
  const open = status === 'open'

  useEffect(() => {
    if (open) ref.current?.focus()
  }, [open])

  if (!plan) return null
  const kanAanpassen = (open || status === 'verlopen') && !!onAanpassen

  return (
    <section ref={ref} className="plan-kaart" aria-labelledby={kopId} tabIndex={-1}>
      <h2 id={kopId} className="plan-kaart-kop">Eerst het plan: klopt dit?</h2>
      <p className="plan-kaart-uitleg">
        Je vraag gaat over meer bronnen. Dit laadt de app als je doorgaat; dat duurt {plan.duur || 'even'}.
      </p>
      <ol className="plan-kaart-bronnen">
        {plan.bronnen.map(bron => (
          <li key={`${bron.dataset}-${bron.titel}`} className="plan-bron">
            <span className="plan-bron-titel">{bron.titel}</span>
            <span className="plan-bron-meta">
              {bron.dataset && bron.dataset !== bron.titel ? `${bron.dataset}, ` : ''}{bron.versie}
            </span>
            {bron.selectie.length > 0 && (
              <ul className="plan-bron-selectie" aria-label={`Selectie uit ${bron.titel}`}>
                {bron.selectie.map(regel => <li key={regel}>{regel}</li>)}
              </ul>
            )}
          </li>
        ))}
      </ol>
      <p className="plan-kaart-sleutel">
        {plan.sleutel ? <>Koppelen op <strong>{plan.sleutel}</strong>.</> : 'Naast elkaar, zonder koppeling.'}
      </p>
      {(open || kanAanpassen) && (
        <div className="plan-kaart-knoppen" role="group" aria-label="Wat wil je met dit plan?">
          {open && onBevestig && (
            <button type="button" className="plan-knop plan-knop-door" onClick={() => onBevestig()} disabled={busy}>
              Klopt, ga door
            </button>
          )}
          {kanAanpassen && (
            <button type="button" className="plan-knop plan-knop-aanpassen" onClick={() => onAanpassen()}
              aria-label="Pas aan: zet je vraag en het plan in het invoerveld">
              Pas aan
            </button>
          )}
        </div>
      )}
      {!open && <p className="plan-kaart-status" role="status">{STATUSREGEL[status]}</p>}
    </section>
  )
}
