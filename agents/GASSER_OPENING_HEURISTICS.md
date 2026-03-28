# Gasser (1996): opening search vs. heuristics — notes for this repo

**Source:** Ralph Gasser, *Solving Nine Men’s Morris*, in *Games of No Chance*, MSRI Publications Volume 29, 1996. Use this file when implementing opening books or leaf evaluation so design choices match what the literature actually did.

## What the solved system used (not a classical eval)

Gasser’s **opening** stage does **not** rely on a hand-tuned polynomial heuristic at leaves. It uses:

- **18-ply alpha-beta** through the placement phase.
- **Leaf evaluation:** **Endgame database lookups** (retrograde analysis), not material/mobility features.
- **Database subset / bounds:** When full DBs did not fit RAM, they used mainly **9-9, 9-8, 8-8** and a two-pass argument (upper/lower bound) to prove the start is a **draw**.
- **Transposition table:** Tuned for **disk I/O** — in their setup, TT entries at **16 plies** (Figure 8 in the paper), not “every depth by default.”
- **Practical opening cache:** **All 8-ply positions** visited by the two α–β passes were stored so real-time play could **search to that layer** for the first eight plies; only a small fraction of 8-ply positions needed actual leaf DB evaluation after pruning.

The paper’s abstract/conclusion stress that Nine Men’s Morris was solved **without** strong **knowledge-based** evaluation in the chess sense: the **knowledge is in databases + search**.

**Implication for us:** A lookup table “like Gasser” at the root means **search + perfect/scored leaves from a DB** (or a bounded substitute). A **pure heuristic leaf** at fixed depth is a **different** design — still valid for a hackathon client, but not a faithful copy of the paper’s opening stage.

## Rule choices documented by Gasser (align client / book with server)

When mirroring Gasser’s assumptions for move generation or book proofs:

- **Double mill in one move:** Only **one** opponent stone may be removed.
- **All opponent stones in mills:** The player may still **remove a stone** (any stone in their implementation).

Confirm the **hackathon server** matches these; `GAME_RULES.md` and `openapi.yaml` remain secondary to observed server behavior.

## If we have no endgame DB yet (Option A, heuristic leaves)

Gasser still gives **indirect** guidance for a **first** static evaluation:

1. **Material / stone difference** — Win rates in the paper correlate with **stone counts**; “more stones are better” is a strong signal.
2. **Do not over-weight “close mills” in the opening** — The paper gives an early position where aggressive mill-closing **loses**; a heuristic must not treat mill closure as universally best.
3. **Move ordering** — The paper suggests **move ordering** may have kept many lines in a **draw**-corridor; use **captures / mill completions / threats / TT move / killers** as in [OPENING_BOOK_OPTION_A.md](./OPENING_BOOK_OPTION_A.md).

### Suggested first-pass feature set (placement-heavy)

| Signal | Role in opening |
|--------|------------------|
| Pieces on board / in hand (material) | Primary; consistent with database statistics in the paper. |
| Closed mills (count) | Positive but **not** dominant (early refutations exist). |
| Two-in-a-row / open mill threats | Core tactical shape in placement. |
| Double threats / forks | Strong when your move generator exposes them. |
| Mobility | Legal placements or neighbor pressure when many moves look equal. |
| Blocked / trapped opponent stones | Secondary. |
| Phase-dependent weights | In **placement-only v1**, emphasize threats + material; omit slide/jump terms until those phases exist. |

### Architecture hook

Structure the evaluator so a **leaf probe** can later call an **endgame database** (or server) without rewriting search — that matches how the solved system behaved.

## Related docs

- [OPENING_BOOK_OPTION_A.md](./OPENING_BOOK_OPTION_A.md) — full build plan (Negamax, TT, book export, tests).
- [GAME_RULES.md](./GAME_RULES.md) — rules cheat sheet for implementers.
