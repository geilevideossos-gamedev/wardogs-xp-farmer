# Manuelle Tests

Checkliste für Tests auf deinem Rechner. Alle Befehle in PowerShell im Projektordner. Hake ab, was klappt, und melde im Planungschat, was nicht klappt (am besten mit der Log-Datei aus `logs/<Datum>/`).

## Layer 0 – Fundament

### 1. Not-Aus im Editor (ohne Spiel)

1. Editor (Notepad) öffnen
2. `.venv\Scripts\python -m heli_farmer.main --hold-test`
3. Innerhalb von 5 Sekunden in den Editor klicken
4. **Erwartet:** Im Editor erscheinen laufend `wwwwww…`
5. F2 drücken
6. **Erwartet:** Die `w` hören sofort auf. Im Konsolenfenster steht `Stopp (f2 gedrückt): alle Eingaben losgelassen nach X ms` mit X deutlich unter 100, danach `Beendet durch Stopp`

### 2. Not-Aus während der Wartezeit

1. `.venv\Scripts\python -m heli_farmer.main --hold-test`
2. Sofort (innerhalb der 5 Sekunden) F2 drücken
3. **Erwartet:** Programm beendet sich sofort, es wird kein `w` geschrieben

### 3. Not-Aus im Spiel

1. WARDOGS starten, auf einen Server gehen, zu Fuß irgendwo stehen
2. `.venv\Scripts\python -m heli_farmer.main --hold-test`
3. Innerhalb von 5 Sekunden ins Spiel wechseln
4. **Erwartet:** Die Figur läuft nach vorne (W gehalten)
5. F2 drücken
6. **Erwartet:** Die Figur bleibt sofort stehen, keine Taste hängt

Wenn die Figur nicht läuft: melden. Dann ignoriert das Spiel die simulierten Tasten, und wir müssen die Eingabe anpassen.

### 4. Probelauf und Sicherheits-Stopp

1. `.venv\Scripts\python -m heli_farmer.main --dry-run`
2. 30 Sekunden warten, nichts drücken
3. **Erwartet:** Log zeigt `Layer None -> UNKNOWN`, nach etwa 30 Sekunden `Stopp (unbekannter Zustand …)` und `Debug-Screenshot gespeichert`
4. Im Ordner `logs/<Datum>/screenshots/` liegt ein Screenshot. **Prüfen:** Er zeigt genau das Spielbild (1920×1080), nicht schwarz und nicht abgeschnitten. Wenn nicht: `game_region` in `config.local.yaml` anpassen (siehe README)

### 5. Aufnahme-Tool

1. `.venv\Scripts\python -m tools.record --map test --seq drop`
2. Ins Spiel wechseln, **F9** drücken, ca. 20 Sekunden herumlaufen, ein paar Tasten und Maustasten drücken, **F9** drücken
3. **F2** drücken, das Tool beendet sich
4. **Erwartet:** Ordner `recordings/test/drop_<datum>_<uhrzeit>/` mit `video.mp4`, `frames.csv`, `inputs.jsonl`, `meta.json`
5. `video.mp4` öffnen: zeigt das Spielbild, flüssig, nicht schwarz
6. **Prüfen:** Das Spiel lief während der Aufnahme nicht spürbar langsamer und die Maus hat nicht geruckelt

### 6. Analyse-Tools

1. `.venv\Scripts\python -m tools.extract_frames wardogs_daten\Video\join+Bakurani.mp4 --every 30`
2. **Erwartet:** Meldung `N Bilder gespeichert in debug\frames\…`, die PNGs zeigen das Spielbild
3. `.venv\Scripts\python -m tools.replay wardogs_daten\Video\join+Bakurani.mp4`
4. **Erwartet:** nach 1–2 Minuten eine Liste mit Abschnitten wie `BUY_MENU`, `TO_ZONE`, `TO_BASE`, `LANDED_BASE` und die Zeile `Abwürfe bei: 173.8s, 316.5s`
5. `.venv\Scripts\python -m tools.overlay_inputs wardogs_daten\Video\join+Bakurani.mp4`
6. **Erwartet:** Datei `wardogs_daten\Video\join+Bakurani.inputs.jsonl` mit Zeilen wie `{"t": 102.1, "type": "key", "key": "b", "action": "down"}`

