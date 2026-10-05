# AGENTS.md — FM_Painter

CPU/OpenCL image→shapes generator whose JSONs are imported into Forza games.
Run sessions with cwd at the repo root — project skills (`.opencode/skills/`)
only resolve when the working directory is inside this worktree.

## Routing (lazy-load — do NOT read everything upfront)

- Generating, comparing, or importing vinyls? Load the matching skill first:
  `vinyl-deliverable-check`, `vinyl-quality-compare`, `forza-json-contracts`,
  `fm8-import-debug` (via the `skill` tool).
- Planning, resuming work, or deciding a track? Then read `ESTADO.md`
  (state + pending decisions) plus `melhorias.md`/`bugs.md` as needed.
- Trivial tasks (run tests, small fix)? This file alone is enough.
- End of significant work: update `ESTADO.md` (date, results, decisions),
  then commit.

## Tmp scratch (gitignored, pre-approved — no need to ask)

- `tmp/` is the session scratch repo: freely read/write/delete without approval.
  Already gitignored (see `.gitignore`); never commit, never store deliverables
  there (`output/` holds artifacts, repo holds code). Never store secrets.
- End of significant work (or when files go obsolete): delete what's obsolete;
  keep `tmp/` empty/small. If a file must survive, move it to `output/` or the
  repo with a real name instead of leaving it in `tmp/`.

## Boundaries (do not cross)

- All code lives in `FM_Painter/`. Never write outside it.
- `../imagens_originais/`, `forza-painter.exe`, KFPS installs are
  **reference inputs — read-only**. Never modify, move, or "fix" them.

## Commands (always run from `FM_Painter/`)

- Tests: `python -m unittest discover -s tests -v` (40 testes, ~3s)
- Generate (CPU): `python tools/gen.py "<abs-image>" --profile profiles/bg_off_fast_beautiful.ini --stop-at 500`
- Generate (GPU, config de referência H0.1): `python tools/gen.py "<abs-image>"
  --profile profiles/gpu_500.ini` (~4–5 min/500 na RX 9070 XT; **teto 10 min/500**).
  Equivale a `--backend opencl --random-samples 400000 --refine-top-k 32
  --mutated-samples 2000 --mutation-rounds 6 --fit-inside --spill-penalty 1000000
  --post-passes 2`.
- Entregáveis (2 arquivos): `python tools/to_old_exe.py <nosso.json> --out
  output/for_old_exe/<nome>.nobg500.json --orig-w 1024 --orig-h 1024 --off 0,4
  --total 500` (app antigo/FH5, SEM fundo = primário) e
  `python tools/strip_bg.py <nosso.json> output/for_kfps/<nome>.500.json` (KFPS).
- Avaliar métrica fiel (RMSE/SSIM/EdgeRMSE/Spill%/LabMAE+Q): `python tools/score_q.py`
- Preview sem máscara (obrigatório no entregável): `python tools/simpreview.py <json>`
- Diagnóstico: `python tools/sweep_post.py`, `python tools/autopsy.py`
- 3-way compare: `python tools/compare3.py --n 500|1000|3000`
- Long runs are normal (timeout ≥30 min). GPU @400k ≈ 4–5 min/500.
- Shell is PowerShell 5.1: in `python -c`, use forward slashes in paths
  (backslash paths crash with `unicodeescape` SyntaxError).

## Environment (verified 2026-09-28 / 2026-10-05)

- Python 3.14.4, Pillow 12.3, numpy 2.5.3, numba 0.67, PyOpenCL 2026.1 (AMD RX 9070 XT / gfx1201).
- `requirements.txt` inclui `pyopencl` (GPU é opt-in via `--backend opencl`).

## Numba rules (learned the hard way)

- `@njit` **without** `nogil=True` serializes `ThreadPoolExecutor` on the GIL (~15% CPU).
  Parallel entry is `score_batch_parallel_nb` (`parallel=True` + `prange`); set threads via
  `generator.resolve_workers` (calls `numba.set_num_threads`).
- Pixel diffs must be **float32** — int16 overflows on `(tr-cr)**2` (see `candidates.error_tiles` fix).
- First call compiles; don't benchmark cold runs.

## JSON contracts (game-facing — breaking these breaks imports)

Full detail: skill `forza-json-contracts` (atualizada in-game 2026-10-05).

- **App antigo/FH5 (trilha primária):** entrega **SEM fundo** (`type:1`), formato
  **exato** (CRLF; `{"type":T, "data":[i..],"color":[i..],"score":S}` sem espaço
  após `data`/`color`; `score` 6 casas), `data`/`color` **inteiros**, coords no
  canvas cheio (somar offset do crop). `bad json.dump` com espaços → "Malformed".
  O app **desenha** o `type:1` como retângulo preto → nunca incluir p/ bg_off.
  Gerar com `tools/to_old_exe.py` (`src/oldexe.py`).
- **KFPS/FM8 (alternativa):** sem `type:1`; desenháveis == camadas do template
  (`tools/strip_bg.py`).
- Todos alpha 255 (`opaque_only`); `score` é cosmético (B3).
- Contagem **exata** (N = camadas); o pós (`src/post.py`) nunca muda N.
- `quantize` (default on) arredonda o shape aceito → busca == entrega (o `.exe`
  grava ints; sem isso o JSON entregue perdia ~0,005).

## Mask semantics (source of B1 — read before touching scoring/render)

- Transparent PNG pixels têm peso 0 no scoring e são pulados por `apply_*`.
- O jogo **não tem máscara**: shapes que invadem o transparente viram tinta
  in-game. Por isso `spillPenalty` alto (ex. 1e6) e sempre validar com
  `tools/simpreview.py` (mask-off, obrigatório no entregável).
- O gerador trabalha no espaço **recortado**; a entrega aplica o offset do crop
  (`to_old_exe --off`).

## Profiles

- Section-less `.ini` (`profile.py` injects `[profile]`); `saveAt` drives checkpoints.
- `bg_off_fast_beautiful.ini` is current default; `float` keys (`redundantTol`) parse separately.
