### De chat verbindt vanzelf weer na een crash van de server (#1169)
- Viel de server weg zonder netjes af te sluiten (een crash, een node die verdween, een time-out van de ingress), dan gaf
  de chat na een halve minuut op met "Geen verbinding.", ook als de server kort daarna terug was. Nu blijft de app
  daarna elke 30 seconden controleren of de server terug is en verbindt hij zelf, zonder klik. De knop "Opnieuw
  verbinden" blijft voor wie niet wil wachten. Bij te veel open vensters of een geweigerd adres wacht hij nog steeds op jou.
