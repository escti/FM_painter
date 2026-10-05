# FM_Painter

Gerador de vinis para Forza (FH5/FM8): converte imagens com fundo removido
(`*_bg_off.png`) em formas geométricas importáveis no jogo. **CPU (numba) e GPU
(OpenCL)** — a GPU é opt-in (`--backend opencl`, default CPU).

> Status: v0.2.0. Campeão **v14** (RMSE entregue **0,132** / spill 0,05%;
> KFPS 0,135; app antigo 0,161). **Trilha primária de entrega: app antigo
> (FH5 → FM8)**; KFPS é alternativa. Detalhes em `ESTADO.md`; bugs em `bugs.md`;
> guia do agente em `AGENTS.md`.

## Requisitos

- Python 3.14 (64-bit) no Windows; Pillow, numpy, numba e PyOpenCL (AMD RX 9070 XT).
- Jogo alvo: FH5 via `forza-painter.exe` clássico (primário) ou FM8 via KFPS.

## Setup

```
pip install -r requirements.txt
python -m unittest discover -s tests -v   # 40 testes, ~3s
```

Todos os comandos abaixo partem da raiz `FM_Painter/`.

## Uso

```
# Gerar (CPU): perfil default
python tools/gen.py "../minha_logo_bg_off.png" --profile profiles/bg_off_fast_beautiful.ini --stop-at 500

# Gerar (GPU, RX 9070 XT): ~4-5 min/500, teto 10 min/500
python tools/gen.py "../minha_logo_bg_off.png" --profile profiles/gpu_500.ini

# Entregáveis (2 arquivos):
# 1) app antigo / FH5 (primário): SEM fundo, formato exato
python tools/to_old_exe.py output/minha_logo_v15/minha_logo_v15.json \
  --out output/for_old_exe/minha_logo.nobg500.json --orig-w 1024 --orig-h 1024 --off 0,4 --total 500
# 2) KFPS / FM8 (alternativa): sem fundo
python tools/strip_bg.py output/minha_logo_v15/minha_logo_v15.json output/for_kfps/minha_logo.500.json

# Avaliar qualidade (RMSE/SSIM/EdgeRMSE/Spill%/LabMAE + Q) e preview sem máscara
python tools/score_q.py
python tools/simpreview.py output/for_kfps/minha_logo.500.json
```

Runs longos são normais (timeout ≥30 min).

## Layout

```
src/         profile.py · image.py (máscara alpha/autocrop) · candidates.py (amostragem vetorizada)
             cpu_backend.py (numba nogil+prange) · opencl_backend.py (GPU residente) · scoring.py (BatchScores)
             generator.py (loop hill-climb) · post.py (refine global) · edgeweight.py (peso de borda)
             oldexe.py (serializador exato .exe) · render.py · redundant.py (legado)
tools/       gen.py · to_old_exe.py · strip_bg.py · score_q.py · simpreview.py · sweep_post.py · autopsy.py
             compare3.py · compare.py · render_old.py · normalize_for_old_exe.py
tests/       test_backends.py · test_g1.py · test_g3.py · test_g5.py · test_g7d.py
profiles/    bg_off_fast_beautiful.ini (default) · bg_off_balanced.ini
output/      gerados — IGNORADO no git
```

## Contratos JSON (quebrar = quebrar o import no jogo)

| Destino | Regras |
|---|---|
| app antigo (FH5) **primário** | **sem fundo**; formato **exato** (CRLF, sem espaço após `data`/`color`, `score` 6 casas); `type:16 [cx,cy,rx,ry,ângulo]` inteiros; coords no canvas cheio |
| KFPS (FM8) alternativa | sem fundo (`strip_bg.py`); contagem **exata** das camadas |
| Ambos | alpha 255; não incluir `type:1` (o app antigo o desenha como retângulo preto) |

Detalhes e armadilhas (máscara, spill in-game, coords): `AGENTS.md` e skill
`forza-json-contracts`.

## Importar no jogo

1. Template com N esferas/círculos = N shapes do JSON, **desagrupado**.
2. **Primário:** arraste o `.json` **sem fundo** no `forza-painter.exe` clássico
   (FH5) e depois transfira para o FM8. Alternativa FM8: KFPS (sem fundo,
   app como admin; após mudar o template: salvar → sair → reabrir → desagrupar).
3. Valide todo entregável com render **sem máscara** (`tools/simpreview.py`).

## Docs

- `ESTADO.md` — handoff (estado atual, resultados, decisões).
- `AGENTS.md` — guia do desenvolvedor/agente (comandos, contratos, gotchas numba).
- `melhorias.md` — backlog + planos G1–G7 (executado) e H0–H4 (próximo).
- `bugs.md` — bugs e registro dos corrigidos.

Licença: MIT.
