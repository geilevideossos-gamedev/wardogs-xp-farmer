# heli-xp-farmer

Ein Windows-Programm für **WARDOGS** (Steam), das automatisch Pilot-XP farmen soll: mit dem Helikopter **Z20 Lakota** Ammo-Paletten von der blauen Base in die Zone fliegen, abwerfen, zurückfliegen – in einer Schleife, bis du **F2** drückst.

Das Programm liest nur den Bildschirm und drückt Tasten/Maus wie ein Mensch. Es greift nicht in das Spiel ein (kein Speicherlesen, keine Injection).

> Hinweis: Automatisierung verstößt sehr wahrscheinlich gegen die Nutzungsbedingungen des Spiels. Nutzung auf eigenes Risiko (Account-Bann möglich).

## Stand

- Fertig: **Fundament** (Not-Aus mit F2, Tastensteuerung, Bildschirmaufnahme, Log-Dateien, Ablaufsteuerung) und **Layer 1 – Crate-Schleife**: Palette kaufen, ein paar Meter steigen, zur Zone drehen und fliegen, vor der Zone bremsen, in der Zone abwerfen, umdrehen, aus der Zone raus, Base suchen, zurückfliegen, landen
- Die Bilderkennung wurde an deinen Videos getestet. Layer 1 wurde am 17.10. zum ersten Mal im Spiel getestet (`docs/test-runs/2026-10-17-layer1.md`), die Korrekturen daraus sind drin, aber noch **nicht im Spiel geprüft**. Die Flugwerte in `config.yaml` sind weiter Startwerte
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

Nach dem Start zählt der Bot 5 Sekunden herunter (im Log `Start in 5 s …`). In der Zeit ins Spiel wechseln. Der Bot drückt nur Tasten, solange WARDOGS im Vordergrund ist. Wechselst du in ein anderes Fenster, lässt er sofort alle Tasten los und wartet, bis das Spiel wieder vorne ist (Log `Spielfenster nicht im Vordergrund`). Zeitlimits der Schritte laufen in der Zeit nicht weiter.

**Kurzbefehl `bot`** (startet immer mit `--layer 1`): einmal in PowerShell `notepad $PROFILE` öffnen, diese Zeile einfügen, `<Projektordner>` durch deinen Pfad ersetzen, speichern und PowerShell neu öffnen:

```powershell
function bot { Push-Location "<Projektordner>"; try { .venv\Scripts\python.exe -m heli_farmer.main --layer 1 @args } finally { Pop-Location } }
```

Danach geht in jedem PowerShell-Fenster: `bot` (Dauerlauf), `bot --once`, `bot --step buy`, `bot --step drop --dry-run`, `bot --map ozeti` usw.

| Befehl | Was passiert |
|---|---|
| `.venv\Scripts\python -m heli_farmer.main --layer 1` | Crate-Schleife im Dauerlauf. Start: du sitzt als Pilot im Z20 Lakota, gelandet in der blauen Base (Hinweis „BUY AMMO / SUPPLIES“ sichtbar) |
| `… --layer 1 --once` | Genau eine Runde, dann Ende |
| `… --layer 1 --step buy` | Nur einen Schritt: `buy` (Palette kaufen), `climb` (ein paar Meter abheben), `turn` (zur Zone bzw. zur Base drehen), `drop` (zur Zone fliegen und abwerfen), `leave` (umdrehen und aus der Zone fliegen), `land` (zur Base fliegen und landen) |
| `… --layer 1 --map ozeti` | Flugwerte für eine Map aus `config.yaml` → `maps` verwenden (`bakurani`, `ozeti`, `zestafona`) |
| `… --dry-run` | Probelauf: drückt keine Tasten, schreibt nur ins Log, was er drücken würde |
| `.venv\Scripts\python -m heli_farmer.main --hold-test` | Test für den Not-Aus: hält nach 5 Sekunden die Taste W gedrückt, bis du F2 drückst. Funktioniert in jedem Fenster (z. B. Editor) |

Beendet wird mit **F2** (oder Strg+C im Konsolenfenster). Am Ende steht im Log eine Zusammenfassung (gekaufte, abgeworfene und bestätigte Paletten, Runden).

Wann der Bot von selbst anhält (immer mit Screenshot in `logs/<Datum>/screenshots/`):

