---
name: vinyl-deliverable-check
description: Checklist pré-jogo de entregáveis de vinis para não desperdiçar idas ao Forza
license: MIT
compatibility: opencode
metadata:
  area: release
  project: FM_Painter
---

# Vinyl Deliverable Check

Use antes de entregar qualquer JSON ao usuário para importar no jogo. Cada item
existe porque já causou uma ida perdida ao FM8/FH5 (ver `bugs.md` B1–B6).

## Checklist (nesta ordem)

1. **Contrato do destino** — aplicar skill `forza-json-contracts`: fundo/int/contagem
   conforme `.exe` (FH5) ou KFPS (FM8). Arquivo errado para o destino = import falha.
2. **Contagem exata por destino** — `.exe`/FH5: **entries totais == camadas**
   (fundo conta como camada → N−1 desenháveis, B7); KFPS/FM8: desenháveis == N.
   Gerar os **dois** arquivos (ver `forza-json-contracts` → "Receita de entrega").
   Pós-processamento nunca muda N (`src/post.py` garante por assert).
3. **Render sem máscara** — gerar preview **sem** ignorar o transparente (fundo
   cinza-automotivo). Procurar lajes de tinta fora do desenho (sintoma do B1:
   elipses gigantes invadindo área transparente, invisíveis no preview mascarado).
   Se houver spill, voltar para `melhorias.md#9`, não entregar.
4. **Sanidade dos scores** — todos numéricos; após o pós, todos carregam o erro
   final (cosmético, B3) — não usar para comparar geradores.
5. **Checkpoints presentes** — `.500`/`.1000` (prefixos re-salvos pós-refino) +
   final, todos com a contagem certa no nome e no conteúdo.
6. **Ritual do jogo** (informar ao usuário junto do arquivo): template com N
   esferas/círculos, salvo → sair → reabrir → **desagrupado**, contagem exata
   informada no importador, app como admin, sem trocar de menu, sem grupos
   duplicados. Se o import falhar, acionar skill `fm8-import-debug`.

## Armadilhas

- Preview mascarado bonito **não** aprova entrega — só o sem máscara aprova.
- Nunca contar o `type:1` de fundo como shape do template na via KFPS — mas no
  `.exe` antigo o fundo **conta** como uma camada (contratos opostos; B7).
- `output/` é ignorado no git: o entregável precisa ser copiado para fora ou
  regenerado — nunca presumir que "está na pasta".
