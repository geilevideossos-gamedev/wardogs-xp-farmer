# heli-xp-farmer – Projektbeschreibung

## Ziel

Ein Windows-Programm, das in **WARDOGS** (Steam) automatisch Pilot-XP farmt: Es fliegt mit dem Helikopter **Z20 Lakota** in einer Endlosschleife Ammo-Crates von der blauen Base in die Zone, wirft sie ab und fliegt zurück.
Es soll **autonom über Nacht** laufen, bis der Hotkey **F2** gedrückt wird.

## Ablauf (Soll-Verhalten)

1. Spiel ist offen → Serverliste → offizieller Server **EU Central** mit mehr als 20 und weniger als 80 Spielern → **Join Match**
2. Team **Blau** wählen
3. Zum Fahrzeughändler gehen → Tab **Air** → **Z20 Lakota** kaufen
4. Als **Pilot** einsteigen
5. **B** drücken → **Ammo Crate** kaufen
6. Abheben und **ohne Crash** in die Zone fliegen
7. Crate mit **G** abwerfen
8. Zurück zur **blauen Base** fliegen und auf dem **grünen quadratischen Landeplatz** landen
9. Weiter bei Schritt 5
10. **F2** stoppt das Programm jederzeit sofort, alle gedrückten Tasten werden losgelassen

Technisch ist das eine hierarchische State Machine mit Layern (Server → Team → Fahrzeug → Crate-Loop), Details in `AGENTS.md`.

Fehlerfälle, die das Programm abfangen soll:

- Heli zerstört / Spieler tot → Respawn, weiter bei Schritt 3
- Aus dem Match geflogen / Match vorbei → weiter bei Schritt 1
- Zu wenig Geld oder unbekannter Bildschirmzustand → sauber stoppen, Screenshot + Log speichern

## Nachtbetrieb

- Läuft ohne Aufsicht: Watchdog, automatischer Rejoin, sicherer Stopp bei Unklarheit
- Am Morgen: Log mit Zusammenfassung (Runden, abgeworfene Crates, Crashes, Fehler mit Screenshot)
- Windows-Energiesparen/Bildschirmsperre muss während des Laufs aus sein

## Spiel-Setup

| Punkt | Wert |
|---|---|
| Plattform | WARDOGS auf Steam |
| Auflösung | 1920 × 1080, Fenster-Vollbild (borderless) |
| Maps | 3 Maps, rotieren |
| Landeplatz Base | immer ein grüner quadratischer Platz |
| Match joinen | Serverliste → Server wählen → „Join Match“ |
| Crate abwerfen | Taste **G** |

Voraussetzungen im Spiel: Pilot-Level 10 und Z20 Lakota freigeschaltet (einmalig $35.000, danach ca. $7.400 pro Kauf), genug Geld für Heli + Crates.

## Technischer Ansatz

- **Python**, reines externes Input-Programm: liest den Bildschirm live (Screenshots, Bilderkennung mit OpenCV) und simuliert Tastatur/Maus
- **Keine KI zur Laufzeit:** Ein Vision-Modell braucht Sekunden pro Entscheidung, der Heli braucht viele Korrekturen pro Sekunde. Außerdem wären die Kosten über eine ganze Nacht zu hoch. KI wird nur beim Entwickeln genutzt
- **Aufnahmen als Testdaten:** Daniel nimmt Abläufe pro Map als Video + Input-Log auf. Claude Code baut daraus Templates und testet die Bilderkennung offline gegen die Videos, bevor im Spiel getestet wird
- **Kein** Lesen oder Schreiben von Spielspeicher, keine Injection, kein Umgehen von Anti-Cheat

Hinweis: Automatisierung verstößt sehr wahrscheinlich gegen die Nutzungsbedingungen des Spiels. Nutzung auf eigenes Risiko (Account-Bann möglich).

## Rollen & Workflow

| Wer | Aufgabe |
|---|---|
| **Claude-Chat (dieses Projekt)** | Planen, Entscheidungen treffen, Prompts für Claude Code schreiben |
| **Claude Code** | Programm schreiben, dokumentieren, committen und pushen (Regeln in `AGENTS.md`) |
| **GitHub** | `geilevideossos-gamedev/wardogs-xp-farmer`, Commits nach Conventional Commits, für Menschen verständlich |
| **Context7 MCP** | Aktuelle Doku zu Libraries für Claude Code |
| **Daniel** | Nimmt Abläufe auf, testet im Spiel, gibt Feedback in den Planungschat |

## Offene Fragen

- Heli-Steuerung: Standard-Tastenbelegung? Steuerung über Maus oder nur Tastatur?
- Woran erkennt man im Bild, dass man in der Zone ist und die Crate abgeworfen wurde? (klärt sich über die Aufnahmen)
