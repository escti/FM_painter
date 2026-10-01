# FM_Painter

Gerador de vinis para Forza (FH5/FM8): converte imagens com fundo removido
(`*_bg_off.png`) em formas geométricas importáveis no jogo. CPU (numba) hoje,
GPU (OpenCL) no roadmap — ver `melhorias.md`.

> Status: geração CPU validada contra o app original e o KFPS em 500/1000/3000
> shapes (ver `output/comparacao3_*/` local — pasta ignorada no git).
> Bugs abertos em `bugs.md`; instruções de agente em `AGENTS.md`.

## Requisitos

- Python 3.14 (64-bit) no Windows; testado com Pillow 12.3, numpy 2.5.3,
  numba 0.67 e PyOpenCL (AMD RX 9070 XT).
- Jogo alvo: FH5 via `forza-painter.exe` clássico, ou FM8 via importador KFPS.

## Setup

```
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Todos os comandos abaixo partem da raiz `FM_Painter/`.

## Uso

```
# Gerar (perfil atual: profiles/bg_off_fast_beautiful.ini)
python tools/gen.py "../minha_logo_bg_off.png" --profile profiles/bg_off_fast_beautiful.ini --stop-at 500
# Saída: output/<nome>/<nome>.json (+ .500/.1000 checkpoints) e previews só nos checkpoints

# Pós-processamento configurável: --post-passes 0 (nada) | 1 (refino, default) | 2+

# Remover shape de fundo p/ import via KFPS (contagem exata p/ o jogo)
python tools/strip_bg.py output/<nome>/<nome>.500.json output/for_kfps/<nome>.500.json

# Comparar app original vs v2 vs KFPS (mesma métrica RMSE + lado a lado)
python tools/compare3.py --n 500|1000|3000
```

Runs longos são normais (1000 ≈ 6 min, 3000 ≈ 16 min + pós) — use timeout ≥30 min.

## Layout

```
src/         profile.py (parser .ini sem seção) · image.py (máscara alpha/autocrop)
             cpu_backend.py (scoring numba nogil+prange) · candidates.py (amostragem guiada)
             generator.py (loop hill-climb) · post.py (prune diagnóstico + refine global)
             render.py (previews) · redundant.py (legado)
tools/       gen.py · compare3.py · compare.py · render_old.py · strip_bg.py
tests/       test_backends.py
profiles/    bg_off_fast_beautiful.ini (default) · bg_off_balanced.ini
output/      gerados — IGNORADO no git
```

## Contratos JSON (quebrar = quebrar o import no jogo)

| Destino | Regras |
|---|---|
| `.exe` antigo (FH5) | 1º shape `type:1` fundo `[0,0,W,H]` + `type:16 [cx,cy,rx,ry,ângulo]` com **inteiros** |
| KFPS (FM8) | sem fundo (`strip_bg.py`), contagem **exata** das camadas do template |
| Ambos | alpha sempre 255; contagem entregue = camadas do template no jogo |

Detalhes e armadilhas (máscara, spill in-game, coordenadas): `AGENTS.md`.

## Importar no jogo

1. Template com N esferas/círculos = N shapes do JSON, **desagrupado**.
2. FH5: arraste o `.json` (com fundo) no `forza-painter.exe` clássico.
   FM8: importe o `.json` sem fundo pelo KFPS (contagem exata, app como admin,
   sem trocar de menu; após qualquer mudança no template: salvar → sair →
   reabrir → desagrupar → localizar de novo).
3. Valide todo entregável com render **sem máscara** antes do jogo.

## Docs

- `AGENTS.md` — guia do desenvolvedor/agente (comandos, contratos, gotchas numba).
- `melhorias.md` — backlog (GPU OpenCL, two-stage, loss por borda, mutação adaptativa…).
- `bugs.md` — bugs abertos B1–B6 + registro dos corrigidos.

Licença: MIT.
