# Padrões de desenvolvimento — Canvas App

Regras que valem para qualquer projeto. As armadilhas com sintoma e conserto
estão em `gotchas.yaml` (executável pelo `validate.py`); aqui ficam as decisões
de arquitetura.

## 1. AutoLayout e o `LayoutMin*`

Prefira `Variant: AutoLayout` + `LayoutDirection` + `FillPortions` +
`AlignInContainer` + `LayoutGap` a `X/Y/Width/Height`. Use Manual quando o
AutoLayout atrapalhar o visual — não force.

**Todo container AutoLayout recebe um `LayoutMin*` pequeno e explícito:**

```yaml
- cntLinhaFiltros:
    Control: GroupContainer@1.5.0
    Variant: AutoLayout
    Properties:
      LayoutDirection: =LayoutDirection.Horizontal
      LayoutGap: =IMCP_Space_Sm
      LayoutMinWidth: =10        # vertical -> LayoutMinHeight: =10
```

Sem isso o container colapsa ou ignora o tamanho vindo dos filhos. O valor é
pequeno de propósito: ele **destrava** o cálculo automático sem impor tamanho.
Use valor maior (120, 200…) só quando a coluna tem largura mínima real de
layout. `validate.py` avisa (`autolayout-minsize`) em todo container sem isso.

> Não confunda com a orientação antiga "LayoutMin* quebra o AutoLayout, use 0 ou
> omita". No uso real é o contrário. Se encontrar essa frase num CLAUDE.md
> antigo, corrija.

**Altura pai × filhos:** se o pai calcula `Height` a partir dos filhos, os filhos
não podem ter altura esticada pelo pai — a tela cresce infinitamente
(gotcha `altura-pai-x-filhos`).

## 2. Dados e delegação

- **Alias plano sempre:** `PacientesData`, nunca `DataBase.Pacientes.data`
  (gotcha `database-indireto-nao-delega`). `Remove` é a única exceção conhecida
  e exige a datasource direta.
- **Não delegam:** `Distinct`, `Sort`, `in`, `Search`, `Or` entre dois
  `StartsWith`, `Trim()` aplicado na coluna. Delegam: `StartsWith`, comparação
  de data, `=`/`<>` em choice e lookup.
- **Validar delegação com dado real** fora das primeiras 500 linhas. O aviso do
  Studio tem falso positivo nos dois sentidos.
- **Coleção espelho** (`ClearCollect`) quando a mesma base alimenta galeria,
  rodapé e botões de paginação: **uma** definição, senão os três divergem — foi
  a causa raiz de dois bugs de paginação neste projeto.

## 3. Escrita

`Patch` sempre, nunca Forms. Padrões que se repetem:

```
// criar-ou-atualizar (idempotente)
With({_reg: LookUp(XData, chave = _id)},
    If(IsBlank(_reg.chave),
        Patch(XData, Defaults(XData), {...}),
        Patch(XData, _reg, {...})))
```

- **Nunca** monte o record de campos numa variável de `With` para passar ao
  `Patch`: o Studio acusa "a coluna X não existe, a mais parecida é X" e a coluna
  reclamada muda conforme você comenta a anterior. Deixe os campos **inline**.
- `ForAll` + `Patch` na mesma fonte exige `With` nomeando a origem
  (gotcha `forall-escreve-na-propria-fonte`).
- Coluna autonumber **nunca** entra no `Patch`.

## 4. UDFs e performance

- Argumento de UDF é **sempre avaliado** — não existe lazy
  (gotcha `udf-argumento-sempre-avaliado`). Para lazy: `If()` no `Default` do
  controle, ou UDF de predicado recebendo escalar já calculado.
- Em galeria, `LookUp` por linha é N+1. Se a mesma linha precisa de 3 campos do
  mesmo registro, carregue a coleção no `OnVisible` e faça `LookUp` na coleção,
  não na datasource.
- Matemática que aparece em mais de um lugar (painel de resumo + gravação) vira
  UDF única. Se divergir, o usuário vê um número e grava outro.

