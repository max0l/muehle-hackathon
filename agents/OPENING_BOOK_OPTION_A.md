# Plan: Option A — Eröffnungsbuch aus starker Suche (Python)

## Ziel

Ein Programm soll aus der **Startstellung von Mühle** die besten Eröffnungszüge berechnen und daraus ein **Opening Book** erzeugen. Dazu durchsucht es die Eröffnungsphase mit **Negamax/Alpha-Beta**, speichert besuchte Stellungen in einer **Transposition Table** und bewertet Blattknoten mit einer **Heuristik** oder später optional mit einer externen Endspieldatenbank.

## Arbeitsschritte

### 1. Regeln und Zustandsmodell festlegen

Das Programm braucht eine saubere Repräsentation für:

- Brett mit 24 Punkten
- Spieler am Zug
- Phase: Setzphase, Zugphase, Sprungphase
- noch nicht gesetzte Steine je Spieler
- Steine auf dem Brett je Spieler
- Wiederholungen, falls wir später Remis korrekt behandeln wollen
- Regelvariante für Steinnehmen:
  - Darf man einen Stein aus einer Mühle schlagen, wenn alle gegnerischen Steine in Mühlen sind?
  - Wird bei Doppelmühle nur **ein** Stein entfernt oder **zwei**?

### 2. Brettrepräsentation bauen

Effizient in Python:

- Punkte als Indizes `0..23`
- Adjazenzliste für Nachbarfelder
- Liste aller Mühlen-Kombinationen
- optional Bitboards mit zwei Integern für Weiß/Schwarz

### 3. Zugerzeugung implementieren

Es müssen legal erzeugt werden:

- **Setz-Züge**
- **Schiebe-Züge**
- **Sprung-Züge**
- dazu jeweils die Sonderbehandlung:
  - wenn eine Mühle geschlossen wird, alle legal schlagbaren Steine erzeugen

### 4. Spielstatus prüfen

Funktionen für:

- Mühle erkannt?
- Gewinn/Niederlage erkannt?
- keine legalen Züge?
- weniger als drei Steine?
- Remis/Wiederholung, falls berücksichtigt

### 5. Bewertungsfunktion schreiben

Für Blattknoten außerhalb des Opening Books:

- Materialvorteil
- Anzahl vorhandener Mühlen
- offene Zweierreihen
- Doppel-Drohungen
- Mobilität
- blockierte gegnerische Steine
- potenzielle Mühlen im nächsten Zug
- Phasenabhängige Gewichtung

### 6. Suchalgorithmus

Implementieren:

- **Negamax mit Alpha-Beta**
- **Iterative Deepening**
- **Move Ordering**
  - Mühle schließen zuerst
  - Schlagen zuerst
  - Drohungen
  - Hash-Move zuerst
- Abbruch über Suchtiefe

### 7. Transposition Table

Speichern pro Stellung:

- Hash
- Tiefe
- Score
- Bound-Typ
- bester Zug

Dafür:

- Zobrist Hashing oder deterministischer Stellungs-Hash

### 8. Eröffnungsbuch erzeugen

Ablauf:

- von der Startstellung aus bis zu einer konfigurierbaren Tiefe suchen
- pro Stellung besten Zug speichern
- Ausgabe als JSON oder Pickle
- optional mehrere beste Züge mit Bewertung speichern

### 9. CLI / Benutzung

Beispiel:

- `python muehle_book.py --depth 8 --output opening_book.json`

optional:

- Anzahl Varianten
- maximale Buch-Tiefe
- Debug-Ausgabe

### 10. Tests

Mindestens testen:

- Mühlen-Erkennung
- Legale Züge in allen Phasen
- Schlagen nach Mühle
- Gewinnbedingungen
- Suchalgorithmus auf kleinen Teststellungen
- Konsistenz des Opening Books

## Sinnvolle erste Version

Zuerst eine **Version 1** mit:

- Standardregeln
- nur **Setzphase/Eröffnung**
- Negamax + Alpha-Beta
- Heuristische Bewertung
- Transposition Table
- Ausgabe eines Opening Books für die ersten Züge

Danach erweiterbar um:

- vollständiges Spiel
- Remis durch Wiederholung
- Sprungphase
- bessere Evaluation
- Endspieltabellen

## Unklarheiten vor dem Code

1. Soll das Programm **nur die Eröffnung/Setzphase** abdecken oder das **komplette Spiel** modellieren?
2. Welche **Regelvariante** soll gelten?
   - Bei allen gegnerischen Steinen in Mühlen: darf man dann trotzdem einen schlagen?
   - Bei gleichzeitiger Doppelmühle: ein Stein schlagen oder zwei?
3. Soll das Opening Book als **JSON-Datei** ausgegeben werden?
4. Reicht zuerst eine **heuristische Blattbewertung**, oder soll die Struktur schon so gebaut werden, dass später eine Endspieldatenbank leicht anschließbar ist?
5. Soll das Programm eher **einfach und gut lesbar** oder eher **leistungsorientiert** geschrieben werden?

Sobald diese Punkte geklärt sind, kann die Python-Implementierung darauf aufsetzen.
