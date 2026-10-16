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
