// Privacy-informatie (#477): wat naar de AI-dienst gaat, wat de server en de browser bewaren en wat
// je zelf kunt doen. De pagina /privacy (ook vóór het inloggen) en de popup (#572) tonen allebei
// deze ene tekst. Dezelfde tekst staat in docs/privacy.md; privacyPage.test.js bewaakt dat de kopjes
// gelijk blijven. Open punten (verantwoordelijke, verwerkersovereenkomst, regio, bewaartermijn) staan
// onderaan als open punten, niet als feit: dit is de demofase.

export const PRIVACY_KOPJES = [
  'Wat naar de AI-dienst gaat',
  'Wat de server bewaart',
  'Wat in je browser staat',
  'Het logboek',
  'Wat je zelf kunt doen',
  'Verantwoordelijke en contact',
  'Open punten',
]

export default function PrivacyInhoud() {
  return (
    <div className="privacy-text">
      <h1>Privacy-informatie</h1>
      <p className="privacy-page-lead">
        Hoe openEDUdata+ met je gegevens omgaat. Dit beschrijft de werking van de demoversie; de formele
        privacyverklaring volgt zodra de open punten onderaan zijn vastgesteld.
      </p>

      <h2>{PRIVACY_KOPJES[0]}</h2>
      <ul>
        <li>
          Je vraag, de eerdere berichten van het gesprek, je instelling en functie uit je profiel en de opgehaalde
          data gaan naar een externe AI-dienst die het antwoord formuleert. Welke dienst en welk model dat is, staat
          onder het invoerveld; op de omgevingen van SURF is dat Microsoft Azure AI Foundry met een Claude-model.
        </li>
        <li>
          De cijfers zelf komen van open bronnen (CBS, DUO en RIO). Daarheen gaat alleen de opvraag (welke tabel,
          welke selectie), niets over jou.
        </li>
        <li>
          Voer geen persoonsgegevens in. De app herkent een BSN, een e-mailadres en een telefoonnummer en waarschuwt
          dan, maar blokkeert niet; een naam herkent zij niet.
        </li>
      </ul>

      <h2>{PRIVACY_KOPJES[1]}</h2>
      <ul>
        <li>
          <strong>Gesprekken</strong>: vraag, antwoord, toolstappen en titel, per account, tot je het gesprek
          verwijdert.
        </li>
        <li>
          <strong>Rapporten en dashboards</strong>: blijven bewaard als je het gesprek verwijdert (de
          verwijderdialoog zegt dat); verwijder ze apart onder Rapporten.
        </li>
        <li>
          <strong>Feedback</strong>: je antwoorden op de vragen bij een rapport of dashboard, en per antwoord je
          duim met toelichting plus een kopie van vraag, antwoord en stappen. Verwijder je het gesprek, dan wordt
          die kopie losgekoppeld van je account en het gesprek, maar blijft zij voor het team bewaard. Wat je via
          de link Feedback stuurt, bewaren we met je accountnaam, de soort die je koos en de pagina waar je was.
        </li>
        <li>
          <strong>Datarecepten</strong>: hoe een tabel is opgehaald (dataset en selectie), zodat een export na een
          herstart nog werkt. Gaan weg met het gesprek.
        </li>
        <li>
          <strong>Inloggen</strong>: met een gebruikersnaam en wachtwoord bewaart de server alleen je
          gebruikersnaam bij je gegevens. Met SURF SRAM is je e-mailadres je accountnaam, ook als auteur van een
          rapport; je naam, organisatie en instelling staan tijdens je sessie in het geheugen van de server (ten
          hoogste 24 uur). Een ingetrokken sessie wordt als hash bewaard tot zij verloopt.
        </li>
        <li>
          <strong>Bewaartermijn</strong>: er is nog geen automatische opschoning; gegevens blijven staan tot je ze
          zelf verwijdert.
        </li>
      </ul>

      <h2>{PRIVACY_KOPJES[2]}</h2>
      <ul>
        <li>
          In de opslag van je browser staan een kopie van je gesprekken en het lopende gesprek, je werkboeken, de
          dashboardchat, je profiel (instelling, functie, weergave) en je sessie. Uitloggen wist dit allemaal uit
          deze browser.
        </li>
        <li>
          Welke gesprekken en rapporten je hier het laatst opende en welke rapporten je als favoriet markeerde, staan
          er als nummers, zonder titel of inhoud. Die blijven na uitloggen staan, zodat je ze een volgende keer
          terugvindt; ze verschijnen alleen bij een gesprek of rapport van het account waarmee je inlogt. Anderen met
          hetzelfde account zien ze niet.
        </li>
        <li>
          Een sessie duurt 8 uur en wordt bij gebruik verlengd tot ten hoogste 24 uur na het inloggen. Tijdens het
          inloggen met SRAM staat er kort een cookie voor de beveiliging van die stap; verder gebruikt de app geen
          cookies en geen analytics.
        </li>
      </ul>

      <h2>{PRIVACY_KOPJES[3]}</h2>
      <ul>
        <li>
          Het serverlog bevat op het normale niveau geen gesprekstekst: van een vraag, een antwoord en de
          toolargumenten staan alleen de lengte en een hash in het log, naast tijdstippen, toolnamen en het model.
          Alleen op het foutzoekniveau, dat niet standaard aanstaat, staat tekst in het log.
        </li>
      </ul>

      <h2>{PRIVACY_KOPJES[4]}</h2>
      <ul>
        <li>Een gesprek verwijderen in de gesprekslijst; een rapport of dashboard verwijderen onder Rapporten.</li>
        <li>Een gesprek exporteren als Markdown en de tabel achter een antwoord downloaden als CSV.</li>
        <li>
          Al je gegevens in één keer verwijderen of exporteren kan nog niet; dat staat bij de open punten.
        </li>
      </ul>

      <h2>{PRIVACY_KOPJES[5]}</h2>
      <p>
        openEDUdata+ is een project van CEDA (Npuls). Wie de verwerkingsverantwoordelijke is en bij wie je terecht
        kunt met een privacyvraag, wordt vastgesteld vóór de demofase eindigt; tot die tijd kun je vragen stellen aan
        het projectteam van CEDA.
      </p>

      <h2>{PRIVACY_KOPJES[6]}</h2>
      <ul>
        <li>Verwerkingsverantwoordelijke (Npuls, SURF of de instelling), contactpunt en functionaris gegevensbescherming.</li>
        <li>Verwerkersovereenkomst met de AI-aanbieder, de regio van het eindpunt en de afspraak dat invoer niet wordt bewaard of gebruikt voor training.</li>
        <li>Bewaartermijn per gegevenssoort, opschoning, en in één keer alles verwijderen of exporteren.</li>
        <li>Of er een DPIA nodig is.</li>
      </ul>
    </div>
  )
}
