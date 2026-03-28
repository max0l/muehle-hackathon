# Plan: Mid- and endgame table lookup (retrograde analysis + indexing)

This document plans how to **precompute** midgame and endgame **outcomes** (and optionally **distance-to-win**) and serve them via **fast lookup**. It complements [OPENING_BOOK_OPTION_A.md](./OPENING_BOOK_OPTION_A.md) (opening book from forward search) and aligns with the database approach in [GASSER_OPENING_HEURISTICS.md](./GASSER_OPENING_HEURISTICS.md).

## Terminology: “hash” vs indexing

- **Endgame database lookup** needs a **deterministic, collision-free (or injective) map** from a **canonical position** to an **array index** — often called a **perfect hash** or **ranking function**, not a cryptographic hash.
- **Zobrist hashing** is ideal for **transposition tables** during search (small memory, rare collisions). It is **not** sufficient alone as the primary key for a **packed retrograde file** unless you accept collision handling and larger records.
- **Practical design:** build DB files addressed by **dense or near-dense indices**; optionally use **Zobrist on top** only as a cache key in the searcher, with verification by canonical index.

## Goal

- **Input:** A position in **movement phase** (slide moves) and/or **jump phase** (player with three stones flies to any empty point), with **side to move**, consistent with server rules.
- **Output:** **Lookup(value)** — at minimum **win / loss / draw** for the player to move; optionally **ply depth** to terminal.
- **Constraint:** Table size explodes with full Morris midgame; scope **subspaces** (e.g. by stone counts) and **symmetry** from the start.

---

## Phase A — Rules and state model

1. **Freeze rule variants** in code (document bitflags): double-mill removal count, removal when all opponent stones in mills, draw by repetition (if modeled), flying rule threshold (≤3 stones).
2. **Define the minimal state vector** needed for mid/end **retrograde**:
   - Occupancy of **24 points** (empty / white / black).
   - **Side to move.**
   - **Phase flag:** normal slide vs fly-for-player-with-three.
   - **Removal sub-state:** after closing a mill, the game is not in the same “layer” as a normal slide — decide whether to encode “must remove opponent stone” as explicit states or collapse into plies (must match how **predecessors** are generated).
3. **Decide repetition policy for v1:**
   - **Full:** include history or graph draw rules → much larger state graph.
   - **Pragmatic:** omit repetition in DB and treat as **search-time** rule only, or build a **smaller** DB that is still sound for positions where repetition cannot change the class (risky — document assumptions).
4. **List terminal predicates** for the player **to move:** cannot move; fewer than three stones; (optional) draw terminals if encoded.

Deliverable: **state schema** + diagram of plies (place done; only move/remove chains in this DB).

---

## Phase B — Canonical encoding and symmetries

5. **Choose a compact encoding** (e.g. base-3 trits per point for {empty, W, B}, plus flags in separate bits).
6. **Implement the eight symmetries** of the square board (or the five independent axes used in Gasser’s discussion — implement **D4** and verify reduction factor).
7. **Canonicalize:** map every state to a **single representative** (e.g. lexicographically smallest encoding under all symmetries). **Lookup** always **normalizes** first.
8. **Move mapping (optional but important for play):** when the engine queries a non-canonical position, store **symmetry id** or re-derive best move by mapping back from canonical best move.

Deliverable: `canonicalize(state) -> (rep, sym_id)` tested on random positions.

---

## Phase C — Index function (the “hash” for files)

9. **Split the state space into subspaces** by **(white_on_board, black_on_board)** (and phase if needed). Dependencies between buckets follow reachability (similar to Gasser’s Figure 4 idea: compute “smaller” material configs before larger ones where required).
10. **For each subspace**, define an **index function** `index(rep) -> int`:
    - **Combinatorial ranking:** choose positions of white stones, then black on remaining empties; multiply by side-to-move and small flags.
    - Or **enumerate** legal states offline and **assign** indices (slower build, flexible).
