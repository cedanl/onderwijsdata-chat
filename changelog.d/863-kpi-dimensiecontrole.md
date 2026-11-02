### Een dashboard-KPI telt geen totaalrij meer op bij de delen (#863)
- `compute_kpi` rekende over elke data_key, ook over een CBS-selectie waarin een dimensie open stond: een som of
  gemiddelde telde dan "Totaal mannen en vrouwen" of "Nederland" mee met de delen, en het dashboard toonde dat getal.
  Nu doet de KPI dezelfde dimensiecontrole als `query_data`, met dezelfde foutmelding, zodat het model eerst filtert
  of groepeert. Een reeks met meer dan één rij per periode (bijvoorbeeld per instelling) krijgt geen eerste, laatste
  of verandering meer; een som of maximum over die rijen kan nog wel.
