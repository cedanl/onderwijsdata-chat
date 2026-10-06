// An answer the check took back (#398): out of the way, but still there to see.
export default function IngetrokkenVersies({ versies }) {
  if (!versies?.length) return null
  return (
    <details className="message-ingetrokken">
      <summary>
        {versies.length === 1 ? 'Eerdere versie ingetrokken na controle' : `${versies.length} eerdere versies ingetrokken na controle`}
      </summary>
      {versies.map((v, i) => <p key={i} className="message-ingetrokken-tekst">{v.tekst}</p>)}
    </details>
  )
}
