# heli-xp-farmer

Ein Windows-Programm für **WARDOGS** (Steam), das automatisch Pilot-XP farmen soll: mit dem Helikopter **Z20 Lakota** Ammo-Paletten von der blauen Base in die Zone fliegen, abwerfen, zurückfliegen – in einer Schleife, bis du **F2** drückst.

Das Programm liest nur den Bildschirm und drückt Tasten/Maus wie ein Mensch. Es greift nicht in das Spiel ein (kein Speicherlesen, keine Injection).

> Hinweis: Automatisierung verstößt sehr wahrscheinlich gegen die Nutzungsbedingungen des Spiels. Nutzung auf eigenes Risiko (Account-Bann möglich).

## Stand

- Fertig: **Fundament** (Not-Aus mit F2, Tastensteuerung, Bildschirmaufnahme, Log-Dateien, Ablaufsteuerung) und **Layer 1 – Crate-Schleife**: Palette kaufen, steigen, zur Zone drehen und fliegen, abwerfen, zurück zur Base, landen
- Die Bilderkennung wurde an deinen Videos getestet. Das Fliegen selbst ist noch **nicht im Spiel getestet**, die Werte in `config.yaml` sind Startwerte
- Noch nicht gebaut: Heli kaufen (Layer 2), Team (Layer 3), Server (Layer 4). Braucht der Bot einen davon (z. B. nach einem Absturz), hält er sicher an und speichert einen Screenshot

## Installation

Voraussetzung: Windows, Python 3.12 oder neuer, Git.

In PowerShell im Projektordner:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## Start

Immer aus dem Projektordner heraus. Spiel in 1920×1080, randloses Fenster.

| Befehl | Was passiert |
|---|---|
| `.venv\Scripts\python -m heli_farmer.main --layer 1` | Crate-Schleife im Dauerlauf. Start: du sitzt als Pilot im Z20 Lakota, gelandet in der blauen Base (Hinweis „BUY AMMO / SUPPLIES“ sichtbar) |
| `… --layer 1 --once` | Genau eine Runde, dann Ende |
| `… --layer 1 --step buy` | Nur einen Schritt: `buy` (Palette kaufen), `climb` (auf sichere Höhe steigen), `turn` (zur Zone bzw. zur Base drehen), `drop` (zur Zone fliegen und abwerfen), `land` (zur Base fliegen und landen) |
| `… --layer 1 --map ozeti` | Flugwerte für eine Map aus `config.yaml` → `maps` verwenden (`bakurani`, `ozeti`, `zestafona`) |
| `… --dry-run` | Probelauf: drückt keine Tasten, schreibt nur ins Log, was er drücken würde |
| `.venv\Scripts\python -m heli_farmer.main --hold-test` | Test für den Not-Aus: hält nach 5 Sekunden die Taste W gedrückt, bis du F2 drückst |

Beendet wird mit **F2** (oder Strg+C im Konsolenfenster). Am Ende steht im Log eine Zusammenfassung (gekaufte, abgeworfene und bestätigte Paletten, Runden).

Wann der Bot von selbst anhält (immer mit Screenshot in `logs/<Datum>/screenshots/`):

- Erste-Hilfe-Symbol (tot), Heli beschädigt (rotes Heli-Symbol unten mittig) oder Heli-Anzeige weg (Crash, ausgestiegen)
- Ein Schritt klappt nicht (z. B. kein Kauf-Hinweis, Kauf erfolglos wegen zu wenig Geld, Zone oder Landung dauert zu lange)
- Bildschirm länger als 30 Sekunden unbekannt

## Aufnahmen für Testdaten

```powershell
.venv\Scripts\python -m tools.record --map <mapname> --seq <sequenz>
```

**F9** startet und stoppt eine Aufnahme, **F2** beendet das Tool. Was du wie oft aufnehmen sollst: `docs/RECORDING.md`.

## Videos auswerten

Funktioniert mit Aufnahmen des Aufnahme-Tools und mit normalen OBS-Videos (MP4, 1920×1080).

Tasten aus einem OBS-Video mit Tasten-Overlay auslesen (schreibt `<video>.inputs.jsonl` neben das Video):

```powershell
.venv\Scripts\python -m tools.overlay_inputs wardogs_daten\Video\join+Bakurani.mp4
```

Ablauf der Crate-Schleife über ein Video anzeigen (Kaufmenü, Flug zur Zone, Rückflug, gelandet, Abwürfe; Tabelle landet in `debug/replay/…`):

```powershell
.venv\Scripts\python -m tools.replay wardogs_daten\Video\join+Bakurani.mp4
```

`--step 3` prüft jedes 3. Bild (genauer, langsamer, Standard 6).

