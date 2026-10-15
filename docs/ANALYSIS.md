# Videoanalyse (Daten aus `wardogs_daten/`)

Stand 2026-10-15. Grundlage für Detektoren und Layer 1. Alle Koordinaten in Pixeln bei 1920×1080, Ursprung oben links.

## Datengrundlage

| Datei | Inhalt |
|---|---|
| `Video/join+Bakurani.mp4` | 403 s, 60 fps, Map **BAKURANI**, Server Official EU Central #9, 2 komplette Crate-Runden |
| `Video/join+Ozeti.mp4` | 512 s, Map **OZETI**, 1 Fehl-Join (Team nicht wählbar), 2 Runden, 1 Crash in der Base |
| `Video/join+Zestafona.mp4` | 503 s, Map laut Ladebildschirm und Serverliste **OZETI** (Server #80), nicht Zestafona. 3 Runden, 1 Absturz in Bäume mit Tod |
| `Images/*.png` | Kommentierte Screenshots (Dateiname = Kommentar): Kauf-Hinweis, falscher Heli, Crash in der Base, Erste-Hilfe-Symbol, Team ausgegraut → ESC → Leave, Baum-Crash, Warten auf Welt, Leave-Dialog, Raketentreffer |
| `Audio/*.mp3` | Raketenwarnung: nach 0,66 s Dauerpiepen mit **V** Flares werfen (nicht ausgewertet, braucht Audio-Capture) |

Für Zestafona gibt es **keine** Aufnahme. Ozeti A/B haben unterschiedliche Basen (A: Beton/Industrie, bewölkt; B: Wiese, sonnig).

Analyse-Werkzeuge: `tools/overlay_inputs.py` (Tasten), `tools/replay.py` (Layer-1-Timeline), Einzelbilder per `tools/extract_frames.py`. Zwischenergebnisse liegen nur lokal (`debug/`).

## Tasten-Overlay (nur in Daniels OBS-Videos)

- Fläche x 600–1500, y 0–370 (Tasten TAB Q W E R / SHIFT A S D F / CTRL Leertaste + Maus-Grafik). Halbtransparent, gedrückt = gelb gefüllt
- Auslesen: Gelbanteil `min(G,R) − B`, Median über zwei Streifen je Taste (oben und unten, ohne Buchstabe). Gedrückt > 75, losgelassen < 65 (Hysterese). Werte im Spiel klar getrennt (≤ 60 / ≥ 70), nur Ladebildschirme liegen bei 40–70
- Geometrie in `config.yaml` → `overlay` (Ursprung TAB-Füllung `[632, 6]`, Raster `[125, 120]`)
- Maus-Grafik: Punkt im weißen Quadrat = Mausbewegung, linke Taste färbt sich gelb. **Im Flug wird die Maus nicht bewegt** (Bakurani 108–245 s: 0 % Bewegung). Maus nur in Menüs und zu Fuß
- **Das Overlay existiert im Spiel nicht.** Kein Detektor nutzt die Fläche x 600–1500, y 0–370. Dort liegen im Spiel Kompass, Zonen-Status („CONTROL ZONE“, „SAFE ZONE“) und oft der Zonen-Marker. Diese sind in den Videos verdeckt und offline nur eingeschränkt prüfbar

## Phasen pro Video

Zeiten in Sekunden. Tasten B/G aus `*.inputs.jsonl` (aus dem Bild abgeleitet).

| Phase | Bakurani | Ozeti A | Ozeti B |
|---|---|---|---|
| Spielstart, Hauptmenü | 0–30 | 0–12 | 0–6 |
| Serverliste → Join | 33–41 | 18–36, nochmal 78–96 | 6–12 |
| Laden der Map | 42–56 | 42–48, 102 | 18–24 |
| Team-Auswahl | 57–59 | 54–66 (Blau grau, kein Beitritt → ESC → Leave, 72 „Returning to menu“), 108 | 30 |
| Deploy, Spawn | 60–68 | 114–120 | 30–36 |
| Fahrzeughändler (Heli kaufen) | 77–83 | 125–127 | 45–46, 86–87 |
| Zum Heli, Einsteigen (F) | 84–98 | 128–142 | 88–102 |
| Crate kaufen (B → Menü) | 102,1 (103–107) · 252,4 · 394,4 | 143,1 · 342,1 · 504,0 | 103,1 · 247,7 · 370,0 |
| Flug zur Zone | 108–173 · 257–316 | 146–216 · 346–434 | 106–172 · 250–306 · 373–438 |
| Abwurf (G) | 173,7 · 316,4 | 216,2 · 434,8 | 172,3 · 307,0 · 439,4 |
| Rückflug | 174–232 · 317–380 | 217–290 · 435–490 | 173–235 · 307–340 · 440–490 |
| Landung | 232–250 · 380–393 | 490–503 | 235–247 · 490–503 |
| Heli beschädigt (rotes Symbol) | – | 234–300 | 321–340 |
| Crash / Tod | – | ~300 Crash in Base (aus Heli geworfen, Neukauf 311–313) | 341 Bäume → Erste-Hilfe 342–347, F gehalten = aufgeben, Respawn-Countdown 348–352 |

Alle 7 Abwürfe wurden mit „SUPPLIES DELIVERED +$2,500“ belohnt.

## HUD-Elemente → Zustand

Positionen sind bildschirmfest (geprüft über alle 1.420 Sekundenbilder). Templates in `assets/`, Werte in `config.yaml` → `vision`.

| Zustand | Merkmal | Ort | Methode / Schwelle |
|---|---|---|---|
| Im Heli (Z20) | Text „Z20 LAKOTA“ unten rechts | x 1788, y 903 (101×17) | Template `label_lakota.png`, TM_CCOEFF_NORMED ≥ 0,55 (Treffer ≥ 0,7, sonst ≤ 0,3) |
| Palette geladen | weißes „G“-Feld über dem Kisten-Symbol, Zähler „001“ | x 1784, y 921 (26×27) | `badge_g.png` ≥ 0,55. Ohne Kiste fehlen G-Feld und Symbol, Zähler „000“ blass. Vor hellem Hintergrund sinkt der Wert kurz auf ~0,57 → Zustandswechsel erst nach 3 gleichen Messungen (`vision.confirm`) |
| Abwurf erfolgt | G-Feld verschwindet; zusätzlich Hinweis „SUPPLIES DELIVERED“ + „+$2,500“ mittig unter dem Heli, oben rechts „SUPPLIES DELIVERED +$2,500“ | Hinweis x 866, y 806 | `popup_delivered.png` ≥ 0,6, ca. 3–4 s sichtbar |
| Kaufbereich der Base | Hinweis „[B] BUY AMMO / SUPPLIES“ | x 866, y 804 (190×25) | `prompt_buy.png` ≥ 0,6. Erscheint schon im Tiefflug nahe der Base (Ozeti B 239 s), nicht nur am Boden |
| Kaufmenü offen | Titel „GARAGE VENDOR“ (Hauptseite) bzw. „// Garage Vendor / LOGISTICS“ | x 220, y 22 / x 221, y 31 | `menu_garage.png` ≥ 0,8, `menu_logistics.png` ≥ 0,8. Fahrzeughändler („VEHICLE VENDOR“) erreicht nur 0,6–0,7 |
| Gelandet | SPD „00“ und AGL „0“ | SPD rechts x≈862, AGL rechts x≈1126, Zeile y 923–933 | Ziffernleser (siehe unten) |
| Heli beschädigt | Heli-Silhouette in der Lageanzeige rot statt grau | Bereich x 955–966, y 908–932 | Median `R − max(G,B)` ≥ 60 (normal < 20, rot > 120) |
| Spieler tot | Erste-Hilfe-Stern im roten Ring, „GIVE UP [F]“, „[E] CALL FOR HELP“, „TOTAL BRIBE“ | Stern x 926, y 938 (68×68) | `first_aid.png` ≥ 0,65 (Treffer ≥ 0,8) |
| In einer Kontrollzone | Banner „CONTROL ZONE“ oben mittig unter dem Kompass (nur einige Sekunden nach Eintritt), Minimap eingefärbt, Leiste „CONTROL: <Fraktion>“ unter der Minimap, Belohnung „CONTROL ZONE ENTERED +$250“ oben rechts | – | Nicht zuverlässig: Banner kurzlebig und unter dem Overlay, Leiste bleibt auch außerhalb stehen. Bot nutzt stattdessen den Zonen-Marker (siehe unten) |
| Base / Safe Zone | Banner „SAFE ZONE“ oben mittig, Basisfläche auf der Minimap blau | – | nicht verwendet |

Weitere HUD-Teile: Geld oben rechts (`-$7,400 | $226,507`, auch im Flug sichtbar), Steuerhinweise rechts (INTERACT F, CHANGE SEAT O, TOGGLE CAMERA C, FREE LOOK ALT, COLLECTIVE LIFT L-SHIFT, COLLECTIVE DESCENT CTRL, DEPLOY FLARES V, LOCKED L), darunter der eigene Spielername (nie in Fixtures).

### Ziffernleser (SPD, AGL)

- Schrift 11 px hoch, Zeilen y 923–933 (SPD, AGL) und 945–955 (ASL), rechtsbündig, Ziffernabstand ~8,25 px, „1“ schmaler
- Top-Hat-Filter (5×5) hebt die hellen, dünnen Striche vom Hintergrund ab. Erste Ziffer an der rechten Kante (±2 px), weitere jeweils 5–10 px links davon, Abbruch wenn links kaum „Tinte“ (< 6 Pixel > 45)
- Vergleich mit 10 Ziffern-Templates (`digits.png`, 15×9, aus ~2.400 Video-Glyphen geclustert) per Kosinus-Ähnlichkeit, Mindestwert 0,8, sonst `None`
- Ergebnis Videos: lesbar in 92–99 % der Bilder mit HUD, keine Sprünge > 40 m bzw. 60 km/h zwischen Sekunden (also keine Fehllesungen). Laufzeit < 1 ms

## Position und Flugrichtung

| Quelle | Befund | Nutzung |
|---|---|---|
| **Zonen-Marker** (Ring mit „CZ“, innerhalb der Zone „HZ“) | Weltmarker über dem Zonenzentrum mit Entfernung („2.2 km“, „328 m“). Liegt die Zone außerhalb des Bildes, klebt der Marker am Rand (x≈120 links, y 200–550). Gefunden in allen Flügen zur Zone und als Randmarker auf dem Rückweg | Richtung: x-Abstand zur Bildmitte. Nähe: y wächst beim Anflug (Horizont ≈ y 390–420) |
| **HQ-Marker** (hellblaues Quadrat + „HQ“ + Entfernung) | Sichtbar, wenn die Base vor einem liegt (Rückflug, Score 0,8–0,9). Hinter dem Heli nicht gefunden (kein Randmarker erkannt). In den letzten ~20 s vor der Landung nicht mehr gefunden | Richtung zur Base. Ist er nicht sichtbar: nach rechts drehen bis er auftaucht |
| Kompass oben mittig | Kurs als Zahl im Kasten („347 N“, „211 SW“) bei x≈925–995, y≈22–45, Skala alle 15° | Im Spiel lesbar, in den Videos vom Overlay verdeckt → noch nicht genutzt |
| Minimap unten links (x 33–288, y 755–970) | Nordausgerichtet, dreht nicht mit. Spieler-Symbol mittig dreht sich. Stark gezoomt (nur Umgebung), Zonen als Kreise mit Nummern-Icons, Base als blaues Rechteck | nicht genutzt |

Template-Suche für Marker: Graustufen, TM_CCOEFF_NORMED, außerhalb der Maske mit Mittelwert gefüllt (schnell, ~40 ms Zone, ~60 ms HQ für das ganze Bild). Schwelle 0,6 / 0,62. Gegen die Erkennung mit Maske verglichen: Zone 92–144 Treffer bei 3–16 Fehltreffern je Video, HQ 27–31 von 28–33 bei 0–8 Fehltreffern. Halbe Auflösung ist schlechter (verworfen).

**Checkpoint-Ergebnis:** Richtung zum Ziel ist über die Marker bestimmbar (Zone immer, notfalls als Randmarker; HQ sobald voraus). Eine absolute Position gibt es nicht, wird für Layer 1 aber nicht gebraucht: Der Bot fliegt relativ zu den Markern. Höhe über Grund und Tempo kommen zuverlässig aus dem HUD. Unsicher bleibt nur, was das Overlay in den Videos verdeckt (Marker hoch im Bild, Kompass). Das muss im Spiel getestet werden.

## Steuerung (aus Overlay und Bild abgeleitet)

| Taste | Wirkung im Heli | Beleg |
|---|---|---|
| Shift | Kollektiv hoch (steigen). Im Reiseflug fast dauernd gedrückt (58–85 % der Flugzeit) | Steuerhinweis „COLLECTIVE LIFT“ |
| Ctrl | Kollektiv runter (sinken). Vor Abwurf und bei Landung | „COLLECTIVE DESCENT“ |
| W / S | Nase runter (beschleunigen) / hoch (bremsen), nur kurz getippt (Median 0,22 s) | Tempo steigt/fällt danach |
| A / D | Rollen links/rechts, kurze Korrekturen (8–45 Tipps pro Strecke) | – |
| Q / E | Gieren links/rechts. E 0,78 s → Zonen-Marker 351 px nach links; Q 0,23 s → 130 px nach rechts | Marker-Bewegung |
| B | Kaufmenü, nur mit Hinweis „BUY AMMO / SUPPLIES“ | Bild |
| G | Palette abwerfen | Bild |
| V | Flares | Steuerhinweis, Audio-Notiz |
| F | Einsteigen; 7 s halten im Erste-Hilfe-Bildschirm = aufgeben und neu spawnen | Bild-Notiz |

Am Boden bewirkt Gieren nichts (Ozeti A 353–360 s: E gehalten, Marker steht).

## Kaufablauf (Ammo-Palette)

1. B → Menü „GARAGE VENDOR“ mit Kacheln AMMO und LOGISTICS. Das Menü merkt sich die letzte Seite: es kann auch direkt in „LOGISTICS / CRATES“ öffnen (Bakurani 253 s)
2. Kachel LOGISTICS (Klick ≈ 955, 520) → Reiter CRATES / PALLETS (PALLETS ≈ 655, 30)
3. Paletten: 1 Bau (Sandsäcke), **2 AMMO SUPPLY PALLET** (≈ 530, 300, $400, „A large pallet containing 1,800 ammunition supplies“, „Will be destroyed by high-speed impacts (approx. 90m free-fall max.)“), 3 Fässer, 4 gemischt
4. Klick auf die Palette kauft sofort, Menü springt zurück auf die Hauptseite mit „LOGISTICS SLOTS FULL“
5. CONFIRM & EXIT (≈ 1560, 972; in Unterseiten steht dort BACK) → zurück im Heli, G-Feld sichtbar
6. Dauer bei Daniel 1,5–4 s

Klickpositionen in `config.yaml` → `buy.clicks`.

## Flugmuster (aus Overlay-Tasten und HUD, 1 Hz)

| Strecke | Dauer | Tempo Median | AGL Median | Shift | Ctrl | Tipps W / S / A / D / E |
|---|---|---|---|---|---|---|
| Bakurani hin 1 | 70 s | 249 km/h | 130 m | 85 % | 1 % | 14 / 5 / 9 / 19 / 10 |
| Bakurani zurück 1 | 79 s | 216 | 103 | 75 % | 20 % | 25 / 28 / 24 / 29 / 11 |
| Bakurani hin 2 | 64 s | 260 | 64 | 79 % | 5 % | 21 / 21 / 13 / 13 / 5 |
| Bakurani zurück 2 | 78 s | 246 | 50 | 64 % | 16 % | 21 / 44 / 32 / 41 / 1 |
| Ozeti A hin 1 | 73 s | 178 | 52 | 70 % | 12 % | 20 / 26 / 25 / 27 / 6 |
| Ozeti A zurück 1 (beschädigt) | 84 s | 163 | 58 | 0 % | 8 % | 19 / 28 / 24 / 19 / 1 |
| Ozeti A hin 2 | 93 s | 167 | 52 | 30 % | 20 % | 19 / 20 / 12 / 31 / 20 |
| Ozeti A zurück 2 | 69 s | 228 | 57 | 60 % | 28 % | 9 / 21 / 18 / 32 / 2 |
| Ozeti B hin 1 | 69 s | 230 | 58 | 70 % | 8 % | 35 / 39 / 8 / 18 / 1 |
| Ozeti B zurück 1 | 75 s | 213 | 51 | 58 % | 26 % | 22 / 37 / 24 / 45 / 3 |
| Ozeti B hin 2 | 59 s | 253 | 64 | 82 % | 12 % | 19 / 23 / 14 / 20 / 0 |
| Ozeti B hin 3 | 69 s | 228 | 41 | 77 % | 6 % | 36 / 37 / 28 / 31 / 2 |
| Ozeti B zurück 3 | 64 s | 241 | 43 | 59 % | 23 % | 25 / 35 / 27 / 30 / 5 |

„hin“ zählt ab dem B-Druck (inkl. 2–5 s Kaufmenü).

- **Steigen:** Shift 2–3 s nach Menü-Ende, erstes W nach 2–6 s. AGL ≥ 40 m nach 5–17 s, ≥ 80 m nach 11–40 s. Daniel steigt und beschleunigt gleichzeitig
- **Drehen:** wenig Gieren; Kurs meist über kurze A/D-Rollen korrigiert. Nach dem Abwurf Kehrtwende mit E (0,6–5,6 s in 20 s) plus A/D
- **Reiseflug:** 160–260 km/h, tief: AGL-Median 41–130 m, oft 40–60 m
- **Abwurf:** beim Einflug in die Zone, nicht über dem Zentrum. Vorher Ctrl (1–7 s) und S zum Bremsen. Bedingungen beim G-Druck: AGL 37–75 m, 75–284 km/h. Grenze laut Spiel 90 m freier Fall
- **Landeanflug:** letzte 30 s: Tempo von ~290 auf ~35 km/h in ~15 s (S 3–6 s gesamt), Ctrl 12–19 s, AGL von ~50 auf 0 in ~10 s (~5 m/s). Aufsetzen mit 0–35 km/h. Gelandet wird auf freien Flächen nahe dem Fahrzeug-/Garagenbereich der Base, nicht auf einem markierten grünen Feld (in keinem Video zu sehen)

## Ableitungen für Layer 1

- Zustände über Templates und Ziffernleser, nicht über das Overlay
- Ziel Zone = Zonen-Marker, Ziel Base = HQ-Marker; Drehen mit Q/E, bis der Marker mittig ist
- Höhe mit Shift/Ctrl regeln, Tempo mit kurzen W/S-Tipps; Reiseflug etwas höher als Daniel (Standard 100 m) wegen Bäumen
- Abwurf unter 90 m AGL; Erfolg = G-Feld weg, Bestätigung „SUPPLIES DELIVERED“
- Landung im Kaufbereich: Hinweis „BUY AMMO / SUPPLIES“ = nahe genug, dann bremsen und sinken
- Sicherheitsfälle mit Bildmerkmal: Erste-Hilfe-Stern, rotes Heli-Symbol, HUD weg (aus dem Heli geworfen)

## Offene Punkte

- Zestafona fehlt als Aufnahme
- Zonen-Marker „CZ“ vs. „HZ“: Bedeutung unklar (vermutlich außerhalb/innerhalb oder Kontrollstatus). Beide werden als Zonen-Marker behandelt
- Unbekannt: Fällt der Heli ohne Shift im Schwebeflug? Hält er die Neigung nach einem W-Tipp? Regler sind darauf ausgelegt, beides zu messen und nachzuregeln
- Raketenwarnung (Audio) und Flares (V) nicht umgesetzt
- Ob B auch in der Luft funktioniert, ist nicht geprüft (Bot landet vorher)
