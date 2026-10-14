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

1. `.venv\Scripts\python -m tools.extract_frames recordings\test\drop_<…>\video.mp4 --every 5`
2. **Erwartet:** Meldung `N Bilder gespeichert in debug\frames\…`, die PNGs zeigen das Spielbild
3. `.venv\Scripts\python -m tools.replay recordings\test\drop_<…>\video.mp4`
4. **Erwartet:** Eine Zeile `0.00s - …s  UNKNOWN  … Frames` (die Erkennung ist noch nicht gebaut)
5. Dasselbe mit einem OBS-Video (MP4, 1920×1080) wiederholen