## 5. Choices e badges

```
Items:            ForAll(Choices(<optionset>), {LogicalName: ThisRecord.Value,
                      Value: BadgesChoiceName(Text(ThisRecord.Value))})
ItemDisplayText:  ThisItem.Value
DefaultSelected:  Filter(<o mesmo ForAll>, LogicalName = ctx.coluna)
Patch:            {coluna: Self.Selected.LogicalName}
```

`Choices()` recebe o **nome do optionset**, não `tabela.coluna`
(gotcha `combobox-choice-items`). Status sempre via
`BadgesChoiceName/Color/Fill` — nunca `Switch` inline na tela.

## 6. Navegação

Passe **escalares**, nunca record: `Navigate(srcX, Fade, {ctxAlgumId: GUID})`.
Record vindo de `Navigate` não traz lookups populados e falha em silêncio.
A tela de destino relê por ID no `OnVisible`.

Documente o "contrato de navegação" de cada tela num comentário no `OnVisible`:
quais `ctx` ela espera.

## 7. Popups

```
- cntOverlayPopupX:          # filho DA TELA, não de um container
    Variant: ManualLayout
    Properties:
      Fill: =RGBA(0, 0, 0, 0.42)
      Height: =Parent.Height
      Width: =Parent.Width
      Visible: =ctxPopupX
    Children:
      - cntPopupX:           # card centralizado
          Properties:
            DropShadow: =DropShadow.Bold
            X: =(Parent.Width - Self.Width) / 2
            Y: =(Parent.Height - Self.Height) / 2
```

Abrir/fechar só com `UpdateContext({ctxPopupX: true/false})`.
**Uma** definição de validação por popup: um label calcula a mensagem de bloqueio
e o botão lê `lblAviso.Text = ""` como "pode prosseguir". Evita a regra divergir
entre a mensagem e o `DisplayMode`.

## 8. Paginação (toda galeria)

```
Items: With({_base: colX, _ipp: Coalesce(ctxItensPorPagina, 6),
             _pag: Coalesce(ctxPag, 1)},
    FirstN(LastN(_base, CountRows(_base) - ((_pag - 1) * _ipp)), _ipp))
```

Rodapé ("Mostrando X-Y de Z") e botões ‹ › contam **a mesma** coleção.

## 9. Fluxos (Power Automate)

- O payload do Canvas e o schema do `Parse_JSON` mudam **sempre juntos**: chave
  fora do schema é ignorada em silêncio (gotcha `chave-fora-do-schema-e-ignorada`).
- Power Fx **não escolhe conector em runtime**. Para alternar entre dois fluxos,
  monte o payload **uma vez** numa variável e faça `Switch` com duas chamadas
  `.Run()` — duplicar o JSON garante que eles divergem.
- Os dois fluxos de um `Switch` devem devolver **o mesmo conjunto de chaves**,
  senão o Power Fx não unifica os tipos.
- Template de documento: caminho em **variável de ambiente**, nunca fixo na ação.

## 10. Formato

- Moeda: `Text(valor, "$ #,##0.00", "pt-BR")` — idioma no 3º argumento. Como tem
  `#`, vai em bloco `|-` (gotcha `yaml-cerquilha-comentario`).
- Data em coluna `datetime`: comparar com `< DateAdd(fim, 1, TimeUnit.Days)`
  (gotcha `data-datetime-comparacao-fim`).
- Separadores do Studio em inglês: `,` entre argumentos, `;` para encadear.
- Fórmula multi-linha em bloco `|-`; nunca string escapada com `\n`.

## 11. Comentários no código

Comente o **porquê**, não o quê. O comentário que vale é o que impede alguém de
"consertar" de volta:

```
// "& ''" e nao Coalesce(x, ""): Coalesce devolve Blank -> null no JSON
// Os 16 campos estao INLINE de proposito: quando vinham de um record montado
// num With, o Studio acusava coluna inexistente. Nao voltar a extrair.
```
