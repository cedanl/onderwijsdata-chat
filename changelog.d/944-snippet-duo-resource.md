### Opgelost

- De Python-snippet onder een DUO-antwoord laadt weer hetzelfde bestand als de app. Gaf het model de resource als tekst-getal (`"4"`), dan schreef de snippet `duo.load("p04hogdipl", "4")`, en `riodata` zocht dan een bestandsnaam met "4" erin (`ResourceNietGevonden`, of stil een ander bestand). De snippet zet nu `duo.load("p04hogdipl", 4)`, met dezelfde omzetting als de app (#944).
