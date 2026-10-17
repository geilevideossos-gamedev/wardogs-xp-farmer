# Entscheidungslog

Format je Eintrag: Datum, Entscheidung, Grund, verworfene Alternativen.

## 2026-10-15 – Python-Version

- **Entscheidung:** `requires-python = ">=3.12"`, Ruff-Ziel `py312`. Entwicklung und Tests laufen lokal mit Python 3.13.
- **Grund:** Vorgabe 3.12; auf dem Entwicklungsrechner ist nur 3.13 installiert. Code nutzt keine 3.13-only-Features, Ruff prüft gegen 3.12.
- **Verworfen:** exakt `==3.12.*` pinnen (würde lokale Tests blockieren).

## 2026-10-15 – Dependencies

| Paket | Version (getestet) | Zweck |
|---|---|---|
| `mss` | 10.2.0 | Screen-Capture der Spielregion. API: `mss.MSS().grab(region)` |
| `opencv-python` | 5.0.0.93 | Farbkonvertierung, PNG, MP4 lesen/schreiben, später Template-Matching |
| `numpy` | 2.5.4 | Frames als Arrays |
| `pydirectinput` | 1.0.4 | Tastatur/Maus über `SendInput` mit Scan-Codes (DirectX-Spiele) |
| `pynput` | 1.8.2 | Globale Low-Level-Hooks für F2/F9 und Input-Aufnahme |
| `pyyaml` | 6.0.3 | Config |
| `ruff`, `pytest` | 0.17.0, 9.1.1 | Dev: Lint/Format, Tests |

- **Grund:** Vorschlag aus `PROJECT.md`, APIs per Context7 und lokal geprüft.
- **Verworfen:** `pydirectinput-rgx` (Fork mit mehr Features; aktuell nicht nötig), `keyboard`-Paket (braucht für Hooks teils Admin, kein Maus-Listener), `pyautogui` (virtuelle Keycodes, von vielen Spielen ignoriert).

## 2026-10-15 – Killswitch und Eingabe

- **Entscheidung:** F2-Callback des pynput-Listener-Threads setzt das Stop-Event **und** ruft direkt `Input.release_all()` auf. `Input` hält alle Sendevorgänge unter einem Lock; nach gesetztem Stop wirft `key_down`/`mouse_down` `Stopped`, statt zu senden.
- **Grund:** Loslassen hängt nicht davon ab, wann der Hauptthread das Event bemerkt. Lock verhindert, dass nach `release_all()` noch eine Taste gedrückt wird. Gemessen: Loslassen < 1 ms nach Callback.
- **Entscheidung:** `pydirectinput.PAUSE = 0`, `pydirectinput.FAILSAFE = False`.
- **Grund:** Standard-PAUSE 0,1 s pro Aufruf würde das 100-ms-Ziel sprengen. Fail-Safe (Maus in Ecke → Exception) kann im Spiel zufällig auslösen und `release_all()` abbrechen; Not-Aus ist F2.
- **Entscheidung:** Warten nur über `killswitch.wait(stop, s)` (`Event.wait`, wirft `Stopped`), kein `time.sleep`.
- **Verworfen:** Polling-Flag mit `time.sleep`-Schleifen (Latenz = Schlafintervall).

## 2026-10-15 – Hold-Test sendet `keyDown` wiederholt

- **Entscheidung:** `--hold-test` sendet `keyDown` alle `hold_test.repeat_s` erneut, nach `hold_test.start_delay_s` Startverzögerung.
- **Grund:** Per `SendInput` injizierte Tasten erzeugen keine Auto-Repeat-Events. Ein einzelnes `keyDown` ergibt im Editor nur ein Zeichen; wiederholt gesendet wird der Stopp-Zeitpunkt sichtbar. Für Spiele ist ein einzelnes `keyDown` ausreichend (Taste gilt bis `keyUp` als gehalten). Startverzögerung, damit die Eingaben nicht in die Konsole gehen.

## 2026-10-15 – Aufnahme: Video in eigenem Prozess

- **Entscheidung:** Capture + Encoding laufen in einem Kindprozess (`multiprocessing`, spawn), Input-Hooks im Hauptprozess. Gemeinsame Uhr über `perf_counter`-Startwert `t0`, der an den Kindprozess übergeben wird.
- **Grund:** pynput-Low-Level-Hooks laufen synchron im Eingabepfad von Windows. Hält ein Capture-/Encoding-Thread im selben Prozess die GIL, verzögert das jede Maus-/Tastatureingabe im Spiel. `perf_counter` (QueryPerformanceCounter) ist prozessübergreifend vergleichbar. Gemessen: 19,8 fps bei 1920×1080, Startverzögerung ~0,3 s.
- **Entscheidung:** Codec `mp4v`, Zeitstempel zusätzlich in `frames.csv`.
- **Grund:** Die pip-Wheels von OpenCV schreiben H.264 nicht zuverlässig, `mp4v` funktioniert ohne Zusatz. Das Video hat nominell `fps`; die echten Zeitpunkte (inkl. verworfener Frames) stehen in `frames.csv`.
- **Verworfen:** Threads im selben Prozess (GIL-Konkurrenz mit Hook-Callbacks), ffmpeg-Subprozess (zusätzliche externe Abhängigkeit).

## 2026-10-15 – Datengrundlage: OBS-Videos statt Aufnahme-Tool

- **Entscheidung:** Daniels OBS-Videos mit Tasten-Overlay sind die Testdaten. `tools/overlay_inputs.py` liest das Overlay (Gelbanteil je Taste, Hysterese 75/65) und schreibt `inputs.jsonl` im Format von `tools/record.py`. B und G kommen aus dem Bild (Kaufmenü öffnet, G-Feld verschwindet).
- **Grund:** Videos lagen vor, Overlay ist eindeutig ablesbar (gedrückt ≥ 70, sonst ≤ 60 außerhalb von Ladebildschirmen).
- **Folge:** Detektoren dürfen die Overlay-Fläche (x 600–1500, y 0–370) nicht als Merkmal nutzen. Was dort im Spiel liegt (Kompass, Zonen-Banner, hohe Marker), ist offline nur eingeschränkt prüfbar.

## 2026-10-15 – Bilderkennung mit festen Template-Fenstern

- **Entscheidung:** HUD-Zustände per `cv2.matchTemplate` (TM_CCOEFF_NORMED, Graustufen) in kleinen festen Fenstern (`x, y, search`). Templates aus den Videos zugeschnitten (`assets/`), Schwellen aus der Verteilung über alle 1.420 Sekundenbilder (Treffer/Nicht-Treffer klar getrennt).
- **Grund:** HUD-Elemente sind bildschirmfest, Fenstersuche < 1 ms, keine neue Dependency.
- **Verworfen:** OCR-Bibliothek (Tesseract/EasyOCR: zusätzliche Installation bzw. großes Modell, langsam), Farbschwellen allein (Hintergrund wechselt stark).

## 2026-10-15 – Ziffernleser für Tempo und Höhe

- **Entscheidung:** Top-Hat-Filter (5×5) + rechtsbündige Ziffernsuche + Kosinus-Vergleich mit 10 eigenen Ziffern-Templates (`digits.png`, aus ~2.400 Glyphen der Videos geclustert). Bei unsicherer Ziffer (< 0,8) `None` statt Raten.
- **Grund:** Weiße, dünne Ziffern ohne Hintergrundfeld auf wechselndem Gelände. Top-Hat macht sie unabhängig von der Helligkeit des Hintergrunds. „1“ ist schmaler → Folgeposition wird gesucht statt fest gerastert. Ergebnis: 92–99 % lesbar, keine Fehllesungen gefunden.
- **Verworfen:** Spalten-Segmentierung (Ziffern verschmelzen durch Hintergrundrauschen), festes Raster (scheitert an „1“).