## Layer 1 – Crate-Schleife

Erst die Erkennung ohne Tastendrücke, dann die einzelnen Schritte, dann eine Runde. Nach jedem Test kurz notieren, was passiert ist, und bei Problemen die Log-Datei aus `logs/<Datum>/` (und den Screenshot aus `screenshots/`) in den Planungschat geben. Ergebnisse der ersten beiden Tests: `docs/test-runs/2026-10-17-layer1.md`.

**Vorbereitung**

- Spiel in 1920×1080, randloses Fenster, auf dem Hauptmonitor (sonst `game_region` in `config.local.yaml`)
- Genug Geld für mehrere Paletten ($400 pro Stück) und einen Ersatz-Heli
- Du sitzt als Pilot im Z20 Lakota, gelandet auf der Grasfläche in der blauen Base, unten mittig steht „[B] BUY AMMO / SUPPLIES“
- Kurzbefehl `bot` einrichten (README, Abschnitt „Start“). Alle Befehle unten sind damit geschrieben, `bot …` ist dasselbe wie `.venv\Scripts\python -m heli_farmer.main --layer 1 …`
- Map dazuschreiben, z. B. `bot --step drop --map zestafona` (im Spiel prüfen, nicht im Ladebildschirm)
- **Nach dem Start 5 Sekunden Countdown** (Log `Start in 5 s …`): in der Zeit ins Spiel wechseln. Danach steht im Log `Vordergrund: 'Wardogs' (Spiel: 'Wardogs')`. Steht dort links ein anderer Name, obwohl das Spiel vorne war, diesen Namen melden (dann muss `window.title` angepasst werden)
- **F2** stoppt jederzeit. Nach jedem Schritt lässt der Bot alle Tasten los. Der Heli behält dann seine Neigung: steht die Nase vorn, fliegt er weiter und sinkt. Sofort den nächsten Schritt starten oder selbst übernehmen
- **Sofort F2**, wenn der Heli schnell und tief über Bäume fliegt (z. B. über 100 km/h unter 40 m). Das darf nie passieren

**Schritt 0 – Erkennung ohne Tastendruck (du fliegst selbst)**

1. Palette kaufen, abheben. Dann: `bot --step drop --dry-run`
2. Selbst normal zur Zone fliegen, nicht selbst abwerfen
3. **Erwartet im Log:** ca. 400 m vor dem Zonenrand `Zone in … m: bremsen und sanft sinken`. Sobald der Marker HZ zeigt **oder** (nach dem Bremspunkt) das Heli-Symbol auf der Minimap im farbigen Kreis liegt: `In der Zone (HZ)` bzw. `In der Zone (Minimap)`, `Abwurf in 3 s`. 3 Sekunden später `Abwurf bei AGL … m` und `dry-run: keyDown g`, egal wie hoch du bist (nur unter 30 m wartet er mit `Warte auf Abwurfhöhe`). Danach stoppt das Programm mit `Crate nach G noch geladen`, das ist im Probelauf richtig
4. Jetzt selbst G drücken und weiterfliegen
5. Melden: Kam `In der Zone` gleich beim Einflug, auch bei **weißem** Kreis? Welche Farbe hatte der Kreis?

**Schritt 1 – Palette kaufen**

1. Gelandet: `bot --step buy`, im Countdown ins Spiel wechseln
2. **Erwartet:** Bot drückt B, klickt LOGISTICS (falls nötig), PALLETS, die grüne Ammo-Palette (2. von links) und CONFIRM & EXIT. Die Maus bleibt vor jedem Klick kurz auf dem Knopf stehen. Danach ist das Menü zu und unten rechts das „G“-Feld mit Kisten-Symbol zu sehen. Log: `Crate gekauft`, Programm endet
3. Zusatztest: Mit schon geladener Palette selbst B drücken, dann `bot --step buy`. **Erwartet:** Log `LOGISTICS SLOTS FULL: Palette ist schon geladen, nur bestätigen`, nur ein Klick auf CONFIRM & EXIT
4. Bleibt das Menü trotzdem offen: im Log steht `Kaufmenü nach CONFIRM & EXIT noch offen (Versuch …)`, er klickt bis zu 3-mal. Bitte melden, wie oft. Hilft es nicht, `buy.hover_s` / `buy.press_s` in `config.local.yaml` größer machen (z. B. 0.4 / 0.2)

