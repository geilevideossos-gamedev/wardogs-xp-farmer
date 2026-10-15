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

Erst die Erkennung ohne Tastendrücke, dann die einzelnen Schritte, dann eine Runde. Nach jedem Test kurz notieren, was passiert ist, und bei Problemen die Log-Datei aus `logs/<Datum>/` (und den Screenshot aus `screenshots/`) in den Planungschat geben.

**Vorbereitung**

- Spiel in 1920×1080, randloses Fenster, auf dem Hauptmonitor (sonst `game_region` in `config.local.yaml`)
- Genug Geld für mehrere Paletten ($400 pro Stück) und einen Ersatz-Heli
- Du sitzt als Pilot im Z20 Lakota, gelandet auf der Grasfläche in der blauen Base, unten mittig steht „[B] BUY AMMO / SUPPLIES“
- Map dazuschreiben, z. B. `--map zestafona` (im Spiel prüfen, nicht im Ladebildschirm)
- **F2** stoppt jederzeit. Nach jedem Schritt lässt der Bot alle Tasten los. Der Heli behält dann seine Neigung: steht die Nase vorn, fliegt er weiter und sinkt. Sofort den nächsten Schritt starten oder selbst übernehmen
- **Sofort F2**, wenn der Heli schnell und tief über Bäume fliegt (z. B. über 100 km/h unter 40 m). Das darf nie passieren

**Schritt 0 – Erkennung ohne Tastendruck (du fliegst selbst)**

1. Palette kaufen, abheben. Dann: `.venv\Scripts\python -m heli_farmer.main --layer 1 --step drop --dry-run`
2. Selbst normal zur Zone fliegen, nicht abwerfen
3. **Erwartet im Log:** ca. 400 m vor dem Zonenrand `Zone in … m: bremsen und sinken`, beim Einflug (HZ-Marker und Kreis auf der Minimap) `In der Zone (HZ + Minimap), Abwurf in 3 s`, gut 3 Sekunden später `dry-run: keyDown g`. Danach stoppt das Programm mit `Crate nach G noch geladen`, das ist im Probelauf richtig
4. Jetzt selbst G drücken und weiterfliegen
5. Melden: Kam die Meldung `Zone in …` ungefähr an der richtigen Stelle? Kam `In der Zone` zur richtigen Zeit (nicht zu früh, nicht zu spät)? Welche Farbe hatte der Kreis auf der Minimap?

**Schritt 1 – Palette kaufen**

1. Gelandet: `.venv\Scripts\python -m heli_farmer.main --layer 1 --step buy`, sofort ins Spiel wechseln
2. **Erwartet:** Bot drückt B, klickt LOGISTICS (falls nötig), PALLETS, die grüne Ammo-Palette (2. von links) und CONFIRM & EXIT. Danach ist unten rechts das „G“-Feld mit Kisten-Symbol zu sehen. Log: `Crate gekauft`, Programm endet
3. Melden, falls ein Klick daneben geht (dann stimmen die Punkte in `buy.clicks` nicht)

**Schritt 2 – Abheben**

1. `… --layer 1 --step climb`
2. **Erwartet:** Heli steigt nur mit Shift senkrecht auf ca. 15 m (AGL unten mittig), Log `Abgehoben: 15 m`, Programm endet. Danach schwebt er ohne Taste auf der Höhe
3. Melden: Steigt er gerade hoch oder driftet er? Hält er danach die Höhe?

**Schritt 3 – Zur Zone drehen**

1. Schwebend mit Palette (direkt nach Schritt 2): `… --layer 1 --step turn`
2. **Erwartet:** Heli dreht nur mit Q/E auf der Stelle, bis der goldene CZ-Marker etwa in der Bildmitte steht. Log `Zielrichtung erreicht`
3. Melden: Pendelt er hin und her (dann `flight.yaw_s_per_px` kleiner)? Findet er den Marker, wenn er anfangs nicht im Bild ist?