## 2026-10-15 – Navigation über Weltmarker

- **Entscheidung:** Ziel Zone = Zonen-Marker (Ring „CZ“/„HZ“), Ziel Base = HQ-Marker. Richtung = x-Abstand zur Bildmitte, Ankunft an der Base = HQ-Marker tief im Bild (`hq_approach_y`) bzw. Kauf-Hinweis (Ankunft an der Zone siehe „Zonen-Eintritt über HZ-Marker und Minimap“). Suche über das ganze Band mit Template, dessen maskierter Rand mit dem Mittelwert gefüllt ist.
- **Grund:** Zonen-Marker immer vorhanden (außerhalb des Bildes am Rand), HQ-Marker sichtbar sobald voraus. Keine absolute Position nötig. Mittelwert-Füllung erlaubt die schnelle FFT-Suche (~40/60 ms statt ~150 ms mit Maske) bei gleicher Trefferquote.
- **Verworfen:** Position über Minimap-Abgleich (braucht Kartenbilder pro Map), Kompass (in den Videos vom Overlay verdeckt, nicht validierbar; Erweiterung möglich), Suche in halber Auflösung (Marker zu klein, viele Fehltreffer), Zonen-Eintritt über Banner „CONTROL ZONE“ oder Minimap-Farbe (kurzlebig bzw. unzuverlässig).

## 2026-10-15 – Zonen-Eintritt über HZ-Marker und Minimap

- **Entscheidung:** „In der Zielzone“ = Zonen-Marker zeigt „HZ“ **und** Minimap um das Heli-Symbol ist eingefärbt (Daniels Regel). HZ/CZ über den Vergleich des Buchstabenfelds mit zwei Templates, Minimap über die Buntheit des Median-Farbtons in einem Ring.
- **Grund:** HZ/CZ ist in allen 1.940 Video-Markern eindeutig. Die Minimap allein färbt auch in der Base und in fremden Zonen (35 % der CZ-Bilder), ist zusammen mit HZ aber eine zweite, unabhängige Bestätigung. Ersetzt die frühere Ankunftsregel „Marker tief im Bild“ (`zone_arrive_y`).
- **Verworfen:** Ganzes Marker-Template für HZ (HZ hat dunklere Füllung, 319 Verwechslungen), Kreis-Erkennung per Hough auf der Minimap (Rand ist innen meist nicht sichtbar, Zone größer als die Minimap).

## 2026-10-15 – Eigener Leser für die Entfernung am Zonen-Marker

- **Entscheidung:** Glyphen-Templates (0–9 . k m) aus 53 von Hand gelesenen Video-Ausschnitten, Lesen über feste Text-Formate mit zentrierter Lage statt Segmentierung.
- **Grund:** Text ist klein (10 px), unscharf und hat wechselnden Hintergrund; Spalten-Segmentierung trennt die Zeichen nicht. Die Formate sind fest, und der Text ist genau über dem Marker zentriert, daher genügt Template-Vergleich an wenigen Positionen. Selbsttraining der Templates hat 5/6/8 vermischt, daher Training nur auf geprüften Beispielen. ~3 % Fehllesungen, deshalb nutzt der Regler nur den Median mehrerer Lesungen.
- **Verworfen:** OCR-Bibliothek (siehe oben), Bildposition des Markers als Entfernungsmaß (hängt von Höhe und Neigung ab), Format `dd km` (keine Zone > 10 km, verursachte „31 km“ statt „3.1 km“).

## 2026-10-15 – Nickwinkel nicht aus dem Bild

- **Entscheidung:** Kein Detektor für den Nickwinkel. Höhe über Meer (ASL) wird gelesen; „sinkt trotz Shift“ gilt als Zeichen für zu viel Neigung.
- **Grund:** Die Horizont-Striche der Lageanzeige zeigen nur die Querneigung, die Bögen den Kollektiv. Der echte Horizont ist durch Dunst, Berge und HUD nicht stabil messbar. Netto-W-Zeit schwankt im Reiseflug zwischen −0,2 und +3,4 s und taugt nicht als Schätzung. ASL ist 1:1 lesbar und unabhängig vom Gelände.
- **Verworfen:** Neigung aus der Lageanzeige, Horizontlinie im Bild, Integration der W/S-Zeiten.

## 2026-10-15 – Flug als Regelkreis mit Pulsen

- **Entscheidung:** `Pilot` regelt jede Achse getrennt pro Tick: Höhe als Zweipunktregler mit Hysterese und Vorhersage (Shift/Ctrl halten), Tempo über eine Soll-Beschleunigung mit kurzen W/S-Pulsen, Gieren mit Q/E-Pulsen proportional zum Marker-Abstand, Landung über Soll-Sinkrate. Pulse sind nicht blockierend.
- **Grund:** Tastatur ist binär; Daniel fliegt genauso (Shift lange gehalten, W/S/A/D kurz getippt, Median 0,22 s). Unbekanntes Flugmodell (hält der Heli die Neigung? sinkt er ohne Shift?) wird durch Messen der Änderungsrate nachgeregelt statt angenommen. Alle Parameter in `flight` und `maps`.
- **Verworfen:** Abspielen aufgenommener Tastenfolgen (bricht bei jeder Abweichung, laut Vorgabe verboten), stufenlose PID-Ausgabe (nicht mit Tasten umsetzbar).

## 2026-10-15 – Flugregler nach Daniels Flugmodell

- **Entscheidung:** Höhe nur über die Dauer von Shift (Ctrl nur beim Landen). Neigung über W/S-Pulse mit Rückmeldung aus Beschleunigung und ASL-Steigrate. Sicherheitsgrenzen: `floor` (Mindesthöhe, im Reiseflug `min_agl` 80 m) und Höchsttempo je AGL (`flight.speed_limits`). Unter der Mindesthöhe immer Shift, nie W, und S, solange noch beschleunigt wird. Sinkt der Heli trotz Shift (ASL), ist die Nase zu weit unten → S.
- **Grund:** Daniel: ohne Taste schwebt der Heli, ~20° Nase vorn + Shift hält die Höhe, W ohne Shift sinkt. Damit ist Shift der Höhenregler und „sinkt trotz Shift“ das messbare Zeichen für mehr als ~20° Neigung (Videos: 4 m/s Sinken bei 250–317 km/h mit Shift). Der Crash in Bild 02 (215 km/h bei AGL 28) wird durch Tempo-Grenze und Mindesthöhe verhindert. ASL statt AGL für die Steigrate, weil AGL über Hügeln springt.
- **Verworfen:** Ctrl im Reiseflug (Daniel: Höhe über Shift-Dauer), Neigung zählen über aufsummierte W/S-Zeit (schwankt im Video zwischen −0,2 und +3,4 s bei gleichem Tempo).

## 2026-10-15 – Layer 1 als Schrittfolge mit Prüfung pro Tick

