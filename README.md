# heli-xp-farmer

Ein Windows-Programm für **WARDOGS** (Steam), das automatisch Pilot-XP farmen soll: mit dem Helikopter **Z20 Lakota** Ammo-Paletten von der blauen Base in die Zone fliegen, abwerfen, zurückfliegen – in einer Schleife, bis du **F2** drückst.

Das Programm liest nur den Bildschirm und drückt Tasten/Maus wie ein Mensch. Es greift nicht in das Spiel ein (kein Speicherlesen, keine Injection).

> Hinweis: Automatisierung verstößt sehr wahrscheinlich gegen die Nutzungsbedingungen des Spiels. Nutzung auf eigenes Risiko (Account-Bann möglich).

## Stand

- Fertig: **Fundament** (Not-Aus mit F2, Tastensteuerung, Bildschirmaufnahme, Log-Dateien, Ablaufsteuerung) und **Layer 1 – Crate-Schleife**: Palette kaufen, ein paar Meter steigen, zur Zone drehen und fliegen, vor der Zone bremsen, in der Zone abwerfen, umdrehen, aus der Zone raus, Base suchen, zurückfliegen, landen
- Die Bilderkennung wurde an deinen Videos getestet. Layer 1 wurde am 17.10. fünfmal im Spiel getestet (`docs/test-runs/2026-10-17-layer1.md`). Kaufen, Abheben, Drehen auf der Stelle, Abwurf und Raus aus der Zone haben je mindestens einmal geklappt. Die Korrekturen aus dem fünften Test (`drop` fliegt selbst los, Sturzflug nur mit S abfangen, Drift beim Drehen mit Palette ausgleichen) sind drin, aber noch **nicht im Spiel geprüft**. Die Landung ist auch in der Simulation noch nicht zuverlässig und wurde mit den neuen Regeln nie im Spiel getestet. Die Flugwerte in `config.yaml` sind weiter Startwerte
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
| `maps.<map>.cruise_speed` | Reisetempo (km/h). Bestimmt, wie weit der Bot die Nase im Reiseflug nach vorne nimmt | 240 |
| `maps.<map>.min_agl` | Mindesthöhe im Reiseflug (m). Darunter steigt der Bot erst mit Shift und nimmt die Nase hoch, bevor er weiter beschleunigt | 80 |
| `maps.<map>.drop_agl` / `drop_speed` | Zielhöhe (m) und Tempo (km/h) vor und in der Zone. Der Bot sinkt sanft dorthin, wirft aber nach 3 s auch höher ab (laut Spieltext zerbricht die Palette ab ca. 90 m freiem Fall) | 70 / 120 |
| `maps.<map>.turn_agl` | So hoch (m) steigt der Bot vor dem Drehen (über die Stromleitungen in der Base) | 25 |
| `maps.<map>.brake_distance` | Ab dieser Entfernung zum Zonenrand (m, Zahl am CZ-Marker) bremst der Bot auf Abwurf-Tempo und sinkt sanft auf Abwurfhöhe | 700 |
| `maps.<map>.drop_min_agl` | G wird nur gedrückt, wenn der Heli mindestens so hoch ist (m). Keine Obergrenze | 30 |
| `flight.drop_delay_s` | Wartezeit nach dem Erreichen der Zone (HZ-Marker oder Heli auf der Minimap im Zonenkreis) bis G | 3 |
| `flight.leave_margin_s` | So lange (s) fliegt der Bot nach dem Verlassen der Zone noch geradeaus, bevor er die Base sucht | 3 |
| `flight.turnaround_s` | So lange (s) dreht der Bot nach dem Abwurf, bevor er aus der Zone fliegt. Mehr = weiter umdrehen | 6 |
| `maps.<map>.land_distance` | Ab dieser Entfernung zur Base (m, Zahl neben dem HQ-Marker) beginnt der Landeanflug: bremsen und sinken. Größer = früher | 1200 |
| `flight.approach_speed_per_m` | Im Landeanflug wird das Soll-Tempo mit der Entfernung kleiner: so viele km/h pro Meter, mindestens `approach_speed`. Kleiner = früher langsam | 0.15 |
| `maps.<map>.hq_approach_y` | Ersatz, falls die Entfernung nicht lesbar ist: Landeanflug, wenn der HQ-Marker so weit unten im Bild ist | 560 |
| `maps.<map>.approach_agl` / `approach_speed` | Höhe (m) und Tempo (km/h) im Landeanflug, bis die Base auf der Minimap unter dem Heli ist | 40 / 40 |
| `flight.hq_overhead_distance` | Ab dieser Entfernung zum HQ (m) über der Base: senkrecht runter | 60 |
| `flight.hq_overshoot_m` | Wird die Entfernung zum HQ im Landeanflug um so viel (m) größer als der kleinste Wert, gilt die Base als überflogen: umdrehen und neu anfliegen | 50 |
| `flight.descend_speed` | Im Sinkflug geht es erst nach unten, wenn der Heli langsamer als das ist (km/h) | 30 |
| `flight.land_timeout_s` | Höchstdauer ab Beginn des Landeanflugs (s), danach sicherer Stopp | 120 |
| `flight.approach_sink_rate` / `drop_sink_rate` | Höchste Sinkrate (m/s) im Landeanflug / vor und in der Zone | 3 / 2 |
| `flight.touchdown_speed` | Unter 10 m sinkt der Bot erst weiter, wenn er langsamer als das ist (km/h) | 15 |
| `flight.bank_speed` / `max_bank` | Ab diesem Tempo (km/h) lenkt der Bot zusätzlich mit A/D, höchstens so schräg (Grad) | 80 / 15 |
| `flight.roll_band` | So viel Schräglage (Grad) gilt noch als gerade | 3 |
| `flight.outside_check_s` | So lange (s) prüft der Bot nach dem Abwurf, ob er schon aus der Zone raus ist | 1 |
| `buy.clicks` | Klickpunkte im Kaufmenü (Logistics, Pallets, Ammo-Palette, Confirm & Exit) | |
| `buy.hover_s` / `press_s` | Pause nach dem Hinbewegen der Maus und Dauer des Klicks (Sekunden). Reagiert ein Knopf nicht, größer machen | 0.2 / 0.1 |
| `buy.confirm_attempts` | So oft klickt der Bot CONFIRM & EXIT, bis das Kaufmenü zu ist | 3 |
| `flight.agl_band` | Erlaubte Abweichung von der Zielhöhe (m) | 8 |
| `flight.yaw_deadband` | Marker gilt als mittig bei dieser Abweichung (Pixel) | 80 |
| `flight.yaw_s_per_px` | Länge eines Q/E-Tipps pro Pixel Abstand zum Ziel (s). Pendelt der Heli beim Drehen: kleiner | 0.0006 |
| `flight.yaw_lookahead_s` | So weit (s) rechnet der Bot das Nachdrehen voraus. Schießt der Marker über die Mitte: größer; bremst er zu früh und kriecht: kleiner | 0.7 |
| `flight.yaw_wait_s` | Pause nach jedem Q/E-Tipp, bis die Wirkung sichtbar ist (s) | 0.5 |
| `flight.turn_done_px_s` | Drehen ist fertig, sobald der Marker im Bild ist (nicht am Rand) und sich langsamer als so viele Pixel pro Sekunde bewegt. Feinlenken übernehmen danach Hinflug und Landung | 200 |
| `flight.turn_timeout_s` | Danach bricht das Drehen mit sicherem Stopp ab (s) | 60 |
| `flight.curve_min_speed` / `curve_exit_speed` | Ab diesem Tempo über Grund (km/h) dreht der Bot im Kurvenflug, erst unter dem zweiten Wert wieder auf der Stelle | 40 / 20 |
| `flight.curve_min_agl` | Kurvenflug (A/D) erst ab dieser Höhe über Grund (m). Darunter, z. B. nach dem Abheben über der Base, nur Q/E auf der Stelle | 60 |
| `flight.turn_hover_speed` | Auf der Stelle: wird der Heli schneller (km/h), bremst er erst, bevor er weiterdreht | 15 |
| `flight.turn_speed` / `turn_bank` | Tempo (km/h) und größte Schräglage (Grad) im Kurvenflug | 60 / 20 |
| `flight.safe_agl` / `safe_speed` | Unter dieser Höhe (m) mit mehr als diesem Tempo (km/h) nur noch steigen und gerade halten | 40 / 50 |
| `flight.dive_sink` | Sturzflug: sinkt schneller als das (m/s) bei mehr als `forward_speed` → Flügel gerade, Shift, nur S-Tipps, nie W | 5 |
| `flight.dive_accel` | Sturzflug nur, wenn das Tempo über Grund dabei wirklich steigt (km/h pro s, über `smooth_s` geglättet). Sinken beim Anflug ist kein Sturzflug | 3 |
| `flight.smooth_s` | Über so viele Sekunden glättet der Bot die Tempo-Änderung für die Sturzflug-Erkennung | 2.0 |
| `flight.brake_max` | So stark (km/h pro s) bremst der Bot höchstens, um auf ein langsameres Ziel-Tempo zu kommen. Kleiner = sanfter, braucht mehr Weg | 8 |
| `flight.dive_exit` | Sturzflug vorbei, wenn er langsamer sinkt als das (m/s) | 1 |
| `flight.dive_tap_s_per_ms` / `dive_tap_max_s` / `dive_interval_s` | S-Tipp im Sturzflug: Sekunden pro m/s Sinkrate, längster Tipp, Abstand (s) | 0.02 / 0.4 / 0.5 |
| `flight.forward_speed` | Über diesem Tempo (km/h) gilt der Heli immer als vorwärts fliegend | 60 |
| `flight.learn_speed` | Nur darunter (km/h) lernt der Bot die Flugrichtung aus seinen Tipps | 40 |
| `flight.drift_accel` | Wird der Heli ohne eigenen W/S-Tipp schneller als das (km/h/s), driftet er: mit Palette W-Tipps, Schräglage ausgleichen | 1 |
| `flight.lean_accel` | Wird der Heli schon stärker als das langsamer (km/h/s), kein weiteres S (nicht weiter zurücklehnen) | 6 |
| `flight.window_taps` / `tap_window_s` | Höchstens so viele W- bzw. S-Tipps in so vielen Sekunden | 3 / 4 |
| `flight.roll_limit` | Größte Schräglage (Grad): darüber sofort gegensteuern, kein Q/E | 25 |
| `flight.hover_roll_band` | Auf der Stelle erst ab dieser Schräglage (Grad) mit A/D ausgleichen | 8 |
| `flight.vertical_limit` | Beim Steigen/Sinken schneller als das (m/s) keine W/S-Tipps (Tempo dann nicht genau messbar) | 3 |
| `flight.sink_rate` | Sinkrate bei der Landung (m/s) | 2.5 |
| `flight.speed_limits` | Höchsttempo je Höhe über Grund als Paare `[Höhe m, km/h]`, dazwischen wird gemittelt. Schützt vor Baum-Crashs wie bei 215 km/h in 28 m Höhe | 20 m → 40, 40 → 100, 60 → 160, 80 → 220, 120 → 280 |
| `flight.sink_guard` | Sinkt der Heli trotz Shift schneller als das (m/s), ist die Nase zu weit unten und der Bot tippt S | 1.5 |
| `flight.pitch_tap_s` / `pitch_interval_s` | Dauer eines W/S-Tipps und Mindestabstand zwischen zwei Tipps (Sekunden) | 0.2 / 1.0 |
| `vision.minimap.min_chroma` / `base_chroma` | Wie bunt die Minimap um das Heli-Symbol sein muss: Zone / Base beim Landen | 14 / 10 |
| `vision.*` | Positionen, Vorlagenbilder und Schwellen der Bilderkennung | |
| `flight.record_s` | So oft (s) schreibt der Bot im Flug eine Zeile in `logs/<Datum>/flight_<Uhrzeit>.csv` | 0.25 |
| `flight.trace_s` | So oft (s) schreibt der Bot im Flug eine Zeile mit Höhe, Tempo, Schräglage, Neigung, Marker und gedrückten Tasten ins Log | 1.0 |
| `loop.tick_s` / `flight.tick_s` | Pause zwischen zwei Bildschirm-Prüfungen außerhalb / in Layer 1 (Sekunden) | 0.1 / 0.05 |
| `hold_test.*`, `recording.*`, `logging.*` | Hold-Test, Aufnahme-Tool, Log-Dateien | |

