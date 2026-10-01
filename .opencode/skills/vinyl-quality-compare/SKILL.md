---
name: vinyl-quality-compare
description: Compara qualidade de JSONs de vinis (original, v2, KFPS) com a mesma métrica RMSE e lado a lado
license: MIT
compatibility: opencode
metadata:
  area: evaluation
  project: FM_Painter
---

# Vinyl Quality Compare

Use ao comparar qualidade entre geradores (app original × FM_Painter × KFPS).
Comparação justa exige **mesmo rasterizador e mesma métrica** — nunca comparar os
campos `score` gravados nos JSONs (cada ferramenta usa uma escala: ~0.41 no app
antigo, ~0.087 no KFPS, RMSE normalizado no v2).

## Passo 1 — Renderizar todos com o mesmo motor

Usar `src/post.py:render_all` (rasterizador numba do projeto) para cada JSON.
Loader deve ser tolerante (ver skill `forza-json-contracts`):

- Pular shapes `type != 16` e `hidden`.
- Aceitar `data` em float (KFPS) e fundo `type:1` ausente (finais KFPS).
- Canvas nativo 1024×1024 com máscara alpha do PNG (`alpha > 10`).
- Nossos JSONs vivem em espaço com crop: reembbedar no canvas cheio via
  offset de `image.load_target` (`stats["crop"]`) — sem reamostrar.

Ferramentas prontas: `tools/compare3.py --n 500|1000|3000` (3 vias) ou
`tools/render_old.py --n <N>` (app original × v2).

## Passo 2 — Métrica única

RMSE mascarado (transparente ignorado), recalculado do zero para cada render:

```
d = target.astype(float32) - render.astype(float32)
rmse = sqrt(mean(d[mask]**2) / 255**2)
```

Reportar também: contagem real de desenháveis (arquivos antigos têm N−1, ex.
`.1000.json` com 999; KFPS pode podar o final, ex. 3000→2982) e distribuição
de alphas.

## Passo 3 — Artefatos

Por comparação, salvar em `output/comparacao[_<tag>]/`:

- `<lado>_<N>.png` por gerador (fundo quadriculado no transparente).
- `lado_a_lado.png`: original + renders na mesma altura, com RMSE no rótulo.
- `metricas.txt`: shapes, canvas, scores gravados (só referência) e RMSE recalculado.

## Armadilhas

- Preview do app durante a geração ≠ render final (ex.: print do KFPS em 2315/3000).
- `output/` é ignorado no git — comparações são descartáveis por design; para
  registrar um resultado, copiar `metricas.txt` + `lado_a_lado.png` para fora
  antes de limpar.