**Schritt 4 – Zur Zone fliegen und abwerfen**

1. Schwebend, Nase zum CZ-Marker (direkt nach Schritt 3): `… --layer 1 --step drop`
2. **Erwartet:**
   - Zuerst steigt er senkrecht (nur Shift, kein W) bis ca. 80 m
   - Dann nimmt er mit kurzen W-Tipps Fahrt auf bis ca. 200 km/h und hält ca. 100 m. Shift ist dabei die meiste Zeit gedrückt
   - Log `Zone in … m: bremsen und sinken` → er wird langsamer (ca. 120 km/h) und sinkt auf ca. 70 m
   - Log `In der Zone (HZ + Minimap) …`, ca. 3 Sekunden später G, Log `Crate abgeworfen` und `Lieferung bestätigt`
3. Melden: Sinkt er im Reiseflug trotz Shift (dann nimmt er die Nase hoch, das sollte man an S-Tipps sehen)? Wird er immer schneller oder schaukelt das Tempo? Wirft er in der Zone ab und kommt „SUPPLIES DELIVERED“? Wie hoch war er beim Abwurf?

**Schritt 5 – Umdrehen und raus aus der Zone**

1. Direkt nach Schritt 4: `… --layer 1 --step leave`
2. **Erwartet:** Log `Umdrehen mit Q` (oder E), er bremst und dreht ca. 4 Sekunden, dann fliegt er geradeaus aus der Zone, Log `Zone verlassen`
3. Melden: Wie weit hat er sich ungefähr gedreht (z. B. halbe Drehung, Viertel)? Danach wird `flight.turnaround_s` eingestellt: für eine halbe Drehung soll er ungefähr zurück Richtung Base zeigen

**Schritt 6 – Base suchen und landen**

1. Direkt nach Schritt 5: `… --layer 1 --step turn`, danach `… --layer 1 --step land`
2. **Erwartet:** `turn` dreht nur mit Q/E, bis der blaue HQ-Marker mittig ist. `land`: Flug zum HQ-Marker, beim Kauf-Hinweis oder nahe der Base bremsen, dann langsam senkrecht sinken (Strg nur hier), aufsetzen, Log `Gelandet im Kaufbereich`
3. Melden: Wo setzt er auf (Grasfläche mit „[B] BUY AMMO / SUPPLIES“, Dach, Bäume)? Zu hart (`flight.sink_rate` kleiner)? Bremst er zu früh oder zu spät (`maps.<map>.hq_approach_y`)?

**Schritt 7 – Eine Runde**

1. Gelandet auf der Grasfläche: `… --layer 1 --once`
2. **Erwartet:** kaufen → abheben → drehen → steigen und zur Zone → bremsen → abwerfen → umdrehen → raus → Base suchen → zurück → landen, danach Ende. Zusammenfassung im Log: `bought 1, dropped 1, delivered 1, rounds 1`

**Schritt 8 – Dauerlauf (erst wenn Schritt 7 mehrmals klappt)**

1. `… --layer 1` und zuschauen, mindestens 3 Runden
2. **Erwartet:** Runden laufen ohne Eingriff, nach jeder Runde `Runde fertig` im Log
3. F2 drücken: Heli bekommt sofort keine Eingaben mehr

**Sicherheit (bei Gelegenheit, nicht absichtlich crashen)**

- Wird der Heli beschädigt (Heli-Symbol unten mittig rot) oder stirbst du: Bot lässt alle Tasten los und stoppt mit Screenshot, Log `Layer 1 verlassen` und `Layer VEHICLE ist noch nicht gebaut`
- Bleibt der Kreis auf der Minimap weiß, wirft der Bot nicht ab und stoppt nach einiger Zeit mit `Zone nicht rechtzeitig erreicht`. Bitte dann melden (mit Screenshot)
- Steht im Log `Taste 'shift' länger als 20 s gedrückt`: normal, der Bot drückt sie gleich wieder