- Erste-Hilfe-Symbol (tot), Heli beschädigt (rotes Heli-Symbol unten mittig) oder Heli-Anzeige weg (Crash, ausgestiegen)
- Ein Schritt klappt nicht (z. B. kein Kauf-Hinweis, Kauf erfolglos wegen zu wenig Geld, Zone oder Landung dauert zu lange)
- Bildschirm länger als 30 Sekunden unbekannt
- Runde vorbei (Bildschirm „NEXT ROUND IN“): Log `Runde vorbei …, kein Crash`. Wieder einem Server beitreten kann der Bot erst mit Layer 4

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

Ablauf der Crate-Schleife über ein Video anzeigen (Kaufmenü, Flug zur Zone, Rückflug, gelandet, Abwürfe, wann der Bot „in der Zone“ erkannt hätte und wo er bremsen würde; Tabelle landet in `debug/replay/…`):

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

Der Bot benutzt im Spiel: Shift (steigen), Strg (sinken), W/S (vorwärts/bremsen), Q/E (drehen), A/D (zur Seite neigen, in Kurven und zum Geradehalten), B (Kaufmenü), G (abwerfen) und Mausklicks im Kaufmenü.

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
| `loop.start_delay_s` | Countdown nach dem Start, bevor der Bot etwas drückt (Sekunden) | 5 |
| `window.title` | Fenstertitel des Spiels. Nur wenn dieses Fenster vorne ist, drückt der Bot Tasten. Nach dem Countdown steht im Log `Vordergrund: '…'`; weicht der Titel ab, hier eintragen | Wardogs |
| `keys.*` | Tasten: `stop` F2, `shop` b, `drop` g, `up` shift, `down` ctrl, `forward` w, `back` s, `yaw_left` q, `yaw_right` e, `roll_left` a, `roll_right` d, `record` f9 | |
| `timeouts.unknown_state_s` | So lange darf der Bildschirm unbekannt sein, bevor das Programm sicher stoppt (Sekunden) | 30 |
| `timeouts.max_hold_s` | Keine Taste wird länger am Stück gehalten (Sekunden) | 20 |
| `timeouts.heli_lost_s` | So lange darf die Heli-Anzeige fehlen, bevor Layer 1 verlassen wird | 2 |
| `maps.<map>.cruise_agl` | Reiseflughöhe über Grund (m) | 100 |
| `maps.<map>.cruise_speed` | Reisetempo (km/h). Bestimmt, wie weit der Bot die Nase im Reiseflug nach vorne nimmt | 180 |
| `maps.<map>.min_agl` | Mindesthöhe im Reiseflug (m). Darunter steigt der Bot erst mit Shift und nimmt die Nase hoch, bevor er weiter beschleunigt | 80 |
| `maps.<map>.drop_agl` / `drop_speed` | Zielhöhe (m) und Tempo (km/h) vor und in der Zone. Der Bot sinkt sanft dorthin, wirft aber nach 3 s auch höher ab (laut Spieltext zerbricht die Palette ab ca. 90 m freiem Fall) | 70 / 120 |
| `maps.<map>.turn_agl` | So hoch (m) steigt der Bot vor dem Drehen (über die Stromleitungen in der Base) | 25 |
| `maps.<map>.brake_distance` | Ab dieser Entfernung zum Zonenrand (m, Zahl am CZ-Marker) bremst der Bot auf Abwurf-Tempo und sinkt sanft auf Abwurfhöhe | 400 |
| `maps.<map>.drop_min_agl` | G wird nur gedrückt, wenn der Heli mindestens so hoch ist (m). Keine Obergrenze | 30 |
| `flight.drop_delay_s` | Wartezeit nach dem Erreichen der Zone (HZ-Marker oder Heli auf der Minimap im Zonenkreis) bis G | 3 |
| `flight.leave_margin_s` | So lange (s) fliegt der Bot nach dem Verlassen der Zone noch geradeaus, bevor er die Base sucht | 3 |
| `flight.turnaround_s` | So lange (s) dreht der Bot nach dem Abwurf, bevor er aus der Zone fliegt. Mehr = weiter umdrehen | 6 |
| `maps.<map>.land_distance` | Ab dieser Entfernung zur Base (m, Zahl neben dem HQ-Marker) beginnt der Landeanflug: bremsen und sinken. Größer = früher | 700 |
| `maps.<map>.hq_approach_y` | Ersatz, falls die Entfernung nicht lesbar ist: Landeanflug, wenn der HQ-Marker so weit unten im Bild ist | 560 |
| `maps.<map>.approach_agl` / `approach_speed` | Höhe (m) und Tempo (km/h) im Landeanflug, bis die Base auf der Minimap unter dem Heli ist | 40 / 40 |
| `flight.hq_overhead_distance` | Ab dieser Entfernung zum HQ (m) über der Base: senkrecht runter | 60 |
| `flight.hq_overshoot_m` | Wird die Entfernung zum HQ im Landeanflug um so viel (m) größer als der kleinste Wert, gilt die Base als überflogen: umdrehen und neu anfliegen | 50 |
| `flight.descend_speed` | Im Sinkflug geht es erst nach unten, wenn der Heli langsamer als das ist (km/h) | 30 |
| `flight.land_timeout_s` | Höchstdauer ab Beginn des Landeanflugs (s), danach sicherer Stopp | 120 |
| `flight.approach_sink_rate` / `drop_sink_rate` | Höchste Sinkrate (m/s) im Landeanflug / vor und in der Zone | 3 / 2 |
| `flight.touchdown_speed` | Unter 10 m sinkt der Bot erst weiter, wenn er langsamer als das ist (km/h) | 15 |
| `flight.max_tilt` | So viele W-Tipps nimmt der Bot die Nase höchstens nach vorne (ein Tipp geschätzt 3–5°). Neigt er zu stark: kleiner | 4 |
| `flight.trim_speed` / `trim_accel` / `trim_tap_s` | Ausgleich, wenn die Palette die Nase hochzieht: kurzer W-Tipp (s), wenn der Heli beim Schweben schneller als `trim_speed` km/h wird bzw. im Reiseflug kaum noch beschleunigt | 4 / 4 / 0.1 |
| `flight.bank_speed` / `max_bank` | Ab diesem Tempo (km/h) lenkt der Bot zusätzlich mit A/D, höchstens so schräg (Grad) | 80 / 15 |
| `flight.roll_band` | So viel Schräglage (Grad) gilt noch als gerade | 4 |
| `flight.outside_check_s` | So lange (s) prüft der Bot nach dem Abwurf, ob er schon aus der Zone raus ist | 1 |
| `buy.clicks` | Klickpunkte im Kaufmenü (Logistics, Pallets, Ammo-Palette, Confirm & Exit) | |
| `buy.hover_s` / `press_s` | Pause nach dem Hinbewegen der Maus und Dauer des Klicks (Sekunden). Reagiert ein Knopf nicht, größer machen | 0.2 / 0.1 |
| `buy.confirm_attempts` | So oft klickt der Bot CONFIRM & EXIT, bis das Kaufmenü zu ist | 3 |
| `flight.agl_band` | Erlaubte Abweichung von der Zielhöhe (m) | 8 |
| `flight.yaw_deadband` | Marker gilt als mittig bei dieser Abweichung (Pixel) | 80 |
| `flight.yaw_s_per_px` | Länge eines Q/E-Tipps pro Pixel Abstand zum Ziel (s). Pendelt der Heli beim Drehen: kleiner | 0.0006 |
| `flight.yaw_lookahead_s` | So weit (s) rechnet der Bot das Nachdrehen voraus. Schießt der Marker über die Mitte: größer; bremst er zu früh und kriecht: kleiner | 0.7 |
| `flight.yaw_wait_s` | Pause nach jedem Q/E-Tipp, bis die Wirkung sichtbar ist (s) | 0.5 |
| `flight.yaw_settle_s` | So lange (s) muss der Marker ruhig in der Mitte stehen, bis das Drehen fertig ist | 1.0 |
| `flight.turn_timeout_s` | Danach bricht das Drehen mit sicherem Stopp ab (s) | 30 |
| `flight.sink_rate` | Sinkrate bei der Landung (m/s) | 4 |
| `flight.speed_limits` | Höchsttempo je Höhe über Grund als Paare `[Höhe m, km/h]`, dazwischen wird gemittelt. Schützt vor Baum-Crashs wie bei 215 km/h in 28 m Höhe | 20 m → 40, 40 → 100, 60 → 160, 80 → 220, 120 → 280 |
| `flight.sink_guard` | Sinkt der Heli trotz Shift schneller als das (m/s), ist die Nase zu weit unten und der Bot tippt S | 1.5 |
| `flight.pitch_tap_s` / `pitch_interval_s` | Dauer eines W/S-Tipps und Mindestabstand zwischen zwei Tipps (Sekunden) | 0.2 / 0.7 |
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
