/* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */
import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { deleteMijnGegevens } from '../api'
import { wachtOpOpslag } from '../gesprekOpslag'
import { useDialog } from '../hooks/useDialog'
import MijnGegevensExport from './MijnGegevensExport'

// "Verwijder al mijn gegevens" (#646, AVG art. 17): alles wat de server onder dit account bewaart, in één keer weg.
// Dat kan niet terug, dus de dialoog zegt wat verdwijnt, biedt eerst de export aan en vraagt om het woord
// "verwijder". De server eist zelf ook die bevestiging; de knop stuurt altijd de vaste tekst. De foutmelding is een
// vaste zin, nooit de technische fout (zoals "API 500" of "Failed to fetch"). Na succes ruimt de app de browser op
// en toont de loginpagina GEGEVENS_VERWIJDERD (App.jsx).
export const BEVESTIGWOORD = 'verwijder'
export const VERWIJDEREN_MISLUKT = 'Het verwijderen is niet gelukt. Probeer het later opnieuw.'
export const GEGEVENS_VERWIJDERD = 'Al je gegevens zijn verwijderd. Je bent uitgelogd.'

// Een telefoontoetsenbord begint met een hoofdletter en zet soms een spatie achter het woord.
export const isBevestigd = invoer => invoer.trim().toLowerCase() === BEVESTIGWOORD

export default function MijnGegevensVerwijderen({ onVerwijderd, verwijder = deleteMijnGegevens }) {
  const [open, setOpen] = useState(false)
  const knopRef = useRef(null)
  const focusTerug = useRef(false)

  // Terug naar de knop die de dialoog opende, ook in een browser die een knop bij een klik geen focus geeft.
  useEffect(() => {
    if (open || !focusTerug.current) return
    focusTerug.current = false
    knopRef.current?.focus()
  }, [open])

  const sluit = () => {
    focusTerug.current = true
    setOpen(false)
  }

  return (
    <div className="mijn-gegevens-verwijderen">
      <button type="button" ref={knopRef} className="mijn-gegevens-verwijderen-btn" onClick={() => setOpen(true)}>
        Verwijder al mijn gegevens
      </button>
      {open && <VerwijderDialoog onClose={sluit} onVerwijderd={onVerwijderd} verwijder={verwijder} />}
    </div>
  )
}

function VerwijderDialoog({ onClose, onVerwijderd, verwijder }) {
  const [invoer, setInvoer] = useState('')
  const [busy, setBusy] = useState(false)
  const [mislukt, setMislukt] = useState(false)
  const busyRef = useRef(false)
  const invoerRef = useRef(null)
  const bevestigRef = useRef(null)
  const focusTerug = useRef(false)
  const titelId = useId()
  const uitlegId = useId()
  const invoerId = useId()
  // Tijdens het verzoek sluiten Escape, de achtergrond en Annuleren niets: het verzoek loopt toch door.
  const dialogRef = useDialog(() => { if (!busyRef.current) onClose() })
  const bevestigd = isBevestigd(invoer)

  // Na useDialog, die de focus op het eerste element zet (de exportknop): de focus hoort in het veld.
  useEffect(() => { invoerRef.current?.focus() }, [])

  // Tijdens het verzoek is de knop uitgeschakeld en verliest hij de focus; mislukt het, dan krijgt hij die terug.
  useEffect(() => {
    if (busy || !focusTerug.current) return
    focusTerug.current = false
    bevestigRef.current?.focus()
  }, [busy])

  async function onSubmit(e) {
    e.preventDefault()
    if (!bevestigd || busyRef.current) return
    busyRef.current = true
    focusTerug.current = document.activeElement === bevestigRef.current
    setBusy(true)
    setMislukt(false)
    try {
      // Een opslag die nog loopt, zou na het wissen een gesprek terugzetten (#635).
      await wachtOpOpslag()
      const resultaat = await verwijder()
      onVerwijderd(resultaat)
    } catch {
      setMislukt(true)
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }

  const sluitVanAchtergrond = e => {
    // A portal's click still bubbles through the React tree to the settings backdrop: stop it here.
    e.stopPropagation()
    if (!busyRef.current) onClose()
  }

  return createPortal(
    <div className="confirm-overlay mijn-gegevens-verwijderen-overlay" onClick={sluitVanAchtergrond}>
      <div
        className="confirm-dialog mijn-gegevens-verwijderen-dialog"
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titelId}
        aria-describedby={uitlegId}
        tabIndex={-1}
        onClick={e => e.stopPropagation()}
      >
        <h2 className="mijn-gegevens-verwijderen-titel" id={titelId}>Al je gegevens verwijderen?</h2>
        <div id={uitlegId} className="mijn-gegevens-verwijderen-uitleg">
          <p>
            Dit verwijdert alles wat de server onder je account bewaart: je gesprekken, je rapporten en dashboards,
            al je feedback (bij rapporten, per antwoord en via de link Feedback) en je datarecepten.{' '}
            <strong>Dit kan niet ongedaan worden gemaakt.</strong>
          </p>
          <p>
            Ook de kopie in deze browser gaat weg en je wordt uitgelogd. Op een ander apparaat blijft de kopie staan
            tot je daar uitlogt.
          </p>
          <p>Gebruik je dit account samen met anderen? Dan verdwijnt hun werk ook.</p>
        </div>
        <p className="mijn-gegevens-verwijderen-export-tip">Bewaar eerst een kopie van je gegevens:</p>
        <MijnGegevensExport />
        {/* One form for field and buttons: Enter in the field submits it. */}
        <form onSubmit={onSubmit}>
          <label htmlFor={invoerId} className="mijn-gegevens-verwijderen-label">
            Typ <strong>{BEVESTIGWOORD}</strong> om te bevestigen
          </label>
          <input
            id={invoerId}
            ref={invoerRef}
            className="mijn-gegevens-verwijderen-invoer"
            type="text"
            value={invoer}
            onChange={e => setInvoer(e.target.value)}
            autoCapitalize="off"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
          />
          {mislukt && <p className="mijn-gegevens-verwijderen-fout" role="alert">{VERWIJDEREN_MISLUKT}</p>}
          <div className="confirm-actions mijn-gegevens-verwijderen-acties">
            <button type="button" className="confirm-cancel" onClick={onClose} disabled={busy}>Annuleren</button>
            <button type="submit" ref={bevestigRef} className="confirm-destructive mijn-gegevens-verwijderen-bevestig"
              disabled={!bevestigd || busy} aria-busy={busy ? 'true' : 'false'}>
              {busy ? 'Bezig met verwijderen…' : 'Definitief verwijderen'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  )
}