Einzelbilder als PNG speichern (landen in `debug/frames/…`):

```powershell
.venv\Scripts\python -m tools.extract_frames <video.mp4> --at 12.5 30
.venv\Scripts\python -m tools.extract_frames <video.mp4> --every 2
.venv\Scripts\python -m tools.extract_frames <video.mp4> --at 12.5 --crop 800 900 300 100
```

## Tasten

| Taste | Wirkung |
|---|---|
| **F2** | Not-Aus: stoppt sofort und lässt alle Tasten los. Im Aufnahme-Tool: beenden |
| **F9** | Aufnahme-Tool: Aufnahme starten/stoppen |

Der Bot benutzt im Spiel: Shift (steigen), Strg (sinken), W/S (vorwärts/bremsen), Q/E (drehen), B (Kaufmenü), G (abwerfen) und Mausklicks im Kaufmenü.

## Einstellungen

Alle Werte stehen in `config.yaml`. Ändere diese Datei nicht für persönliche Werte, sondern lege daneben eine `config.local.yaml` an. Sie wird nicht hochgeladen und überschreibt nur das, was darin steht. Beispiel:

```yaml
game_region:
  left: 1920
maps:
  ozeti:
    cruise_agl: 120
```

Die wichtigsten Einstellungen:

| Einstellung | Bedeutung | Standard |
|---|---|---|
| `game_region` | Bildschirmbereich des Spiels (links, oben, Breite, Höhe in Pixeln) | 0, 0, 1920, 1080 |
| `keys.*` | Tasten: `stop` F2, `shop` b, `drop` g, `up` shift, `down` ctrl, `forward` w, `back` s, `yaw_left` q, `yaw_right` e, `record` f9 | |
| `timeouts.unknown_state_s` | So lange darf der Bildschirm unbekannt sein, bevor das Programm sicher stoppt (Sekunden) | 30 |
| `timeouts.max_hold_s` | Keine Taste wird länger am Stück gehalten (Sekunden) | 20 |
| `timeouts.heli_lost_s` | So lange darf die Heli-Anzeige fehlen, bevor Layer 1 verlassen wird | 2 |
| `maps.<map>.cruise_agl` | Reiseflughöhe über Grund (m) | 100 |
| `maps.<map>.cruise_speed` | Reisetempo (km/h) | 200 |
| `maps.<map>.drop_agl` / `drop_speed` | Höchstens so hoch (m) und schnell (km/h) beim Abwurf. Über ca. 90 m zerbricht die Palette | 60 / 120 |
| `maps.<map>.zone_arrive_y` | Abwurf, wenn der Zonen-Marker so weit unten im Bild ist (Pixel von oben). Kleiner = früher abwerfen | 620 |
| `maps.<map>.hq_approach_y` | Bremsen, wenn der HQ-Marker so weit unten ist (oder der Kauf-Hinweis erscheint) | 560 |
| `maps.<map>.approach_speed` | Ab diesem Tempo (km/h) beginnt der Sinkflug zur Landung | 60 |
| `buy.clicks` | Klickpunkte im Kaufmenü (Logistics, Pallets, Ammo-Palette, Confirm & Exit) | |
| `flight.agl_band` | Erlaubte Abweichung von der Zielhöhe (m) | 8 |
| `flight.yaw_deadband` | Marker gilt als mittig bei dieser Abweichung (Pixel) | 40 |
| `flight.sink_rate` | Sinkrate bei der Landung (m/s) | 4 |
| `vision.*` | Positionen, Vorlagenbilder und Schwellen der Bilderkennung | |
| `loop.tick_s` / `flight.tick_s` | Pause zwischen zwei Bildschirm-Prüfungen außerhalb / in Layer 1 (Sekunden) | 0.1 / 0.05 |
| `hold_test.*`, `recording.*`, `logging.*` | Hold-Test, Aufnahme-Tool, Log-Dateien | |

Alle Werte mit Erklärung: `docs/ARCHITECTURE.md` (Abschnitt „Config-Abschnitte“).

## Logs

Jeder Start schreibt eine Log-Datei nach `logs/<Datum>/`. Stoppt das Programm von selbst, liegt dort zusätzlich ein Screenshot unter `screenshots/`.

## Für Entwickler

```powershell
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .
.venv\Scripts\python -m pytest
.venv\Scripts\python -m pytest -m videos
```

Der letzte Befehl vergleicht die Erkennung mit deinen Videos in `wardogs_daten/` (dauert ca. 2 Minuten).

Aufbau: `docs/ARCHITECTURE.md`. Videoanalyse: `docs/ANALYSIS.md`. Entscheidungen: `docs/DECISIONS.md`. Manuelle Tests: `docs/TESTING.md`.
