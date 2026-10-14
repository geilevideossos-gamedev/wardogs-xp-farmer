# heli-xp-farmer

Ein Windows-Programm für **WARDOGS** (Steam), das später automatisch Pilot-XP farmen soll: mit dem Helikopter **Z20 Lakota** Ammo-Crates von der blauen Base in die Zone fliegen, abwerfen, zurückfliegen – in einer Schleife, bis du **F2** drückst.

Das Programm liest nur den Bildschirm und drückt Tasten/Maus wie ein Mensch. Es greift nicht in das Spiel ein (kein Speicherlesen, keine Injection).

> Hinweis: Automatisierung verstößt sehr wahrscheinlich gegen die Nutzungsbedingungen des Spiels. Nutzung auf eigenes Risiko (Account-Bann möglich).

## Stand

Fertig ist das **Fundament**: Not-Aus mit F2, Tastensteuerung, Bildschirmaufnahme, Log-Dateien und die Ablaufsteuerung. Die Bilderkennung und das eigentliche Fliegen fehlen noch. Wenn du den Bot jetzt startest, erkennt er den Bildschirm noch nicht und stoppt nach 30 Sekunden von selbst.

## Installation

Voraussetzung: Windows, Python 3.12 oder neuer, Git.

In PowerShell im Projektordner:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## Start

Immer aus dem Projektordner heraus:

| Befehl | Was passiert |
|---|---|
| `.venv\Scripts\python -m heli_farmer.main` | Bot starten |
| `.venv\Scripts\python -m heli_farmer.main --dry-run` | Probelauf: drückt keine Tasten, schreibt nur ins Log, was er drücken würde |
| `.venv\Scripts\python -m heli_farmer.main --hold-test` | Test für den Not-Aus: hält nach 5 Sekunden die Taste W gedrückt, bis du F2 drückst |

Beendet wird mit **F2** (oder Strg+C im Konsolenfenster).

## Aufnahmen für Testdaten

```powershell
.venv\Scripts\python -m tools.record --map <mapname> --seq <sequenz>
```

**F9** startet und stoppt eine Aufnahme, **F2** beendet das Tool. Sequenzen: `join`, `team`, `buy_heli`, `board`, `buy_crate`, `fly_to_zone`, `drop`, `fly_to_base`, `land`, `full_loop`, `death`. Was du wie oft aufnehmen sollst: `docs/RECORDING.md`.

## Tasten

| Taste | Wirkung |
|---|---|
| **F2** | Not-Aus: stoppt sofort und lässt alle Tasten los. Im Aufnahme-Tool: beenden |
| **F9** | Aufnahme-Tool: Aufnahme starten/stoppen |

## Einstellungen

Alle Werte stehen in `config.yaml`. Ändere diese Datei nicht für persönliche Werte, sondern lege daneben eine `config.local.yaml` an. Sie wird nicht hochgeladen und überschreibt nur das, was darin steht. Beispiel, wenn das Spiel auf dem zweiten Monitor rechts läuft:

```yaml
game_region:
  left: 1920
```

| Einstellung | Bedeutung | Standard |
|---|---|---|
| `game_region` | Bildschirmbereich des Spiels (links, oben, Breite, Höhe in Pixeln) | 0, 0, 1920, 1080 |
| `keys.stop` | Not-Aus-Taste | `f2` |
| `keys.shop` | Taste für das Kaufmenü im Spiel | `b` |
| `keys.drop` | Taste zum Abwerfen der Crate | `g` |
| `keys.record` | Aufnahme starten/stoppen (Aufnahme-Tool) | `f9` |
| `loop.tick_s` | Pause zwischen zwei Prüfungen des Bildschirms (Sekunden) | 0.1 |
| `timeouts.unknown_state_s` | So lange darf der Bildschirm unbekannt sein, bevor das Programm sicher stoppt (Sekunden) | 30 |
| `hold_test.key` | Taste für den Hold-Test | `w` |
| `hold_test.repeat_s` | Wie oft der Hold-Test die Taste erneut sendet (Sekunden) | 0.03 |
| `hold_test.start_delay_s` | Wartezeit vor dem Hold-Test, um ins Zielfenster zu wechseln (Sekunden) | 5 |
| `recording.root` | Ordner für Aufnahmen | `recordings` |
| `recording.fps` | Bilder pro Sekunde der Aufnahme | 20 |
| `recording.scale` | Größe des Aufnahmevideos (1.0 = volle Auflösung, 0.5 = halbe) | 1.0 |
| `logging.root` | Ordner für Log-Dateien | `logs` |
| `logging.level` | Wie viel geloggt wird (`INFO` oder `DEBUG`) | `INFO` |

## Logs

Jeder Start schreibt eine Log-Datei nach `logs/<Datum>/`. Stoppt das Programm wegen eines unbekannten Bildschirms, liegt dort zusätzlich ein Screenshot unter `screenshots/`.

## Für Entwickler

```powershell
.venv\Scripts\ruff check .
.venv\Scripts\ruff format --check .
.venv\Scripts\python -m pytest
```

Aufbau: `docs/ARCHITECTURE.md`. Entscheidungen: `docs/DECISIONS.md`. Manuelle Tests: `docs/TESTING.md`.
