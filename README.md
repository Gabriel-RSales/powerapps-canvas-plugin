# powerapps-canvas

Plugin do [Claude Code](https://claude.com/claude-code) para desenvolver, revisar
e validar apps **Power Apps Canvas** (`.pa.yaml`) com Dataverse ou SharePoint.

Power Apps não tem compilador offline: o único validador de Power Fx é o Studio,
e cada ida até lá custa commit → push → merge → abrir. Este plugin encurta esse
ciclo.

## Instalar

```
/plugin marketplace add <seu-usuario>/powerapps-canvas-plugin
/plugin install powerapps-canvas@powerapps-canvas
```

Requisito: Python 3.8+ com `pyyaml` (`pip install pyyaml`).

## O que vem junto

| | |
|---|---|
| **Validador offline** | YAML inválido, nome de controle duplicado, token/UDF inexistente, container AutoLayout sem `LayoutMin*` e as armadilhas conhecidas — tudo antes de abrir o Studio |
| **Base de gotchas executável** | 28 armadilhas com sintoma, conserto e data de verificação; 6 viram lint automático. Cresce com um comando |
| **Espelho do schema** | Lê a solution exportada e gera a lista exata de display names, PKs, alvos de lookup e optionsets |
| **Padrões** | Nomenclatura, desenvolvimento (AutoLayout, delegação, `Patch`, UDF, popups), code review e ALM |

## Uso

Depois de instalado, a skill carrega sozinha quando você pede para mexer numa
tela, investigar um erro do Studio ou revisar código Canvas. Para forçar:
`/powerapps-canvas`.

Validar um app antes de abrir o Studio:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/validate.py" .
```

```
ERRO  coalesce-string-vazia  Src/srcGestaoAtivos.pa.yaml:1786
      Coalesce(x, "") devolve Blank, nao ""
      -> Use `x & ""` para garantir string.
AVISO autolayout-minsize     Src/srcFechamento.pa.yaml:6
      Container AutoLayout 'cntLinha' (vertical) sem LayoutMinHeight
      -> Defina LayoutMinHeight: =10 (valor pequeno).
```

Procurar uma mensagem de erro do Studio antes de depurar:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/gotcha.py" find "cannot be used in expressions"
```

Gerar o espelho do banco:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/schema_mirror.py" Main/<Solution> -o SCHEMA.md
```

```
SCHEMA.md: 24 tabelas, 257 colunas, 19 optionsets, 190 relacionamentos
```

## O ciclo que impede repetir o erro

Errou no Studio → procura → não achou → registra → vira lint:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/gotcha.py" add \
  --id minha-armadilha \
  --title "Resumo de uma linha" \
  --symptom "A mensagem EXATA do Studio" \
  --fix "O conserto" \
  --property ItemDisplayText --contains "IsBlank("

python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/validate.py" . --only minha-armadilha
```

`gotchas.yaml` é o ativo que cresce — é o que não se recupera depois.

## Estrutura

```
plugins/powerapps-canvas/
  .claude-plugin/plugin.json
  skills/powerapps-canvas/
    SKILL.md
    scripts/      validate.py · schema_mirror.py · gotcha.py
    references/   gotchas.yaml · development.md · naming.md
                  code-review.md · alm.md · bootstrap.md
```

## Escopo e limites

- O validador **não entende Power Fx** — trabalha sobre texto e YAML. Reduz as
  idas ao Studio; não as elimina.
- O espelho do schema lê **solution do Dataverse exportada**. Lista do SharePoint
  não é coberta pelo script (o `SKILL.md` explica o que muda).
- Verificado em Python 3.12, pyyaml 6.0.3, app de 31 telas e 24 tabelas, Windows.

## Licença

MIT — ver [LICENSE](LICENSE).
