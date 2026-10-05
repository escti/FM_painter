# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui, em formato
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).
Versionamento Semântico: `vX.0.0` (módulo novo), `v0.X.0` (funcionalidade),
`v0.0.X` (ajuste/correção). A versão vigente vive em `src/version.py`
(espelho deste arquivo; `tools/gen.py --version` a exibe).

## [Unreleased]

## [0.2.0] - 2026-10-05

Backend GPU (OpenCL), spill in-game resolvido, entrega sem fundo no app antigo
(formato exato) e métrica fiel. Campeão **v14** (RMSE entregue 0,132).

### Added

- Backend **GPU OpenCL** residente (`src/opencl_backend.py`): scoring/apply/erro
  na GPU (work-group por candidato, linhas coalescidas), fallback CPU;
  `--backend opencl|gpu|auto` (default cpu). `src/scoring.py` (`BatchScores`,
  sem listas de tuplas). 50k/shape ≈18ms (~34× CPU); full-500 @50k em 64s.
- Ferramentas: `tools/to_old_exe.py` + `src/oldexe.py` (serializador **exato**
  do `.exe` antigo), `tools/score_q.py` (RMSE_mask/SSIM/EdgeRMSE/Spill%/LabMAE+Q),
  `tools/simpreview.py` (preview sem máscara), `tools/sweep_post.py`,
  `tools/autopsy.py`, `tools/normalize_for_old_exe.py` (`--check exe|kfps`).
- Scoring: peso de borda (`edgeBoost`), spill penalty (`spillPenalty`),
  `fitInsideBbox`, `fullCanvas`, `maxAspect`, late-small, mutação adaptativa
  (`adaptiveMut`), two-stage (`refineTopK`), luma (`lumaBands`), paleta
  (`paletteColors`), UDF-lite (`udfBoost`/`udfTau`/`areaNorm`), `quantize`.
  Amostragem de candidatos **vetorizada** (`candidates._sample_centers`).
- Testes: `test_g1`, `test_g3`, `test_g5` (paridade CPU×GPU), `test_g7d`
  (round-trip byte a byte do formato `.exe`). 39 no total.

### Changed

- Entrega em **2 arquivos**: app antigo/FH5 **sem fundo** (trilha primária) +
  KFPS/FM8 sem fundo. `postPasses` default → 2; `quantize` alinha busca×entrega
  (o `.exe` grava ints; recuperava ~0,005 no RMSE entregue).
- Score de candidatos ponderado (cor ótima por média ponderada).

### Fixed

- **B1** spill in-game: `spillPenalty` alto → 11,7% → 0,05% (validado in-game).
- **B2** export recortado: entrega aplica o offset do crop; opção full-canvas.
- **B7** import `.exe` antigo: formato exato (CRLF/sem espaços/6 casas) + fundo
  `type:1` é desenhado como retângulo → entregar **sem fundo**.

## [0.1.0] - 2026-09-28

Primeira base versionada: gerador CPU validado + kit de comparação + docs.

### Added

- Gerador hill-climb em `src/` (`profile`, `image` com máscara alpha/autocrop,
  `cpu_backend` numba `nogil+prange`, `candidates` com amostragem guiada por
  erro e schedule grosso→fino, `generator`, `post` com prune diagnóstico +
  refine com aceite global, `render`).
- CLI `tools/gen.py` (`--profile/--stop-at/--post-passes/--preview/--outdir`,
  previews só em checkpoints, contagem de shapes sempre preservada).
- Kit de avaliação: `tools/compare3.py` (original × v2 × KFPS, RMSE mascarado
  + lado a lado), `tools/render_old.py`, `tools/strip_bg.py` (variante sem
  fundo p/ import via KFPS).
- Perfis `bg_off_balanced.ini` e `bg_off_fast_beautiful.ini` (default).
- Testes `tests/test_backends.py` (`python -m unittest discover -s tests -v`).
- Docs: `README.md`, `AGENTS.md`, `melhorias.md` (backlog, incl. GPU OpenCL),
  `bugs.md` (B1–B6 abertos + corrigidos), `.opencode/skills/` (4 skills PT-BR:
  `fm8-import-debug`, `vinyl-quality-compare`, `forza-json-contracts`,
  `vinyl-deliverable-check`).
- Empacotamento: `requirements.txt`, `LICENSE` (MIT), `.gitignore`
  (`output/` ignorado), `.gitattributes`, `src/version.py`.

### Changed

- Export travado em opaco (`opaque_only`): jogos são efetivamente opaco-only
  (auditoria 10.494/10.494 nos JSONs antigos); previews lavrados eliminados.
- Scoring com cor ótima em forma fechada e amostragem focada na área opaca
  (~21% de pixels transparentes não gastam shapes no `efr_logo2_bg_off`).

### Fixed

- GIL presa (~15% CPU) → ~84% com `nogil+prange`.
- Prune com deriva cumulativa (1000→209 shapes) → diagnóstico sem remoção.
- Refine com aceite local (piorava o erro) → aceite global.
- Overflow int16 no mapa de erro → float32.
