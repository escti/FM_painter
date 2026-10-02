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

## G1 executado (2026-10-01, itens 8+9)

Ferramentas novas: `tools/normalize_for_old_exe.py` (+`--check` exe|kfps),
`tools/simpreview.py` (preview sem máscara, backdrop cinza 160 = só fundo,
nunca shape). Núcleo: `spillPenalty` (default 0.0/off) em `_score_one` +
`score_parallel`, `fitInsideBbox` (default off) em candidates,
`fullCanvas` opt-in em `dump_json`/`gen.py` (+flags CLI `--spill-penalty`,
`--fit-inside`, `--full-canvas`). Testes 14/14 OK.
`--check exe --expect 500` passa no nosso 500; simpreview quantificou o B1:
163.724 px de spill (72,3% da área transparente).

- Calibração fatiada (pós, mesma base 500): w=30/300/3000 → RMSE
  0.14118/0.14119/0.14125 vs 0.14118 baseline; spill 163721/163832/163117.
  Pós quase não move o spill (aceite é global-mascarado; gigantes nascem na geração).
- Prova de geração (`--stop-at 100 --spill-penalty 3000`, 41s, sem pós):
  spill 68,1%→**17,9%** (154063→40443 px) por +0,00014 RMSE
  (0,20799→0,20813); maior gigante 353k→152k px.
- Recomendado: `spillPenalty=3000` p/ runs com spill; default segue 0.0 até
  validação full-500. `fit-inside` com mecanismo+teste, sem validação em geração.
  Full-canvas opt-in, sem import de validação ainda.
- Full-500 com multa (`output/efr_logo2_bg_off_v5_spill3000/`, gen 179s + pós):
  RMSE 0.14059 (melhor que 0.14118 do v4) e spill 72,3%→**23,8%**
  (163724→53805 px). Entregáveis: `output/sweep_post_500_w3000/`
  `efr_logo2_bg_off.sweep1.json` (via exe/FH5, check-OK) +
  `output/for_kfps/efr_v5_spill3000.500.json` (via KFPS/FM8, check-OK).
  Bug achado e corrigido no run: `dump_json`/crop vazavam `np.int64`
  (TypeError no save pós-refino) — corrigido com coerção p/ int; resgate via
  `sweep_post --json` do pré-pós salvo. Aguardando import de validação no jogo.
- Full-500 trava+multa v6 (`output/efr_logo2_bg_off_v6_fit_w3000/`, gen 186s):
  RMSE **0.14041** (recorde) e spill 72,3%→**14,9%** (163724→33780 px).
  `@100`: trava só = 19,2% spill + melhor RMSE (0,20727); trava+multa = 7,3%.
  Entregáveis v6: `output/efr_logo2_bg_off_v6_fit_w3000/efr_logo2_bg_off.json`
  (exe/FH5, check-OK) + `output/for_kfps/efr_v6_fit_w3000.500.json`
  (KFPS/FM8, check-OK). KFPS-preview do v5 mostrou resto de spill (lajes
  marrons no topo, ovais cinzas, agulhas, pingo embaixo) — v6 ataca isso.
- Full-500 combo v7 = v6 + teto A=12 (`output/efr_logo2_bg_off_v7_combo/`):
  RMSE 0.14133 e spill 15,2% (34486 px) — **pior que o v6 nos dois**.
  Teto de aspecto ajuda qualidade no 100 mas não derruba spill no 500;
  cinza lavado precisa do G3 (peso de borda estilo UDF, validado na literatura:
  LIVE/CVPR22 `color mean error`, pesos pequenos). **v6 segue o campeão**;
  entregável v7 em `output/for_kfps/efr_v7_combo.500.json` (check-OK) só p/
  comparação no KFPS-preview.
- G3 peso de borda (`src/edgeweight.py`: Sobel + p99, `w=1+k·e`, cor ótima
  ponderada; `edgeBoost` default 0.0 + `--edge-boost`). Testes 23/23 OK.
  Lição: borda SEM máscara de interior premia a silhueta → spill 84–95%
  (k=3/k=8); com interior erodido (8px) o mapa fica seguro. `@100` com
  trava+multa+k=3: spill **6,6%** (recorde) por RMSE 0,21394 (+0,005 vs
  0,20895 sem borda). Cores saturadas cedo no EFR. Falta validar no 500
  se o gap fecha; literatura (LIVE) manda pesos pequenos.
- Full-500 com borda v8 (v6 + k=3, `output/efr_logo2_bg_off_v8_edge/`):
  RMSE 0.14573 e spill 14,8% — **pior que o v6 nos dois, gap não fechou**.
  k=1 `@100`: RMSE 0,21271, spill 8,3% (entre sem-borda e k=3, sem vantagem).
