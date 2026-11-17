---
name: powerapps-canvas
description: Desenvolver, revisar e validar apps Power Apps Canvas (.pa.yaml) com Dataverse ou SharePoint. Use ao criar ou editar telas, escrever Power Fx, revisar código Canvas, investigar erro do Power Apps Studio (PA2108, PA2231, delegação, "cannot be used in expressions"), espelhar o schema do Dataverse, ou preparar deploy/solution. Traz validador offline, base de gotchas executável e padrões de nomenclatura, code review e ALM.
---

# Power Apps Canvas — desenvolvimento, validação e ALM

Power Apps não tem compilador offline: o único validador de Power Fx é o Studio,
e cada ida até ele custa commit → push → merge → abrir. Esta skill encurta esse
ciclo com um **validador local** e uma **base de armadilhas executável**.

**Onde ficam os scripts.** Os exemplos usam o caminho de plugin instalado. Se a
skill foi copiada para dentro de um projeto, troque o prefixo:

| Instalação | Prefixo |
|---|---|
| plugin (`/plugin install`) | `${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas` |
| cópia no repo do projeto | `.claude/skills/powerapps-canvas` |

O argumento final (`.`) é a raiz do repo do **app Canvas** que você está
validando. Precisa de `pyyaml` (`pip install pyyaml`).

## 1. Antes de tocar numa tela

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/validate.py" .
```

Pega offline o que custaria uma volta no Studio: YAML inválido, nome de controle
duplicado, token/UDF inexistente, container AutoLayout sem `LayoutMin*` e todas
as armadilhas de `references/gotchas.yaml`.

`exit 0` limpo · `1` tem ERRO · `2` só avisos (`--strict` faz aviso virar erro).
Outras flags: `--json` (saída para script), `--quiet` (só o resumo),
`--only <id>` (roda **uma** regra, para testar gotcha recém-criado).

Saída real deste repo:

```
ERRO  coalesce-string-vazia  Src/srcGestaoAtivosAdministracao.pa.yaml:1786
      Coalesce(x, "") devolve Blank, nao ""
      -> Use `x & ""` para garantir string.
AVISO autolayout-minsize     Src/srcTeste.pa.yaml:6
      Container AutoLayout 'cntTeste' (vertical) sem LayoutMinHeight
      -> Defina LayoutMinHeight: =10 (valor pequeno).
```

## 2. Quando o Studio reclamar

**Procure antes de depurar** — a mensagem de erro é a chave de busca:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/gotcha.py" find "cannot be used in expressions"
```

Se não achar, você encontrou uma armadilha nova. Registre (passo 5).

## 3. Espelhar o banco

