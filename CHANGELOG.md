# Changelog

Todas as mudanças notáveis deste projeto são documentadas aqui, em formato
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).
Versionamento Semântico: `vX.0.0` (módulo novo), `v0.X.0` (funcionalidade),
`v0.0.X` (ajuste/correção). A versão vigente vive em `src/version.py`
(espelho deste arquivo; `tools/gen.py --version` a exibe).

## [Unreleased]

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
