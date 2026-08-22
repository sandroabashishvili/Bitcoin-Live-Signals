# SmartSignalHub – Bitcoin Live Signals

![SmartSignalHub – Bitcoin Live Signals](assets/site-social-og.png)

SmartSignalHub ist ein langfristiges Software- und Datenprojekt rund um Bitcoin-Marktdaten und regelbasierte Handelsentscheidungen.

Die öffentliche Plattform verfolgt dabei drei einfache Ziele:

1. **Entscheidungen verständlicher machen** – Signale und Marktbedingungen werden nicht nur angezeigt, sondern mit ihrem Kontext nachvollziehbar dargestellt.
2. **Positionsmanagement sichtbar machen** – Entry, Stop-Loss, Take-Profit und der weitere Verlauf einer simulierten Position werden gemeinsam betrachtet.
3. **Strategielogik beobachtbar machen** – Nutzer können sehen, wann ein Einstieg erlaubt, blockiert oder verworfen wird und wie sich die zugrunde liegenden Regeln im Zeitverlauf verhalten.

SmartSignalHub ist damit weder ein Versprechen auf profitable Trades noch ein fertiger Trading-Bot, sondern eine transparente technische Plattform zum Beobachten, Testen und Weiterentwickeln von Handelslogik.

**Live:** [sandro-abashishvili.de/Bitcoin-Live-Signals](https://sandro-abashishvili.de/Bitcoin-Live-Signals/)

## Was die Plattform zeigt

- getrennte Ansichten für Spot, Futures und Hedge
- aktuelle Signale und Einstiegsbedingungen
- blockierte oder verworfene Einstiege mit sichtbarem Kontext
- simulierte Positionen mit Entry, TP und SL
- abgeschlossene Trades und Strategieauswertungen
- Portfolio-, Markt- und Orderbuchkontext
- verständliche Erklärungen zu sichtbaren Entscheidungen
- responsive öffentliche Dashboards

## Wie das System arbeitet

Markt- und Systemdaten werden durch Python-Services verarbeitet. Regelbasierte Komponenten bewerten Bedingungen, erzeugen Zustände und simulieren Positionsverläufe. Die Ergebnisse werden anschließend in statische Web-Dashboards überführt.

Das Gesamtsystem verbindet damit:

- Datenverarbeitung
- regelbasierte Entscheidungslogik
- Spot-, Futures- und Hedge-Simulation
- Positions- und Risikologik
- Diagnosen und Tests
- automatisch erzeugte Webansichten

Dieses Repository enthält die für GitHub Pages veröffentlichte statische Version. Teile der sichtbaren HTML-Dateien werden aus der lokalen Entwicklungsumgebung generiert und sind deshalb nicht die vollständige Quellstruktur des Gesamtsystems.

## Technischer Stack

- Python
- HTML
- CSS
- JavaScript
- externe Markt- und Nachrichtendaten
- statische Veröffentlichung über GitHub Pages

## Status und Grenzen

SmartSignalHub befindet sich in aktiver Entwicklung. Die öffentlich sichtbaren Bereiche dienen der technischen Demonstration, Beobachtung und Auswertung simulierter Strategielogik.

- kein Trading-Bot für fremde Konten
- keine Anlage- oder Finanzberatung
- kein Gewinnversprechen
- keine öffentlich behauptete Live-Geld-Ausführung
- Simulationen und Entwicklungsbereiche werden als solche gekennzeichnet

## Nächste Entwicklungsstufen

Geplante Erweiterungen umfassen unter anderem:

- historische Tests und vergleichbare Auswertungen
- weitere handelbare Assets neben Bitcoin
- Weiterentwicklung der Strategie-, TP-/SL- und Positionslogik
- zusätzliche Daten- und Diagnoseebenen
- spätere Exchange-Integration nach technischer und sicherheitsbezogener Vorbereitung

## Autor

Sandro Abashishvili

[Portfolio](https://sandro-abashishvili.de/) ·
[GitHub](https://github.com/sandroabashishvili) ·
[LinkedIn](https://www.linkedin.com/in/aleksandre-abashishvili-03417617a/)
