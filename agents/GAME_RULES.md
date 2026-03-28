# Nine Men’s Morris — rules cheat sheet (for implementers)

Use this when coding **move generation** and **evaluation**. Exact edge cases must match the **server**; treat discrepancies as bugs in the client.

## Equipment

- Board: **24 points** (intersections), usually arranged as three concentric squares connected at midpoints.
- Each player has **9 stones**.

## Phases (typical flow)

1. **Placement:** Players alternate placing stones on empty points until each has placed all nine.
2. **Movement:** After all stones are placed, players alternate **moving one stone** along a board line to an **adjacent empty** point.
3. **Flying (optional rule):** When a player has only **three stones** left, some rule sets allow moving to **any empty** point instead of only adjacent. **Confirm whether the hackathon server uses flying** via behavior or documentation; implement accordingly.

## Mills

- A **mill** is three own stones in a **straight row** along a line of the board.
- **Completing a mill** usually allows removing one **opponent** stone, with common restrictions:
  - Often cannot remove from an opponent mill **unless** all opponent stones are in mills.
- After a removal, play passes to the opponent (unless the server specifies otherwise).

## Win / loss

- A player **loses** when reduced to **two stones** (cannot form a mill and, in standard rules, cannot move in the movement phase).
- **Draw** handling depends on server rules (repetition, move limits, etc.) — check API state fields and error messages when implementing.

## Client implementation notes

- **Field indexing:** The API uses string indices (`fieldIndex`, `toFieldIndex`). The repo’s canonical **integer** labeling **`0…23`** and line sets are defined in **[`game/board.py`](../game/board.py)** (`ADJACENCY`, `MILLS`, ASCII diagram in-source). Convert strings ↔ ints at the HTTP boundary.
- **Board payload:** `Board` expects server fields **`Index`** and **`Color`** (ints); empty=`0`, white=`1`, black=`2` — confirm against your server.
- **Actions:** The HTTP API exposes `place`, `move`, and `remove` — align with **`Move.type`** and `GameState` in `game/board.py` as logic grows.