- **Entscheidung:** `CrateLoop` führt die Schritte `buy, climb, turn, drop, leave, turn, land` prozedural aus. Jeder Tick läuft durch `observe()`, das Erste-Hilfe-Symbol, Heli-Schaden und fehlendes HUD prüft und dann `LeaveLayer` wirft. Fehlgeschlagene Schritte werfen `StepFailed` → sicherer Stopp mit Screenshot.
- **Grund:** Einfach zu lesen und einzeln testbar (`--step`), äußere Bedingungen werden trotzdem jeden Tick geprüft. `has_heli` liefert `None` bei fehlendem HUD, damit kurze Aussetzer nicht sofort stoppen; nach `unknown_state_s` greift der Watchdog.
- **Verworfen:** Tick-basierter Unterautomat pro Schritt (mehr Zustandsverwaltung für Menüfolgen ohne Mehrwert).
- **Entscheidung:** Abwurf erst unter `drop_agl` (Standard 70 m), Landung dort, wo der Kauf-Hinweis erscheint.
- **Grund:** Spieltext: Palette zerbricht ab ca. 90 m freiem Fall. Ein markierter grüner Landeplatz ist in keinem Video zu sehen; Daniel landet auf freien Flächen im Kaufbereich.
- **Entscheidung:** `timeouts.max_hold_s` (20 s) gilt für jede Taste; der Regler drückt sie im nächsten Tick neu.
- **Grund:** Vorgabe „keine Taste länger als Timeout am Stück“. Daniel hält Shift bis zu 59 s, ein kurzes Loslassen kostet nur wenige Meter.

## 2026-10-15 – Ablauf nach Daniels Navigationsregeln

- **Entscheidung:** `climb` nur bis `turn_agl` (15 m), dann nur gieren; Steigen auf Reiseflughöhe erzwingt danach die Mindesthöhe im Regler. Bremsen vor der Zone über den Median der CZ-Entfernungen (`brake_distance`). Abwurf `drop_delay_s` (3 s) nach „HZ + Minimap“ und erst unter `drop_max_agl`. Neuer Schritt `leave`: zeitgesteuert umdrehen (`turnaround_s`), geradeaus raus bis CZ bzw. Minimap ohne Färbung, erst dann HQ suchen (`turn`).
- **Grund:** Daniels Regeln aus PROJECT.md „Navigation“. HQ-Marker ist in der Zone nie sichtbar (0 von 7 Anflügen), daher erst raus. Die Drehrate von Q/E ist unbekannt, eine zeitgesteuerte Kehrtwende ist einfach einzustellen. Median, weil ~3 % der Entfernungen falsch gelesen werden.
- **Verworfen:** Kehrtwende bis der Marker am Rand klebt (dreht nur ~45°), Steigen auf volle Reiseflughöhe vor dem Drehen (Daniel: ein paar Meter reichen, kostet Zeit pro Runde).

## 2026-10-15 – Neigung zählen und nach dem Bremsen ausrichten

- **Entscheidung:** `Pilot.tilt` zählt W-Pulse minus S-Pulse (0 am Boden). Beim Bremsen auf Schweben (Ziel und Tempo ≤ `hover_speed`) tippt der Bot so lange die Gegentaste, bis der Zähler 0 ist. Unter der Mindesthöhe nimmt er die Nase nur hoch, wenn sie laut Zähler vorn ist.
- **Grund:** Die Neigung bleibt nach dem Loslassen stehen, und das HUD-Tempo hat kein Vorzeichen. Ohne Ausgleich würde der Heli nach dem Bremsen rückwärts beschleunigen, und der Regler würde wegen „zu schnell“ weiter S tippen. Daniel gleicht in den Videos genauso aus (Zestafona 172–180 s: S 1,5 s, danach W 1,8 s). Der Zähler gilt nur über kurze Zeit als verlässlich; über ganze Flüge driftet er (siehe „Nickwinkel nicht aus dem Bild“).
- **Verworfen:** Bremsen ohne Ausgleich (Rückwärts-Aufschaukeln), Richtung aus Bewegung im Bild (zu aufwendig für jetzt).

## 2026-10-15 – Strg im Abwurf- und Landeanflug, Landung tief anfliegen

- **Entscheidung:** `fly(sink=True)` erlaubt Strg, wenn der Heli über `Ziel + agl_band` ist; nur im Abwurf-Anflug und im Landeanflug. Landung: tief und langsam (`approach_agl` 30 m, `approach_speed` 60 km/h) weiter zum HQ, bis der Kauf-Hinweis erscheint, dann senkrecht runter. Nach dem Zonen-Eintritt wird nicht mehr zum HZ-Marker gegiert. Nach dem Verlassen der Zone noch `leave_margin_s` geradeaus.
- **Grund:** In der Simulation sank der Heli mit wenig Neigung ohne Strg kaum (Abwurf erst 11 s nach Eintritt), Daniel nutzt vor Abwurf und Landung selbst Strg (1–19 s). Senkrecht aus 100 m sinken landete außerhalb des Kaufbereichs. Gieren zum HZ-Marker ließ den Heli um die Zonenmitte schwenken; direkt nach dem Verlassen trieb er beim Drehen zurück in die Zone (HQ dort unsichtbar).
- **Verworfen:** Strg im Reiseflug (Daniel: Höhe über Shift-Dauer), niedrigere Reiseflughöhe (Mindesthöhe 80 m wegen Bäumen).

## 2026-10-15 – Video-Abgleich als eigener Test-Marker

- **Entscheidung:** `tests/test_replay_videos.py` mit Marker `videos`, per `addopts` im Standardlauf abgewählt; Aufruf `pytest -m videos`.
- **Grund:** Videos liegen nur lokal (1,1 GB, nicht im Repo) und der Lauf dauert einige Minuten. Marker und Minimap werden nur in jeder 5. Zeile (2 Bilder/s) gelesen, weil die Marker-Suche ~100 ms pro Bild kostet.

## 2026-10-17 – Startverzögerung und Eingaben nur ins Spielfenster

- **Entscheidung:** Countdown `loop.start_delay_s` vor jedem Lauf (ersetzt `hold_test.start_delay_s`). Eingaben nur, wenn der Vordergrund-Fenstertitel exakt `window.title` ist; sonst `release_all` und warten. Die Wartezeit wird aus der Uhr von `CrateLoop` herausgerechnet (`Input.paused_s`). Ohne Prüfung: `--dry-run`, `--hold-test` (Not-Aus-Test läuft im Editor).
- **Grund:** Test 17.10.: Der Bot startete sofort und tippte in die Konsole, Daniel wechselte per Alt+Tab (Screenshot 002840 zeigt den Fensterumschalter). Exakter Titel, weil „wardogs“ auch in anderen Titeln vorkommt (VS Code „… - wardogs_script - …“, Explorer `wardogs_daten`). ctypes ist Teil von Python, keine neue Dependency. Uhr anhalten, damit ein kurzer Blick ins Log keinen Schritt-Timeout auslöst.
- **Verworfen:** `pywin32`/`pygetwindow` (neue Dependency für zwei API-Aufrufe), Teilstring-Vergleich des Titels, Prozessname (Name der Spiel-EXE unbekannt), Fokus nur beim Start prüfen.

## 2026-10-17 – Kaufmenü: Klick mit Pause, Schließen prüfen

- **Entscheidung:** Klick = Maus hinbewegen, `buy.hover_s` warten, Taste `buy.press_s` halten. Nach CONFIRM & EXIT prüfen, ob das Menü zu ist, sonst bis `buy.confirm_attempts`-mal erneut. „LOGISTICS SLOTS FULL“ im Hauptmenü = Palette schon geladen → nur bestätigen.
- **Grund:** Test 17.10. (Screenshot 002114): Cursor stand auf CONFIRM & EXIT, das Menü blieb offen. Bewegung, Drücken und Loslassen kamen im selben Moment; das Spiel hat den Klick vermutlich nicht als Hover + Klick gesehen. Im zweiten Versuch klickte der alte Ablauf ohne offenes Logistik-Menü blind auf PALLETS und die Ammo-Palette (Gefahr, im Hauptmenü etwas anderes zu kaufen).
- **Verworfen:** Enter/Esc statt Klick (unbekannt, ob das Spiel damit bestätigt), feste längere Pausen ohne Prüfung.

## 2026-10-17 – Rundenende als sicherer Stopp

