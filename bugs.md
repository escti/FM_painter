# Bugs — FM_Painter

> Última atualização: 2026-09-28. Só bugs **abertos** têm correção pendente;
> os já corrigidos ficam em registro para não reabrir. Correções planejadas
> vivem em `melhorias.md`.

## Abertos

- **B1. Spill em área transparente (GRAVE, confirmado in-game no FM8).**
  Elipses gigantes (ex. `[779, 1006, 858, 131]` no `for_kfps/*.500.json`)
  invadem região transparente: invisível no preview mascarado, vira laje
  de tinta onde deveria aparecer a pintura do carro. Miolo (capacete/EFR)
  correto — só falta contenção. Fix: `melhorias.md#9` (penalidade de
  derramamento + trava fit-inside + export full-canvas + simpreview).
- **B2. Export em espaço recortado (1024×1020 + offset (0,4)).**
  Micro-deslocamento vs PNG 1024×1024 no jogo. Fix: export full-canvas
  (`melhorias.md#9`).
- **B3. Scores dos checkpoints sobrescritos (cosmético).** Após o pós, os
  `.500`/`.1000.json` carregam o erro final em todos os shapes, não o erro
  da etapa. Não afeta o jogo (só métrica). Fix: preservar `scores` por
  etapa ao re-salvar prefixos no pós.
- **B4. `.exe` antigo rejeita JSON do KFPS ("Malformed or invalid geometry
  file").** Causas: finals sem shape `type:1` de fundo + `data` com floats
  (parser antigo espera fundo + ints). Fix: normalizador
  (`melhorias.md#8`, aguardando aprovação).
- **B5. KFPS conta `type:1` como shape visível (off-by-one 501).**
  Comportamento externo (`transfer_bridge.py:133-138` conta todo dict sem
  `hidden`). Contornado com `output/for_kfps/` (sem fundo, contagem
  exata). Sem fix de código do nosso lado.
- **B6. Falha de ownership no FM8 após adicionar camada ao vivo.**
  `locator-session.json` mostra `invalid_group_vector` após edição live do
  template (501). Diagnóstico fechado; fix é ritual, não código: template
  limpo + salvar → sair → reabrir → desagrupar → localizar de novo.

## Já corrigidos (registro)

- GIL presa (~15% CPU) → `nogil=True + prange`, ~84% no 7600X.
- Prune com deriva cumulativa (1000→209 shapes, erro 0.108→0.179) →
  `prune_diagnostic` sem remoção + drift absoluto.
- Refine com aceite local (piorava o erro global) → aceite global
  (top-K reavaliados com render full).
- Overflow int16 no mapa de erro (`candidates.error_tiles`) → float32 +
  guarda NaN.
- Previews a cada 10 shapes (~100 PNGs) → só checkpoints + final.
- Export com alpha semi-transparente (preview lavado + incompatível com o
  jogo, que é 100% opaco) → `opaque_only` travado; auditoria confirmou
  10.494/10.494 shapes opacos nos JSONs antigos.
- **B7. Import do `.exe` antigo (FH5): formato + fundo.** Duas causas
  resolvidas. (1) O parser é sensível ao formato: `json.dump` com espaços/LF dava
  "Malformed or invalid geometry file"; correção = serializador exato
  (`src/oldexe.py`: CRLF, sem espaço após `data`/`color`, `score` 6 casas,
  coords cheias) — validado por round-trip byte a byte (`tests/test_g7d.py`).
  (2) O app **desenha o `type:1` como retângulo preto** de canvas cheio (alpha 0
  ignorado) e força o preview a enquadrar o canvas (logo parece pequeno); nos
  arquivos dele isso some porque os shapes transbordam e cobrem tudo. Correção:
  entregar **sem fundo** (`tools/to_old_exe.py --bg none`, padrão). `.exe`/FH5
  confirmado in-game 2026-10-05.
