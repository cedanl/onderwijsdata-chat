// Een markdown-tabel in een antwoord scrolt zelf zijwaarts als hij breder is dan de tekstkolom (#626). Zonder
// deze verpakking duwde een brede tabel de hele berichtenlijst breder dan het scherm. Focusbaar, zodat ook wie
// met het toetsenbord werkt de tabel kan verschuiven.
// eslint-disable-next-line no-unused-vars -- node is react-markdown's AST node, not a DOM attribute
export default function TabelScroll({ node, children, ...props }) {
  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scrollable region must take focus (WCAG 2.1.1); not every browser focuses it by itself
    <div className="tabel-scroll" role="region" aria-label="Tabel" tabIndex={0} onScroll={geefScrollDoor}>
      <table {...props}>{children}</table>
    </div>
  )
}

// Een open herkomst van een getal in de tabel hangt buiten deze scrollbox, anders knipte die hem af (#657,
// styles.css); met de scrollpositie als CSS-variabele schuift hij met de tabel mee.
function geefScrollDoor(e) {
  const box = e.currentTarget
  box.style.setProperty('--tabel-scroll-x', `${box.scrollLeft}px`)
  box.style.setProperty('--tabel-scroll-y', `${box.scrollTop}px`)
}
