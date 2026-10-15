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
2. **Erwartet:** Meldung `N Bilder gespeichert in debugrames\…`, die PNGs zeigen das Spielbild
3. `.venv\Scripts\python -m tools.replay wardogs_daten\Video\join+Bakurani.mp4`
4. **Erwartet:** nach 1–2 Minuten eine Liste mit Abschnitten wie `BUY_MENU`, `TO_ZONE`, `TO_BASE`, `LANDED_BASE` und die Zeile `Abwürfe bei: 173.8s, 316.5s`
5. `.venv\Scripts\python -m tools.overlay_inputs wardogs_daten\Video\join+Bakurani.mp4`
6. **Erwartet:** Datei `wardogs_daten\Video\join+Bakurani.inputs.jsonl` mit Zeilen wie `{"t": 102.1, "type": "key", "key": "b", "action": "down"}`

## Layer 1 – Crate-Schleife

Erst die einzelnen Schritte, dann eine Runde, dann den Dauerlauf. Nach jedem Test: kurz notieren, was passiert ist, und bei Problemen die Log-Datei aus `logs/<Datum>/` (und den Screenshot aus `screenshots/`) in den Planungschat geben.

**Vorbereitung**

- Spiel in 1920×1080, randloses Fenster, auf dem Hauptmonitor (sonst `game_region` in `config.local.yaml`)
- Genug Geld für mehrere Paletten ($400 pro Stück) und einen Ersatz-Heli
- Du sitzt als Pilot im Z20 Lakota, gelandet in der blauen Base, unten mittig steht „[B] BUY AMMO / SUPPLIES“
- Optional: Name der Map dazuschreiben, z. B. `--map bakurani`
- **F2** stoppt jederzeit. Nach jedem Schritt lässt der Bot alle Tasten los: Der Heli fliegt dann ohne Eingabe weiter. Sofort den nächsten Schritt starten oder selbst übernehmen

**Schritt 0 – Erkennung ohne Tastendruck**

1. Im Heli auf dem Landeplatz: `.venv\Scripts\python -m heli_farmer.main --layer 1 --step climb --dry-run`
2. Ins Spiel wechseln, ~10 Sekunden warten, F2
3. **Erwartet:** im Log `Layer None -> CRATE_LOOP`, `Schritt climb` und die Zeile `dry-run: keyDown shift`. Steht dort stattdessen `UNKNOWN`: Screenshot und Log schicken (dann erkennt der Bot „Z20 LAKOTA“ unten rechts nicht)

**Schritt 1 – Palette kaufen**

1. `.venv\Scripts\python -m heli_farmer.main --layer 1 --step buy`, sofort ins Spiel wechseln
2. **Erwartet:** Bot drückt B, klickt LOGISTICS (falls nötig), PALLETS, die grüne Ammo-Palette (2. von links) und CONFIRM & EXIT. Danach ist unten rechts das „G“-Feld mit Kisten-Symbol zu sehen. Log: `Crate gekauft`, Programm endet
3. Melden, falls ein Klick daneben geht (dann stimmen die Punkte in `buy.clicks` nicht)

**Schritt 2 – Steigen**

1. `… --layer 1 --step climb`
2. **Erwartet:** Heli steigt senkrecht (Shift) auf ca. 100 m (AGL unten mittig), Log `Sichere Höhe erreicht`, Programm endet, Heli fliegt ohne Eingabe weiter
3. Melden: Steigt er gerade hoch oder driftet er? Wie hoch schießt er über 100 m hinaus? Sinkt er nach dem Loslassen?

**Schritt 3 – Drehen**

1. In der Luft (z. B. direkt nach Schritt 2), Palette geladen: `… --layer 1 --step turn`
2. **Erwartet:** Heli dreht mit Q/E auf der Stelle, bis der Zonen-Marker („CZ“-Ring) etwa in der Bildmitte steht. Log `Zielrichtung erreicht`
3. Ohne Palette dreht er stattdessen zum HQ-Marker (blaues Quadrat „HQ“). Ist der nicht zu sehen, dreht er nach rechts, bis er auftaucht
4. Melden: Dreht er zu weit hin und her (dann `flight.yaw_s_per_px` kleiner)?

**Schritt 4 – Zur Zone fliegen und abwerfen**

1. In der Luft, Palette geladen, Nase grob Richtung Zone: `… --layer 1 --step drop`
2. **Erwartet:** Heli beschleunigt auf ca. 200 km/h, hält ca. 100 m Höhe und korrigiert die Richtung zum Marker. Wenn der Marker weit unten im Bild ist (über der Zone), bremst er, sinkt auf ca. 60 m, drückt G. Log `Crate abgeworfen` und meist `Lieferung bestätigt` („SUPPLIES DELIVERED +$2,500“)
3. Melden: Tempo stabil oder wird er immer schneller/langsamer? Wirft er zu früh/spät ab (`maps.<map>.zone_arrive_y` anpassen)? Gefährliche Höhe über Bäumen/Häusern?

**Schritt 5 – Zurück und landen**

1. In der Luft ohne Palette: zuerst `… --layer 1 --step turn` (Richtung Base), dann `… --layer 1 --step land`
2. **Erwartet:** Flug zum HQ-Marker, beim Kauf-Hinweis oder nahe der Base Bremsen, dann langsames Sinken, Aufsetzen, Log `Gelandet im Kaufbereich`
3. Melden: Wo setzt er auf (frei, auf Dach, in Bäumen)? Zu hart (`flight.sink_rate` kleiner)? Hört er zu früh/spät auf zu fliegen?

**Schritt 6 – Eine Runde**

1. Auf dem Landeplatz: `… --layer 1 --once`
2. **Erwartet:** kaufen → steigen → drehen → Zone → abwerfen → drehen → zurück → landen, danach Ende. Zusammenfassung im Log: `bought 1, dropped 1, delivered 1, rounds 1`

**Schritt 7 – Dauerlauf**

1. `… --layer 1` und zuschauen, mindestens 3 Runden
2. **Erwartet:** Runden laufen ohne Eingriff, nach jeder Runde `Runde fertig` im Log
3. F2 drücken: Heli bekommt sofort keine Eingaben mehr

**Sicherheit (bei Gelegenheit, nicht absichtlich crashen)**

- Wird der Heli beschädigt (Heli-Symbol unten mittig rot) oder stirbst du: Bot lässt alle Tasten los und stoppt mit Screenshot, Log `Layer 1 verlassen` und `Layer VEHICLE ist noch nicht gebaut`
- Steht im Log `Taste 'shift' länger als 20 s gedrückt`: normal, der Bot drückt sie gleich wieder
