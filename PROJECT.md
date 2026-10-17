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
8. Zurück zur **blauen Base** fliegen und auf der **rechteckigen Grasfläche** landen (dort erscheint „[B] BUY AMMO / SUPPLIES“)
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
| Maps | `bakurani`, `ozeti`, `zestafona` (rotieren) |
| Landeplatz Base | rechteckige Grasfläche in der Base, dort erscheint „[B] BUY AMMO / SUPPLIES“ |
| Match joinen | Serverliste → Server wählen → „Join Match“ |
| Hotkeys Bot | F2 (Stopp) und F9 (Aufnahme) sind im Spiel nicht belegt |

Voraussetzungen im Spiel: Pilot-Level 10 und Z20 Lakota freigeschaltet (einmalig $35.000, danach ca. $7.400 pro Kauf), genug Geld für Heli + Crates.

## Steuerung

Zu Fuß: **F** beim Händler öffnet das Kaufmenü für den Heli.

Im Heli ist die **Maus irrelevant**, nur Tastatur:

| Taste | Wirkung |
|---|---|
| W | Nase runter (vorwärts) |
| S | Nase hoch (bremsen/rückwärts) |
| A / D | nach links / rechts neigen |
| Q / E | um die eigene Achse links / rechts drehen |
| Shift | Höhe gewinnen |
| Strg | Höhe verlieren |
| B | Kaufmenü im Heli → große Ammo-Palette kaufen |
| G | Palette in der Luft über der Zone abwerfen |
| Tab | irrelevant (in den Videos ignorieren) |

## Flugverhalten Z20 Lakota

- Keine Taste gedrückt: Heli schwebt und hält die Höhe
- W ohne Shift: fliegt vorwärts und verliert Höhe
- **Reiseflug:** ca. **10–15°** Nase nach vorne + Shift halten → Höhe bleibt konstant. Mehr Neigung ist zu aggressiv, dann mit S zurücknehmen
- **Mit Palette geladen:** Gewicht hinten → Heli kippt beim Schweben langsam nach hinten → mit etwas W ausgleichen
- **Drehen hat Schwung:** Nach Q/E dreht der Heli nach. Vor dem Ziel mit der Gegentaste abbremsen, sonst pendelt er um das Ziel
- **Abheben:** in der Base gibt es Stromleitungen → vor dem Drehen auf ca. 25 m steigen
- **Lenken bei Tempo:** Q/E (Heckrotor) allein reicht bei höherem Tempo nicht, sonst fliegt er endlos Kreise → zusätzlich mit A/D in die Kurve neigen
- **Landen:** Strg allein reicht nicht, weil der Heli noch vorwärts fliegt → mit S abbremsen. Sinkflug etwa doppelt so früh beginnen wie bisher. Es reicht, wenn die Landefläche auf der Minimap unter dem Heli liegt, sie muss nicht im Bild zu sehen sein
- **In der Zone:** nicht aggressiv sinken, Heli gerade halten, aus sicherer Höhe abwerfen. Nach G trägt der Schwung den Heli meist von selbst aus der Zone
- Hauptgefahr: zu schnell und zu tief über Bäumen (Crash bei 215 km/h und AGL 28 m; Crash in der Zone durch zu schnelles, schiefes Sinken)

## Navigation

- **Goldener CZ-Marker** = Richtung zur Zone, mit Entfernung in m/km daneben
- CZ-Marker nicht sichtbar beim Start: mit Shift ein paar Meter steigen, dann nur Q/E drehen, bis der CZ-Marker im Bild ist
- **In der Zone:** Heli-Symbol auf der Minimap liegt im Zonen-Kreis (Kreis blau, grün, rot oder **weiß**) **oder** der CZ-Marker wird durch HZ ersetzt. Eines davon reicht → 3 s warten → G. Keine Obergrenze für die Abwurfhöhe, sonst fliegt er durch die Zone durch
- **Base überflogen:** Wird die HQ-Entfernung beim Landeanflug wieder größer, umdrehen und neu anfliegen. Nie irgendwo außerhalb der Base landen
- Heli-Symbol nicht im Kreis = noch nicht in der Zone, weiter Richtung CZ
- Nach „SUPPLIES DELIVERED“ umdrehen. In der Zone ist der HQ-Marker (blauer Kreis) nicht sichtbar → erst aus der Zone rausfliegen, dann HQ-Marker suchen und zur Base fliegen

## Spielverhalten (aus Daniels Notizen)

- **Ladebildschirm und Serverliste können die alte Map zeigen:** Nach Rundenende läuft der Server weiter, der Map-Name wird erst verzögert aktualisiert. Die Map daher nie aus dem Ladebildschirm bestimmen, sondern im Spiel (z. B. Minimap)
- **Rundenende:** Bildschirm mit „NEXT ROUND IN mm:ss“ (Tabs SCORE / PROGRESSION / SCOREBOARD) → Heli ist weg, das ist kein Crash
- Kaufmenü im Heli: „LOGISTICS SLOTS FULL“ = Palette ist schon geladen → nicht nochmal kaufen, nur „CONFIRM & EXIT“
- Während „Waiting for world to load“ oder „Waiting for player x of 66“ (weiß, oben) nichts drücken
- Team-Hintergrund leicht grau und nach 30 s kein Join möglich → Esc → mit der Maus „Yes“ → zurück im Hauptmenü, neuen Server suchen
- Beim Händler kann der falsche Heli gekauft werden → Kauf prüfen
- Crash im Spawnbereich: man stirbt nicht, wird aber aus dem Heli geworfen → zurück zum Händler, neuen Heli kaufen
- Abgeschossen oder zu schnell in Bäume gecrasht → Erste-Hilfe-Symbol erscheint → **F 7 s halten** → wieder in der Base ohne Heli
- Rakete zerstört den Rotor → nicht weiterfliegen, W halten, in den Boden crashen, wie Tod behandeln
- Bäume sind die Hauptgefahr beim Fliegen → genug Höhe halten

## Daniels Testdaten

Ordner `wardogs_daten/` (lokal, nie committen):

- `Video/join+<Map>.mp4`: alle drei Videos sind auf der Map im Dateinamen. `join+Zestafona.mp4` ist Zestafona, obwohl der Ladebildschirm Ozeti zeigt (siehe Spielverhalten). OBS-Aufnahmen 1920×1080, 60 fps, 7–9 min pro Map, vom Joinen bis zu mehreren Crate-Runden. Oben links ist ein **Tasten-Overlay** eingeblendet (TAB Q W E R / SHIFT A S D F / CTRL + Maus): gedrückte Tasten leuchten **gelb**. B und G sind darin **nicht** sichtbar. Das Overlay gibt es nur in den Videos, nicht im echten Spiel
- `Images/*.png`: Screenshots wichtiger Situationen, der **Dateiname ist Daniels Erklärung** dazu

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

- Schwebetest (20 s ohne Tasten auf 100 m, dann W tippen) steht noch aus, Ergebnis laut Daniel siehe „Flugverhalten“
