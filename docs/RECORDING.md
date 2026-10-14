# Aufnahmen machen

Die Aufnahmen sind die Testdaten für die Bilderkennung. Du spielst einen Ablauf ganz normal von Hand, das Aufnahme-Tool speichert dabei das Spielbild und alle Tasten- und Mauseingaben mit Zeitstempel. Daraus lerne ich später, woran man z. B. „Heli bereit“ oder „Crate abgeworfen“ erkennt.

Aufnahmen bleiben auf deinem Rechner im Ordner `recordings/` und werden **nicht** hochgeladen.

## Vorbereitung (einmalig)

1. Spiel auf **1920×1080** stellen, am besten **randloses Fenster** (Borderless). Bei echtem Vollbild kann die Aufnahme schwarz werden
2. Läuft das Spiel nicht auf dem Hauptmonitor oben links: `game_region` in `config.local.yaml` eintragen (siehe README)
3. Prüfen, ob **F9** im Spiel belegt ist. Wenn ja, eine andere Taste in `config.local.yaml` unter `keys.record` eintragen

## So nimmst du auf

1. PowerShell im Projektordner öffnen
2. Tool starten, z. B. für die Map „harbor“ und den kompletten Crate-Ablauf:
   ```powershell
   .venv\Scripts\python -m tools.record --map harbor --seq full_loop
   ```
   Im Fenster steht dann `Bereit: F9 startet/stoppt eine Aufnahme, F2 beendet`
3. Ins Spiel wechseln, an den Startpunkt des Ablaufs gehen
4. **F9** drücken → Aufnahme läuft. Ca. 2 Sekunden ruhig stehen bleiben
5. Ablauf ganz normal spielen
6. Am Ende ca. 2 Sekunden ruhig bleiben, dann **F9** → Aufnahme gespeichert
7. Für eine weitere Aufnahme derselben Sequenz einfach wieder **F9** (neuer Ordner)
8. **F2** beendet das Tool (eine laufende Aufnahme wird vorher gespeichert)

Map-Namen: kurz, klein, ohne Leerzeichen und für jede Map immer gleich (z. B. `harbor`, `desert`, `forest`).

Ergebnis pro Aufnahme: `recordings/<map>/<sequenz>_<datum>_<uhrzeit>/` mit

| Datei | Inhalt |
|---|---|
| `video.mp4` | Spielbild, 20 Bilder pro Sekunde |
| `frames.csv` | Zeitpunkt jedes Bildes |
| `inputs.jsonl` | Jede Taste und Maustaste (gedrückt/losgelassen) und jede Mausbewegung mit Zeitpunkt |
| `meta.json` | Einstellungen der Aufnahme |

Kurz prüfen: `video.mp4` öffnen. Sieht man das Spiel (nicht schwarz, nicht abgeschnitten)?

**Achtung:** Das Tool zeichnet alle Tasten auf, auch Chat-Nachrichten. Während einer Aufnahme keine Passwörter oder Privates tippen.

## Was aufnehmen – nach Priorität

Jede Sequenz auf **jeder der 3 Maps**. Mehrere Durchgänge, weil Licht, Wetter, Spieler und kleine Abweichungen variieren.

### Priorität 1 – Crate-Schleife (Layer 1, wird als Erstes gebaut)

Startpunkt: Du sitzt als Pilot im Z20 Lakota auf dem grünen Landeplatz in der blauen Base.

| Sequenz | Was genau | Pro Map |
|---|---|---|
| `full_loop` | Kompletter Ablauf: B → Ammo Crate kaufen → Menü zu → abheben → in die Zone fliegen → mit G abwerfen → zurückfliegen → auf dem grünen Landeplatz landen | 3× |
| `buy_crate` | Nur: B drücken → Ammo Crate kaufen → Menü schließen | 3× |
| `drop` | Anflug auf die Zone (letzte ca. 20 s) → G drücken → Crate fällt → kurz weiterfliegen | 3× |
| `land` | Anflug auf die Base (letzte ca. 30 s) → auf dem grünen Landeplatz aufsetzen → 3 s stehen | 3× |
| `fly_to_zone` | Abheben bis zur Zone, ohne Abwurf | 2× |
| `fly_to_base` | Nach dem Abwurf von der Zone zurück bis über die Base | 2× |

Bitte bei `full_loop` möglichst die Route fliegen, die du für sicher hältst – der Bot soll sie später nachfliegen.

### Priorität 2 – Heli besorgen (Layer 2)

| Sequenz | Was genau | Pro Map |
|---|---|---|
| `buy_heli` | Zum Fahrzeughändler gehen → Tab Air → Z20 Lakota kaufen | 2× |
| `board` | Vom gekauften Heli bis du als Pilot drin sitzt | 2× |
| `death` | Heli wird zerstört oder du stirbst → Respawn-Bildschirm → bis du wieder steuern kannst | 2× |

### Priorität 3 – Team (Layer 3)

| Sequenz | Was genau | Pro Map |
|---|---|---|
| `team` | Vom Team-Auswahlbildschirm bis du im Team Blau gespawnt bist | 2× |

### Priorität 4 – Server (Layer 4)

| Sequenz | Was genau | Wie oft |
|---|---|---|
| `join` | Vom Hauptmenü → Serverliste → EU Central Server mit 20–80 Spielern → Join Match, bis zur Team-Auswahl. Als `--map` den Namen der Map nehmen, die geladen wird | 3× insgesamt |

## Bekannte Grenzen

- Mausbewegungen werden als Bildschirmposition gespeichert. Wenn das Spiel die Maus fängt (Kamera/Steuern), steht dort nur die Position des Mauszeigers, nicht die tatsächliche Kamera-Drehung
- Die Aufnahme braucht etwas Rechenleistung. Wenn das Spiel spürbar ruckelt: `recording.fps` oder `recording.scale` in `config.local.yaml` verringern und Bescheid geben

## Eigene OBS-Videos

Normale OBS-Aufnahmen (MP4, 1920×1080) funktionieren auch mit den Analyse-Tools, aber ohne Tasten-Log. Für Priorität 1 bitte das Aufnahme-Tool verwenden.