**Schritt 2 – Abheben**

1. `bot --step climb`
2. **Erwartet:** Heli steigt mit Shift senkrecht auf ca. 25 m (über die Stromleitungen), Log `Abgehoben: 25 m`. Mit Palette kippt er nicht mehr nach hinten weg: wird er beim Schweben langsam rückwärts, tippt der Bot kurz W
3. Melden: Steigt er gerade hoch oder driftet er (vor, zurück, seitlich)?

**Schritt 3 – Zur Zone drehen**

1. Schwebend mit Palette (direkt nach Schritt 2): `bot --step turn`
2. **Erwartet:** Heli dreht nur mit Q/E auf der Stelle, in kurzen Tipps mit Pausen dazwischen. Läuft der Marker schnell auf die Mitte zu, tippt der Bot **vorher die Gegentaste** (z. B. E nach Q) und bremst die Drehung ab. Kein Hin- und Herpendeln um den Marker. Er hört erst auf, wenn der goldene CZ-Marker ruhig in der Mitte steht und sich 1 Sekunde nicht mehr bewegt (Log `Zielrichtung erreicht: Marker bei x=…`, x zwischen 880 und 1040). Dauer: meist unter 15 Sekunden, Abbruch erst nach 30 Sekunden
3. Zusatztest: Vor dem Start so drehen, dass der CZ-Marker ganz am linken Rand klebt. **Erwartet:** er dreht nach links (Q), bremst vor der Mitte ab und bleibt stehen
4. Melden: Pendelt er trotzdem (wie oft schießt der Marker über die Mitte)? Bremst er zu früh und kriecht dann langsam heran? Wie lange hat es gedauert? Zum Nachjustieren in `config.local.yaml`: pendelt er → `flight.yaw_s_per_px` kleiner (z. B. 0.0004) oder `flight.yaw_lookahead_s` größer (z. B. 0.9); kriecht er → `yaw_lookahead_s` kleiner (z. B. 0.5)

**Schritt 4 – Zur Zone fliegen und abwerfen**

1. Schwebend, Nase zum CZ-Marker (direkt nach Schritt 3): `bot --step drop`
2. **Erwartet:**
   - Zuerst steigt er senkrecht (nur Shift, kein W) bis ca. 80 m
   - Dann nimmt er die Nase ca. 3° weiter nach vorne als beim letzten Test (höchstens 4 W-Tipps hintereinander, dann nur noch kurze Ausgleichs-Tipps) und fliegt ca. 160–180 km/h in ca. 100 m Höhe. Du solltest nicht mit S gegenhalten müssen
   - Weicht der Marker bei Tempo zur Seite ab, lenkt er mit Q/E **und** A/D, nimmt die Lenkung aber zurück, bevor der Marker die Mitte erreicht. Er pendelt nicht mehr links-rechts. Kein Kreisfliegen
   - Log `Zone in … m: bremsen und sanft sinken` → er wird langsamer (ca. 120 km/h) und sinkt langsam (höchstens 2 m/s) Richtung 70 m
   - Log `In der Zone (HZ)` oder `In der Zone (Minimap)` gleich beim Einflug, auch bei weißem Kreis: er fliegt gerade weiter, sinkt nicht schnell, kippt nicht zur Seite. Nach 3 Sekunden `Abwurf bei AGL … m` (auch über 85 m), G, `Crate abgeworfen`, `Lieferung bestätigt`
3. Melden: Wie weit war die Nase im Reiseflug vorne (zu viel → `flight.max_tilt` 3, zu wenig → 5)? Pendelt er noch im Flug? War er in der Zone gerade und ruhig? Wie hoch war er beim Abwurf, und kam `Lieferung bestätigt` (oder oben rechts „SUPPLIES DESTROYED ON IMPACT“)?

**Schritt 5 – Raus aus der Zone**

1. Direkt nach Schritt 4: `bot --step leave`
2. **Erwartet:** Ist der Heli durch den Schwung schon aus der Zone: Log `Schon aus der Zone raus (Schwung nach dem Abwurf)`, Programm endet nach ca. 1 Sekunde. Sonst: Log `Umdrehen mit Q` (oder E), er dreht ca. 6 Sekunden, fliegt raus, Log `Zone verlassen, noch 3 s weiter`
3. Melden: Welcher Fall kam?

