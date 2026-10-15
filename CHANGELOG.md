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

### Geändert

- `tools/replay.py` zeigt jetzt den Ablauf der Crate-Schleife pro Video (Kaufmenü, Flug zur Zone, Rückflug, gelandet, beschädigt, tot) und die Abwurfzeitpunkte. `python -m pytest -m videos` gleicht das mit `docs/ANALYSIS.md` ab
