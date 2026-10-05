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
| `.exe` antigo (FH5) | **omitir p/ bg_off** (o app DESENHA o `type:1` como retângulo — vira barra preta) | **inteiros** + formato exato (abaixo) | 255 | entries = camadas **sem** fundo |
| KFPS (FM8) | **proibido na prática** (conta como shape visível) | aceita floats | 255 | desenháveis = camadas |

Contrato `.exe` confirmado in-game (2026-10-05): entregar **sem fundo**, formato
exato, coords cheias → importa e renderiza cheio/limpo. Com fundo `type:1`, o app
antigo o **pinta como retângulo preto de canvas cheio** (alpha 0 ignorado), o que
some quando os shapes cobrem tudo (caso dos arquivos dele, que transbordam) mas
aparece nos nossos `fit-inside` (bg_off) — além de forçar o preview a enquadrar o
canvas inteiro (logo parece pequeno). Ver `bugs.md` B7.

**Trilha primária de entrega:** app antigo (FH5 → depois FM8), por bordas
melhores que o import do KFPS. KFPS é alternativa.

Jogos são efetivamente opaco-only (`opaque_only` travado). `score` é cosmético.

## Procedimento de validação

1. `shapes` é lista não vazia?
2. `.exe`: **sem `type:1`**, todos `type==16`, `data`/`color` inteiros, alphas 255,
   formato exato (CRLF/sem espaços).
3. KFPS: nenhum `type:1`, contagem de desenháveis == camadas.
4. Contagem: `.exe` → entries == N (sem fundo); KFPS → desenháveis == N.

## Normalização

- **`.exe`/FH5 (primário):** `python tools/to_old_exe.py <in.json> --out <out.json>
  --orig-w 1024 --orig-h 1024 --off 0,4 --total N` (padrão `--bg none`). Escreve
  o formato **EXATO** (ver abaixo) via `src/oldexe.py`.
- **KFPS/FM8 (alternativo):** `python tools/strip_bg.py <in.json> <out.json>`.

### Formato EXATO do `.exe` (reverso-engenheirado)

O parser do app antigo é sensível ao formato (nosso `json.dump` com espaços dava
"Malformed or invalid geometry file"). Reproduzir byte a byte:
- `{"shapes":` + **CRLF** + `[` … entradas separadas por `,` + CRLF … fim **CRLF** + `]}`
- entrada: `{"type":T, "data":[i,..],"color":[i,..],"score":S}` — **sem espaço**
  após `"data":`/`"color":`; com espaço só em `"type":N, `
- `data`/`color` inteiros; `score` com **6 casas** (trim)
- shapes em **coordenadas cheias** (somar offset do crop); **sem fundo**
- (se um dia precisar de fundo: `{"type":1, "data":[0,0,W-1,H-1], "color":[255,0,255,0], "score":0}`)
Verificado por round-trip byte a byte em `tests/test_g7d.py`.

## Receita de entrega (2 arquivos por run)

Para um run de N camadas, entregar:
1. **`.exe`/FH5 (primário):** `output/for_old_exe/<nome>.nobgN.json`
   (formato exato, N shapes, **sem fundo**) → importar no app antigo (FH5) e
   depois transferir para FM8.
2. **KFPS/FM8 (alternativo):** `output/for_kfps/<nome>.N.json` (sem fundo, N).

## Armadilhas

- "Visible shapes" do KFPS inclui qualquer dict sem `hidden` — fundo conta.
- Nunca editar os JSONs de referência em `../imagens_originais/` ou nas pastas
  do KFPS: normalizar sempre para cópia nova em `output/`.