- **Entscheidung:** „NEXT ROUND IN“ (Template ohne Zeit) → `RoundOver(SafeStop)`: alle Tasten los, Screenshot, Exit 3. Geprüft in `CrateLoop.observe` vor allen anderen Prüfungen und im `UNKNOWN`-Handler.
- **Grund:** Test 17.10. (`land`, Screenshot 002840): Runde endete, Heli weg, der Bot meldete „Heli-Anzeige weg (Crash oder ausgestiegen)“ und wartete 30 s auf den Watchdog. Rundenende ist kein Crash; Rejoin gehört zu Layer 4.
- **Verworfen:** Tab-Leiste SCORE/PROGRESSION/SCOREBOARD als Merkmal (ausgewählter Tab wechselt die Farbe), weiter auf den Watchdog warten.

## 2026-10-17 – Querneigung aus der Lageanzeige, HQ-Entfernung lesen

- **Entscheidung:** `Vision.roll` liest die Querneigung aus den zwei Horizont-Strichen der Lageanzeige (Linien-Score über Winkel, Minimum beider Seiten). `hq_marker` liest die Entfernung rechts neben dem HQ-Marker mit denselben Glyphen wie die CZ-Entfernung (linksbündig).
- **Grund:** Daniel: Lenken bei Tempo braucht A/D, in der Zone „Heli gerade halten“. Ohne Messung bleibt eine A/D-Neigung stehen (Video: Neigung bleibt nach dem Loslassen, driftet ~1°/s). Abgleich mit dem Tasten-Overlay (`pytest -m videos`): Tipps ≥ 0,25 s ändern die Neigung in Tipp-Richtung (D = +), 23 von 26 isolierten Tipps ≥ 3°; ~0,3 s ≈ 5–8°, ~0,5 s ≈ 13–16°. HQ-Entfernung: Daniel beginnt den Landeanflug (erstes Strg) bei 600–800 m (Bakurani 233 s / 375 s, Zestafona 221 s). Die HQ-Schrift ist grau auf hellem Grund; im Video werden ~1/3 der km-Werte falsch gelesen (1↔8, 8↔6), daher Median über `flight.distance_history` Werte.
- **Verworfen:** Querneigung über den Mittelwert der Strich-Pixel (Rauschen bei Bäumen im Hintergrund, Konzentration < 0,4), HQ-Marker-Höhe im Bild als Entfernungsmaß (Video: y 411–427 zwischen 500 m und 1,6 km, hängt von der Nicklage ab), Nickwinkel (weiterhin nicht ablesbar).

## 2026-10-17 – Flug nach Daniels erstem Test

- **Entscheidung (Nicklage):** Höchstens `max_tilt` gezählte W-Tipps (3 ≈ 12–15°, ein Tipp geschätzt 4–5°). Darüber nur ungezählte Trimm-Tipps, wenn der Heli kaum noch beschleunigt (`trim_accel`). `cruise_speed` 200 → 180.
- **Grund:** Daniel musste im Reiseflug mit S ausgleichen (10–15° reichen). Der alte Regler tippte W, bis die Soll-Beschleunigung (bis 15 km/h/s) erreicht war, also weit über 20°. Eine harte Grenze allein bricht mit Palette: Sie zieht die Nase hoch, der Zähler bleibt bei 3, der Heli wird langsamer (Simulation: 55 statt 160 km/h, mit stärkerer Drift Rückwärtsflug). Daniels Videos zeigen genau dieses Nachtippen (Netto-W bis +3,4 s pro Strecke).
- **Entscheidung (Palette, Schweben):** Beim Schweben/Bremsen keine Tipps, solange das Tempo nicht steigt. Steigt es über `trim_speed`: gegen den Zähler tippen, mit Palette und Zähler 0 kurzer ungezählter W-Tipp. Bremsen mit S, bis mindestens `brake_accel` verzögert wird; wird der Heli mit Nase oben (Zähler < 0) wieder schneller, W.
- **Grund:** Daniel: mit Palette kippt der Heli beim Schweben nach hinten, mit etwas W ausgleichen. Das alte „Zähler sofort auf 0 tippen“ kippte bei falschem Zähler die Nase nach vorn (Simulation: Landung 400 m hinter der Base). Daniel: Strg allein reicht beim Landen nicht, mit S bremsen.
- **Entscheidung (Querneigung):** `Pilot.bank` hält die Querneigung auf 0 und neigt ab `bank_speed` proportional zur Marker-Abweichung in die Kurve (bis `max_bank`). Läuft in jedem `CrateLoop._fly`, also in allen Flugphasen.
- **Grund:** Daniel: Q/E allein reicht bei Tempo nicht (`--once`: endlose Kreise), A/D nötig; in der Zone ist der Heli schief abgesackt und in einen Baum geflogen (Screenshot 004742). Schräglage kostet Auftrieb.
- **Entscheidung (Zone):** Vor und in der Zone sinken höchstens mit `drop_sink_rate` (2 m/s, Ctrl wird gepulst statt gehalten). In der Zone kein Gieren, keine W/S-Tipps außer Sicherheitsregeln, Querneigung 0. G weiterhin erst unter `drop_max_agl`, mit Log, wenn er darauf wartet.
- **Grund:** Altes `sink=True` hielt Ctrl, bis die Zielhöhe erreicht war (zu schnelles, schiefes Sinken → Crash 1,3 s nach dem Eintritt). Probelauf 001810 (kein G in 12 s): Countdown startet nicht neu (`entered` wird nur einmal gesetzt), der Heli war mit ~96 m über `drop_max_agl`; Daniels eigener Abwurf dort ergab „SUPPLIES DESTROYED ON IMPACT“.
- **Entscheidung (Drehen, Verlassen, Landen):** `turn` sucht in Richtung der letzten Marker-Seite und ist erst fertig, wenn der Marker `confirm`-mal mittig ist und kein Gier-Puls läuft. `leave` endet sofort, wenn der Heli schon draußen ist. `land`: Anflug ab `land_distance` (700 m, Median der HQ-Entfernung), sinken mit `approach_sink_rate`, senkrecht runter, sobald die Minimap eingefärbt ist (Base unter dem Heli) und HQ ≤ `hq_overhead_distance` nah oder nicht mehr sichtbar. Unter `sink_slow_agl` erst runter, wenn langsamer als `touchdown_speed`.
- **Grund:** Screenshot 002225: CZ-Marker am linken Rand, die Suche drehte nach rechts, sobald der Marker kurz nicht erkannt wurde → Timeout. Daniel: nach G trägt der Schwung den Heli meist aus der Zone; Landefläche auf der Minimap unter dem Heli reicht; Sinkflug doppelt so früh (Video: Daniel ab 600–800 m, vorher löste erst Marker-y ≥ 560 aus).
- **Verworfen:** Neigungszähler mit fester Driftrate für die Palette (Rate unbekannt), Ctrl-Pulse nach fester Zeit, Kehrtwende immer.

## 2026-10-17 – Gedämpfter Drehregler

