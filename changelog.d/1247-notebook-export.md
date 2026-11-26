### Gesprek exporteren als Jupyter-notebook (#1247)
- "Exporteer gesprek" vraagt nu het formaat: Markdown (zoals voorheen, de standaard) of Jupyter-notebook (`.ipynb`).
  Het notebook opent in Jupyter, VS Code, Hex of Deepnote: bovenaan één cel met de versiekop en de `%pip install` die
  de pakketten van de snippets ophaalt, dan per vraag een markdowncel met het antwoord, de bronnen, de meldingen en de
  herkomst zoals in de Markdown-export, en per stap zijn code als cel. Een stap zonder code krijgt de vaste zin dat de
  app voor die stap geen code maakt.
- Mislukte stappen en foutmeldingen gaan alleen mee met de bestaande keuze; een ingetrokken antwoord staat er alleen
  als citaat. De bestandsnaam volgt dezelfde regel als bij Markdown. Draaien kan een ander getal geven als de bron
  sinds de export is bijgewerkt: de dataversie onder Herkomst zegt waarmee de app rekende.