11. **Validate injectivity** on a sample: no two legal canonical states share an index.
12. **Reserve “invalid” ranges** if using a loose hash (Gasser allowed a slightly larger range than exact count); mark unused slots so lookup never reads garbage as real.

Deliverable: `index` / `unrank` (optional) with unit tests on small subspaces (e.g. 3–3 fly phase only).

---

## Phase D — Move generation for retrograde

13. **Forward moves:** already required elsewhere — slide/jump, mill closure → removals, terminal checks.
14. **Backward moves (predecessors):** for each state, generate all states that could **lead to it in one full ply** (including undoing a removal and unsliding). This is the error-prone core; **mirror the forward rules exactly**.
15. **Consistency check:** from random states, apply random forward move then **one step backward** should reach a set containing the original (up to symmetry).

Deliverable: `predecessors(state) -> iterable` with tests.

---

## Phase E — Retrograde analysis core

16. **Initialize** database entries:
    - **Loss** for player to move if **no legal move** or **<3 stones** (as encoded).
    - **Win** for positions where the player to move **closes a mill** and can **reduce opponent to two** stones, if those are encoded as immediate wins in your model (match Gasser’s initialization discussion for excluded subspaces).
    - **Draw** seeds if you model forced draws explicitly.
17. **Propagate** using the **counting retrograde** pattern (Gasser Table 2): for each solved state, update predecessors — loss for STM propagates to **win** for opponent predecessor; **win** for STM forces predecessor counts until all successors are wins, then **loss**.
18. **Iteration order:** process subspaces in an order consistent with **backward** reachability (often decreasing material or following a dependency DAG).
19. **Termination:** when no entry changes, remaining “draw” (or unknown) class is fixed.

Deliverable: tiny full solve for a **toy subspace** (e.g. both players 3 stones, fly only, small board variant **or** a hand-traced 10-state graph) before scaling.

---

## Phase F — Storage format and lookup API

20. **Value packing:** at least **2 bits** per position for {loss, draw, win} relative to side to move; **+ depth** if you need distance (more bytes; Gasser merged count/value cleverly during build).
21. **File header:** `magic`, **rule flags**, **subspace id** (e.g. 7–5), **index range**, **symmetry version**, **build git hash / date**.
22. **Runtime API:**
    - `lookup(state) -> Optional[Outcome]`  
    - Path: **normalize** → **index** → **mmap/array slice**.
23. **Optional memory map:** large files via `mmap` for zero-copy read on desktop.

Deliverable: `read_header`, `lookup` under 1 µs per hit target (platform-dependent).

---

## Phase G — Scale, engineering, and verification

24. **Estimate sizes** per subspace before building; **stream to disk** if RAM-bound (retrograde is I/O heavy on full Morris).
25. **Parallelism:** parallelize predecessor batches per layer with care for **write races** to the same index (partition by index ranges or use atomic updates where safe).
26. **Verification:**
    - **Internal:** no index out of range; counts reach zero consistently; all terminals classified.
    - **External:** **forward α–β or BFS** on random positions in small subspaces must agree with DB value.
27. **Integration:** plug into opening search as **leaf oracle** (see Gasser opening) or into client move picker for midgame.

---

## Suggested incremental roadmap (hackathon-realistic)

| Milestone | Scope |
|-----------|--------|
| **M1** | Schema + canonicalization + index for **one** small subspace (e.g. 3–3 jump phase subset). |
| **M2** | Full retrograde for M1 + packed file + `lookup`. |
| **M3** | Add slide moves for **one** material band (e.g. 6–6 down to 4–4) if time; otherwise document as future work. |
| **M4** | Symmetry + dependency-ordered build pipeline for multiple files. |

---

## Related docs

- [GASSER_OPENING_HEURISTICS.md](./GASSER_OPENING_HEURISTICS.md) — how solved-system DBs fed opening search.
- [GAME_RULES.md](./GAME_RULES.md) — rules touchstones (must match server).
- [OPENING_BOOK_OPTION_A.md](./OPENING_BOOK_OPTION_A.md) — forward-search opening book; can use this DB at leaves later.
