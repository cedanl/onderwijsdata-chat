### Arbeidsmarkt: de vacatures komen van CBS 83599NED, per kwartaal en per bedrijfstak (#1228, #1223, #1224, #1225)
- De dashboards Arbeidsmarkt en Mijn instelling nemen hun vacatures uit CBS-tabel 83599NED "Openstaande vacatures; SBI
  2008, regio" (open data, licentie CC BY 4.0) in plaats van de UWV-momentopname van mei 2023 (besluit #1221). Het
  vacatureaanbod in de provincie toont per bedrijfstak het laatste kwartaal, met de periode en "voorlopig" waar CBS dat
  zegt; een bedrijfstak zonder cijfer staat eronder, niet als 0.
- De aansluiting per sector rekent met het gemiddelde van de laatste vier kwartalen en een koppeltabel van
  bedrijfstakken aan onderwijssectoren (`data/sbi_onderwijssector.csv`, met de hand opgesteld). De uitleg zegt dat een
  vacature bij de bedrijfstak van de werkgever telt, niet bij het beroep, en dat het label daarom indicatief is. Een
  sector zonder koppeling (Entree, sectoroverstijgend) krijgt geen label maar "geen vacaturegegevens per bedrijfstak
  voor deze sector".
- Het bronblok noemt CBS 83599NED met link, licentie, kwartalen en de voorlopige kwartalen. UWV Open Match staat niet
  meer op de dashboards; de chattool `get_uwv_vacatures` blijft.
- 83599NED staat in de CBS-catalogus met titel, licentie, frequentie en laatste periode.
