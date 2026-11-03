import { useEffect, useId, useRef, useState } from 'react'
import { useDialog } from '../hooks/useDialog'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { aanBeurten, metKeuze, voortbouwNotitie } from '../rapportKeuze'

// Before a report (#751): the research question it answers, filled in and open to change (#732). Genereer, or Enter
// as in the chat input, sends the text along; an empty field sends none, and the server takes the first question.
// Escape or Annuleren closes without a report.
//
// Above the field, the checklist of turns with data (#908): which of them the report rests on. All on to begin with; the
// user switches off what does not belong (a side step, the wrong dataset). The field stays the user's: it is not
// rewritten from the choice. The list comes from the server; without one (an older conversation without evidence per
// turn, no data, a failed request) the dialog is the field alone, and the report rests on the whole conversation.

// On a phone the list starts collapsed, so the field is not pushed off the screen (keep in step with styles.css).
const KLEIN_SCHERM = '(max-width: 600px)'
const NIETS_GEKOZEN = 'Kies minstens één vraag met data voor het rapport. Zonder data kan er geen rapport komen.'

// The field grows with the question, so all of it shows; max-height in styles.css caps it on a small screen.
function pasHoogteAan(veld) {
  veld.style.height = 'auto'
  veld.style.height = `${veld.scrollHeight + veld.offsetHeight - veld.clientHeight}px`
}

export default function OnderzoeksvraagDialoog({ voorstel, max, checklist, onGenereer, onClose }) {
  const dialogRef = useDialog(onClose)
  const veldRef = useRef(null)
  const labelId = useId()
  const veldId = useId()
  const uitlegId = useId()
  const keuzeId = useId()
  const foutId = useId()
  const [tekst, setTekst] = useState(() => voorstel.slice(0, max))
  const [uit, setUit] = useState(() => new Set())
  const klein = useMediaQuery(KLEIN_SCHERM)
  const items = checklist?.items ?? []
  const keuze = metKeuze(checklist)
  const aan = aanBeurten(items, uit)
  const nietsGekozen = keuze && aan.length === 0
  // Until the list is in, Genereer would send the whole conversation: it comes in a moment, or the request fails.
  const wacht = checklist?.status === 'laden'

  // The focus goes to the field, below the checklist; the cursor goes to the end, where a narrowing gets added.
  useEffect(() => {
    const veld = veldRef.current
    veld.focus()
    pasHoogteAan(veld)
    veld.setSelectionRange(veld.value.length, veld.value.length)
  }, [])

  function wissel(beurt, aangevinkt) {
    setUit(vorige => {
      const volgende = new Set(vorige)
      if (aangevinkt) volgende.delete(beurt)
      else volgende.add(beurt)
      return volgende
    })
  }

  function genereer(e) {
    e.preventDefault()
    if (wacht || nietsGekozen) return
    onGenereer(tekst.trim(), keuze ? aan : undefined)
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) genereer(e)
  }

  return (
    <div className="confirm-overlay">
      <form className="confirm-dialog onderzoeksvraag-dialoog" ref={dialogRef} role="dialog" aria-modal="true"
        aria-labelledby={labelId} tabIndex={-1} onSubmit={genereer}>
        {keuze && (
          <details className="rapport-keuze" open={!klein}>
            <summary className="rapport-keuze-samenvatting">Vragen in het rapport: {aan.length} van {items.length}</summary>
            <fieldset className="rapport-keuze-set" aria-describedby={nietsGekozen ? foutId : undefined}>
              <legend className="rapport-keuze-legend">Welke vragen met data horen in het rapport?</legend>
              <ul className="rapport-keuze-lijst">
                {items.map(item => {
                  const bron = [...(item.bronnen ?? []), voortbouwNotitie(item, items)].filter(Boolean).join(' · ')
                  return (
                    <li key={item.beurt}>
                      <label>
                        <input type="checkbox" checked={!uit.has(item.beurt)} onChange={e => wissel(item.beurt, e.target.checked)}
                          aria-describedby={bron ? `${keuzeId}-${item.beurt}` : undefined} />
                        <span>
                          <span className="rapport-keuze-vraag">{item.vraag}</span>
                          {bron && <span className="rapport-keuze-bron" id={`${keuzeId}-${item.beurt}`}>{bron}</span>}
                        </span>
                      </label>
                    </li>
                  )
                })}
              </ul>
            </fieldset>
          </details>
        )}
        {nietsGekozen && <p className="rapport-keuze-fout" id={foutId} role="alert">{NIETS_GEKOZEN}</p>}
        {wacht && <p className="onderzoeksvraag-uitleg" role="status">De vragen met data worden opgehaald…</p>}
        {checklist?.status === 'fout' && (
          <p className="onderzoeksvraag-uitleg" role="status">
            De vragen met data konden niet worden opgehaald. Het rapport gebruikt het hele gesprek.
          </p>
        )}
        <label className="onderzoeksvraag-label" id={labelId} htmlFor={veldId}>Onderzoeksvraag van het rapport</label>
        <textarea
          ref={veldRef}
          id={veldId}
          className="onderzoeksvraag-veld"
          rows={2}
          value={tekst}
          maxLength={max}
          aria-describedby={uitlegId}
          onChange={e => { setTekst(e.target.value); pasHoogteAan(e.target) }}
          onKeyDown={onKeyDown}
        />
        <p className="onderzoeksvraag-uitleg" id={uitlegId}>
          Het rapport beantwoordt deze vraag. Pas haar aan om af te bakenen. Leeg laten: het rapport neemt je eerste vraag.
        </p>
        <div className="confirm-actions">
          <button type="button" className="confirm-cancel" onClick={onClose}>Annuleren</button>
          <button type="submit" className="confirm-primary" aria-disabled={wacht || nietsGekozen || undefined}
            aria-describedby={nietsGekozen ? foutId : undefined}>Genereer</button>
        </div>
      </form>
    </div>
  )
}
