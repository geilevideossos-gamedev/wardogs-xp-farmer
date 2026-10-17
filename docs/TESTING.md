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

Erst die Erkennung ohne Tastendrücke, dann die einzelnen Schritte, dann eine Runde. Nach jedem Test kurz notieren, was passiert ist, und bei Problemen die Log-Datei aus `logs/<Datum>/` (und den Screenshot aus `screenshots/`) in den Planungschat geben. Ergebnisse der ersten sechs Tests: `docs/test-runs/2026-10-17-layer1.md`. Im Log steht im Flug jede Sekunde eine Zeile `Flug: AGL …, km/h (Boden …, Steigen …, Beschl. …), Schräglage, Marker, Tasten`, dazu pro Lauf die Tabelle `logs/<Datum>/flight_<Uhrzeit>.csv`. Bitte bei Problemen beides mitschicken.

**Reihenfolge für den nächsten Test:** (1) `bot --step climb` + `bot --step turn` mehrmals, auch wenn du **verkehrt herum gelandet** bist (CZ-Marker hinter dir), (2) `bot --once` und zuschauen **bis nach dem Drehen zur Base** (Log `Schritt land`), dann F2 oder weiterlaufen lassen, (3) `bot --step land` einzeln (Schritt 6). Raketenwarnung: bei Gelegenheit (Abschnitt „Flares“ unten).

**Vorbereitung**

- Spiel in 1920×1080, randloses Fenster, auf dem Hauptmonitor (sonst `game_region` in `config.local.yaml`)
- Genug Geld für mehrere Paletten ($400 pro Stück) und einen Ersatz-Heli
- Du sitzt als Pilot im Z20 Lakota, gelandet auf der Grasfläche in der blauen Base, unten mittig steht „[B] BUY AMMO / SUPPLIES“
- Kurzbefehl `bot` einrichten (README, Abschnitt „Start“). Alle Befehle unten sind damit geschrieben, `bot …` ist dasselbe wie `.venv\Scripts\python -m heli_farmer.main --layer 1 …`
- Map dazuschreiben, z. B. `bot --step drop --map zestafona` (im Spiel prüfen, nicht im Ladebildschirm)
- **Nach dem Start 5 Sekunden Countdown** (Log `Start in 5 s …`): in der Zeit ins Spiel wechseln. Danach steht im Log `Vordergrund: 'Wardogs' (Spiel: 'Wardogs')`. Steht dort links ein anderer Name, obwohl das Spiel vorne war, diesen Namen melden (dann muss `window.title` angepasst werden)
- **F2** stoppt jederzeit. Nach jedem Schritt lässt der Bot alle Tasten los. Der Heli behält dann seine Neigung: steht die Nase vorn, fliegt er weiter und sinkt. Sofort den nächsten Schritt starten oder selbst übernehmen
- **Sofort F2**, wenn der Heli schnell und tief über Bäume fliegt (z. B. über 100 km/h unter 40 m) oder sich weit nach hinten lehnt. Das darf nie passieren
- Regen und Nebel sind kein Hindernis mehr für die Bilderkennung. Bitte notieren, welches Wetter war

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
2. **Erwartet (neu):** `turn` holt nur das Ziel ins Bild. Ist der CZ-Marker schon im Bild (nicht am Rand) und bewegt sich kaum, endet `turn` sofort mit `Ziel im Bild: Marker bei x=…` (meist nach 1–3 s). Sonst Log `Drehen auf der Stelle (… km/h über Grund, AGL … m)`, Q/E auf der Stelle in kurzen Tipps, **nie Kurvenflug** (keine Zeile `Drehen im Kurvenflug`), kein Zentrieren und kein Warten auf Stillstand. `drop` lenkt danach selbst nach
3. **Verkehrt herum gelandet** (CZ-Marker hinter dir oder am Rand): er dreht in Richtung des Randmarkers weiter, bis der Marker im Bild ist. Läuft der Marker dabei aus der Mitte weg (Schwung), drückt er sofort die Gegentaste statt eine ganze Runde zu drehen. Nimmt er dabei Fahrt auf (über 15 km/h), bremst er erst und dreht dann weiter
4. Melden: Wie lange hat es gedauert? Ist er nach dem Ende gleich in `drop` sauber losgeflogen (beim `--once`)? Hat er bei Drift die Höhe gehalten?

**Schritt 4 – Zur Zone fliegen und abwerfen**