- **Entscheidung:** `Pilot.yaw` schätzt die Drehrate aus der Marker-Bewegung (`Trend` über `yaw_history_s`) und regelt auf den Haltepunkt `lead = Fehler + Rate × yaw_lookahead_s`: Puls Richtung `lead` (bei Überschwingen also die Gegentaste), nach jedem Puls `yaw_wait_s` warten, solange der Heli noch dreht erst ab `yaw_coast_band` eingreifen. Fertig (`turn`) erst bei mittigem, ruhigem Marker und Tempo ≤ `hover_speed`, `yaw_settle_s` am Stück. `bank` neigt nach `lead` statt nach `x`. `yaw_deadband` 40 → 80, `yaw_s_per_px` 0,0015 → 0,0006, `turn_timeout_s` 25 → 30, `turnaround_s` 4 → 6 (Suche wartet jetzt zwischen den Pulsen).
- **Grund:** Test 17.10., 2. Durchgang: `turn` 5/5 nach 25 s abgebrochen, Daniel: Q bis der Marker vorn ist, nie E zum Bremsen, Pendeln; im Flug Pendeln links-rechts. Video-Messung (Zestafona 116,9 s, Q 0,33 s): Totzeit ~0,3 s, Marker läuft ~1,5 s nach, gesamt 216 px; Modell Totzeit 0,3 s + Anlauf 0,2 s + Auslauf 0,5 s, 40°/s passt auf ±2 px. Der alte Regler tippte alle 0,4 s nach, bevor die Wirkung sichtbar war. Simulation mit diesem Modell: alter Regler bricht in 7 von 11 Dreh-Tests nach dem Timeout ab (wie im Spiel), in 2 weiteren meldet er fertig, obwohl der Heli noch mit 33°/s dreht; neuer Regler fertig in ≤ 12 s ohne Überschwingen; Totzone 80 px, weil ein Puls von einem Tick (0,05–0,2 s) schon 50–150 px dreht. Robust in 322 von 324 Kombinationen aus Totzeit 0,15–0,45 s, Auslauf 0,3–0,8 s, 30–55°/s und Bildtakt 0,05/0,15 s.
- **Verworfen:** feste Bremspulse nach jedem Puls (hängt von der unbekannten Drehrate ab), blockierende kurze Tipps für feinere Pulse (stoppen die übrigen Regler, in der Simulation nicht abbildbar), kleinere Totzone (Grenzzyklen bei 0,15 s Bildtakt).

## 2026-10-17 – Bremsrichtung aus der Reaktion

- **Entscheidung:** Beim Bremsen (`_pitch_for`, Ziel ≤ `hover_speed`) merkt sich der Regler die Beschleunigung beim letzten Brems-Tipp. Wird der Heli danach noch schneller (über `reverse_accel`), fliegt er rückwärts: `reverse` umschalten, mit W statt S bremsen. Zurückgesetzt, sobald Tempo ≤ `trim_speed`.
- **Grund:** Simulation der neuen Landung: Nach dem Abbremsen driftete der Heli rückwärts, der Zähler `tilt` stand auf 0 (tatsächlich Nase ~4° oben), der Regler tippte S und beschleunigte rückwärts bis 155 km/h und in den Boden. Das HUD-Tempo hat kein Vorzeichen. Die alte Regel (W nur bei `tilt < 0` und Beschleunigung > `accel_band`) griff bei falschem Zähler und langsamer Beschleunigung (4 km/h/s) nicht. Eine Entscheidung allein nach `tilt` schlug in beide Richtungen fehl (W/S im Wechsel).
- **Verworfen:** Richtung nur aus `tilt` (driftet), Rückwärtsflug über die Marker-Bewegung erkennen (Marker beim Schweben oft nicht im Bild).

## 2026-10-17 – Zone über HZ oder Minimap, keine Höchsthöhe

- **Entscheidung:** Zone erreicht = Marker zeigt HZ **oder** Minimap eingefärbt, je `vision.confirm` Bilder. Die Minimap zählt erst ab dem Bremspunkt (Median CZ-Entfernung ≤ `brake_distance`), weil Base und andere Zonen auch eingefärbt sind (Start in der Base: Minimap blau). G nach `drop_delay_s`, sobald AGL ≥ `drop_min_agl` (30 m); `drop_max_agl` entfällt. `tools/replay.zone_visits` nach derselben Regel.
- **Grund:** Daniel (Test 17.10., 2. Durchgang): Kreis weiß, Erkennung 25 s zu spät, Bot flog durch die Zone und warf am anderen Rand ab; danach noch `Warte auf Abwurfhöhe: AGL 118 m, Grenze 85 m`. Daniels Regel (PROJECT.md): eines von beiden reicht, keine Obergrenze. Weißer Kreis über Helligkeit nicht von hellem Gelände trennbar (Messwerte in `docs/ANALYSIS.md`). Videos: alle 7 Abwürfe weiter in erkannten Besuchen, Zestafona 4,5 s früher.
- **Risiko:** Laut Spieltext zerbricht die Palette ab ca. 90 m freiem Fall; Test 1 (96 m, 225 km/h) ergab „SUPPLIES DESTROYED ON IMPACT“. Der Bot sinkt vor und in der Zone weiter sanft auf `drop_agl` (70 m). Zeigt der Test zerbrochene Paletten, braucht es wieder eine Grenze.
- **Verworfen:** Weißen Kreis über Ring-Helligkeit, Kontrast oder Sättigung erkennen; Minimap ohne Bremspunkt-Bedingung (Abwurf in der Base).

## 2026-10-17 – Landeanflug mit Rückweg

- **Entscheidung:** `land` als Phasen `cruise`/`approach`/`descend`/`turn`. Überflug (HQ-Entfernung > kleinste + `hq_overshoot_m`, oder HQ weg ohne Base auf der Minimap) → anhalten, mit `_align` zum HQ drehen, neu anfliegen. HQ im Reiseflug weg → anhalten und suchen. Im Sinkflug weder Kauf-Hinweis noch Minimap-Färbung → steigen, umdrehen. `Pilot.descend` sinkt erst unter `descend_speed` (30 km/h) statt unter `speed_limit(agl)`. Frist `land_timeout_s` (120 s) ab Anflugbeginn. `_align` (auch `turn`) ist erst fertig, wenn der Heli langsamer als `hover_speed` ist.
- **Grund:** Daniel (Test 17.10., 2. Durchgang): einmal ins Nirgendwo geflogen (Marker nicht gefunden, Reiseflug geradeaus), beim Anflug über die Base hinaus, dann Landeversuch im Nichts ohne Ende. Log: Sinkflug 8 s nach Anflugbeginn bei 695 m, also mit hohem Tempo über der Base-Färbung; `descend` sank bei 40 m schon unter 100 km/h. Nach einer Kehrtwende fliegt der Heli mit altem Schwung rückwärts weiter, daher erst anhalten, dann neu anfliegen (Simulation: sonst „Base überflogen“ in Serie).
- **Offen:** Der HQ-Marker verschwindet in den Videos oft schon 800 m vor der Base; die Landefläche liegt nahe dem HQ-Symbol auf der Minimap (Zestafona 495 s: ~45 px nördlich). Landet der Bot in der Base, aber neben der Fläche, stoppt er sicher (`Gelandet, aber kein Kauf-Hinweis`). Nächster Schritt wäre Navigation über das HQ-Symbol der Minimap.
- **Verworfen:** Sinken nur mit Kauf-Hinweis (erscheint in Bakurani/Ozeti erst unter ~11 m), Landung abbrechen erst nach dem Aufsetzen.

## 2026-10-17 – Abheben 25 m, Reiseflug-Neigung 4 Tipps

- **Entscheidung:** `maps.default.turn_agl` 15 → 25, `flight.max_tilt` 3 → 4.
- **Grund:** Daniel (Test 17.10., 2. Durchgang): beim Drehen nach dem Abheben fast gegen eine Stromleitung (Screenshot 014529: Mast neben dem Heli), Reiseflug-Neigung ca. 3° zu wenig.

## 2026-10-17 – Drehen in zwei Modi, Fluglage hat Vorrang

