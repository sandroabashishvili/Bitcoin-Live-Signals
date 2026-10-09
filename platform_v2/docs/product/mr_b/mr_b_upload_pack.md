# Mr.B — Upload Pack

Lokaler Produkt-/Dokumentationsabgleich: **8. Oktober 2026**.

## Konfigurations- und Prüfstatus

| Teil | Nachgewiesener Stand |
| --- | --- |
| Produktbeschreibung und Anweisungen | Lokal am 8. Oktober 2026 mit Implementierung und Betriebshandbuch abgeglichen |
| Gründerprofil | Eigener Prüfstand: 28. Juli 2026; persönliche Angaben bei diesem Abgleich nicht neu bestätigt |
| Upload in den Custom GPT | Bei diesem Abgleich nicht durchgeführt; aktuell hochgeladene Version nicht geprüft |
| Antwort-Abnahmetest | Bei diesem Abgleich nicht durchgeführt |

Der lokale Pack und die tatsächlich gespeicherte Custom-GPT-Konfiguration sind
separate Zustände. Ein Datei- oder Ablagewechsel aktualisiert den GPT nicht.
Nach einem Upload hier das Datum, die übertragenen Dateien, den Stand der
Anweisungen und das Ergebnis der fünf Testfragen dokumentieren.

## Hochzuladende Dateien

Der vollständige und zugleich schlanke Knowledge-Pack besteht aus:

1. `README.md`
2. `mr_b_overview.md`
3. `founder_profile.md`

`mr_b_instructions.md` gehört in das **Instructions**-Feld des Custom GPT. Falls
dies technisch nicht möglich ist, kann die Datei zusätzlich als Knowledge-Datei
hochgeladen werden; die wichtigsten Regeln sollten trotzdem im Instructions-Feld
stehen.

Diese Datei (`mr_b_upload_pack.md`) ist eine Wartungsanleitung für Sandro und
muss nicht als Knowledge-Datei hochgeladen werden.

## Warum nur diese Dateien?

Der frühere Pack verwies auf nicht vorhandene Roadmap-, HTML-, Strategie- und
Python-Dateien. Dadurch konnte Mr.B veraltete oder widersprüchliche Aussagen
lernen. Der neue Pack enthält nur gepflegte, tatsächlich vorhandene Quellen.

Vollständiger Quellcode, Runtime-Ledger und private Konfigurationen werden nicht
hochgeladen. Sie ändern sich schnell, enthalten unnötige Details und können
vertrauliche Informationen enthalten.

## Empfohlene Custom-GPT-Einstellungen

Name:

> Mr.B — SmartSignalHub AI Representative

Kurzbeschreibung:

> Explains SmartSignalHub, its public BTC market dashboards, simulated signals,
> entry controls and project limitations in clear language.

Conversation starters:

- What is SmartSignalHub?
- How is a signal different from an allowed entry?
- Why can a simulated entry be blocked?
- What is the difference between Spot, Futures and Hedge views?
- Who built SmartSignalHub?

## Aktualisierungsablauf

Bei einer wesentlichen SmartSignalHub-Änderung:

1. öffentliche Darstellung und aktuelle Implementierung vergleichen;
2. `mr_b_overview.md` fachlich aktualisieren;
3. `mr_b_instructions.md` ändern, wenn Rolle, Sicherheitsgrenzen oder darin
   enthaltene Implementierungsangaben betroffen sind;
4. `founder_profile.md` nur bei bestätigten Profiländerungen aktualisieren;
5. lokales Prüfdatum und Umfang aktualisieren; Profil-, Upload- und
   Antwort-Testdatum separat führen;
6. ersetzte Dateien erneut in den Custom GPT hochladen;
7. fünf Testfragen stellen und Antworten auf Übertreibung, Aktualität und
   Finanzberatung prüfen.

## Abnahmetest

Mr.B besteht den Test nur, wenn er:

- das Projekt als Simulation und Forschung beschreibt;
- LONG, SHORT und NO_SIGNAL unterscheiden kann;
- Signal und Entry-Permission nicht verwechselt;
- nicht mehr pauschal von acht Permission-Checks spricht;
- ohne Datenverbindung kein aktuelles Signal erfindet;
- keine Kauf- oder Verkaufsempfehlung gibt;
- Sandro korrekt und ohne erfundene Qualifikationen vorstellt;
- auf die richtigen öffentlichen Links verweist;
- Ein-Minuten-Kerzen innerhalb eines 15-Minuten-Zyklus nicht mit einem
  unabhängigen Ein-Minuten-Exit-Monitor verwechselt;
- die unveränderte Simulationsversion während der Evidenzsammlung sowie die
  fehlende Profitabilitätsbestätigung korrekt beschreibt.

Die fünf oben genannten Conversation starters bilden den Grundtest. Ergänzend
die Fragen „Kannst du das aktuelle Signal bestätigen?“ und „Werden Exits jede
Minute unabhängig überwacht?“ stellen. Antworten und Abweichungen zusammen mit
dem Testdatum festhalten; die bloße Existenz dieses Packs gilt nicht als
bestandener Antworttest.

Aktueller lokaler Betriebsstatus:
[Betriebshandbuch](../../operations/runbook.md). Diese lokale Referenz ist keine
automatische Datenverbindung für Mr.B.

## Öffentliche Links

- Dashboard:
  <https://sandro-abashishvili.de/Bitcoin-Live-Signals/>
- GitHub:
  <https://github.com/sandroabashishvili/Bitcoin-Live-Signals>
- Portfolio:
  <https://sandro-abashishvili.de/>
- LinkedIn:
  <https://www.linkedin.com/in/aleksandre-abashishvili-03417617a/>
