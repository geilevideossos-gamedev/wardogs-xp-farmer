# Videoanalyse (Daten aus `wardogs_daten/`)

Stand 2026-10-15. Grundlage für Detektoren und Layer 1. Alle Koordinaten in Pixeln bei 1920×1080, Ursprung oben links.

## Datengrundlage

| Datei | Inhalt |
|---|---|
| `Video/join+Bakurani.mp4` | 403 s, 60 fps, Map **BAKURANI**, Server Official EU Central #9, 2 komplette Crate-Runden |
| `Video/join+Ozeti.mp4` | 512 s, Map **OZETI**, 1 Fehl-Join (Team nicht wählbar), 2 Runden, 1 Crash in der Base |
| `Video/join+Zestafona.mp4` | 503 s, Map **ZESTAFONA** (Server #80). Ladebildschirm und Serverliste zeigen fälschlich „Ozeti“ (Server zeigt nach Rundenende die alte Map). 3 Runden, 1 Absturz in Bäume mit Tod |
| `Images/*.png` | Kommentierte Screenshots (Dateiname = Kommentar): Kauf-Hinweis, falscher Heli, Crash in der Base, Erste-Hilfe-Symbol, Team ausgegraut → ESC → Leave, Baum-Crash, Warten auf Welt, Leave-Dialog, Raketentreffer. Neu am 15.10.: CZ-Marker mit Entfernung, Heli außerhalb/innerhalb des Zonenkreises, HQ in der Zone unsichtbar, SUPPLIES DELIVERED, Landefläche (Auswertung siehe unten) |
| `Images/chat_2026-10-15/01–09` | 01–05 und 07–09 sind Kopien der Bilder oben (gleicher Bildinhalt), 06 ist eine allgemeine Physik-Skizze (Kräfte am geneigten Heli), keine Spieldaten |
| `Audio/*.mp3` | Raketenwarnung: nach 0,66 s Dauerpiepen mit **V** Flares werfen (nicht ausgewertet, braucht Audio-Capture) |

Jede Map hat eine eigene Base (Ozeti: Beton/Industrie, bewölkt; Zestafona: Wiese, sonnig). Die Map wird nie aus Ladebildschirm oder Serverliste abgeleitet (zeigen nach Rundenende die alte Map), Fixture-Namen folgen dem Video.

Analyse-Werkzeuge: `tools/overlay_inputs.py` (Tasten), `tools/replay.py` (Layer-1-Timeline), Einzelbilder per `tools/extract_frames.py`. Zwischenergebnisse liegen nur lokal (`debug/`).

## Tasten-Overlay (nur in Daniels OBS-Videos)

- Fläche x 600–1500, y 0–370 (Tasten TAB Q W E R / SHIFT A S D F / CTRL Leertaste + Maus-Grafik). Halbtransparent, gedrückt = gelb gefüllt
- Auslesen: Gelbanteil `min(G,R) − B`, Median über zwei Streifen je Taste (oben und unten, ohne Buchstabe). Gedrückt > 75, losgelassen < 65 (Hysterese). Werte im Spiel klar getrennt (≤ 60 / ≥ 70), nur Ladebildschirme liegen bei 40–70
- Geometrie in `config.yaml` → `overlay` (Ursprung TAB-Füllung `[632, 6]`, Raster `[125, 120]`)
- Maus-Grafik: Punkt im weißen Quadrat = Mausbewegung, linke Taste färbt sich gelb. **Im Flug wird die Maus nicht bewegt** (Bakurani 108–245 s: 0 % Bewegung). Maus nur in Menüs und zu Fuß
- **Das Overlay existiert im Spiel nicht.** Kein Detektor nutzt die Fläche x 600–1500, y 0–370. Dort liegen im Spiel Kompass, Zonen-Status („CONTROL ZONE“, „SAFE ZONE“) und oft der Zonen-Marker. Diese sind in den Videos verdeckt und offline nur eingeschränkt prüfbar

## Phasen pro Video

Zeiten in Sekunden. Tasten B/G aus `*.inputs.jsonl` (aus dem Bild abgeleitet).

| Phase | Bakurani | Ozeti | Zestafona |
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
| Kaufbereich der Base | Hinweis „[B] BUY AMMO / SUPPLIES“ | x 866, y 804 (190×25) | `prompt_buy.png` ≥ 0,6. Erscheint schon im Tiefflug nahe der Base (Zestafona 239 s), nicht nur am Boden |
| Kaufmenü offen | Titel „GARAGE VENDOR“ (Hauptseite) bzw. „// Garage Vendor / LOGISTICS“ | x 220, y 22 / x 221, y 31 | `menu_garage.png` ≥ 0,8, `menu_logistics.png` ≥ 0,8. Fahrzeughändler („VEHICLE VENDOR“) erreicht nur 0,6–0,7 |
| Gelandet | SPD „00“ und AGL „0“ | SPD rechts x≈862, AGL rechts x≈1126, Zeile y 923–933 | Ziffernleser (siehe unten) |
| Heli beschädigt | Heli-Silhouette in der Lageanzeige rot statt grau | Bereich x 955–966, y 908–932 | Median `R − max(G,B)` ≥ 60 (normal < 20, rot > 120) |
| Spieler tot | Erste-Hilfe-Stern im roten Ring, „GIVE UP [F]“, „[E] CALL FOR HELP“, „TOTAL BRIBE“ | Stern x 926, y 938 (68×68) | `first_aid.png` ≥ 0,65 (Treffer ≥ 0,8) |
| In der Zielzone | Zonen-Marker zeigt „HZ“ statt „CZ“ **oder** Minimap um das Heli-Symbol eingefärbt (Kreis blau, grün, rot oder weiß), eines reicht (Daniel, 17.10.) | Marker: Buchstabenfeld x 6–15, y 9–22 im Template. Minimap: Ring r 12–30 px um x 160, y 862 | HZ/CZ: TM_CCOEFF_NORMED des Buchstabenfelds gegen `marker_zone_hz.png` und `marker_zone.png`, höherer gewinnt (1.940/1.940 Marker richtig, Abstand ≥ 0,28). Minimap: Median-Farbe im Ring, Buntheit `max − min` ≥ 14 (innen 15–47, außen ohne Zone ≤ 10) |
| In einer Kontrollzone (Banner) | Banner „CONTROL ZONE“ oben mittig, Leiste „CONTROL: <Fraktion>“ unter der Minimap, „CONTROL ZONE ENTERED +$250“ oben rechts | – | nicht verwendet: Banner kurzlebig und unter dem Overlay, Leiste bleibt auch außerhalb stehen |
| Höhe über Meer | ASL unter AGL | rechts x≈1126, Zeile y 945–955 | Ziffernleser wie AGL (9/9 Fixtures, 93 % lesbar im Video). Steig-/Sinkrate unabhängig vom Gelände |
| Lageanzeige unten mittig | Heli-Silhouette fest; zwei kurze Horizont-Striche links/rechts kippen mit der **Querneigung**; die Bögen links/rechts sind weiß oben bei Shift, weiß unten bei Strg (= **Kollektiv**) | x 880–1040, y 880–975 | nicht verwendet: Mittelwert der Horizont-Striche bleibt bei 0, 300 km/h und Vollbremsung gleich (y ≈ 65 im Ausschnitt) → **Nickwinkel ist nicht ablesbar** |
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
| **Zonen-Marker** (gelber Ring mit „CZ“, innerhalb der Zone „HZ“) | Weltmarker über dem Zonenzentrum mit Entfernung darüber. **CZ-Entfernung = Abstand zum Zonenrand** (fällt beim Anflug auf ~0), **HZ-Entfernung = Abstand zur Zonenmitte** (166–323 m beim Eintritt, also Radius ~170–330 m). Nach dem Verlassen zählt CZ wieder ab 0 hoch. Anzeige springt nur 1× pro Sekunde. Liegt die Zone außerhalb des Bildes, klebt der Marker am Rand (x≈120 links, y 200–550) | Richtung: x-Abstand zur Bildmitte. Bremsen: CZ-Entfernung (Median der letzten Lesungen) |
| Entfernung am Marker | Text „744 m“, „1.6 km“, „3 km“ zentriert über dem Marker, weiß mit dunklem Rand, 10 px hoch, Ziffernabstand 8 px. Formate `d m`, `dd m`, `ddd m`, `d km`, `d.d km` | Leser: Glyphen 0–9 . k m (`distance_glyphs.png`, aus 53 von Hand gelesenen Video-Ausschnitten). Pro Format Glyphen an festen Positionen (zentriert, ±1 px) per TM_CCOEFF_NORMED, Format mit größter Summe `score − 0,7` gewinnt, schwächste Glyphe ≥ 0,6. Ergebnis: Code = Analyse in 1.930/1.940 Markern, ~3 % Fehllesungen (fehlende führende „1“, 6/8/9) → im Regler nur gefiltert nutzen |
| **HQ-Marker** (hellblaues Quadrat + „HQ“ + Entfernung) | Sichtbar, wenn die Base vor einem liegt (Rückflug, Score 0,8–0,9). Hinter dem Heli nicht gefunden (kein Randmarker erkannt). In den letzten ~20 s vor der Landung nicht mehr gefunden | Richtung zur Base. Ist er nicht sichtbar: nach rechts drehen bis er auftaucht |
| Kompass oben mittig | Kurs als Zahl im Kasten („347 N“, „211 SW“) bei x≈925–995, y≈22–45, Skala alle 15° | Im Spiel lesbar, in den Videos vom Overlay verdeckt → noch nicht genutzt |
| Minimap unten links (x 33–288, y 755–970) | Nordausgerichtet, dreht nicht mit. Spieler-Symbol mittig (x 160, y 862). Stark gezoomt, Zonen als große eingefärbte Kreise mit hellem Rand (größer als die Minimap, innen ist die ganze Karte getönt), Base ebenfalls blau getönt, kleine gelbe Ringe = andere Objekte. Färbung beginnt 0–12 s **vor** dem HZ-Wechsel, auch Base und andere Zonen färben | nur zusammen mit HZ: „in der Zielzone“ |

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

Am Boden bewirkt Gieren nichts (Ozeti 353–360 s: E gehalten, Marker steht).

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
| Ozeti hin 1 | 73 s | 178 | 52 | 70 % | 12 % | 20 / 26 / 25 / 27 / 6 |
| Ozeti zurück 1 (beschädigt) | 84 s | 163 | 58 | 0 % | 8 % | 19 / 28 / 24 / 19 / 1 |
| Ozeti hin 2 | 93 s | 167 | 52 | 30 % | 20 % | 19 / 20 / 12 / 31 / 20 |
| Ozeti zurück 2 | 69 s | 228 | 57 | 60 % | 28 % | 9 / 21 / 18 / 32 / 2 |
| Zestafona hin 1 | 69 s | 230 | 58 | 70 % | 8 % | 35 / 39 / 8 / 18 / 1 |
| Zestafona zurück 1 | 75 s | 213 | 51 | 58 % | 26 % | 22 / 37 / 24 / 45 / 3 |
| Zestafona hin 2 | 59 s | 253 | 64 | 82 % | 12 % | 19 / 23 / 14 / 20 / 0 |
| Zestafona hin 3 | 69 s | 228 | 41 | 77 % | 6 % | 36 / 37 / 28 / 31 / 2 |
| Zestafona zurück 3 | 64 s | 241 | 43 | 59 % | 23 % | 25 / 35 / 27 / 30 / 5 |

„hin“ zählt ab dem B-Druck (inkl. 2–5 s Kaufmenü).

- **Steigen:** Shift 2–3 s nach Menü-Ende, erstes W nach 2–6 s. AGL ≥ 40 m nach 5–17 s, ≥ 80 m nach 11–40 s. Daniel steigt und beschleunigt gleichzeitig
- **Drehen:** wenig Gieren; Kurs meist über kurze A/D-Rollen korrigiert. Nach dem Abwurf Kehrtwende mit E (0,6–5,6 s in 20 s) plus A/D
- **Reiseflug:** 160–260 km/h, tief: AGL-Median 41–130 m, oft 40–60 m
- **Abwurf:** 0,1–10,8 s nach dem Wechsel CZ → HZ. Vorher Ctrl (1–7 s) und S zum Bremsen. Bedingungen beim G-Druck: AGL 37–75 m, 75–284 km/h. Grenze laut Spiel 90 m freier Fall
- **Nach dem Abwurf:** Daniel bremst fast bis zum Schweben (Zestafona 172 → 179 s: 157 → 38 km/h), dreht mit E und fliegt raus. HZ bleibt 12–28 s nach Eintritt, dann wieder CZ. Der HQ-Marker wurde in keinem der 7 Anflüge erkannt, solange HZ stand; 1–8 s nach dem Rausfliegen ist er da
- **Landeanflug:** letzte 30 s: Tempo von ~290 auf ~35 km/h in ~15 s (S 3–6 s gesamt), Ctrl 12–19 s, AGL von ~50 auf 0 in ~10 s (~5 m/s). Aufsetzen mit 0–35 km/h. Landefläche ist laut Daniel eine rechteckige Grasfläche in der Base (von Mauern umgeben), dort erscheint „[B] BUY AMMO / SUPPLIES“
- **Neigung:** W/S verstellen die Neigung, sie bleibt nach dem Loslassen stehen. Netto-Tippzeit W − S im Reiseflug schwankt stark (−0,2 bis +3,4 s bei 250–300 km/h), taugt also nicht als Neigungsmaß. Messbar ist die Folge: Bakurani 133–163 s mit Shift dauernd gedrückt, 250–317 km/h → ASL sinkt von 232 auf 113 m (~4 m/s). Bei ~200–250 km/h hält Shift die Höhe. **Sinkt der Heli trotz Shift, ist die Nase zu weit unten** (Daniel: ~20° + Shift = Höhe konstant)

## Offline-Abgleich der Zonen-Erkennung (`tools/replay.py`, `pytest -m videos`)

Marker und Minimap mit 2 Bildern/s, Bestätigung 3 Bilder in Folge, Bremsen bei Median der letzten 5 CZ-Entfernungen ≤ 400 m.

| Video | Abwürfe (Daniel) | „In der Zone“ erkannt | Bremspunkt |
|---|---|---|---|
| Bakurani | 173,7 · 316,4 | 173,5–195,0 · 321,0–340,5 | 169,5 (4 s vor Eintritt) · keiner |
| Ozeti | 216,2 · 434,8 | 213,0–225,5 · 428,0–442,0 | keiner · keiner |
| Zestafona | 172,3 · 307,0 · 439,4 | 165,5–194,5 · 305,5–327,0 · 436,0–456,0 | 164,0 (6 s vor Eintritt) · keiner · keiner |

Seit 17.10. gilt „HZ **oder** Minimap ab Bremspunkt“: Zestafona 165,5 statt 170,0 s (Heli schon im blauen Kreis, HZ kam später), alle anderen Eintritte unverändert (±0,5 s)

- Alle 7 Abwürfe liegen in einem erkannten Besuch. Bakurani 316,4: Daniel warf 0,1 s nach dem HZ-Wechsel ab, die Erkennung kam 4,6 s später (Marker unter dem Overlay)
- HQ-Marker nie zusammen mit HZ, nach dem Verlassen 0–7,5 s bis zum ersten HQ-Treffer
- Bremspunkte nur in 2 von 7 Anflügen: Die Entfernung steht knapp über dem Marker und damit in den Videos meist unter dem Overlay-Rand (y ≤ 370); Marker gefunden, Entfernung `None`. Im Spiel ohne Overlay zu prüfen (TESTING Layer 1, Schritt 0)

## Querneigung und HQ-Entfernung (17.10.)

- **Querneigung:** Die zwei Horizont-Striche der Lageanzeige liegen auf einer Geraden durch (959, 945), Radius 47–58 px. Sie kippen mit der Querneigung; D kippt nach rechts (+), A nach links. Die Neigung bleibt nach dem Loslassen stehen und driftet langsam (Zestafona 148–163 s: von −2° auf −8°). Antwort auf isolierte Tipps (Overlay): 0,1–0,2 s → 0–8°, 0,3 s → 5–8°, 0,5 s → 13–16°, 1,0 s → 29–37°, Wirkung ~0,3 s verzögert. `pytest -m videos` prüft das für alle drei Videos
- **HQ-Entfernung:** steht rechts neben dem HQ-Marker („3.4 km“, „759 m“), grau auf hellem Himmel, schlechter lesbar als die CZ-Entfernung. Daniels erstes Strg im Landeanflug: Bakurani 233 s (letzte Werte 818/839 m bei ~285 km/h), 375 s (751 m), Zestafona 221 s (828/742 m) → Landeanflug ab ~700 m
- **Basis auf der Minimap:** Über der Base liegt das Heli-Symbol in einem blau eingefärbten Quadrat; `minimap_in_zone` ist dort `True` (Bakurani ab 236 s, Landung 251 s)

## Nachdrehen nach Q/E (17.10.)

Marker-x mit 10 Bildern/s nach isolierten Q/E-Tipps (Overlay-Zeiten):

| Video | Tipp | Verlauf |
|---|---|---|
| Zestafona 116,9–117,23 s | Q 0,33 s, 44 km/h | Marker 770 px bewegt sich erst ab ~117,3 s, Spitze ~200 px/s bei 117,7–118,0 s, steht bei ~119,1 s auf 984 px (+216 px) |
| Ozeti 155,3–155,8 s und 156,2–157,0 s | E 0,43 s + 0,8 s, 30–47 km/h | 1630 → 660 px; nach dem Loslassen bei 157,0 s noch 0,7 s mit ~560 px/s, dann Auslauf bis ~159 s |

Modell (Ausgleichsrechnung auf Zestafona, mittlere Abweichung 2,3 px bei 16,8 px/°): Totzeit 0,3 s, Anlauf (Tiefpass) 0,2 s, Auslauf 0,5 s, Enddrehrate 40°/s. Gesamtdrehung ≈ 40° pro Sekunde Tastendruck, nach dem Loslassen dreht der Heli noch ~1 s weiter. Angeheftete Marker: Liegt das Ziel außerhalb des Bildes, klebt der Zonen-Marker am Rand (x ≈ 120 bzw. 1800, Screenshots 015014, 015543). Bildtakt des Bots mit Marker-Suche ~7 Bilder/s (Marker-Suche ~71 ms).

## Daniels Screenshots vom 15.10. (Dateiname = Erklärung)

| Bild | Befund | Folge für den Bot |
|---|---|---|
| „das golden ct ist imme die richtung …“ | Goldener CZ-Marker mit „2.9 km“ beim Start in der Base, Hinweis „[B] BUY AMMO / SUPPLIES“ im Bild | Richtung = CZ-Marker, Entfernung lesen (`zone_marker().distance`) |
| „heli symbol nicht im kreis …“ (= chat 01, Zestafona 163 s) | Heli-Symbol knapp außerhalb eines weißen Zonenkreises, noch CZ | weiter Richtung CZ |
| „auf der minimap sollte das heli symbol …“ (Zestafona 166 s) | Heli im blauen Kreis, Marker zeigt HZ | Zone erreicht = Minimap eingefärbt **und** HZ, dann 3 s warten, dann G |
| „umdrehen sobald supplys deliverd …“ (= chat 04) | „SUPPLIES DELIVERED +$2,500“ unter dem Heli und oben rechts | nach der Bestätigung umdrehen |
| „sobald abgworfen und zone sieht man hq …“ (= chat 03, Zestafona 183 s) | Nach dem Abwurf: HZ-Marker mit „100 m“ am Rand, kein HQ-Marker | erst raus aus der Zone, dann HQ suchen |
| „das die landungs zone immer so eine 4eckige grass fläche …“ | Rechteckige Grasfläche mit Mauern in der Base, Anflug mit 188 km/h, AGL 57 | Landen, wo „[B] BUY AMMO / SUPPLIES“ erscheint |
| chat 02 (Baum-Crash) | 215 km/h bei AGL 28 m, 0,1 s vor dem Crash, Heli-Symbol rot | Tempo-Grenze je Höhe und Mindesthöhe im Reiseflug |
| chat 05 (Rakete) | Rotor abgeschossen, Heli-Symbol rot, AGL 75, 204 km/h | Bot stoppt bei rotem Symbol (Layer 1). „W halten, Crash, wie Tod behandeln“ gehört zu Layer 2 |
| chat 06 | Physik-Skizze: geneigter Rotor teilt Auftrieb in Hub und Vortrieb | erklärt „20° + Shift = Höhe konstant“ |

Für spätere Layer (nur vermerkt): chat 07 Team-Auswahl, Blau links (Layer 3); chat 08 „Waiting for world to load“, weiß oben, nichts drücken (Layer 3); chat 09 Dialog „Leave match?“ mit „Yes“ nach Esc (Layer 4).

## Ableitungen für Layer 1

- Zustände über Templates und Ziffernleser, nicht über das Overlay
- Ziel Zone = Zonen-Marker, Ziel Base = HQ-Marker; Drehen nur mit Q/E (nach ein paar Metern Steigen), bis der Marker mittig ist
- Höhe nur über die Shift-Dauer regeln (Strg nur bei der Landung). Tempo mit W/S-Tipps nach Beschleunigung. Neigungsgrenze: sinkt der Heli trotz Shift (ASL-Rate), Nase hoch (S)
- Sicherheit: Mindesthöhe im Reiseflug (Standard 80 m), Höchsttempo abhängig von der AGL. Darunter erst Shift und Nase hoch, nie weiter beschleunigen
- Bremsen vor der Zone über die CZ-Entfernung (Abstand zum Rand), Abwurf 3 s nach „HZ oder Minimap“ (Minimap erst ab Bremspunkt), keine Höchsthöhe (Daniel, 17.10.), Mindesthöhe 30 m; Erfolg = G-Feld weg, Bestätigung „SUPPLIES DELIVERED“
- Danach umdrehen, raus aus der Zone (CZ oder Minimap ohne Färbung), erst dann HQ suchen
- Landung im Kaufbereich: Hinweis „BUY AMMO / SUPPLIES“ = nahe genug, dann bremsen und sinken
- Sicherheitsfälle mit Bildmerkmal: Erste-Hilfe-Stern, rotes Heli-Symbol, HUD weg (aus dem Heli geworfen)

## Offene Punkte

- Weißer Zonenkreis: Minimap-Färbung ist dort kaum bunt (Bakurani 172 s: Buntheit 8). Im Spiel (Test 17.10.) blieb er weiß, die Erkennung kam erst 25 s später. Helligkeit taugt nicht als Ersatz: Ring-Grauwert halb im weißen Kreis 75 (Bakurani 172 s, Zestafona 164 s: 63), außerhalb von Zonen auf Ozeti bis 86 (helle Felder, 2 Bilder/s über das ganze Video), Kontrast und Sättigung ebenso überlappend. Daher reicht seit 17.10. HZ allein; der weiße Kreis selbst wird nicht erkannt
- Wie viel Grad ein W-Tipp (0,2 s) Nicklage ergibt, ist unbekannt. Annahme 4–5°, `flight.max_tilt` 3 Tipps ≈ 12–15°
- Drehrate von Q/E gemessen (Abschnitt „Nachdrehen nach Q/E“); im Spiel mit dem Bot noch zu bestätigen
- Wie viele W-Tipps „20°“ sind, ist unbekannt; der Regler misst stattdessen Beschleunigung und Sinkrate
- Raketenwarnung (Audio) und Flares (V) nicht umgesetzt
- Ob B auch in der Luft funktioniert, ist nicht geprüft (Bot landet vorher)