- **Entscheidung (Drehen):** Über `curve_min_speed` (30 km/h) dreht der Bot im Kurvenflug: A/D in die Kurve (bis `turn_bank` 20°) plus Q/E, Tempo-Soll `turn_speed` (60 km/h, sanft bremsen), Höhe mit Shift, Mindesthöhe `min(min_agl, Ziel − agl_band)`. Darunter auf der Stelle wie bisher. Gleiches Umdrehen in `leave`. `turn_timeout_s` 30 → 45 (Kurve über 300° dauert bis ~40 s).
- **Grund:** Test 17.10., 3. Durchgang: `turn` nach `leave` bei ~150 km/h 3× Timeout, 2× Crash; Screenshots 031444/031533: Heli stark nach hinten gekippt, 031555: in Bäumen bei AGL 6. Daniel: Q/E reicht mit Fahrt nicht, A/D nutzen, nicht erst mit S stark bremsen. Simulation mit Schwung: Drehen nur der Nase lässt den Heli seitlich/rückwärts weiterrutschen, das Bremsen mit S beschleunigt dann rückwärts.
- **Entscheidung (Fluglage):** Rücklage-Grenze für S (höchstens `max_back_tilt` Tipps hinter die Mitte, höchstens `back_taps` solche Tipps in `back_window_s`); S-Regeln „zu schnell“ und „sinkt trotz Shift“ nur mit Nase vorne; sinkt er langsam trotz Shift und Nase nicht vorne → W. `recovering` (unter Mindesthöhe oder unter `safe_agl` mit über `safe_speed`): nur Shift, Lage gerade, kein Gieren. Echte Tippdauer in `tilt` nachrechnen. Rückwärts-Erkennung nur bis `reverse_max_speed`, nach zweimal Umschalten nur Nase gerade. A/D-Neigung zum Ziel auch langsam (Grenze ∝ Tempo).
- **Grund:** Die alte Regel „sinkt trotz Shift → Nase zu tief → S“ galt auch mit Nase oben: S verstärkte die Rücklage, der Heli sank weiter, wieder S (Spirale). Mit Nase oben fliegt der Heli rückwärts, das HUD zeigt Tempo ohne Vorzeichen, „zu schnell für die Höhe → S“ machte ihn rückwärts schneller (Simulation: −38° Nicklage, 160 km/h rückwärts). Pulse dauern durch den Bildtakt länger als 0,2 s, der Zähler unterschätzte die Neigung um bis zu 50 %. Langsam ohne A/D driftet der Heli durch Rest-Schräglage seitlich und kreist um die Base.
- **Entscheidung (Simulation):** Geschwindigkeit als Vektor mit Windfahne, Seitenkraft, translational lift; Nicklage bis −40°. Neue Tests stellen die Crash-Fälle nach (Kurve nach `leave` in vier Richtungen, Schweben mit Palette, Rücklage-Grenze). Alter Regler in der neuen Simulation: 5 von 9 dieser Tests scheitern (2× Drehen-Timeout, −17,5° Rücklage, `leave` dreht nur 17°, volle Runde zu tief und zu schnell).
- **Entscheidung (Reiseflug):** `cruise_speed` 180 → 240, `max_tilt` 4 → 5, Landeanflug ab `land_distance` 1200 m (vorher 700) mit Tempo-Soll ∝ Entfernung (`approach_speed_per_m` 0,15 km/h pro m, mindestens `approach_speed`), weil die Rücklage-Grenze härteres Bremsen verbietet.
- **Grenzen:** Ursache des Crashs im `--once`-Lauf (031630, Drehen direkt nach dem Abheben mit Palette) nicht sicher geklärt, es gibt keinen Screenshot und das Log hatte keine Flugdaten. Wahrscheinlich dieselbe Spirale (Palette zieht die Nase hoch → sinkt trotz Shift → S). In der Simulation landet der Bot in 21 von 27 Varianten (Bildtakt 0,05–0,15 s, Drehdynamik, Windfahne); die Fehlschläge liegen alle in der Landung (seitliches Abdriften, Landung neben der Fläche → sicherer Stopp).
- **Verworfen:** Erst auf Schwebeflug abbremsen, dann drehen (Daniel: nicht; Simulation: Rückwärtsrutschen); feste Kurvengeschwindigkeit 140 km/h (Kurve zu weit, Höhenverlust bis zur Mindesthöhe); Rücklage nur über den Tipp-Zähler (driftet mit Palette und Tippdauer); engere Roll-Toleranz beim Schweben und Erholung mit Hysterese (in der Simulation schlechter).

## 2026-10-17 – Base auf der Minimap mit eigener Schwelle

- **Entscheidung:** `Vision.minimap_over_base` mit `minimap.base_chroma` 10 für `land` (Sinkflug starten und abbrechen); `minimap_in_zone` bleibt bei 14 für Zone und `leave`.
- **Grund:** Regen-Screenshot 031755: Base-Färbung Buntheit 12; Ozeti-Video nach der Landung 11–13 bei klarem Wetter. In `land` ist die Minimap nur nahe der Base gefragt (Entfernung ≤ `hq_overhead_distance` oder HQ weg), Fehlalarme kosten dort wenig. In `drop` würde eine niedrige Schwelle bis zu ~300 m vor der Zone abwerfen (Videos: 10–13 auch kurz vor Zonen).
- **Verworfen:** gemeinsame Schwelle 10 oder 12, Blau-Anteil (B − R) statt Buntheit (die Tönung ist immer bläulich, keine bessere Trennung).

## 2026-10-17 – Fluglage aus Messwerten statt Tipp-Zählen

- **Entscheidung:** Kein Neigungszähler mehr. `Pilot` leitet alles aus Messwerten ab: Tempo über Grund `ground` (HUD-Tempo ohne Steiggeschwindigkeit), Steigrate, Beschleunigung (Ausgleichsgerade über `history_s`). Bremsen/Schub als `_tap(brake)`, die Taste hängt von der vermuteten Flugrichtung `reverse` ab, die aus der Wirkung der Tipps und dem Durchgang durch Tempo 0 gelernt wird. Rücklage-Grenze nach Wirkung (`lean_accel`, `window_taps`). Sicherheit erkennt Sturzflug (AGL fällt, Tempo steigt) und bremst dann dosiert, richtet die Flügel aus und gibt Shift. Beim Steigen/Sinken über `vertical_limit` keine W/S-Tipps.
- **Grund:** Test 17.10., 4. Durchgang: 3 Crashes beim Drehen, Log jeweils „Neigung −2,4 Tipps“, während das Tempo auf 230–278 km/h stieg und AGL auf 4–10 m fiel; die Rücklage-Grenze blockierte S, weil der Zähler die Nase hinten glaubte. Nach dem Abheben zeigte das HUD 33 km/h bei reinem Steigen (AGL 12→22 m pro Sekunde) → `turn` schaltete sofort in den Kurvenflug. Schräglagen bis 45–56° mit Q/E bei Fahrt → Nase fällt (Sturzflug ohne W).
- **Entscheidung (Drehen):** Modus nach Tempo über Grund mit Hysterese (`curve_min_speed` 40 / `curve_exit_speed` 20), kein Wechsel bei unlesbarem Tempo. Auf der Stelle nur Q/E, bei mehr als `turn_hover_speed` erst bremsen ohne zu gieren (Drehen beim Bremsen dreht die Bremsrichtung mit). Kurvenflug mindestens auf `safe_agl + agl_band`, gemessene Schräglage über `roll_limit` → sofort Gegenpuls, kein Q/E in steiler Schräglage. Seite des Ziels bleibt, bis der Marker im mittleren Bildbereich ist (`side_band`). Abheben ohne W/S.
- **Entscheidung (Simulation):** Kalibriert an den Logs (Shift ~9 m/s, HUD-Tempo mit Steigrate, Seitenruder-Kopplung in Schräglage, Baum-Crash unter 10 m über 60 km/h). Die 3 Crash-Abläufe sind als Tests nachgestellt (Drehen direkt nach dem Abheben mit Restschwung nach oben, Drehen schwebend mit Palette, Kurve mit Fahrt). Der vorige Regler scheitert in der kalibrierten Simulation an 8 von 11 dieser Tests (Zeitlimit, 100 km/h direkt nach dem Abheben, 295 km/h in der Kurve), der neue an keinem.
- **Geprüft, nicht umgesetzt:** Längsneigung direkt aus dem Bild. Die Lageanzeige zeigt nur die Querneigung (siehe `docs/ANALYSIS.md`). Am Heli selbst ist die Neigung sichtbar (Videos: bei 280 km/h klein und flach, beim Bremsen groß mit Heck nach unten), aber Hintergrund, Regen und Kamera machen ein Auslesen aufwendig.
- **Grenzen:** Landung in der kalibrierten Simulation nicht zuverlässig (2 Tests als `xfail`: Überflug-Szenario, volle Runde). Nahe Tempo 0 ist die Flugrichtung aus dem vorzeichenlosen Tempo schwer zu erkennen; der Heli pendelt vor/zurück oder setzt neben der Fläche auf. Kandidat für später: Bewegungsrichtung aus dem Verschieben der Minimap (Karte ist nordausgerichtet, Heli-Symbol dreht mit).
- **Verworfen:** Tipp-Zähler mit Korrekturen (driftet, war Ursache der Crashes), Richtung allein aus „Tempo steigt = Nase unten“ (falsch im Rückwärtsflug), Lernen bei jeder einzelnen Abweichung (Lag des Trends → Hin-und-her).

