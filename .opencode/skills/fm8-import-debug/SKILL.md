---
name: fm8-import-debug
description: Diagnostica falhas de importação de vinis no Forza Motorsport 8 via KFPS lendo o locator-session.json
license: MIT
compatibility: opencode
metadata:
  area: fm8-import
  project: ForzaPainter2
---

# FM8 Import Debug

Use quando um import no FM8 via KFPS falhar (`Transfer failed`, `no_match`,
`exit code 1`). Nunca chute a causa: o run grava o diagnóstico completo em disco.

## Passo 1 — Abrir a sessão do run que falhou

O log do KFPS mostra a pasta, ex.:
`.../runtime/universal-import/fm8-live-import-<N>-<data>/`. Leia o arquivo
`locator-session.json` dela (só leitura). Campos decisivos:

- `request.layer_count` — contagem que o app procurou na memória.
- `outcome.reason` / `failure_reason` — motivo oficial da recusa.
- `backend_diagnostics.profile_locator.*.rejection_counts` — ex.
  `invalid_group_vector: 12` indica hierarquia obsoleta.
- `cache.previous_session` — revela repetição do mesmo erro.

## Passo 2 — Mapear o motivo para o fix

| `failure_reason` | Causa provável | Fix |
|---|---|---|
| `No safe live layer group matched the requested layer count` | `request.layer_count` ≠ camadas reais do jogo (caso real: pediu 3000, jogo tinha 500) | Informar a contagem exata do jogo ou usar template reutilizável de 3000 (o importador apara para o JSON) |
| `the complete live vinyl hierarchy was not ownership-verified` | Template editado **ao vivo** (camada adicionada/removida sem salvar) → vetor de grupo inválido | Refazer template limpo: salvar → sair → reabrir → desagrupar → `Auto-locate` de novo |
| `template_shape_check=M/N` | Camadas do template não são o shape esperado (círculos brancos) | Recriar template só com círculos |
| Scan atinge `time_limit` sem `candidates` | Contagem errada, menu errado ou grupo ainda agrupado | Checklist do passo 3 |

## Passo 3 — Checklist pré-relocate (ordem importa)

1. Grupo **salvo**, editor **reaberto**, template **desagrupado** com camadas individuais visíveis.
2. Contagem do app = contagem exata do jogo. Atenção: o KFPS conta nosso `type:1`
   de fundo como shape visível — para JSONs nossos, usar a variante sem fundo
   (`output/for_kfps/`, ver skill `forza-json-contracts`).
3. Importar sempre os `finals/*.v2.json` (import-ready), nunca os `checkpoints/` raw.
4. KFPS como administrador, sem trocar de menu no jogo durante o scan, sem grupos
   duplicados empilhados no editor.
5. Se falhar de novo após update do jogo: rodar o updater do KFPS (RTTI.dat
   desatualizado quebra o locator) e reler o novo `locator-session.json`.

## Armadilhas

- O `.exe` antigo (`forza-painter by the_adawg`) só enxerga `ForzaHorizon5.exe`:
  nunca usar para FM8, mesmo que o log pareça similar.
- `count_hits` alto com `candidates=0` é normal quando a contagem pedida não existe
  no jogo — não é bug do scanner, é mismatch de contagem.
