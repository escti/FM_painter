# ESTADO — FM_Painter (handoff entre sessões)

> Última atualização: 2026-10-01. Comece aqui + `melhorias.md` + `bugs.md`.
> Rode as sessões com cwd na raiz do repo (skills só carregam assim).

## Onde estamos

Gerador CPU validado (v0.1.0 no ar em `escti/FM_painter`, branch `main`).
Trilha GPU OpenCL provada viável (PyOpenCL + kernel teste OK na RX 9070 XT),
não implementada. Import FM8 funciona via KFPS; `.exe` antigo só serve ao FH5.
Plano agrupado salvo em `melhorias.md` (G1–G5, ordem G4→G1→G3→G2→G5).
G4 executado em 2026-10-01 sobre o nosso 500
(`output/efr_logo2_bg_off_v4_3000/efr_logo2_bg_off.500.json`):
sweep pós 0/1/2/3 + autopsia (só nosso) — ver seção G4 abaixo.

## Resultados medidos (RMSE mascarado, mesmo rasterizador)

| Shapes | App original | Nosso v2 | KFPS | Artefatos (gitignored) |
|---|---|---|---|---|
| 500 | 0.161 (499 reais) | 0.145 | 0.135 | `output/comparacao3_500/` |
| 1000 | 0.138 (999) | 0.118 | 0.110 | `output/comparacao3_1000/` |
| 3000 | 0.111 (2999) | **0.081** | 0.089 (podou p/ 2982) | `output/comparacao3_3000/` |

Scores gravados nos JSONs usam escalas incompatíveis — nunca comparar diretamente.

## G4 executado (2026-10-01, base: nosso 500)

Ferramentas novas: `tools/sweep_post.py`, `tools/autopsy.py`
(artefatos gitignored: `output/sweep_post_500/`, `output/autopsy_500/`).

- Sweep pós (mesma base, N=500 preservado):
  0→0.14544 (0s), 1→0.14118 (41s, 398/500 melhorados),
  2→0.13963 (68s, +345), 3→0.13864 (99s, +267).
  Sem platô em 2 — ganho cai (0.0043/0.0016/0.0010) mas segue positivo.
  Prune-diagnóstico: 9/500 redundantes (3–5 após refines) — N preservado correto.
- Autopsia: área p50=1345/p99=70222/max=353109; aspecto max 127.5;
  gigante #1 = B1 (`779,1006,858x131`); curva erro×índice com cauda longa
  (+0.002/bloco até o fim); tile de maior residual `(5,7)` tem só 3 shapes
  (correlação densidade×residual 0.205 — sampler mal alocado); paleta ~toda única.
- Item 13: `prune_diagnostic` é O(N²) (500 renders full no 500);
  no 3000 ≈ 36× o custo — especificação da poda por importância estilo-KFPS
  fica para depois do G1 (usa ganho marginal da autopsia).

## Provado in-game (FM8)

- KFPS-500 (gerado por ele): **OK**.
- Nosso-500: **lajes de tinta** fora do desenho (B1) — elipses gigantes invadem
  área transparente, invisível no preview mascarado.
- Ownership 501: template editado ao vivo invalida a hierarquia (B6) — ritual
  é template limpo + salvar → sair → reabrir → desagrupar.

## Decisões pendentes (dono: usuário)

1. **Fix do spill** (`melhorias.md#9`: penalidade + export full-canvas +
   simpreview) — falta aprovar + informar a cor da pintura do carro.
2. **Normalizador KFPS→`.exe`** (`melhorias.md#8`) — aprovar ou não.
3. **Trilha**: (A) adotar KFPS / (B) continuar CPU / (C) híbrida.
4. **Go do backend GPU** + teto de tempo (antes: 1h por bateria).
5. **Resolução 1536** — estacionada (exige 1 import de validação).

## Dependências externas (fora do repo)

- PNGs fonte: `../imagens_originais/` (ex. `efr_logo2_bg_off.png` 1024², 21% transparente).
- KFPS instalado fora do repo (geração GPU + import FM8); `.exe` antigo só FH5.
- Templates no jogo: N esferas/círculos = N shapes, desagrupados.

## Retomar

```
cd D:\GitHub\FM_Painter
pip install -r requirements.txt
python -m unittest discover -s tests -v   # 6 testes, ~2s
python tools/gen.py "<png>" --profile profiles/bg_off_fast_beautiful.ini --stop-at 500
```

Runs longos: 1000 ≈ 6 min, 3000 ≈ 16 min + pós (timeout ≥30 min).
 Powershell 5.1: paths com `\` quebram `python -c` — usar `/`.
