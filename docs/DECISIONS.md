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

- **Entscheidung:** Ziel Zone = Zonen-Marker (Ring „CZ“/„HZ“), Ziel Base = HQ-Marker. Richtung = x-Abstand zur Bildmitte, Ankunft = Marker tief im Bild (`zone_arrive_y`, `hq_approach_y`) bzw. Kauf-Hinweis. Suche über das ganze Band mit Template, dessen maskierter Rand mit dem Mittelwert gefüllt ist.
- **Grund:** Zonen-Marker immer vorhanden (außerhalb des Bildes am Rand), HQ-Marker sichtbar sobald voraus. Keine absolute Position nötig. Mittelwert-Füllung erlaubt die schnelle FFT-Suche (~40/60 ms statt ~150 ms mit Maske) bei gleicher Trefferquote.
- **Verworfen:** Position über Minimap-Abgleich (braucht Kartenbilder pro Map), Kompass (in den Videos vom Overlay verdeckt, nicht validierbar; Erweiterung möglich), Suche in halber Auflösung (Marker zu klein, viele Fehltreffer), Zonen-Eintritt über Banner „CONTROL ZONE“ oder Minimap-Farbe (kurzlebig bzw. unzuverlässig).

## 2026-10-15 – Flug als Regelkreis mit Pulsen

- **Entscheidung:** `Pilot` regelt jede Achse getrennt pro Tick: Höhe als Zweipunktregler mit Hysterese und Vorhersage (Shift/Ctrl halten), Tempo über eine Soll-Beschleunigung mit kurzen W/S-Pulsen, Gieren mit Q/E-Pulsen proportional zum Marker-Abstand, Landung über Soll-Sinkrate. Pulse sind nicht blockierend.
- **Grund:** Tastatur ist binär; Daniel fliegt genauso (Shift lange gehalten, W/S/A/D kurz getippt, Median 0,22 s). Unbekanntes Flugmodell (hält der Heli die Neigung? sinkt er ohne Shift?) wird durch Messen der Änderungsrate nachgeregelt statt angenommen. Alle Parameter in `flight` und `maps`.
- **Verworfen:** Abspielen aufgenommener Tastenfolgen (bricht bei jeder Abweichung, laut Vorgabe verboten), stufenlose PID-Ausgabe (nicht mit Tasten umsetzbar).
