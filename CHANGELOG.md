# Changelog

Alle wichtigen Änderungen an diesem Projekt. Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Unreleased]

### Hinzugefügt

- Projekt-Grundgerüst: Python-Projekt mit Prüfwerkzeugen (Ruff) und automatischen Tests (Pytest)
- Einstellungsdatei `config.yaml` mit neutralen Standardwerten (Spielbereich 1920×1080, Tasten F2/B/G/F9, Zeitlimits). Eigene Werte kommen in `config.local.yaml`, die nicht hochgeladen wird
- Not-Aus mit F2: stoppt sofort und lässt alle gedrückten Tasten und Maustasten los (Ziel unter 100 ms)
- Ablaufsteuerung in Ebenen (Server → Team → Heli → Crate-Schleife): prüft bei jedem Schritt von außen nach innen und fällt automatisch auf die äußere Ebene zurück. Bilderkennung ist noch ein Platzhalter
- Sicherheits-Stopp: Ist der Bildschirmzustand länger als 30 Sekunden unbekannt, stoppt das Programm
- Bot-Start mit `--dry-run` (Probelauf ohne Tastendrücke) und `--hold-test` (hält W gedrückt, um den Not-Aus zu testen)
- Log-Dateien pro Tag unter `logs/<Datum>/`, bei einem Sicherheits-Stopp zusätzlich ein Screenshot
- Aufnahme-Tool `tools/record.py`: nimmt Spielbild und alle Eingaben synchron auf (Start/Stopp mit F9, Beenden mit F2). Anleitung in `docs/RECORDING.md`
- Analyse-Tools: `tools/extract_frames.py` speichert Einzelbilder aus Videos (zu Zeitpunkten oder in Abständen, optional zugeschnitten), `tools/replay.py` zeigt, welche Zustände der Bot in einem Video erkennt. Beide funktionieren auch mit OBS-Videos
- Bilderkennung: liest Tempo und Höhe aus dem HUD und erkennt „Z20 LAKOTA“, die geladene Palette, den Kauf-Hinweis „BUY AMMO / SUPPLIES“, das Kaufmenü, die Lieferbestätigung, das Erste-Hilfe-Symbol, Heli-Schaden sowie die Marker für Zone und Base. Getestet mit 43 zugeschnittenen Bildern aus allen drei Videos (Vorlagenbilder in `assets/`)
- Tool `tools/overlay_inputs.py`: liest das Tasten-Overlay aus OBS-Videos aus und schreibt eine Tasten-Liste im Format des Aufnahme-Tools. B und G erkennt es am Bild (Kaufmenü geht auf, Palette ist weg)
- Videoanalyse `docs/ANALYSIS.md`: Ablauf pro Video mit Zeiten, woran der Bot welchen Zustand erkennt, Steuerung, Kaufablauf und Flugmuster. In `docs/RECORDING.md` steht, welche Aufnahmen noch fehlen
- Tastensteuerung kann Tasten halten, kurz tippen, im Menü klicken und zu lange gehaltene Tasten von selbst loslassen
- Flugregler: hält die Höhe über Grund (Shift/Strg), regelt das Tempo mit kurzen W/S-Tipps und dreht mit Q/E zum Ziel-Marker
- Layer 1 – Crate-Schleife: kauft die Ammo-Palette, steigt, dreht zur Zone, fliegt hin, wirft unter 60 m ab, dreht zur Base, fliegt zurück und landet im Kaufbereich. Start mit `--layer 1`, eine Runde mit `--once`, ein einzelner Schritt mit `--step buy|climb|turn|drop|land`, Flugwerte pro Map mit `--map`. Keine Taste bleibt länger als 20 Sekunden am Stück gedrückt (`timeouts.max_hold_s`). Stoppt sicher mit Screenshot bei Tod, Heli-Schaden, Crash oder wenn ein Schritt nicht klappt. Am Ende steht eine Zusammenfassung im Log
- Bilderkennung für die Zone: erkennt, ob der Zonen-Marker „CZ“ oder „HZ“ zeigt, liest die Entfernung darüber („744 m“, „1.6 km“) und prüft, ob das Heli-Symbol auf der Minimap in einem eingefärbten Zonenkreis liegt. Außerdem wird die Höhe über Meer (ASL) gelesen. Getestet mit 17 neuen Testbildern aus allen drei Videos

### Geändert

- `tools/replay.py` zeigt jetzt den Ablauf der Crate-Schleife pro Video (Kaufmenü, Flug zur Zone, Rückflug, gelandet, beschädigt, tot) und die Abwurfzeitpunkte. `python -m pytest -m videos` gleicht das mit `docs/ANALYSIS.md` ab
- Flugregler nach Daniels Flugmodell: Die Höhe wird nur noch mit Shift gehalten (Strg nur beim Landen). Das Tempo regelt der Bot über kurze W/S-Tipps. Neu sind Sicherheitsgrenzen: eine Mindesthöhe im Reiseflug (80 m) und ein Höchsttempo je Höhe. Ist der Heli zu tief oder zu schnell, steigt er zuerst mit Shift und nimmt die Nase hoch. Sinkt der Heli trotz Shift, nimmt er die Nase ebenfalls hoch
- Crate-Schleife nach Daniels Navigationsregeln: Nach dem Kauf steigt der Bot nur ein paar Meter und dreht dann nur mit Q/E zur Zone. Er steigt auf mindestens 80 m, bevor er Fahrt aufnimmt. Ab 400 m vor der Zone (Zahl am CZ-Marker) bremst er und sinkt auf Abwurfhöhe. In der Zone (Minimap und HZ) wartet er 3 Sekunden und wirft dann ab, aber nur unter 85 m. Danach dreht er um, fliegt aus der Zone und sucht erst dann den HQ-Marker. Neuer Einzelschritt `--step leave`
- Nach dem Bremsen richtet der Bot den Heli wieder gerade aus (so viele W-Tipps wie vorher S-Tipps), damit er nicht rückwärts wegfliegt. Vor dem Abwurf und bei der Landung darf er zum Sinken Strg benutzen. Die Landung fliegt er tief und langsam an, bis „[B] BUY AMMO / SUPPLIES“ erscheint, und erst dann geht er senkrecht runter. Nach dem Verlassen der Zone fliegt er noch 3 Sekunden weiter, bevor er die Base sucht

### Behoben

- Das Video `join+Zestafona.mp4` wird jetzt richtig als Zestafona geführt (Doku und Testbilder). Der Ladebildschirm hatte fälschlich Ozeti gezeigt, weil der Server nach Rundenende noch die alte Map anzeigt
