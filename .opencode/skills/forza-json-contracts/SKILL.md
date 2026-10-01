---
name: forza-json-contracts
description: Valida e normaliza JSONs de vinis por destino (exe antigo FH5 ou KFPS FM8) antes de importar
license: MIT
compatibility: opencode
metadata:
  area: json-compat
  project: ForzaPainter2
---

# Forza JSON Contracts

Use antes de entregar ou importar qualquer `.json` de shapes. Cada destino tem
um contrato diferente — o mesmo arquivo raramente serve aos dois.

## Contratos

| Destino | Fundo `type:1` | `data`/`color` | Alpha | Contagem |
|---|---|---|---|---|
| `.exe` antigo (FH5) | **obrigatório** 1º shape `[0,0,W,H]` | **inteiros** (floats → "Malformed or invalid geometry file") | 255 | = camadas do template |
| KFPS (FM8) | **proibido na prática** (conta como shape visível: nosso 500 vira 501) | aceita floats | 255 | **exata** (app rejeita JSON maior que o template) |

Jogos são efetivamente opaco-only (`opaque_only` travado; auditoria: 10.494/10.494
opacos nos JSONs antigos). Campo `score` é cosmético — ignorar na validação.

## Procedimento de validação

Para um candidato `x.json`, conferir nesta ordem (parar no primeiro erro):

1. `shapes` é lista não vazia?
2. Destino `.exe`? → `shapes[0]["type"] == 1`, todos `data`/`color` inteiros,
   todos `type == 16` (fora o fundo), alphas 255.
3. Destino KFPS? → nenhum `type:1`, contagem de desenháveis == camadas do jogo.
4. Contagem de desenháveis == N do template (atenção: arquivos antigos `.N.json`
   costumam ter N−1 shapes reais).

## Normalização

- `python tools/strip_bg.py <in.json> <out.json>` — remove fundo, arredonda para
  int, grava só desenháveis em `output/for_kfps/`. Usar para a via KFPS/FM8.
- Para a via `.exe`/FH5, manter o arquivo original **com** fundo (gerador já
  salva ints + fundo).
- Direção KFPS→`.exe` (JSONs `finals/*.v2.json` deles): `strip_bg.py` não serve
  (eles já vêm sem fundo) — seria preciso **injetar** `type:1` + arredondar;
  não implementado (ver `melhorias.md#8`).

## Armadilhas

- "Visible shapes" do KFPS inclui qualquer dict sem `hidden` — fundo conta.
- Nunca editar os JSONs de referência em `../imagens_originais/` ou nas pastas
  do KFPS: normalizar sempre para cópia nova em `output/`.