## 2026-10-17 – Eindeutige Regeln für Flugrichtung und Sturzflug

- **Entscheidung:** Über `forward_speed` (60 km/h) gilt der Heli immer als vorwärts; Richtungs-Lernen aus Tipps nur unter `learn_speed` (40 km/h). Schub ist immer W, nur die Bremstaste hängt von `reverse` ab. Mit Ziel-Tempo (Reiseflug) startet der Heli im Stand immer vorwärts. Sturzflug (`diving`, höchste Priorität): über `forward_speed` und Sinkrate < −`dive_sink` (5 m/s) oder AGL fällt schneller als `dive_agl_rate` bei steigendem Tempo → Shift, Flügel gerade, nur S-Tipps proportional zur Sinkrate (`dive_tap_s_per_ms`, höchstens `dive_tap_max_s`), nie W, bis die Sinkrate unter `dive_exit` (1 m/s) liegt. Ein W/S-Tipp pro `pitch_interval_s` (0,7 → 1,0 s = `history_s`, Wirkung abwarten). Palette + Schweben: wird der Heli ohne eigenen W/S-Tipp schneller (`drift_accel`), gilt das als Rückwärtsdrift → kurze W-Tipps, auch beim Drehen auf der Stelle (`_align` gibt mit Palette Tempo-Soll 0). Bei Drift auf der Stelle Querneigung mit `roll_band` statt `hover_roll_band` ausgleichen.
- **Grund:** Test 17.10., 5. Durchgang. `drop` aus dem Schweben mit Palette tat 12 s nichts: `reverse` war im Stand = Palette, und mit `reverse` lief `_pitch_for` im Brems-Modus. Nach Daniels manuellem W blieb `reverse` stehen, die Sicherheit „bremste“ im Sturzflug mit W (−22 bis −31 m/s, 249 km/h, Crash). `--once`: beim Drehen auf der Stelle mit Palette stieg das Tempo ohne Taste von 2 auf 40 km/h → Kurvenflug → 256 km/h, W/S im Wechsel (Richtung falsch gelernt). Flugdaten dazu: Schräglage blieb während der Drift bei −7 bis −8° (unter `hover_roll_band` 8, kein A/D); g·tan(8°) ≈ 5 km/h/s passt zur gemessenen Beschleunigung von 4–9 km/h/s. Die Drift war also vermutlich (auch) seitlich durch Rest-Schräglage. Im `drop`-Schweben mit 0° Schräglage blieb der Heli mit Palette 12 s bei 1 km/h.
- **Tests:** Entscheidungs-Tests mit den echten Flugdaten (`tests/fixtures/flight/`, `tests/test_flight_replay.py`): jede CSV-Zeile als Zustand an `Pilot.fly`, in keiner Zeile mit Sinkrate < −5 m/s über 60 km/h W, im Sturzflug S; in den Schwebe-Zeilen mit steigendem Tempo ohne W ist der erste Nick-Tipp W. Simulation: Palette erzeugt Rückwärtsdrift (`World.crate_drift`), `drop` aus ruhigem Schweben, `drop` nach einem manuellen W-Ruck (`World.nudges`, `World.dive_w` zählt W im Sturzflug), Drehen auf der Stelle mit ±8° Rest-Schräglage. Alter Regler: scheitert an 5 der 7 neuen Tests (`drop` erreicht die Zone nie, 24 Takte W im Sturzflug, 60–66 km/h beim Drehen auf der Stelle, W im Sturzflug in der Turn-Crash-CSV).
- **Grenzen:** `test_land_brakes_descends_and_checks_prompt` jetzt auch `xfail` (setzt in der Simulation ~10 m neben der Fläche auf, kein Crash). Die Landung reagiert in der Simulation chaotisch auf kleine Änderungen nahe Tempo 0 (verrauschtes `ground` beim Sinken mit Strg/Shift-Wechsel).
- **Verworfen:** Gegentipp vor dem Stillstand (`ground + accel × Vorschau < 0`) und Nulldurchgang über Tiefpunkt + Anstieg: im verrauschten Sinkflug falsche Umschaltungen, Landungen in der Simulation schlechter. Richtung zurücksetzen bei verrauschtem `ground` ≤ `trim_speed` statt HUD-Tempo (löschte das Gelernte bei jedem Ausreißer).

## 2026-10-17 – Drehen = Ziel ins Bild holen

- **Entscheidung:** `turn` endet, sobald der Marker in zwei Messungen hintereinander im Bild ist (nicht am Rand, `edge_margin`) und sich dazwischen langsamer als `turn_done_px_s` (200 px/s) bewegt. Kein Zentrieren, kein `yaw_settle_s`, `Pilot.on_target` entfällt. Rückflug-`turn` startet in der Drehrichtung von `leave` (`_turn_side`); gesehene Marker setzen die Seite (= sofort gegensteuern, wenn er aus der Mitte läuft), Randmarker nur, solange keine Seite feststeht. Kurvenflug nur ab `curve_min_agl` (60 m, Hysterese `agl_band`) und nie im Hinflug-`turn` (nach `climb` über der Base).
- **Grund:** Test 17.10., 6. Durchgang. Daniel: „turn soll nur markieren, wo das Ziel ist; sobald es zwischen 0 und 1920 ist und sich pro Ausgabe um weniger als 200 px ändert, weiter“. Der Rückflug-`turn` lief 4× in den Timeout: nach `leave` mit Q drehte er mit E (Randmarker rechts) fast eine ganze Runde, bei 200 km/h mit 20° Schräglage (rechnerisch ~50 s für 180°). Im Hinflug war der Marker schon bei x = 882 im Bild (bot_063518), der Bot wartete auf Stillstand, driftete auf 37 km/h, wechselte in 32 m in den Kurvenflug und crashte (ebenso bot_063420 kurz nach dem Start).
- **Beibehalten:** über `turn_hover_speed` auf der Stelle erst bremsen, ohne zu gieren. In der Simulation flog der Heli sonst nach einer Drehung auf der Stelle mit Restfahrt rückwärts weiter, der Bot bremste mit S in die falsche Richtung und stürzte ab.
- **Tests:** Entscheidungs-Tests mit den Flugdaten vom 6. Durchgang (`turn_climb_063523.csv`, `turn_climb_063300.csv`, `turn_back_062829.csv`): Hinflug-`turn` endet bei 063523 in den ersten Zeilen (Marker 777–882 im Bild, vor der Drift), nie Kurvenflug nach dem Abheben, unter 50 m nie Kurvenflug, Rückflug mit Seite Q drückt zuerst und überwiegend Q (im Spiel: E). Simulation: Gegensteuern bei Marker im Bild mit Drehschwung.
- **Verworfen:** Bewegung pro Bild statt pro Sekunde (bei ~4–20 Bildern/s wäre fast jede Drehung „ruhig“), Drehrichtung immer zum näheren Rand (Spiel heftet den Marker nicht verlässlich an den kürzeren Weg).

