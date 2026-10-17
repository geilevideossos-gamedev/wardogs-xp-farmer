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
