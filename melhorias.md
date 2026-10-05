# Melhorias — FM_Painter

> Última atualização: 2026-10-04. Itens aprovados/não implementados, ideias
> registradas e referências para `bugs.md`. Nada aqui altera o fluxo antigo
> (`output/` existente); tudo novo entra em `FM_Painter/`.

## Aprovadas, não implementadas

1. **Backend GPU OpenCL** — scoring de candidatos em batch, imagens
   (target/current/mask) residentes na GPU, 1 work-item por candidato,
   fallback CPU quando sem driver. Viabilidade **provada** na RX 9070 XT
   (PyOpenCL instalado, plataforma `AMD Accelerated Parallel Processing`,
   kernel de teste executado em `gfx1201`). Objetivo: busca ~400k
   candidatos/shape a ~100ms/shape para superar o KFPS, combinada com
   amostragem guiada + pós com aceite global (já provados melhores no 3000).
   **Feito no G5** (`src/opencl_backend.py`, `--backend opencl`, default cpu):
   implementação usou **work-group por candidato** (não 1 work-item — a
   divergência de bbox dominava) e linhas coalescidas; sampler vetorizado.
   50k/shape ≈ 18ms (CPU 605ms, ~34x); full-500 @50k em 64s com RMSE 0,13520.
   Ver `ESTADO.md` seção G5.
2. **Two-stage random** — amostra grossa (passo 2) + refina top-K=2048
   (parâmetros calibrados do KFPS: `randomCoarseSampleStep=2`,
   `randomRefineTopK=2048`).
   Implementado (CPU/G2) como `refineTopK` (top-K distribuído no orçamento);
   com GPU o top-2048 do KFPS passa a ser viável — reavaliar o K no G5.
3. **Late-small candidates** — 66% dos candidatos pequenos na 2ª metade do
   run (texto fino; `lateSmallCandidateShare=0.66`,
   `lateSmallCandidateStart=0.50`).
4. **Loss ponderada por borda** — Sobel/Canny no target prioriza texto e
   filetes; literatura reporta +1–2 dB sem custo extra de busca (Exp C).
   Implementado no G3 (`src/edgeweight.py`, Sobel + p99, cor ponderada,
   `edgeBoost` default 0.0): versão ingênua premiava a silhueta (spill
   84–95%); com interior erodido fica segura mas não se paga aqui
   (v8: 0.14573 / 14,8% vs v6 0.14041 / 14,9%). **Estacionado** — UDF de
   verdade (distância ao contorno do shape) é caro; reavaliar no sampler.
   **PRIORIDADE após G5**: o v11 já bate o KFPS em RMSE (0,13271 vs 0,13458)
   mas *parece* pior — o MSE gasta erro em manchas de cor média em áreas
   texturizadas em vez das bordas/texto. Loss edge-aware/estrutural correto
   (UDF do LIVE, agora viável na GPU) é o caminho para fechar o gap visual.
5. **Mutação adaptativa por shape** — encolhe o passo a cada falha, reseta
   no acerto, 50% das vezes passo aleatório (Exp D, anti-mínimo-local).
6. **Sweep de pós 0/1/2/3** sobre resultado 500 já salvo (só pós, sem
   regenerar; barato; espera-se platô em ~2).
   Feito no G4 (`tools/sweep_post.py`): 0→0.14544, 1→0.14118, 2→0.13963,
   3→0.13864 — sem platô em 2.
7. **Autopsia JSON** (`tools/autopsy.py`, só leitura): distribuição de
   área/aspecto/ângulo, ganho marginal por shape (curva erro × índice),
   densidade espacial shapes-vs-erro, paleta usada — calibra o sampler e
   mostra onde o budget vaza. Vale para JSONs antigos e novos.
   Feita no G4 (escopo: só nosso 500).
