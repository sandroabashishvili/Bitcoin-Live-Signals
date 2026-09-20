# SmartSignalHub – Bitcoin Live Signals

![SmartSignalHub – Bitcoin Live Signals](platform_v2/public_site/assets/site-social-og.png)

SmartSignalHub ist ein langfristiges Entwicklungsprojekt für nachvollziehbare
Bitcoin-Signale, Marktkontext und simulierte Strategieauswertung. Die Plattform
trennt Spot-, Futures- und Hedge-Simulationen und macht Signale, blockierte
Einstiege, TP-/SL-Strukturen, Positionen und Ergebnisse sichtbar.

**Live:** [sandro-abashishvili.de/Bitcoin-Live-Signals](https://sandro-abashishvili.de/Bitcoin-Live-Signals/)

## Projekt und Veröffentlichung

Der Entwicklungsordner ist das private Quellcode-Repository `SmartSignalHub`.
Es enthält Python-Code, Generatoren, Tests, Dokumentation und statische Ressourcen.
`publish/Bitcoin-Live-Signals` bleibt ein separates öffentliches Git-Repository
für die erzeugte Website auf `main`. Änderungen am Quellcode veröffentlichen
nicht automatisch die Website.

`.env`, Zugangsdaten, virtuelle Umgebungen, SQLite-Datenbanken, Logs, Caches
und erzeugte Laufzeitdateien werden nicht versioniert. Git ersetzt keine
Datenbank-Backups. Details: [Repository und Einrichtung](platform_v2/docs/operations/source_repository.md).

## Funktionsbereiche

- getrennte Spot-, Futures- und Hedge-Simulationen
- Markt-, Multi-Timeframe-, Momentum-, Trend- und Orderbuchkontext
- sichtbare Einstiegsentscheidungen und blockierte Einträge
- simulierte Positionen mit TP, SL und Ergebnisprotokoll
- Portfolio-, Strategie- und Trade-Auswertungen
- statisch erzeugte responsive Dashboards
- tägliche Bitcoin-Nachrichten und Ressourcen
- Diagnostics-, Backup-, Sitemap- und GitHub-Publish-Werkzeuge

## Technischer Ansatz

Python verarbeitet Markt- und Systemdaten, verwaltet die Simulationszustände
und erzeugt die öffentlichen Ansichten. HTML, CSS und JavaScript bilden die
statische Benutzeroberfläche. Die internen Module sind nach Spot, Futures,
Hedge, gemeinsam genutzter Infrastruktur und Werkzeugen getrennt.

Wichtige Einstiegspunkte:

- [`platform_v2/spot/spot_system.md`](platform_v2/spot/spot_system.md)
- [`platform_v2/futures/futures_system.md`](platform_v2/futures/futures_system.md)
- [`platform_v2/futures_hedge/futures_hedge_system.md`](platform_v2/futures_hedge/futures_hedge_system.md)
- [`platform_v2/shared/shared_system.md`](platform_v2/shared/shared_system.md)
- [`platform_v2/tools/tools_system.md`](platform_v2/tools/tools_system.md)
- [`platform_v2/docs/operations/runbook.md`](platform_v2/docs/operations/runbook.md)

## Status und Grenzen

SmartSignalHub befindet sich in aktiver Entwicklung. Alle sichtbaren
Handelsergebnisse stammen aus Simulationen und dienen der technischen
Demonstration und Strategieanalyse.

- kein Trading-Bot für fremde Konten
- keine Anlage- oder Finanzberatung
- kein Gewinnversprechen
- keine Behauptung eines bereits bewiesenen profitablen Systems

## Autor

Sandro Abashishvili

[Portfolio](https://sandroabashishvili.github.io/) ·
[GitHub](https://github.com/sandroabashishvili) ·
[LinkedIn](https://www.linkedin.com/in/aleksandre-abashishvili-03417617a/)
