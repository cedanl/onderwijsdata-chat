// An answer the check took back (#398): out of the way, but still there to see.
// Only a version that differs from the final answer, with the check's reason (CH-01):
// an empty block, or one with the same text as the answer, says nothing.
// The heading is plain language: "ingetrokken" read as internal noise (#496, F-01).
export default function IngetrokkenVersies({ versies, eindtekst = '' }) {
  const anders = (versies || []).filter(v => v.tekst?.trim() && v.tekst.trim() !== eindtekst.trim())
  if (!anders.length) return null
  return (
    <details className="message-ingetrokken">
      <summary>
        {anders.length === 1
          ? 'Eerste versie van dit antwoord is aangepast na controle — bekijk wat er veranderde'
          : `${anders.length} eerdere versies van dit antwoord zijn aangepast na controle — bekijk wat er veranderde`}
      </summary>
      {anders.map((v, i) => (
        <div key={i}>
          {v.reden?.length > 0 && <p className="message-ingetrokken-reden">Reden: {v.reden.join(' ')}</p>}
          <p className="message-ingetrokken-tekst">{v.tekst}</p>
        </div>
      ))}
    </details>
  )
}