8. **Normalizador KFPS→`.exe` antigo + validador `--check`**
   (`tools/normalize_for_old_exe.py`): injeta `type:1` se ausente,
   arredonda `data`/`color` para int, valida contagem. O `.exe` antigo
   rejeita finals do KFPS ("Malformed": sem fundo + floats) — ver B4.
   Feito no G1 (+`--check --dest exe|kfps --expect N`).
9. **Correção do spill in-game** (ver B1/B2):
   - penalidade de derramamento no scoring (custo por pixel transparente
     coberto; espelho do `boundary_penalty` do KFPS);
   - trava `fit-inside-bbox` opcional (flag, default off);
   - export em coordenadas cheias 1024×1024 (somar offset do crop);
   - **simpreview sem máscara obrigatório** em todo entregável (fundo
     cinza-automotivo) — teria pego o B1 antes do jogo.
   Feito no G1 (`tools/simpreview.py`, `spillPenalty` default 0.0,
   `fitInsideBbox`/`fullCanvas` opt-in; w=3000 corta o spill 68%→18% por
   +0,00014 RMSE no 100; backdrop cinza nunca é shape).
15. **Q-perceptual + UDF-lite no loop (fix do RMSE que mente).**
    Diagnóstico 2026-10-04 (dono confirmou ranking visual
    `antigo > KFPS > nosso` nas 4 imagens EFR): RMSE mascarado ordena
    `KFPS 0.135 < nosso 0.145 < antigo 0.161` no 500, mas no jogo o antigo
    tem EFR legível e o nosso tem EFR quebrado (`EFFP` pixelado) + 2 barras
    cinzas diagonais + spill. Causa: `src/cpu_backend.py:_score_one` usa cor
    média + delta somado → premia gigante borrado (color mean error, LIVE
    CVPR22), peso zero p/ texto fino, spill grátis (`spillPenalty` default 0.0),
    RGB não-perceptual. `edgeBoost` estático do G3 não resolve
    (v8 0.14573/14,8% vs v6 0.14041/14,9%) porque premia silhueta sem UDF
    por candidato. Recomendação do assistente: Q-offline primeiro (mais rápido,
    sem mexer na geração), só depois UDF-lite no loop; dono aprovou.
    Fase A — Q-offline (rápido, sem mexer na geração):
    - Novo `tools/score_q.py`: `RMSE_mask + SSIM_mask + EdgeRMSE + Spill% + Lab-MAE`.
      `EdgeRMSE` = RMSE só nos 15% px de maior Sobel no interior erodido 8px
      (reusa `src/edgeweight.py`). `Spill%` = `tools/simpreview.py` mask-off.
      Mesmo rasterizador `src/post.py:render_all` p/ todos (regra
      `vinyl-quality-compare`); nunca comparar `score` gravado nos JSONs.
    - Estender `tools/compare3.py` p/ cuspir `metricas.txt` com as 5 colunas +
      `Q = a*RMSE + b*(1-SSIM) + c*EdgeRMSE + d*Spill`. Calibrar `a,b,c,d`
      até `Q` ordenar `antigo < KFPS < nosso` (menor = melhor) no 500 existente.
      Sem fusão prematura: publica os 4 números primeiro, funde depois.
    - Aceite A: Q coloca o antigo na frente. Sem isso, não mexer no loop.
    Fase B — L-online UDF-lite (só após A):
    - Em `src/cpu_backend.py:_score_one` + kernel `score_batch` em
      `src/opencl_backend.py`: `w_total = emap_estatico * udf_dinamico`,
      `rho2=(lx/rx)^2+(ly/ry)^2`, `w_udf = 1 + udfBoost*exp(-((1-rho)/0.15)^2)`.
      Cor ótima vira média ponderada por UDF. Reusa `lx,ly` já computados.
    - `delta_norm = delta / cnt^areaNorm`, `areaNorm ~0.5` testável, p/ tirar
      viés pró-gigante.
    - Flags novas default off: `udfBoost=0.0`, `areaNorm=0.0` (+ `--udf-boost`,
      `--area-norm` em `tools/gen.py` via `src/generator.py`/`src/profile.py`).
      `spillPenalty=3000` + `fitInsideBbox` seguem como trava. Paridade CPU×GPU
      obrigatória em `tests/`.
    - Contratos preservados: `opaque_only`, `data`/`color` int, contagem exata N
      (`src/post.py` assert), `forza-json-contracts` + `vinyl-deliverable-check`
      (simpreview mask-off obrigatório).
    - Aceite B: `@100` varrendo `udfBoost/areaNorm` → full-500 campeão vs
      v6/v9/v11 em Q-offline + `EFR` legível + sem barra cinza + import no jogo.
    - Passo a passo p/ sessão build: 1) `compare3.py --n 500` + `autopsy.py`
      antigo vs v9/v11; 2) cria `score_q.py`; 3) roda Q e calibra pesos;
      4) implementa `udfBoost/areaNorm` CPU+GPU; 5) `@100` → full-500 →
      simpreview mask-off → `normalize_for_old_exe.py --check` → import.
    Status final 2026-10-05: Fase A ✅ (`tools/score_q.py`: RMSE_mask +
    SSIM_mask + EdgeRMSE + Spill% + LabMAE + Q). Spill resolvido SEM código
    novo (`spillPenalty`: @100 w=1e6→0,00%; full-500 v12 → spill 0,05%, era
    11,7%). Paleta (`paletteColors`) e UDF-lite (`udfBoost`/`udfTau`/`areaNorm`,
    CPU+GPU com paridade) **rejeitados** nesta imagem (default off). `quantize`
    alinha busca×entrega (+~0,005 no RMSE entregue) e `postPasses=2`.
    **Campeão v14** entregue 0,13164 / spill 0,05% (KFPS 0,13458; antigo 0,161).
    Poda acha só 2–3 obsoletos (G7b pouco a fazer). Entrega (app antigo) **sem
    fundo** — ver G7 no "Plano agrupado".