- G2 resto (testes 30/30 OK, tudo default off): late-small (3+11,
  `lateSmallShare/Start/detailMaxR`, `@100` 0,20956/8,0% — inconclusivo por
  construção, precisa do 500); mutação adaptativa (5, `adaptiveMut`,
  `@100` 0,20864/**4,0%** — melhor spill até aqui); two-stage top-K (2,
  `refineTopK=8`, orçamento neutro 9600 scorings/shape, `@100` **0,20782**
  melhor RMSE); luma opt-in (12, `--luma-bands`, confirmado OFF p/ EFR:
  0,21253 vs 0,20984 no ORIGINAL — docs KFPS tinham razão).
  Stack `@100`: 0,20782/4,5%. Falta o 500 full-stack vs v6 (0,14041/14,9%).
- Full-500 full-stack v9 (trava+multa+late+adaptativa+topK8,
  `output/efr_logo2_bg_off_v9_g2/`): RMSE **0.13962 (recorde)** e spill
  **13,0%** (29510 px) — **novo campeão nos dois eixos** (v6: 0,14041/14,9%).
  Entregáveis: `output/efr_logo2_bg_off_v9_g2/efr_logo2_bg_off.json`
  (exe/FH5, check-OK) + `output/for_kfps/efr_v9_g2.500.json` (KFPS/FM8,
  check-OK). G2 dado como completo (itens 2,3,5,11 colhidos; 12 opt-in).
  **G3 estacionado**: mecanismo pronto e testado (default off), mas peso de
  borda estático não paga nesta imagem — borda de verdade (UDF por distância
  ao contorno do shape) exigiria reescore por candidato, caro; reavaliar no
  G2-sampler (amostragem guiada por erro já foca texto). **v6 segue campeão**.
- G5 GPU (itens 1/5, `src/opencl_backend.py`, default **off** via
  `backend=cpu`; CLI `--backend opencl`): kernels OpenCL C portáveis
  (score/apply/erro) residentes, com fallback CPU. Device gfx1201
  (`OpenCL C 2.0`; 2.2 é inalcançável/irrelevante — sem SPIR-V). Testes
  34/34 OK incl. paridade CPU×GPU (argmin, apply, erro).
  Lições de kernel: (a) 1 work-item/candidato divergia (tempo = maior bbox);
  (b) work-group por candidato + linhas coalescidas resolveu; (c) sampler
  Python (744ms/50k) virou gargalo → vetorizado (`candidates._sample_centers`,
  40ms/50k). Escala medida: 50k GPU≈18ms vs CPU 605ms (~34x); 200k≈62ms.
  Full-500 GPU @50k (`output/efr_logo2_bg_off_v10_gpu/`): 64s gen + pós,
  RMSE **0.13520** e spill 14,0% — melhor que o v9 CPU (0,13962, 197s).
  Entregáveis v10: `output/efr_logo2_bg_off_v10_gpu/efr_logo2_bg_off.json`
  (exe/FH5) + `output/for_kfps/efr_v10_gpu.500.json` (KFPS/FM8), ambos check-OK.
  **Novo campeão**. Falta validação in-game.
- G5 tuning (v11, `output/efr_logo2_bg_off_v11_400k/`): busca ampliada
  (400k/2000/6/k32) + fit-inside + spill 3000, sem late/adaptive (esses
  PIORAM o RMSE no GPU). 500 em 253s. **RMSE nativo 0,13271** e spill 11,9%.
  Comparação justa (mesmo renderizador, canvas nativo 1024²):
  **KFPS 500v2 = 0,13458** vs nosso v11 = **0,13271** → numericamente
  **passamos o KFPS**. Luma (12) confirmado pior no original (trapaça no
  alvo posterizado). Entregáveis v11: `.../efr_logo2_bg_off.json` +
  `output/for_kfps/efr_v11_400k.500.json`, check-OK.
- GAP PERCEPTUAL restante (dono decide): mesmo com RMSE melhor, o KFPS
  *parece* mais limpo porque concentra erro nas bordas/texto (EFR nítido),
  enquanto o nosso MSE gasta erro em manchas de cor média (cinzas) em áreas
  texturizadas. Próximo passo focado: loss perceptual/estrutural (edge-aware
  correto, estilo UDF do LIVE) usando a GPU — o G3 estático não resolveu.

## Provado in-game (FM8)

- KFPS-500 (gerado por ele): **OK**.
- Nosso-500: **lajes de tinta** fora do desenho (B1) — elipses gigantes invadem
  área transparente, invisível no preview mascarado.
- Ownership 501: template editado ao vivo invalida a hierarquia (B6) — ritual
  é template limpo + salvar → sair → reabrir → desagrupar.

## Decisões pendentes (dono: usuário)

1. ~~**Fix do spill**~~ feito no G1 (penalidade + `fit-inside` + full-canvas opt-in
   + simpreview). Backdrop cinza é só fundo, nunca shape. Falta: import de
   validação no jogo (full-canvas + ausência de lajes).
2. ~~**Normalizador KFPS→`.exe`**~~ feito no G1 (`--check` cobre exe|kfps).
3. **Trilha**: (A) adotar KFPS / (B) continuar CPU / (C) híbrida.
4. ~~**Go do backend GPU**~~ feito no G5 (`--backend opencl`, default cpu;
   50k/shape em ~90ms; falta decidir orçamento oficial por run e teto de tempo).
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