Alle Werte mit Erklärung: `docs/ARCHITECTURE.md` (Abschnitt „Config-Abschnitte“).

## Logs

Jeder Start schreibt eine Log-Datei nach `logs/<Datum>/`. Im Flug steht dort jede Sekunde eine Zeile `Flug: AGL … m, … km/h (Boden …, Steigen …, Beschl. …), Schräglage …°, Marker …, Tasten …` (mit „Sicherheit: Lage und Höhe zuerst“, wenn die Sicherheit Vorrang hat, bzw. „Sicherheit: Sturzflug abfangen“). Dazu kommt pro Lauf eine Tabelle `flight_<Uhrzeit>.csv` mit 4 Zeilen pro Sekunde (Höhe, Tempo, Tempo über Grund, Steigrate, Beschleunigung, Schräglage, Marker, Tasten). Stoppt das Programm von selbst, liegt dort zusätzlich ein Screenshot unter `screenshots/`.

## Für Entwickler

```powershell
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .
.venv\Scripts\python -m pytest
.venv\Scripts\python -m pytest -m videos
```

Der letzte Befehl vergleicht die Erkennung mit deinen Videos in `wardogs_daten/` (dauert ca. 2 Minuten).

Aufbau: `docs/ARCHITECTURE.md`. Videoanalyse: `docs/ANALYSIS.md`. Entscheidungen: `docs/DECISIONS.md`. Manuelle Tests: `docs/TESTING.md`.
