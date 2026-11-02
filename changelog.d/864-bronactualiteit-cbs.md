### Een opgehaalde CBS-tabel geldt na 24 uur niet meer als actueel (#864)
- Een tabel in de datastore die langer dan 24 uur geleden bij de bron is opgehaald, gaat eruit; een gesprek dat hem
  nog gebruikt, haalt hem uit zijn recept opnieuw op, met wat de bron dan zegt. Ook de CBS-metadata (kolomdefinities,
  dimensies met hun periodestatus, tabelbeschrijving) komt na 24 uur opnieuw van CBS. Tot nu toe bleef een revisie of
  een nieuwe periode onzichtbaar tot de server herstartte.
- `laatste_update` in een CBS-antwoord is de dag waarop CBS de tabel volgens CBS zelf het laatst bijwerkte, niet meer
  de datum uit de catalogus van de package; antwoordt CBS niet, dan blijft het de catalogusdatum. Het antwoord noemt
  ook de dag van ophalen.
- De bronregel van een CBS-tabel onder een antwoord eindigt met "bijgewerkt door CBS op …, opgehaald op …".
