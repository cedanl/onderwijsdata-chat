// Privacy-informatie (#477): wat naar de AI-dienst gaat, wat de server en de browser bewaren en wat
// je zelf kunt doen. De pagina /privacy (ook vóór het inloggen) en de popup (#572) tonen allebei
// deze ene tekst. docs/privacy.md is de technische versie voor wie de opzet toetst, met de tabellen en de code erbij;
// privacyPage.test.js bewaakt dat de kopjes gelijk blijven. Open punten (verwerkersovereenkomst, regio, bewaartermijn
// van logs en back-ups, DPIA) staan onderaan als open punten, niet als feit: dit is de demofase. De bewaartermijn van
// de gegevens in de app is besloten (#485): persistence/opschonen.py. De verwerkingsverantwoordelijke is besloten
// (#553): de deelnemende instelling.
//
// Taal (#1139): B1. Elk kopje begint met één korte zin (`privacy-kern`) die zegt wat er gebeurt; geen zin boven de 25
// woorden; vaktaal alleen met uitleg ernaast; elke datum als "19 oktober 2026". privacyPage.test.js meet het.

import { useTermijnen, getal } from '../termijnen'
import { useBronnenLijst, bronnamen } from '../bronnenLijst'

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
  // De termijnen die de backend toepast (#835), in de standaardinstelling 90 en 365 dagen, 8 en 24 uur.
  const { gesprekkenDagen, rapportenDagen, sessieUren, sessieMaxUren } = useTermijnen()
  const [gesprek, rapport, sessie, sessieMax] = [gesprekkenDagen, rapportenDagen, sessieUren, sessieMaxUren].map(getal)
  // De partijen waar een opvraag heen kan in deze omgeving (#1006); niet alle bronnen zijn open data.
  const bronnen = useBronnenLijst()
  const opvraagbaar = bronnamen(bronnen.filter(b => b.opvraag !== false))
  const noten = bronnen.map(b => b.privacynoot).filter(Boolean)
  return (
    <div className="privacy-text">
      <h1>Privacy-informatie</h1>
      <p className="privacy-page-lead">
        Zo gaat openEDUdata+ met je gegevens om. Dit is de demoversie. De officiële privacyverklaring volgt zodra de
        open punten onderaan zijn beantwoord.
      </p>

      <h2>{PRIVACY_KOPJES[0]}</h2>
      <p className="privacy-kern">Je vraag gaat naar een externe AI-dienst, die het antwoord schrijft.</p>
      <ul>
        <li>
          De AI-dienst krijgt je vraag, de eerdere berichten in het gesprek, de opgehaalde data en de instelling en
          functie uit je profiel. Koos je zelf geen instelling, dan gaat de instelling uit je SRAM-account mee (het
          inlogsysteem van SURF), als de app die kent. De kop toont welke dat is. Onder het invoerveld staat welke
          dienst en welk model je gebruikt. Op de omgevingen van SURF is dat Microsoft Azure AI Foundry met een
          Claude-model.
        </li>
        <li>
          De cijfers zelf komen van {opvraagbaar}. Naar die bronnen gaat alleen de opvraag (welke tabel, welke
          selectie), niets over jou. Dat geldt ook voor de sites waar een bron haar bestanden publiceert, zoals
          data.overheid.nl of DataverseNL. {noten.join(' ')}
        </li>
        <li>
          Voer geen persoonsgegevens in. De app herkent een BSN, een e-mailadres en een telefoonnummer en waarschuwt
          dan. Ze blokkeert niets en maskeert niets. Een naam herkent ze niet. Verstuur je de vraag toch, dan gaat de
          tekst met die gegevens naar de AI-dienst. De tekst blijft staan in het gesprek op de server en in de kopie in
          je browser, tot je het gesprek verwijdert. Ook een export van het gesprek bevat hem. Alleen de titel van het gesprek
          wordt gemaskeerd: de app maakt zulke gegevens daar onleesbaar.
        </li>
        <li>
          Kleine aantallen blijven onderdrukt. DUO en CBS publiceren een klein aantal niet, zodat niemand in een kleine
          groep herkenbaar is. De app rekent zo&apos;n cel niet terug als het totaal min de zichtbare delen.
        </li>
      </ul>

      <h2>{PRIVACY_KOPJES[1]}</h2>
      <p className="privacy-kern">Na {gesprek} dagen zonder gebruik verwijderen we een gesprek, na {rapport} dagen een rapport.</p>
      <ul>
        <li>
          <strong>Gesprekken</strong>: je vraag, het antwoord, de stappen die de app voor het antwoord zette en de
          titel. Ze staan onder je account, tot {gesprek} dagen na je laatste bericht in het gesprek. Verwijder je een
          gesprek eerder, dan gaat het eerder weg.
        </li>
        <li>
          <strong>Rapporten en dashboards</strong>: blijven bewaard als je het gesprek verwijdert. De
          verwijderdialoog zegt dat ook. Verwijder ze apart onder Rapporten. Een rapport of dashboard dat je {rapport} dagen
          niet hebt geopend of gewijzigd, wordt verwijderd.
        </li>
        <li>
          <strong>Feedback</strong>: je antwoorden op de vragen bij een rapport of dashboard. We bewaren ze met de
          titel van het rapport en de instelling die je in de app koos (als je er een koos). De vragen over je
          instelling krijg je alleen na een eigen keuze (Help ons verder). De vragen over het rapport kun je zonder
          die vragen versturen. Wat je via de link Feedback stuurt, bewaren we met je accountnaam, de soort die je
          koos en de pagina waar je was. Feedback wordt {gesprek} dagen nadat je hem gaf verwijderd, of eerder als je
          al je gegevens verwijdert. Een oordeel op een antwoord (👍/👎) bewaren we sinds 9 november 2026 niet meer.
          Wat er stond, is verwijderd.
        </li>
        <li>
          <strong>Hoe een tabel is opgehaald</strong>: de dataset en de selectie. Zo werkt een export na een herstart
          van de app nog. Dit gaat weg met het gesprek, of na {gesprek} dagen als het gesprek er niet meer is.
          Verwijder je al je gegevens, dan gaat het ook weg.
        </li>
        <li>
          <strong>Bewijs per antwoord</strong>: bij elk antwoord op data bewaart de server drie dingen. Dat zijn waar de
          data vandaan kwam (bron en selectie), de uitkomsten van berekeningen en de stappen achter de figuren. Dit staat onder een
          controlecode van de antwoordtekst: een code waar de tekst zelf niet uit terug te halen is. Zo geeft een
          rapport bij een heropend gesprek hetzelfde resultaat als in het gesprek zelf. Je vraag en het antwoord staan
          er niet in. Het bewijs gaat weg met het gesprek, of na{' '}
          {gesprek} dagen als het gesprek er niet meer is. Verwijder je al je gegevens, dan gaat het ook weg.
        </li>
        <li>
          <strong>Inloggen</strong>: met een gebruikersnaam en wachtwoord bewaart de server alleen je gebruikersnaam
          bij je gegevens. Met SURF SRAM is je e-mailadres je accountnaam, ook als auteur van een rapport. Je naam,
          organisatie en instelling uit SRAM staan in de database van de server, ten hoogste {sessieMax} uur. Ze gaan
          eerder weg als je uitlogt of al je gegevens verwijdert. Een ingetrokken sessie (bijvoorbeeld na uitloggen)
          bewaart de server als controlecode, tot ze verloopt.
        </li>
        <li>
          <strong>Tellers</strong>: de server telt twee dingen. Het eerste is wat een account het model kostte, als
          één getal per dag, 62 dagen lang. Het tweede is hoe vaak een account of IP-adres in korte tijd iets doet. Het
          gaat om inloggen, een bericht of feedback sturen, een Word-document maken en de koppeling voor andere
          AI-apps gebruiken. Dat is één rij per poging, hoogstens tien minuten lang. Bij het inloggen staat daar ook
          je IP-adres bij. Alles staat onder een pseudoniem (een code waar je accountnaam of adres niet uit terug te
          halen is). De server maakt dat pseudoniem met een eigen geheim. Het getal per dag hoort toch bij je account:
          het zit in de export, en gaat weg als je al je gegevens verwijdert.
        </li>
        <li>
          <strong>Bewaartermijn</strong>: elke nacht verwijdert de server wat over zijn termijn is. Je gesprekken
          verdwijnen {gesprek} dagen na je laatste bericht erin. Je feedback verdwijnt {gesprek} dagen nadat je hem
          gaf. Rapporten en dashboards verdwijnen {rapport} dagen nadat je ze voor het laatst opende of wijzigde.
          Eerder verwijderen kan altijd zelf, één voor één of alles tegelijk.
        </li>
      </ul>

      <h2>{PRIVACY_KOPJES[2]}</h2>
      <p className="privacy-kern">Je browser bewaart een kopie van je werk en je instellingen.</p>
      <ul>
        <li>
          In je browser staan een kopie van je gesprekken en rapporten, het gesprek waar je mee bezig bent, je
          profiel en je sessie. Je profiel is je instelling, functie en weergave. Uitloggen wist dit allemaal uit deze
          browser, en al je gegevens verwijderen ook.
        </li>
        <li>
          Ook onthoudt je browser welke gesprekken en rapporten je het laatst opende en welke rapporten je als
          favoriet markeerde. Dat zijn alleen nummers, zonder titel of inhoud. Ze blijven na uitloggen staan, zodat je
          ze een volgende keer terugvindt. Ze verschijnen alleen bij een gesprek of rapport van het account waarmee je
          inlogt. Anderen met hetzelfde account zien ze niet. Verwijder je al je gegevens, dan gaan ook deze nummers
          weg.
        </li>
        <li>
          Een sessie duurt {sessie} uur en wordt bij gebruik verlengd tot ten hoogste {sessieMax} uur na het inloggen.
          Tijdens het inloggen met SRAM staan er kort drie cookies in je browser. Ze horen bij die ene login en blijven
          hoogstens 10 minuten staan. Daarna worden ze verwijderd, ook als het inloggen misgaat. Verder gebruikt de
          app geen cookies en geen meetsoftware die bijhoudt wat je doet.
        </li>
      </ul>

      <h2>{PRIVACY_KOPJES[3]}</h2>
      <p className="privacy-kern">In het logboek van de server staat geen tekst van je gesprekken.</p>
      <ul>
        <li>
          Van een vraag, een antwoord en wat de app aan een stap meegeeft, staat alleen de lengte en een controlecode
          in het logboek. Uit die code is de tekst niet terug te halen. Daarnaast staan er tijdstippen, de namen van
          de gebruikte stappen en het model in.
        </li>
        <li>Alleen in de foutzoekstand (debug) staat er wel tekst in het logboek. Die staat niet standaard aan.</li>
        <li>De app schrijft geen toegangslog: je IP-adres en de adressen die je opent staan er niet in.</li>
      </ul>

      <h2>{PRIVACY_KOPJES[4]}</h2>
      <p className="privacy-kern">Je kunt je gegevens zelf downloaden en verwijderen.</p>
      <ul>
        <li>Een gesprek verwijderen in de gesprekslijst. Een rapport of dashboard verwijderen onder Rapporten.</li>
        <li>Een gesprek exporteren als Markdown en de tabel achter een antwoord downloaden als CSV.</li>
        <li>
          Het bewijs van een antwoord downloaden met &ldquo;Bewijs (JSON)&rdquo;. Je browser maakt dat bestand uit het
          antwoord op je scherm; er gaat niets naar de server. Erin staan het antwoord, de bronnen, de herkomst en per
          stap wat de app opvroeg, met de code. Dat kan tekst uit je vraag zijn, soms de hele vraag als zoekterm. Je
          accountnaam en de ruwe data van de bron staan er niet in.
        </li>
        <li>
          Een rapport downloaden als HTML, Markdown of Word, of opslaan als PDF. Het Word-document bevat niets meer
          dan het rapport. Je browser stuurt alleen de grafieken als afbeelding mee, en de server bewaart ze niet.
        </li>
        <li>
          Al je gegevens in één keer exporteren: in de instellingen met &ldquo;Exporteer al mijn gegevens&rdquo;
          (<code>/api/mijn-gegevens/export</code>). Je krijgt één JSON-bestand met je gesprekken, rapporten en
          dashboards, feedback, de gegevens over hoe tabellen zijn opgehaald en het bewijs per antwoord.
          Ook je tokengebruik zit erin: wat je vragen het model kostten, als één getal per dag. Log je in met SRAM, dan
          zitten ook je naam, organisatie en instelling uit SRAM erin. Niet erin: wat alleen in je browser
          staat. Zonder eigen login kan het niet.
        </li>
        <li>
          Al je gegevens in één keer verwijderen: in de instellingen met &ldquo;Verwijder al mijn gegevens&rdquo;.
          Typ daarna het woord &ldquo;verwijder&rdquo;. Dat kan niet ongedaan worden gemaakt, dus exporteer eerst.
          Dan verdwijnt alles wat de server onder je account bewaart. Dat zijn je gesprekken, rapporten en
          dashboards, al je feedback, de gegevens over hoe tabellen zijn opgehaald, het bewijs per antwoord en je
          tokengebruik. Ook je naam, organisatie en instelling uit SRAM gaan weg. Ook de kopie in deze browser gaat
          weg. Je wordt uitgelogd, ook op een ander apparaat. De tellers van het inloggen en de limieten gaan niet
          direct weg. Ze staan onder een pseudoniem en verdwijnen na
          hoogstens tien minuten. Wat blijft verder: de serverlogs (zonder gesprekstekst) en de back-ups van de
          beheerder. Ook blijft een controlecode van je accountnaam staan, tot je laatste sessie verlopen is. Een
          controlecode van een sessie waarmee je uitlogde blijft staan tot zij verloopt. De kopie in de browser van een
          ander apparaat blijft staan tot je daar uitlogt.
        </li>
        <li>Gebruik je een gedeeld account, dan verdwijnt ook het werk van de anderen. Zonder eigen login kan het niet.</li>
      </ul>

      <h2>{PRIVACY_KOPJES[5]}</h2>
      <p className="privacy-kern">De deelnemende instelling is verantwoordelijk voor je gegevens.</p>
      <p>
        openEDUdata+ is een project van CEDA (Npuls). De verwerkingsverantwoordelijke (wie bepaalt wat er met je
        gegevens gebeurt) is de deelnemende instelling. Met een privacyvraag kun je terecht bij die instelling: bij
        de privacycontactpersoon of de functionaris gegevensbescherming (FG) van de instelling. Het projectteam van
        CEDA is er alleen voor vragen over de demo zelf.
      </p>

      <h2>{PRIVACY_KOPJES[6]}</h2>
      <p className="privacy-kern">Dit moeten we nog beantwoorden voordat de tekst definitief is.</p>
      <p>Over de verwerkingsverantwoordelijke is besloten op 19 oktober 2026 (zie hierboven). Dit blijft open:</p>
      <ul>
        <li>
          Verwerkersovereenkomst met de AI-aanbieder: de afspraken over wat die met de gegevens doet. Ook open: in
          welke regio de dienst draait, en de afspraak dat de aanbieder je invoer niet bewaart of gebruikt om te
          trainen.
        </li>
        <li>De bewaartermijn van het serverlog en van de back-ups van de beheerder.</li>
        <li>Of er een DPIA nodig is: een onderzoek naar de privacyrisico&rsquo;s.</li>
      </ul>
    </div>
  )
}
