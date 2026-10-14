# heli-xp-farmer – Projektbeschreibung

## Ziel

Ein Windows-Programm, das in **WARDOGS** automatisch Pilot-XP farmt, indem es mit dem Helikopter **Z20 Lakota** in einer Endlosschleife Ammo-Crates von der blauen Base in die Zone fliegt.
Das Programm läuft so lange, bis der Hotkey **F2** gedrückt wird.

## Ablauf (Soll-Verhalten)

1. Spiel ist offen → Programm joint automatisch einem Match
2. Team **Blau** wählen
3. Zum Fahrzeughändler gehen → Tab **Air** → **Z20 Lakota** kaufen
4. Als **Pilot** einsteigen
5. **B** drücken → **Ammo Crate** kaufen
6. Abheben und die Crate **ohne Crash** in die Zone fliegen
7. Zurück zur **blauen Base** fliegen und dort landen
8. Wieder **B** → Ammo Crate kaufen → weiter bei Schritt 6
9. **F2** stoppt das Programm jederzeit sofort, alle gedrückten Tasten werden losgelassen

Fehlerfälle, die das Programm abfangen soll:

- Heli zerstört / Spieler tot → Respawn, weiter bei Schritt 3
- Aus dem Match geflogen / Match vorbei → weiter bei Schritt 1
- Zu wenig Geld oder unbekannter Bildschirmzustand → sauber stoppen und ins Log schreiben

## Voraussetzungen im Spiel

- Pilot-Level 10 und Z20 Lakota bereits freigeschaltet (einmalig $35.000, danach ca. $7.400 pro Kauf)
- Genug Geld für Heli + Crates

## Technischer Ansatz

- Reines **externes Input-Programm**: liest nur den Bildschirm (Screenshots, Bilderkennung) und simuliert Tastatur/Maus
- **Kein** Lesen oder Schreiben von Spielspeicher, keine Injection, kein Umgehen von Anti-Cheat
- Sprache und Libraries werden im Planungschat festgelegt (Vorschlag: Python, mss, OpenCV, pydirectinput, pynput)

Hinweis: Automatisierung verstößt sehr wahrscheinlich gegen die Nutzungsbedingungen des Spiels. Nutzung auf eigenes Risiko (Account-Bann möglich).

## Rollen & Workflow

| Wer | Aufgabe |
|---|---|
| **Claude-Chat (dieses Projekt)** | Planen, Entscheidungen treffen, Prompts für Claude Code schreiben |
| **Claude Code** | Programm schreiben, dokumentieren, committen und pushen (Regeln in `AGENTS.md`) |
| **GitHub** | Speichert den Code, Commits nach Conventional Commits, für Menschen verständlich |
| **Context7 MCP** | Aktuelle Doku zu Libraries für Claude Code |
| **Daniel** | Testet das Programm selbst im Spiel und gibt Feedback in den Planungschat |

## Offene Fragen

- Plattform von WARDOGS (eigenständig auf Steam oder Roblox-Experience)?
- Bildschirmauflösung und Fenstermodus beim Spielen?
- Muss die Crate in der Zone aktiv abgeworfen werden oder reicht Hinfliegen?
- Ist die Map fix oder wechselt sie? Ist der Spawn-/Landepunkt in der Base immer gleich?
- Wie wird ein Match gejoint (Quick Join, Serverliste)?
