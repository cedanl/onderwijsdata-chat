// De tekst van de homepage per doelgroep (#103): IR-specialisten krijgen de data-kant (koppelen, reproduceren, zelf
// analyseren), bestuurders en directeuren de besluit-kant (snel, onderbouwd, één versie). De doelgroep volgt uit de
// functie in de instellingen; wie geen functie koos, ziet de IR-tekst (de doelgroep van de eerste demo's). De intro
// noemt de bronnen van deze omgeving (bronnenLijst.js, #1006): `intro(bronnen)`. Kop, voordelen en cta zeggen alleen
// "open" zolang er geen gelicentieerde bron in die lijst staat (#1010), dus ook die zijn functies van de lijst.
import { bronnamen, heeftGelicentieerd, onderwijsdata } from './bronnenLijst'

const BESTUUR = new Set(['Bestuurder', 'Directeur'])

export const doelgroepVan = functie => (BESTUUR.has(functie) ? 'bestuur' : 'ir')

export const HOME_TEKST = {
  ir: {
    kop: bronnen => [`Van ${onderwijsdata(bronnen)} naar `, 'reproduceerbare inzichten'],
    intro: bronnen => `openEDUdata+ koppelt en harmoniseert onderwijsdata van ${bronnamen(bronnen)} alvast voor je. Stel een ad-hoc vraag over instroom, voortgang, arbeidsmarkt of diplomering en krijg een onderbouwd, herleidbaar antwoord.`,
    voordelenTitel: 'Waarom IR-dataprofessionals openEDUdata+ gebruiken',
    voordelen: () => [
      { icon: 'tijd', title: 'Tijd terug', desc: 'Geen weken kwijt aan koppelen en opschonen. De cijfers staan klaar, direct inzetbaar voor jouw analyse.' },
      { icon: 'schild', title: 'Verdedigbare cijfers', desc: 'Reproduceerbare methodiek met volledige bronvermelding. Bestand tegen vragen van auditors, accountants en bestuur.' },
      { icon: 'tabel', title: 'Eén brontabel voor iedereen', desc: "Instelling, management en collega-IR'ers werken met exact dezelfde geharmoniseerde cijfers. Geen discussie over wiens versie klopt." },
      { icon: 'regelaar', title: 'Zelf aan het stuur', desc: 'Ruwe, gekoppelde data beschikbaar voor eigen modellen en analyses. Geen afhankelijkheid van een vaste rapportagevorm.' },
    ],
    cta: bronnen => `Stel je eerste vraag aan openEDUdata+ en ontdek wat gekoppelde ${onderwijsdata(bronnen)} voor jouw analyses betekent.`,
  },
  bestuur: {
    kop: bronnen => [`Van ${onderwijsdata(bronnen)} naar `, 'onderbouwde besluiten'],
    intro: bronnen => `openEDUdata+ beantwoordt je vragen over instroom, voortgang, arbeidsmarkt en diplomering met data van ${bronnamen(bronnen)}. Je wacht niet op een rapportage en je ziet bij elk antwoord waar het vandaan komt.`,
    voordelenTitel: 'Waarom bestuurders en directeuren openEDUdata+ gebruiken',
    voordelen: bronnen => [
      { icon: 'tijd', title: 'Direct antwoord', desc: 'Stel je vraag in gewone taal, ook als het dashboard er nog niet is. Geen wachtrij bij de afdeling informatievoorziening.' },
      { icon: 'schild', title: 'Cijfers die je kunt verdedigen', desc: 'Elk antwoord noemt de bron en de definitie. In het overleg laat je zien waar een cijfer vandaan komt.' },
      { icon: 'tabel', title: 'Eén versie van de cijfers', desc: 'Bestuur, IR en opleidingen werken met dezelfde cijfers. Geen discussie over wiens versie klopt.' },
      { icon: 'regelaar', title: 'Je instelling naast de sector', desc: `Zet je eigen instroom, uitval en diplomering naast landelijke ${heeftGelicentieerd(bronnen) ? '' : 'open '}data, als houvast voor je keuzes.` },
    ],
    cta: bronnen => `Stel je eerste vraag aan openEDUdata+ en zie wat ${onderwijsdata(bronnen)} voor jouw besluiten betekent.`,
  },
}
