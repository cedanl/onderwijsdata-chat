"""Na een vaste melding "niet in deze bron": een andere maat aanbieden, niet ongevraagd ophalen (#975).

Review 08-B7: "Hoe tevreden zijn studenten van ROC van Amsterdam over hun opleiding?" De Studiekeuzedatabase meldde
terecht dat ze alleen hbo en wo heeft. Daarna haalde het model ongevraagd DUO-indicatoren en aantallen op en zette die
in een grote tabel, waar de vraag om een tevredenheidsoordeel ging. De melding zelf zegt nu wat het model wel doet:
de beperking noemen en een andere maat als vraag aanbieden; ophalen pas als de gebruiker daarop ingaat.
"""

ALLEEN_AANBIEDEN = (
    "Haal in deze beurt geen vervangende cijfers op waar de gebruiker niet om vroeg (andere indicatoren, aantallen uit "
    "een andere bron): noem deze beperking en bied zo'n andere maat hooguit in één zin aan als vraag. Pas als de "
    "gebruiker daarop ingaat, haal je die cijfers op."
)
