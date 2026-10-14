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