1. Schwebend, Nase zum CZ-Marker (direkt nach Schritt 3): `bot --step drop`
2. **Erwartet:**
   - Zuerst steigt er senkrecht (nur Shift, kein W) bis ca. 80–100 m
   - **Dann fliegt er von selbst los** (beim letzten Test schwebte er hier 12 s still): W-Tipps, höchstens einer pro Sekunde, danach kurze Ausgleichs-Tipps. Bitte **nicht selbst W drücken**, auch wenn es ein paar Sekunden dauert. Er fliegt ca. 230–250 km/h in ca. 100 m Höhe, die Höhe bleibt konstant (Shift). Du solltest nicht mit S gegenhalten müssen
   - Sinkt er doch schnell (in den `Flug:`-Zeilen „Steigen“ unter −5 m/s) oder fällt die Höhe bei steigendem Tempo: Log `Sicherheit: Sturzflug abfangen`, Flügel gerade, Shift und **nur S-Tipps, kein einziges W**, bis er kaum noch sinkt
   - Weicht der Marker bei Tempo zur Seite ab, lenkt er mit Q/E **und** A/D, nimmt die Lenkung aber zurück, bevor der Marker die Mitte erreicht. Er pendelt nicht mehr links-rechts. Kein Kreisfliegen
   - Log `Zone in … m: bremsen und sanft sinken` → er wird langsamer (ca. 120 km/h) und sinkt langsam (höchstens 2 m/s) Richtung 70 m
   - Log `In der Zone (HZ)` oder `In der Zone (Minimap)` gleich beim Einflug, auch bei weißem Kreis: er fliegt gerade weiter, sinkt nicht schnell, kippt nicht zur Seite. Nach 3 Sekunden `Abwurf bei AGL … m` (auch über 85 m), G, `Crate abgeworfen`, `Lieferung bestätigt`
3. Melden: Welches Tempo hat er im Reiseflug erreicht (Log-Zeilen `Flug: …`)? Hält er dabei die Höhe? Pendelt er noch im Flug? War er in der Zone gerade und ruhig? Wie hoch war er beim Abwurf, und kam `Lieferung bestätigt` (oder oben rechts „SUPPLIES DESTROYED ON IMPACT“)?

**Schritt 5 – Raus aus der Zone**

1. Direkt nach Schritt 4: `bot --step leave`
2. **Erwartet:** Ist der Heli durch den Schwung schon aus der Zone: Log `Schon aus der Zone raus (Schwung nach dem Abwurf)`. Sonst: Log `Umdrehen mit Q` (oder E), Kurve mit A/D und Q/E, **neu ca. 180°** statt 90–130°: Log `Umgedreht: …° laut Minimap` (ca. 170°). Kommt diese Zeile nicht, hat die Minimap keine Richtung geliefert, dann dreht er höchstens 14 s. Danach geradeaus raus, Log `Zone verlassen, noch 3 s weiter`
3. Melden: Wie weit hat er gedreht (zeigt die Nase danach ungefähr Richtung Base)? Kam `Umgedreht: … laut Minimap`?

**Schritt 6 – Base suchen und landen**

1. Direkt nach Schritt 5: `bot --step turn`, danach `bot --step land`. Im `--once` passiert beides automatisch
2. **Erwartet beim Drehen zur Base:**
   - Log `Drehrichtung wie beim Umdrehen: Q` (bzw. E): er dreht **in dieselbe Richtung wie `leave`** weiter (beim letzten Test drehte er in die Gegenrichtung und lief 4× ins Zeitlimit). Bei `--step turn` einzeln fehlt diese Zeile, dann dreht er zur Seite des Randmarkers
   - Mit Fahrt und über 60 m: `Drehen im Kurvenflug (…)`, Schräglage höchstens ca. 25°. Unter 60 m nur auf der Stelle
   - Fertig mit `Ziel im Bild: Marker bei x=…`, sobald der HQ-Marker im Bild ist und sich kaum bewegt. Er muss **nicht** in der Mitte stehen
3. **Erwartet bei der Landung:**
   - Reiseflug zum HQ-Marker, ab ca. 1200 m `Base in … m: bremsen und sinken (Landeanflug)`
   - Im blauen Bereich um HQ verschwindet der HQ-Marker: Log `HQ-Marker weg, HQ auf der Minimap: danach fliegen`. Er fliegt jetzt nach dem HQ-Symbol auf der Minimap, dreht sich dazu mit Q/E und fliegt langsam (höchstens ca. 40 km/h)
   - Stehen andere Helis auf der Minimap still, fliegt er zum nächsten davon. Log `Über der Landezone (Helis)` (oder nach 5 s Warten über dem HQ `Über der Landezone (HQ)`), dann `Sinkflug`. Kommt vorher der Kauf-Hinweis: sofort `Sinkflug (Kauf-Hinweis)`
   - Rutscht er beim Sinken weg: Log `Landezone weggerutscht: nachfliegen (Minimap)`, er fliegt nach und sinkt erneut
   - Aufsetzen, Log `Gelandet im Kaufbereich`
