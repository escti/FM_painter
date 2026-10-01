# Melhorias — ForzaPainter2

> Última atualização: 2026-09-28. Itens aprovados/não implementados, ideias
> registradas e referências para `bugs.md`. Nada aqui altera o fluxo antigo
> (`output/` existente); tudo novo entra em `ForzaPainter2/`.

## Aprovadas, não implementadas

1. **Backend GPU OpenCL** — scoring de candidatos em batch, imagens
   (target/current/mask) residentes na GPU, 1 work-item por candidato,
   fallback CPU quando sem driver. Viabilidade **provada** na RX 9070 XT
   (PyOpenCL instalado, plataforma `AMD Accelerated Parallel Processing`,
   kernel de teste executado em `gfx1201`). Objetivo: busca ~400k
   candidatos/shape a ~100ms/shape para superar o KFPS, combinada com
   amostragem guiada + pós com aceite global (já provados melhores no 3000).
2. **Two-stage random** — amostra grossa (passo 2) + refina top-K=2048
   (parâmetros calibrados do KFPS: `randomCoarseSampleStep=2`,
   `randomRefineTopK=2048`).
3. **Late-small candidates** — 66% dos candidatos pequenos na 2ª metade do
   run (texto fino; `lateSmallCandidateShare=0.66`,
   `lateSmallCandidateStart=0.50`).
4. **Loss ponderada por borda** — Sobel/Canny no target prioriza texto e
   filetes; literatura reporta +1–2 dB sem custo extra de busca (Exp C).
5. **Mutação adaptativa por shape** — encolhe o passo a cada falha, reseta
   no acerto, 50% das vezes passo aleatório (Exp D, anti-mínimo-local).
6. **Sweep de pós 0/1/2/3** sobre resultado 500 já salvo (só pós, sem
   regenerar; barato; espera-se platô em ~2).
7. **Autopsia JSON** (`tools/autopsy.py`, só leitura): distribuição de
   área/aspecto/ângulo, ganho marginal por shape (curva erro × índice),
   densidade espacial shapes-vs-erro, paleta usada — calibra o sampler e
   mostra onde o budget vaza. Vale para JSONs antigos e novos.
8. **Normalizador KFPS→`.exe` antigo + validador `--check`**
   (`tools/normalize_for_old_exe.py`): injeta `type:1` se ausente,
   arredonda `data`/`color` para int, valida contagem. O `.exe` antigo
   rejeita finals do KFPS ("Malformed": sem fundo + floats) — ver B4.
9. **Correção do spill in-game** (ver B1/B2):
   - penalidade de derramamento no scoring (custo por pixel transparente
     coberto; espelho do `boundary_penalty` do KFPS);
   - trava `fit-inside-bbox` opcional (flag, default off);
   - export em coordenadas cheias 1024×1024 (somar offset do crop);
   - **simpreview sem máscara obrigatório** em todo entregável (fundo
     cinza-automotivo) — teria pego o B1 antes do jogo.

## Ideias registradas, não decididas

10. **Resolução 1536** de trabalho com reescala para 1024 no export.
    Exige 1 import de validação no jogo (mapeamento de coords é a
    incógnita). Estacionada para etapa futura.
11. **Perfil detalhe-fino**: últimos N shapes só com raio 1–4px nos tiles
    de texto.
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