16. **Engenharia reversa do app antigo — só geração, Nível 1 primeiro
    (decidido 2026-10-04).**
    Base: `forza-painter.exe` (754 KB, 08/11/2023, Dear ImGui) é MIT derivado de
    `geometrize-lib` + `Primitive` (`README.md:157-160`, `LICENSE:1-7` dele) —
    técnica está no open-source, sem precisar descompilar. Strings: `ellipse/mse/
    sample/mutat/Hill/alpha/shape`; perfis `settings/*.ini` usam as mesmas chaves
    que as nossas (`randomSamples/mutatedSamples/maxResolution/saveAt/stopAt`).
    Decisões do dono: (1) só geração, nada de injeção; (2) esgotar Nível 1 antes
    de pensar em estática; (3) dinâmica só juntos, passo a passo, em cópia isolada.
    Passo a passo Nível 1 (build): 1) inventário read-only dos `.json` antigos +
    `settings/*.ini`; 2) `tools/autopsy.py` antigo vs v6/v9/v11 (área/aspecto/ordem/
    paleta/alpha); 3) `tools/compare3.py --n 500` + `simpreview` mask-off
    (RMSE/EdgeRMSE/Spill%); 4) mapa `primitive/main.go` + `geometrize-lib/runner`
    (scoring/mutate/faixas); 5) tabela `antigo-faz-X / nós-fazemos-Y / ação` em
    `output/reverse_n1/` (gitignored). Aceite: explica `antigo > KFPS > nosso` no
    olho com RMSE invertido. Nível 2 (estática em cópia no temp opencode) e Nível 3
    (dinâmica guiada) só se o Nível 1 não fechar. Guardrails: `.exe`,
    `../imagens_originais/`, KFPS sempre read-only; atribuição MIT preservada.