4. Wenn etwas schiefgeht, soll der Bot selbst zurückfinden (bitte nur bei Gefahr eingreifen):
   - `Base überflogen` kommt nur noch, wenn die HQ-Entfernung dreimal hintereinander deutlich steigt
   - HQ-Marker weg und kein HQ auf der Minimap (z. B. noch weit weg): `HQ-Marker weg, kein HQ auf der Minimap: anhalten und suchen`
   - Dauert der Landeanflug länger als 2 Minuten: sicherer Stopp mit `Landeanflug dauert zu lange` und Screenshot
5. Melden: Kam `HQ auf der Minimap`? Ist er zu den stehenden Helis geflogen (oder zum HQ)? Wo hat er aufgesetzt? **Wichtig:** Fliegt er über der Base in die falsche Richtung oder dreht im Kreis, bitte sofort F2 und melden (Minimap-Maßstab und Lenkung sind noch geschätzt)

**Schritt 7 – Eine Runde**

1. Gelandet auf der Grasfläche: `bot --once`
2. **Erwartet:** kaufen → abheben → drehen → steigen und zur Zone → bremsen → abwerfen → raus (oder schon draußen) → Base suchen → zurück → landen, danach Ende. Zusammenfassung im Log: `bought 1, dropped 1, delivered 1, rounds 1`. Du musst nicht eingreifen

**Schritt 8 – Dauerlauf (erst wenn Schritt 7 mehrmals klappt)**

1. `bot` und zuschauen, mindestens 3 Runden
2. **Erwartet:** Runden laufen ohne Eingriff, nach jeder Runde `Runde fertig` im Log
3. F2 drücken: Heli bekommt sofort keine Eingaben mehr

**Flares bei Raketenwarnung (bei Gelegenheit)**

1. Spielton über das **Windows-Standard-Ausgabegerät** (sonst hört der Bot nichts). Beim Start steht im Log `Raketenwarnung hört mit auf: <Gerät>`
2. Wird auf dich geschossen: Das langsame „bip bip bip“ (Anvisieren) löst noch nichts aus. Sobald der **Dauer-Piepton** 0,66 s läuft: Log `Raketenwarnung erkannt, Flares (Nr. …)`, V wird gedrückt, Flares fliegen. Frühestens 3 s später wieder
3. Melden: Kamen die Flares rechtzeitig? Gab es Flares ohne Rakete (Fehlalarm)? Am Ende steht `flares` in der Zusammenfassung

**Fenster wechseln (bei Gelegenheit, Heli schwebend)**

1. Während eines Schritts mit Alt+Tab in ein anderes Fenster wechseln
2. **Erwartet:** sofort alle Tasten los (Heli schwebt bzw. behält seine Neigung), Log `Spielfenster nicht im Vordergrund: alle Tasten los, warte`. Im anderen Fenster wird nichts getippt
3. Zurück ins Spiel: Log `Spielfenster wieder im Vordergrund nach … s`, der Bot macht weiter

**Sicherheit (bei Gelegenheit, nicht absichtlich crashen)**

- Wird der Heli beschädigt (Heli-Symbol unten mittig rot) oder stirbst du: Bot lässt alle Tasten los und stoppt mit Screenshot, Log `Layer 1 verlassen` und `Layer VEHICLE ist noch nicht gebaut`
- Nie tief und schnell, kein Sturzflug: Unter 40 m mit mehr als 50 km/h oder unter der Mindesthöhe greift die Sicherheit ein (Log `Flug: … Sicherheit: Lage und Höhe zuerst`): Flügel gerade, Shift, Nase dosiert hoch, bis das Tempo nicht mehr steigt; gedreht wird erst danach. Sturzflug (über 60 km/h und sinkt schneller als 5 m/s, oder Höhe fällt bei steigendem Tempo): Log `Sicherheit: Sturzflug abfangen`, nur S (je schneller er sinkt, desto länger), **nie W**, bis er langsamer als 1 m/s sinkt. Bitte melden, wenn er sich trotzdem weit nach hinten lehnt oder sinkt, während er Shift hält
- Runde vorbei (Bildschirm „NEXT ROUND IN“): Bot lässt alle Tasten los und stoppt sofort mit `Stopp (Runde vorbei (NEXT ROUND IN), kein Crash …)` und Screenshot, nicht erst nach 30 Sekunden
- Steht im Log `Taste 'shift' länger als 20 s gedrückt`: normal, der Bot drückt sie gleich wieder