**Schritt 6 – Base suchen und landen**

1. Direkt nach Schritt 5: `bot --step turn`, danach `bot --step land`
2. **Erwartet:**
   - `turn` bremst bis fast zum Stillstand und dreht wie in Schritt 3 gedämpft, bis der blaue HQ-Marker ruhig mittig ist
   - `land`: Reiseflug zum HQ-Marker. Ca. 700 m vor der Base Log `Base in … m: bremsen und sinken (Landeanflug)`. Er bremst mit S auf ca. 40 km/h und sinkt sanft auf ca. 40 m
   - Sobald die Base auf der Minimap unter dem Heli ist (blaues Quadrat um das Heli-Symbol) und der HQ-Marker nah oder aus dem Bild ist, oder der Kauf-Hinweis kommt: Log `Sinkflug (…)`. Er bremst **erst unter 30 km/h ab** und sinkt dann senkrecht. Unter 10 m geht er erst weiter runter, wenn er langsamer als 15 km/h ist
   - Aufsetzen, Log `Gelandet im Kaufbereich`
3. Wenn etwas schiefgeht, soll der Bot selbst zurückfinden (bitte nicht eingreifen, außer er fliegt tief und schnell auf Bäume zu):
   - Fliegt er über die Base hinaus (Zahl am HQ-Marker wird wieder größer): Log `Base überflogen (HQ … m, vorher … m): umdrehen`, er bremst, dreht zum HQ-Marker und fliegt neu an
   - Verschwindet die Base im Sinkflug von der Minimap: Log `Base nicht mehr unter dem Heli: steigen, umdrehen`. Er landet nie außerhalb des blauen Quadrats
   - Ist der HQ-Marker im Reiseflug länger als 3 s weg: Log `HQ-Marker weg: anhalten und suchen`, er bleibt stehen und dreht, bis der Marker mittig ist
   - Dauert der Landeanflug länger als 2 Minuten: sicherer Stopp mit `Landeanflug dauert zu lange` und Screenshot
4. Melden: Wo setzt er auf (Grasfläche mit „[B] BUY AMMO / SUPPLIES“, daneben, Dach)? Welche der Meldungen aus Punkt 3 kamen, und hat er danach selbst richtig weitergemacht?

**Schritt 7 – Eine Runde**

1. Gelandet auf der Grasfläche: `bot --once`
2. **Erwartet:** kaufen → abheben → drehen → steigen und zur Zone → bremsen → abwerfen → raus (oder schon draußen) → Base suchen → zurück → landen, danach Ende. Zusammenfassung im Log: `bought 1, dropped 1, delivered 1, rounds 1`. Du musst nicht eingreifen

**Schritt 8 – Dauerlauf (erst wenn Schritt 7 mehrmals klappt)**

1. `bot` und zuschauen, mindestens 3 Runden
2. **Erwartet:** Runden laufen ohne Eingriff, nach jeder Runde `Runde fertig` im Log
3. F2 drücken: Heli bekommt sofort keine Eingaben mehr

**Fenster wechseln (bei Gelegenheit, Heli schwebend)**

1. Während eines Schritts mit Alt+Tab in ein anderes Fenster wechseln
2. **Erwartet:** sofort alle Tasten los (Heli schwebt bzw. behält seine Neigung), Log `Spielfenster nicht im Vordergrund: alle Tasten los, warte`. Im anderen Fenster wird nichts getippt
3. Zurück ins Spiel: Log `Spielfenster wieder im Vordergrund nach … s`, der Bot macht weiter

**Sicherheit (bei Gelegenheit, nicht absichtlich crashen)**

- Wird der Heli beschädigt (Heli-Symbol unten mittig rot) oder stirbst du: Bot lässt alle Tasten los und stoppt mit Screenshot, Log `Layer 1 verlassen` und `Layer VEHICLE ist noch nicht gebaut`
- Runde vorbei (Bildschirm „NEXT ROUND IN“): Bot lässt alle Tasten los und stoppt sofort mit `Stopp (Runde vorbei (NEXT ROUND IN), kein Crash …)` und Screenshot, nicht erst nach 30 Sekunden
- Steht im Log `Taste 'shift' länger als 20 s gedrückt`: normal, der Bot drückt sie gleich wieder
