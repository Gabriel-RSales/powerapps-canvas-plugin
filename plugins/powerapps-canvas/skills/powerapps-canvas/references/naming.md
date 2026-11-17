# Nomenclatura — Canvas App

Nome de controle é **global no app**, não por tela. O Studio aceita duplicata e
renomeia em silêncio; `validate.py` falha com `nome-duplicado`.

## Controles: `<prefixo><Assunto><Tela>`

| Prefixo | Controle |
|---|---|
| `cnt` | GroupContainer |
| `gal` | Gallery |
| `lbl` | Label |
| `btn` | Button (classic/modern) |
| `rec` | Rectangle |
| `ico` | Icon |
| `inp` | TextInput |
| `cmb` | ModernCombobox |
| `dtp` | DatePicker |
| `chk` | Checkbox |
| `pdf` | PDFViewer |
| `img` | Image |
| `tmr` | Timer |
| `cmp` | instância de componente |
| `src` | Screen |

O sufixo da tela evita colisão: `lblTituloFechamento`, `lblTituloContrato`.
Repetir o prefixo em toda a cadeia torna o `Ctrl+F` eficiente —
`btnSalvarModalEdicao`, `cntHeaderColFechamento`.

**Botão executor oculto:** `__btnExecutarXxx` (dois underscores). É o padrão para
lógica longa reutilizável: `Height: =1`, `Visible: =false`, `Text: =""`, chamada
por `Select(__btnExecutarXxx)`. Serve para (a) rodar a mesma rotina do `OnVisible`
e de um botão, (b) manter o `OnSelect` do botão visível legível.

## Variáveis

| Prefixo | Escopo | Quando |
|---|---|---|
| `ctx` | contexto (tela) | **padrão** — `UpdateContext` |
| `gbl` / `var` | global | só quando atravessa telas (`Set`) |
| `col` | coleção | `ClearCollect`, espelho em memória |
| `_x` | local em `With()` | sempre com underscore |
| `As _Iter` | alias de iteração | `ForAll(x As _Item, ...)` |

Variável de contexto de **texto** inicializa com `""`, nunca `Blank()`
(ver gotcha `blank-em-ctx-vira-record-vazio`).

## Design tokens

Nunca cor, espaçamento ou raio literal na tela. Tudo em `App.Formulas` com
prefixo do projeto: `IMCP_Color_Primary`, `IMCP_Space_Md`, `IMCP_Card_Radius`,
`IMCP_Button_Height`, `IMCP_FontSize_BodyMd`.

`validate.py` detecta o prefixo sozinho (o mais frequente em `App.Formulas`) e
falha com `token-inexistente` em qualquer token que não exista.

Famílias que valem a pena existir desde o dia 1:
`Color_*`, `Space_*`, `Radius_*`, `Shadow_*`, `Font_*`, `FontSize_*`,
`FontWeight_*`, `Button_*`, `Card_*`, `Input_*`, `Badge_*`, `Topbar/Sidebar_*`.

## Dados

- **Alias plano por tabela:** `PacientesData = pacientes;` — é o que delega.
- **UDF:** verbo + substantivo, argumentos com `_`:
  `RepasseValorContrato(_cirurgia_id:GUID):Number`. Retorno numérico é sempre
  `Number` (gotcha `udf-decimal`).
- **Helpers de badge:** `BadgesChoiceName/Color/Fill(Text(x.status))` — um só
  `Switch` em `App.Formulas`, nunca `Switch` inline na tela.

## Telas

`src<Area><Assunto>`: `srcDashboardComercial`, `srcFechamentoRepasseFinanceiro`.
Renomear tela **sempre pelo Studio** (botão direito → renomear): ele atualiza
todos os `Navigate` e o menu. Renomear no `.pa.yaml` quebra as referências.