## 2026-10-17 – Sanfter bremsen: Sturzflug nur bei echter Tempo-Zunahme

- **Entscheidung:** Neuer geglätteter Trend `Pilot.trend` (Steigung von `ground` über `smooth_s` 2 s). Sturzflug nur noch bei `climb` < −`dive_sink` **und** `trend` > `dive_accel`; die Regel „AGL fällt“ (`dive_agl_rate`) entfällt. Bremsen im Tempo-Regler höchstens `brake_max` (8 km/h/s) statt `accel_max` (15), dafür Bremspunkt `brake_distance` 400 → 700 m. Durchgang durch Tempo 0 wird auch ohne eigenen Bremstipp erkannt (Heli rollt mit Restneigung durch 0, kein W/S-Tipp seit `tap_window_s`).
- **Grund:** Daniel, 6. Durchgang: „Bremsen ist zu aggressiv; solange sich das Tempo über Grund nicht ändert, sind Steigung und Beschleunigung egal.“ In den Flugdaten (062212, 062829) sank der Heli im Anflug mit Strg auf −5 bis −8 m/s, das galt als Sturzflug und löste S-Pulse bis 0,4 s alle 0,5 s aus (−15 km/h/s). In 061244 meldete fallendes Gelände im Reiseflug 22-mal Sturzflug. Nachgerechnet auf denselben Daten: 6–8 statt 12 S-Tipps im Anflug, 0 statt 12–46 Sturzflug-Zeilen; die Crash-Daten vom 5. Durchgang (−22 m/s bei steigendem Tempo) bleiben Sturzflug.
- **Nicht übernommen:** den geglätteten Trend auch im Tempo-Regler (`_pitch_for`). In der Simulation reagierte der Regler dann zu spät, rollte nahe Tempo 0 durch und flog rückwärts weiter (Landetest mit Absturz).
- **Grenze:** Ohne Vorzeichen am Tempo bleibt die Flugrichtung nahe 0 km/h geraten. Kandidat: Bewegungsrichtung aus der Minimap.

## 2026-10-17 – Raketenwarnung per WASAPI-Loopback (soundcard) und Ton-Detektor

- **Entscheidung:** Systemaudio wird mit `soundcard` (WASAPI-Loopback des Standard-Ausgabegeräts) in einem eigenen Thread (`FlareWatcher`) mitgehört. `MissileWarning` erkennt den Dauerton bei ~1697 Hz an seinem Energieanteil im schmalen Band (±30 Hz) relativ zu 300–4000 Hz pro 40-ms-Frame. Alarm nach ≥ 0,66 s Ton, Aussetzer bis 0,2 s werden toleriert, danach 3 s Sperrzeit. V nur, wenn das Spiel im Vordergrund ist. Für Tests dekodiert `av` (PyAV, nur dev) die Aufnahmen.
- **Grund:** Nur lesender Zugriff auf die Audioausgabe, kein Eingriff ins Spiel. Daniels Beispiel-„mp3“ ist ein MP4 mit AAC-Ton (9 s): 2,93–4,27 s langsames Lock-Piepen bei ~1610 Hz (0,12 s an/aus), 4,33–6,86 s Dauerton 1695–1703 Hz = „konstantes bipppp“. Dieselben Töne in allen drei Videos (Bakurani 299,7 s, Ozeti 214,8/220,5/226,6 s, Zestafona 305,96/316,5 s). Ein Frequenzverhältnis ist unabhängig von der Lautstärke und robust gegen Rotor (tieffrequent) und breitbandige Explosionen. Abgleich mit ca. 24 min Gameplay: kein Fehlalarm, alle Dauertöne erkannt, auch mit 3-fach lautem Gameplay überlagert. `soundcard` ist reines Python über cffi und liefert bei Stille Nullen statt zu blockieren (Stop-Event wird regelmäßig geprüft).
- **Verworfen:** `PyAudioWPatch` (PortAudio-Fork mit C-Extension, umständlichere Loopback-Auswahl), `sounddevice` (kein Loopback), `miniaudio`/`soundfile` für Tests (kein AAC/MP4), Erkennung über Lautstärke oder Pulsmuster (lautstärkeabhängig, Verwechslung mit Lock-Piepen), ffmpeg per subprocess (externe Installation).
- **Grenze:** Live-Loopback während des Spiels nicht getestet. Spielt das Spiel nicht über das Windows-Standardgerät, hört der Bot nichts.

## 2026-10-17 – Landung über die Minimap, Umdrehen nach Minimap-Kurs

- **Entscheidung:** `land` bekommt die Phase `base`: Ist der HQ-Marker weg und das HQ-Symbol auf der Minimap, fliegt der Bot nach Peilung auf der Minimap (Ziel relativ zum eigenen Heli-Symbol, Kurs aus `minimap_heading`, Fehler als virtuelles Marker-`x` an `Pilot.yaw`). Ziel ist der nächste Heli, der relativ zum HQ ≥ `pad_still_s` stillsteht (`Pads`), sonst das HQ (dort `pad_wait_s` warten). Vorwärts/rückwärts nahe Tempo 0 wird über die Bewegung des HQ-Symbols gegen die Nasenrichtung gemessen (`Pilot.backward`). Überflug erst nach `vision.confirm` neuen Entfernungswerten über `nearest + hq_overshoot_m`; HQ-Marker weg ohne Minimap-HQ heißt „suchen“, nicht „überflogen“. `leave` dreht, bis die aufsummierte Kursänderung laut Minimap `leave_turn_deg` (170°) erreicht, höchstens `turnaround_s` (14 s).
- **Grund:** Daniel, 6. Durchgang: „Sobald man in den blauen eckigen Bereich bei HQ kommt, verschwindet das HQ-Symbol, und der Bot ist verwirrt; dafür erscheint das HQ-Symbol auf der Minimap. Andere Helis, die stationär auf der Minimap sind, zeigen die Landezone.“ bot_061822: `Base überflogen (HQ 1000 m, vorher 1000 m)`, ausgelöst durch „HQ-Marker weg und Minimap nicht eingefärbt“. `leave` drehte in 6 s nur 90–130°. In der Simulation flog der Heli nahe Tempo 0 nach einer Drehung rückwärts, der Bot bremste mit S in die falsche Richtung (2 Abstürze in Landetests); mit `Pilot.backward` landet die Simulation jetzt auch im bisher als unzuverlässig markierten Landetest.
- **Annahmen (im Spiel prüfen):** Maßstab der Minimap unbekannt; `base_speed_per_px` und `pad_radius_px` sind geschätzt (Simulation mit 0,5 px/m). Das eigene Symbol liegt bis ~22 px neben der Mitte, deshalb alle Versätze relativ zu `minimap_position`.
- **Verworfen:** Kompass oben im HUD (in den Videos vom Overlay verdeckt, nicht prüfbar), feste Zeit fürs Umdrehen (6 s = 90–130°, je nach Tempo), Base-Zentrum statt stehender Helis (Landefläche liegt je Map anders als das HQ), Überflug-Prüfung über einen einzelnen Entfernungswert.

