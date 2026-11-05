### De chat vraagt weer terug als een vraag niet helemaal duidelijk is (#932)
- Een telling zonder afbakening ("Hoeveel studenten?") krijgt nu eerst een kaart uit code: landelijk (mbo, hbo en wo
  samen) of per sector. Een instelling of regio noem je via "Anders formuleren". Een vraag met een instelling, sector,
  gebied of eigennaam, of een profiel dat de instelling of sector al bepaalt, krijgt geen kaart.
- Een vraag kan tot drie kaarten achter elkaar krijgen (was één): code leest de vraag samen met de gekozen opties, vraagt
  een slot nooit twee keer, en het model mag er zelf nog een stellen als er een dimensie openstaat waar het antwoord
  van afhangt. Daarna gaat het door met aannames die het noemt.
