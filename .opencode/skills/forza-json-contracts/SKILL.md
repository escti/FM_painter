---
name: forza-json-contracts
description: Valida e normaliza JSONs de vinis por destino (exe antigo FH5 ou KFPS FM8) antes de importar
license: MIT
compatibility: opencode
metadata:
  area: json-compat
  project: FM_Painter
---

# Forza JSON Contracts

Use antes de entregar ou importar qualquer `.json` de shapes. Cada destino tem
um contrato diferente — o mesmo arquivo raramente serve aos dois.

## Contratos

| Destino | Fundo `type:1` | `data`/`color` | Alpha | Contagem |
|---|---|---|---|---|
| `.exe` antigo (FH5) | **obrigatório** 1º shape `[0,0,W,H]` | **inteiros** (floats → "Malformed or invalid geometry file") | 255 | **entries totais = camadas** (o fundo CONTA como camada → N−1 desenháveis) |
| KFPS (FM8) | **proibido na prática** (conta como shape visível) | aceita floats | 255 | desenháveis = camadas (sem fundo) |

Modelo do `.exe` (app antigo, `imagens_originais/.../efr_logo2_bg_off.500.json`):
**500 entries = 1 fundo + 499 desenháveis** para um template de 500 camadas. O
fundo ocupa uma camada. Arquivo com 501 entries (`500 shapes + fundo`) **falha**
por estourar o template (B7).

Jogos são efetivamente opaco-only (`opaque_only` travado; auditoria: 10.494/10.494
opacos nos JSONs antigos). Campo `score` é cosmético — ignorar na validação.

## Procedimento de validação

Para um candidato `x.json`, conferir nesta ordem (parar no primeiro erro):

1. `shapes` é lista não vazia?
2. Destino `.exe`? → `shapes[0]["type"] == 1`, todos `data`/`color` inteiros,
   todos `type == 16` (fora o fundo), alphas 255.
3. Destino KFPS? → nenhum `type:1`, contagem de desenháveis == camadas do jogo.
4. Contagem: `.exe` → **entries totais == N** (fundo conta); KFPS → desenháveis
   == N. Arquivos antigos `.N.json` do `.exe` têm N−1 shapes reais (fundo incluso).

## Normalização

- **KFPS/FM8:** `python tools/strip_bg.py <in.json> <out.json>` — remove fundo,
  arredonda para int, grava desenháveis em `output/for_kfps/`. Contagem = N reais.
- **`.exe`/FH5:** `python tools/normalize_for_old_exe.py <in.json> --out <out.json>
  --canvas W,H --exe-total N` — injeta `type:1` se ausente, arredonda p/ int e
  **corta os desenháveis p/ N−1** (fundo conta; B7). Validar com
  `--check --dest exe --expect N`.
- Direção KFPS→`.exe` (`finals/*.v2.json`, sem fundo): `normalize_for_old_exe.py`
  injeta o fundo + ints (`--exe-total` ajusta a contagem).

## Receita de entrega (2 arquivos por run)

Para um run de N camadas, entregar **sempre dois** arquivos:
1. KFPS/FM8: `output/for_kfps/<nome>.N.json` (sem fundo, N desenháveis).
2. `.exe`/FH5: `output/for_old_exe/<nome>.exeN.json` (fundo + N−1 desenháveis = N entries).
Validar os dois com `normalize_for_old_exe.py --check` (KFPS e exe).

## Armadilhas

- "Visible shapes" do KFPS inclui qualquer dict sem `hidden` — fundo conta.
- Nunca editar os JSONs de referência em `../imagens_originais/` ou nas pastas
  do KFPS: normalizar sempre para cópia nova em `output/`.
