# AGENTS.md — FM_Painter

CPU/OpenCL image→shapes generator whose JSONs are imported into Forza games.
Read `melhorias.md` (backlog) and `bugs.md` (open B1–B6) before planning work.

## Boundaries (do not cross)

- All code lives in `FM_Painter/`. Never write outside it.
- `../imagens_originais/`, `forza-painter.exe`, KFPS installs are
  **reference inputs — read-only**. Never modify, move, or "fix" them.

## Commands (always run from `FM_Painter/`)

- Tests: `python -m unittest discover -s tests -v`
- Generate: `python tools/gen.py "<abs-image>" --profile profiles/bg_off_fast_beautiful.ini --stop-at 500`
- 3-way compare (old/v2/KFPS): `python tools/compare3.py --n 500|1000|3000`
- Render old-app JSON: `python tools/render_old.py --n 500`
- Strip bg for KFPS import: `python tools/strip_bg.py <in.json> <out.json>`
- Long runs are normal (1000 ≈ 6 min, 3000 ≈ 16 min + post) — set timeouts ≥30 min.
- Shell is PowerShell 5.1: in `python -c`, use forward slashes in paths
  (backslash paths crash with `unicodeescape` SyntaxError).

## Environment (verified 2026-09-28)

- Python 3.14.4, Pillow 12.3, numpy 2.5.3, numba 0.67, pyopencl (AMD gfx1201 OK).
- `requirements.txt` is **stale** (missing `pyopencl`) — check `pip list` before assuming deps.

## Numba rules (learned the hard way)

- `@njit` **without** `nogil=True` serializes `ThreadPoolExecutor` on the GIL (~15% CPU).
  Parallel entry is `score_batch_parallel_nb` (`parallel=True` + `prange`); set threads via
  `generator.resolve_workers` (calls `numba.set_num_threads`).
- Pixel diffs must be **float32** — int16 overflows on `(tr-cr)**2` (see `candidates.error_tiles` fix).
- First call compiles; don't benchmark cold runs.

## JSON contracts (game-facing — breaking these breaks imports)

- Old `.exe` (FH5) requires: leading `type:1` bg `[0,0,W,H]` + **integer** `data`/`color`
  (floats → "Malformed or invalid geometry file").
- KFPS counts the `type:1` bg as a visible shape (off-by-one: our 500 counts as 501) —
  use `tools/strip_bg.py` output (`output/for_kfps/`) for the KFPS/FM8 path.
- All shape alphas must be 255 (`opaque_only`); games are effectively opaque-only.
- `score` field is cosmetic (post overwrites per-step scores with final err — see B3).
- Delivered counts must be **exact** (500/1000/3000 = template layers). Post-processing
  (`src/post.py`) must never change N: prune is diagnostic-only, refine needs global acceptance.

## Mask semantics (source of B1 — read before touching scoring/render)

- Transparent PNG pixels have weight 0 in scoring and are skipped by `apply_*`.
- The game has **no mask**: oversized ellipses paint over "transparent" zones in-game
  while previews hide the spill. Validate every deliverable with a mask-off render.
- Export is currently in **cropped** working space (autocrop +1px, B2); target is full-canvas export.

## Profiles

- Section-less `.ini` (`profile.py` injects `[profile]`); `saveAt` drives checkpoints.
- `bg_off_fast_beautiful.ini` is current default; `float` keys (`redundantTol`) parse separately.