No Canvas você escreve o **display name** (`ThisItem.'nome completo'`), não o
lógico. Errar isso é barato de fazer e caro de achar. Gere a lista exata:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/schema_mirror.py" Main/<Solution> -o SCHEMA.md
```

```
SCHEMA.md: 24 tabelas, 257 colunas, 19 optionsets, 190 relacionamentos
```

Resolve três coisas que só se descobre lendo os arquivos: a "PK" do Power Fx é o
display name do atributo `Type: primarykey`; o **alvo do lookup não está no yml
do atributo** (está em `entityrelationships/`); e display name com espaço exige
aspas simples — o espelho marca esses com ⚠️.

Regenere depois de cada `pac solution export`. O repo é um retrato, não o
ambiente (ver `references/alm.md`).

> **Só Dataverse.** O script lê a solution exportada; **lista do SharePoint não
> tem equivalente e não foi implementado**. Para SharePoint, gere o espelho à
> mão a partir de *Configurações da lista* e guarde no mesmo `SCHEMA.md` — e
> saiba que as regras mudam: o nome interno difere do exibido (espaço vira
> `_x0020_`), não há optionset global (choice é coluna de texto com valores
> fixos), a PK é `ID`, lookup devolve record `{Id, Value}`, e o teto de
> delegação é bem mais baixo (`Filter` por choice/lookup frequentemente **não**
> delega). Os padrões de tela, nomenclatura e code review valem igual.

## 4. Escrever a tela

Carregue a referência conforme a tarefa:

| Arquivo | Quando |
|---|---|
| `references/development.md` | **sempre** — AutoLayout, delegação, `Patch`, UDF, popup, paginação, fluxos |
| `references/naming.md` | nomear qualquer controle, variável ou token |
| `references/bootstrap.md` | projeto novo — esqueleto do `App.Formulas`, ordem de montagem, modelagem |
| `references/code-review.md` | revisar mudança, registrar dívida |
| `references/alm.md` | Studio × Git, solution, variáveis de ambiente, security roles, deploy |
| `references/gotchas.yaml` | antes de depurar qualquer erro do Studio |

Três regras que quebram o dia se esquecidas:

- **O Studio é a fonte da verdade quando alguém está editando nele.** O export
  sobrescreve o `.pa.yaml`. Correção que a pessoa vai colar no Studio: entregue
  só o Power Fx **sem o `=` inicial** e **não** edite o arquivo.
- **Todo container AutoLayout recebe `LayoutMinHeight: =10` (vertical) ou
  `LayoutMinWidth: =10` (horizontal).** Sem isso ele ignora o tamanho dos filhos.
- **Alias plano de tabela** (`PacientesData`), nunca `DataBase.Pacientes.data` —
  a indireção mata a delegação e o `LookUp` devolve `Blank()` em silêncio.

## 5. Alimentar a skill (o ciclo que impede repetir o erro)

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/gotcha.py" add \
  --id minha-armadilha \
  --title "Resumo de uma linha" \
  --symptom "A mensagem EXATA do Studio" \
  --fix "O conserto" \
  --property ItemDisplayText --contains "IsBlank("
```

Com `--property`/`--contains`/`--regex` a armadilha vira **lint automático**; sem
elas, fica como leitura obrigatória. Confira que a regra pega o caso real e não
o resto do app:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/validate.py" . --only minha-armadilha
```

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/powerapps-canvas/scripts/gotcha.py" list
```

```
[lint] itemdisplaytext-isblank      error    ItemDisplayText do ModernCombobox nao aceita IsBlank
28 gotchas, 6 com lint automatico
```

Armadilha (sintoma + conserto) vai para `gotchas.yaml`. **Dívida** (padrão
repetido, modelo errado, pendência de schema) vai para `CODE-REVIEW-TODO.md` —
são coisas diferentes, ver `references/code-review.md`.

## Gotchas do próprio ferramental

- **`pyyaml` quebra em `Propriedade: =`** (valor vazio, que o Studio exporta
  bastante): o `=` solitário é a tag YAML 1.1 `value`. Os scripts registram um
  construtor para ela; sem isso metade das telas falha ao carregar.
- **Lint ingênuo acusa a própria documentação.** `validate.py` mascara
  comentários (`//`, `/* */`) e, no scan de UDF, também strings e identificadores
  `'com aspas simples'` — preservando offsets para o número da linha continuar
  certo. Sem isso, o comentário que ensina "nunca use `DataBase.X.data`" virava
  um ERRO.
- **O validador não entende Power Fx**, só texto e YAML. Ele reduz as idas ao
  Studio; não as elimina.
- **Testado em:** Python 3.12, pyyaml 6.0.3, app de 31 telas / 24 tabelas,
  Windows. Caminhos saem com `\` no Windows — cosmético.

## Publicar / reaproveitar

O diretório é autocontido: copie `.claude/skills/powerapps-canvas/` para outro
repo e funciona. Nada é específico do projeto — o prefixo de token é detectado,
e os caminhos de solution/Src são descobertos por varredura.

Ao reaproveitar, leve `gotchas.yaml` junto: é o ativo que cresce. Mantenha o
campo `verified` com a data em que a armadilha foi comprovada **no Studio** —
não em documentação.