17. **Import do app antigo (FH5) rende bordas melhores que o KFPS com o MESMO
    JSON (observado 2026-10-05).** O mesmo v14 importado pelo app antigo
    (FH5 → transferido p/ FM8) tem bordas visivelmente melhores que via KFPS.
    Hipóteses: ordem/estado da injeção no FH5, ou AA/quantização do importador.
    Investigar (black-box + upstream geometrize/Primitive). Não bloqueia nada —
    a **trilha primária de entrega já é o app antigo**. Sessão futura.

## Ideias registradas, não decididas

10. **Resolução 1536** de trabalho com reescala para 1024 no export.
    Exige 1 import de validação no jogo (mapeamento de coords é a
    incógnita). Estacionada para etapa futura.
11. **Perfil detalhe-fino**: últimos N shapes só com raio 1–4px nos tiles
    de texto.
    Extra G2 já pronto: teto de aspecto (`maxAspect`, default off, +`--max-aspect`;
    A=12 dá melhor RMSE no 100 mas não derruba spill no 500 — v7 0.14133/15,2%).
12. **Pré-processo luma bands** (ideia KFPS, sem teste).
13. **Poda por importância** estilo KFPS (nosso `prune_diagnostic` é O(N²),
    caro no 3000).
14. **Decisão de trilha**: (A) adotar KFPS como gerador / (B) continuar CPU
    / (C) híbrida (raw KFPS + nosso pós). Aguardava leitura do comparativo
    triplo — ver `output/comparacao3_{500,1000,3000}/`.

## Referências de bugs (detalhes em `bugs.md`)

- B1 spill in-game → correção neste arquivo, item 9.
- B2 export recortado → correção neste arquivo, item 9.
- B3 scores dos checkpoints sobrescritos (cosmético).
- B4 rejeição do JSON KFPS pelo `.exe` antigo → correção item 8.

## Plano agrupado (2026-10-01; status 2026-10-05)

> Agrupa por correlação (mesmos arquivos/risco) e fixa a ordem; os itens acima
> têm o detalhe. Nada aqui muda o fluxo antigo de `output/`.

- **G1 — Entregável jogável** ✅ (8+9): normalizador/`--check`, simpreview
  mask-off, full-canvas opt-in, penalidade de spill. B1/B2 resolvidos.
- **G2 — Motor de candidatos** ✅ (2+3+5+11+12): sampler parametrizado e
  **vetorizado** (`candidates._sample_centers`); late-small, mutação adaptativa,
  two-stage (`refineTopK`), teto de aspecto; luma opt-in.
- **G3 — Função objetivo** ⏸️ (4): `edgeBoost` estático implementado mas
  **estacionado** (default off) — loss perceptual não pagou (ver G6).
- **G4 — Diagnóstico barato** ✅ (6+7+13): `tools/sweep_post.py`,
  `tools/autopsy.py`.
- **G5 — Escala/GPU** ✅ (1+10+14): backend OpenCL residente
  (`src/opencl_backend.py`, `--backend opencl`, default cpu) + `src/scoring.py`
  (`BatchScores`); 50k/shape ≈18ms (~34× CPU); full-500 @50k em 64s.
- **G6 — Qualidade perceptual** ✅ (15): `tools/score_q.py` (métrica fiel);
  spill a ~0; paleta e UDF-lite testados e **rejeitados** (opt-in off).
- **G7 — Pós iterativo + entrega** ✅: B7 (formato **exato** do `.exe`,
  `src/oldexe.py`, `tools/to_old_exe.py`), `quantize` (busca=entrega),
  `postPasses=2`, **entrega sem fundo** no app antigo (ele desenha o `type:1`).
  Poda+refill (13) dispensada (só 2–3 obsoletos no 500).

**Ordem executada: G4 → G1 → G3(estac.) → G2 → G5 → G6-A → G6-B(rejeitado) →
G7.** Campeão **v14** (entregue 0,13164 / spill 0,05%; KFPS 0,13458; antigo
0,161). **Trilha primária de entrega: app antigo (FH5→FM8)**, KFPS alternativa.
Próximo: item 16 (reversa do app antigo) e item 17 (bordas melhores no import
do app antigo).
