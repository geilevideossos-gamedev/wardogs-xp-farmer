# AGENTS.md – Regeln für Coding-Agents (Claude Code)

Projekt: **heli-xp-farmer** – Bot für WARDOGS (Steam), der mit dem Z20 Lakota in einer Schleife Ammo-Crates von der blauen Base in die Zone fliegt, dort abwirft und zurückfliegt, bis F2 gedrückt wird. Ziel: autonom über Nacht XP farmen.
Vollständige Beschreibung und Soll-Ablauf: `PROJECT.md`. Lies sie vor jeder Aufgabe.

Repo: `git@github.com:geilevideossos-gamedev/wardogs-xp-farmer.git` (Branch `main`)

## Für wen wird geschrieben

| Was | Leser | Stil |
|---|---|---|
| Code, Config, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` | **KI** | Präzise, knapp, eindeutige Namen, keine Füllprosa. Muss für eine KI ohne Vorwissen verständlich sein |
| Commit-Messages, `CHANGELOG.md`, `README.md`, `docs/TESTING.md`, `docs/RECORDING.md`, Abschlussmeldung | **Daniel (Mensch)** | Einfache Sprache, ohne Code-Kontext verständlich, konkrete Schritte |

## Rollen

- Planung passiert im Claude-Chat des Projekts. Du bekommst von dort Prompts.
- Du schreibst Code und Doku, committest und pushst selbstständig.
- **Daniel testet im Spiel selbst.** Du startest den Bot nie gegen das laufende Spiel und sendest keine Eingaben an das Spiel.
- Wenn eine Anforderung unklar ist oder einer Regel hier widerspricht: nachfragen statt raten.

## Harte Regeln für das Programm

- Nur externer Input: Bildschirm lesen, Tastatur/Maus simulieren
- Kein Lesen/Schreiben von Spielspeicher, keine DLL-Injection, keine Prozess-Manipulation, kein Umgehen von Anti-Cheat
- **F2 stoppt immer und sofort**, auch mitten in einem Flug oder einer Wartezeit. Beim Stopp werden alle gedrückten Tasten und Maustasten losgelassen
- Unbekannter Bildschirmzustand länger als ein konfigurierbares Timeout → sicher stoppen, Tasten loslassen, Screenshot + Log speichern
- Koordinaten, Timings, Schwellwerte und Tastenbelegung gehören in die Config, nicht hart in den Code

## Ablauf: hierarchische State Machine

Jeder Tick prüft die Bedingungen **von außen nach innen**. Ist eine äußere Bedingung verletzt (z. B. Heli zerstört, vom Server geflogen), fällt der Bot auf diesen Layer zurück.

| Layer | Bedingung | Ablauf |
|---|---|---|
| 4 Server (außen) | nicht auf einem Server | Serverliste → offizieller Server **EU Central** mit **mehr als 20 und weniger als 80 Spielern** → Join Match |
| 3 Team | auf Server, kein Team | Team **Blau** beitreten |
| 2 Fahrzeug | Team Blau, kein Heli | zum Fahrzeughändler → Tab Air → **Z20 Lakota** kaufen → als Pilot einsteigen |
| 1 Crate-Loop (innen) | Server + Team Blau + funktionierender Heli | **B** → Ammo Crate kaufen → in die Zone fliegen → mit **G** abwerfen → zur Base fliegen → auf dem grünen quadratischen Landeplatz landen → wiederholen |
| 0 Fundament | immer | F2-Killswitch, Input, Screen-Capture, Logging, Watchdog |

Jeder State ist einzeln testbar. Detektoren sind Funktionen `frame -> Ergebnis`, damit sie offline gegen Aufnahmen laufen.

## Entwicklungs- und Testablauf

1. Fundament (Layer 0) und Aufnahme-Tools zuerst
2. Dann **innerster Layer zuerst** (Crate-Loop), danach jeweils der nächste äußere
3. Pro Layer: du programmierst → Daniel testet im Spiel → Feedback → du verbesserst → Daniel testet wieder
4. Erst wenn Daniel „passt“ sagt, kommt der nächste äußere Layer

## Testdaten (Aufnahmen)

- Daniel nimmt Abläufe pro Map (3 Maps) als Video mit Input-Log auf (`tools/record.py`, Anleitung in `docs/RECORDING.md`)
- Aufnahmen liegen in `recordings/` und werden **nicht** committet (zu groß)
- Für Tests benötigte Einzelbilder kommen nach `tests/fixtures/`, Templates nach `assets/`
- Bilderkennung wird zuerst offline gegen diese Aufnahmen getestet, bevor Daniel im Spiel testet

## Code-Stil

- **Keine Kommentare** in Code- und Config-Dateien. Erklärungen für KI gehören in `docs/`
- Kleine Module mit einer klaren Aufgabe (Bildschirm lesen, Eingabe, States, Config, Hotkey)
- **Kein Bloat:** nur schreiben, was für die aktuelle Aufgabe gebraucht wird. Keine spekulativen Abstraktionen, keine ungenutzten Parameter, keine Platzhalter für spätere Features, keine Wrapper ohne Mehrwert, keine doppelte Doku. Weniger Code ist besser. Daniels Tokens nicht verschwenden
- Neue Dependencies nur mit Begründung im Commit-Body und Eintrag in `docs/DECISIONS.md`

## Online-Hilfe

- Für Library-Doku (APIs, Versionen, Beispiele) **Context7 MCP** verwenden, bevor du aus dem Gedächtnis schreibst
- Bei spielspezifischen Fragen (Menüs, Tasten, Ablauf) nicht raten, sondern als offene Frage an Daniel zurückgeben oder in den Aufnahmen nachsehen

## Git & GitHub

- Du darfst selbst committen und pushen
- Kleine, zusammenhängende Commits: ein Commit = eine logische Änderung
- Format **Conventional Commits**, Betreff auf Deutsch, Imperativ, max. 72 Zeichen:
  - `feat:` neue Funktion
  - `fix:` Fehlerbehebung
  - `refactor:` Umbau ohne Verhaltensänderung
  - `docs:` nur Doku
  - `test:` Tests
  - `chore:` Setup, Config, Dependencies, Tooling
  - `perf:` Performance
  - optional Scope: `feat(flight): Route zur Zone als Wegpunkte`
- Body (wenn nötig): **warum** die Änderung, nicht nur was. Für einen Menschen ohne Kontext verständlich
- Kein `--force`-Push, keine Umschreibung der History auf `main`, keine Secrets/Tokens committen
- Vor jedem Commit: Linter und Tests laufen lassen, nur committen wenn grün

## Public Repo: was nie gepusht wird

Das Repo ist **öffentlich**. Vor jedem Commit `git status` prüfen und nur Dateien committen, die zum Programm gehören.

- Nie committen: virtuelle Umgebungen, Caches, Build-Ordner, Logs, Debug-Screenshots, Aufnahmen (`recordings/`, `*.mp4`, `*.mkv`), `.env`, `config.local.yaml`, IDE-Ordner (`.idea/`, `.vscode/`), `.claude/settings.local.json`
- Keine persönlichen Daten: keine Steam-Namen, Spielernamen, lokalen Pfade (`C:\Users\...`), E-Mails, Tokens, Keys
- Persönliche Einstellungen gehören in `config.local.yaml` (ignoriert), `config.yaml` enthält nur neutrale Standardwerte
- Screenshots für `assets/` und `tests/fixtures/` auf den relevanten Ausschnitt zuschneiden, sodass keine Spielernamen, Chat oder Killfeed sichtbar sind
- `.gitignore` gleich beim Setup vollständig anlegen und bei neuen Datei-Arten erweitern
- Ist etwas versehentlich committet worden: sofort Daniel melden, nicht selbst die History umschreiben

## Dokumentation

Nach jeder Aufgabe aktuell halten:

| Datei | Inhalt |
|---|---|
| `README.md` | Was das Programm macht, Installation, Start, Hotkeys, Config-Optionen |
| `CHANGELOG.md` | Pro Änderung ein Eintrag unter `## [Unreleased]` (Keep a Changelog, Deutsch) |
| `docs/ARCHITECTURE.md` | Module, Layer/State Machine (Mermaid), Datenfluss |
| `docs/DECISIONS.md` | Entscheidungslog: Datum, Entscheidung, Grund, verworfene Alternativen |
| `docs/TESTING.md` | Manuelle Test-Checkliste für Daniel pro Layer/State |
| `docs/RECORDING.md` | Welche Aufnahmen Daniel pro Map machen soll und wie |

Doku-Änderungen kommen in denselben Commit wie der zugehörige Code, reine Doku-Updates als `docs:`.

## Abschluss jeder Aufgabe

Kurz zurückmelden (für Daniel, einfache Sprache):

1. Was wurde gemacht (2–4 Punkte)
2. Commits (Hash + Betreff)
3. **Was Daniel im Spiel testen soll** – konkrete Schritte und erwartetes Ergebnis
4. Offene Fragen / bekannte Grenzen
