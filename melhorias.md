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
    Status 2026-10-04: Fase A feita (`tools/score_q.py`: RMSE_mask + SSIM_mask
    + EdgeRMSE + Spill% + LabMAE + Q). Fase B (spill) resolvida SEM código
    novo: `spillPenalty` alto basta (@100 w=200000→0,02%, w=1e6→0,00%).
    Full-500 v12 (`spillPenalty=1e6`) → spill 0,05% (era 11,7%). Paleta
    (`paletteColors`, k-means só nos opacos) e UDF-lite (`udfBoost`) testados
    e **rejeitados** p/ esta imagem (default off). B7/G7: `.exe` conta o fundo
    como camada (`--exe-total`); `quantize` alinha busca×entrega (+~0,005 no
    RMSE entregue); `postPasses=2`. **v14** entregue 0,13164 / spill 0,05%
    (KFPS 0,13458). Poda só acha 2–3 obsoletos → G7b pouco a fazer.
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

## Plano agrupado (2026-10-01, ordem de execução)

> Decidido com o dono em 2026-10-01. Não muda os itens acima, só agrupa
> por correlação (mesmos arquivos/risco) e fixa a ordem para não esquecer.

- **G1 — Entregável jogável**: 8 + 9 (contrato game-facing, B1/B2/B4).
  Juntos economizam idas ao Forza; sem isso todo resto gera preview
  bonito e laje de tinta in-game.
- **G2 — Motor de candidatos**: 2 + 3 + 5 + 11 + 12 (um único sampler
  parametrizado em `src/candidates.py`; fazer separado gera conflito).
- **G3 — Função objetivo**: 4 + penalidade-spill do 9 (soma ponderada única
  em `score_batch`; senão há dupla-contagem).
- **G4 — Diagnóstico barato → alimenta 14**: 6 + 7 + 13 (só leitura/pós,
  sem regenerar). Base fixada: `output/efr_logo2_bg_off_v4_3000/`
  `efr_logo2_bg_off.500.json`. Autopsia escopo inicial: só o nosso JSON.
- **G5 — Escala**: 1 + 10 + 14 (GPU OpenCL + 1536 + trilha A/B/C; GPU é o
  acelerador do G2, 1536 muda coordenada de export).
- **G6 — Qualidade perceptual**: 15 Fase A → Fase B (depende do Q calibrado;
  não conflita com G1–G5 porque tudo novo é default off).

**Ordem: G4 → G1 → G3 → G2 → G5 → G6-A (diagnóstico+Q-offline, barato) → G6-B (UDF-lite+area-norm, caro).** G4 e G1 destravam tudo com custo baixo;
G3 antes do G2 porque muda o scoring que o sampler otimiza. G6-A antes de G6-B
porque o Q calibrado é o critério de aceite do novo loop.
