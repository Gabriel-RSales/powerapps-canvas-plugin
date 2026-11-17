# Bootstrap — projeto Canvas novo

Montar `App.Formulas` **antes** da primeira tela é o que mais economiza tempo
depois. Sem isso, cores e `Switch` de status se espalham por 20 telas e não tem
mais volta barata.

Troque `APP_` pelo prefixo do projeto (3–5 letras). O `validate.py` detecta o
prefixo sozinho.

## `App.Formulas` — esqueleto

```powerfx
// ============================================================
// 1. FONTES — alias PLANO por tabela. É o que delega.
//    NUNCA DataBase.<T>.data em Filter/LookUp.
// ============================================================
PacientesData = pacientes;
PedidosData = pedidos;
ItensPedidoData = item_pedidos;

// 2. CHOICES — o record aninhado serve SÓ para choices.
DataBase = {
    Pedidos: {
        data: pedidos,
        choices: {status: status_pedido, tipo: tipo_pedido}
    },
    Pacientes: {data: pacientes, choices: {sexo: sexo_paciente}}
};

// ============================================================
// 3. DESIGN TOKENS — nenhuma cor/medida literal nas telas
// ============================================================
APP_Color_Primary = RGBA(31, 78, 160, 1);
APP_Color_OnPrimary = RGBA(255, 255, 255, 1);
APP_Color_Surface = RGBA(255, 255, 255, 1);
APP_Color_SurfaceContainerLow = RGBA(246, 248, 252, 1);
APP_Color_OnSurface = RGBA(28, 32, 38, 1);
APP_Color_OnSurfaceVariant = RGBA(96, 104, 116, 1);
APP_Color_OutlineVariant = RGBA(222, 228, 236, 1);
APP_Color_Error = RGBA(186, 26, 26, 1);
APP_Color_Transparent = RGBA(0, 0, 0, 0);

APP_Space_Xs = 4;   APP_Space_Sm = 8;   APP_Space_Base = 12;
APP_Space_Md = 16;  APP_Space_Lg = 24;  APP_Content_Margin = 24;

APP_Radius_Default = 8;  APP_Radius_Full = 999;
APP_Card_Radius = 12;    APP_Card_Padding = 24;
APP_Input_Height = 40;   APP_Input_Radius = 8;
APP_Button_Height = 44;  APP_Button_Radius = 8;

APP_Font_Family = Font.'Open Sans';
APP_FontSize_LabelMd = 10;  APP_FontSize_BodyMd = 12;

// badges: um par Fill/Text por intenção
APP_Badge_SuccessFill = RGBA(226, 246, 232, 1);
APP_Badge_SuccessText = RGBA(22, 104, 54, 1);
APP_Badge_WarningFill = RGBA(255, 244, 222, 1);
APP_Badge_WarningText = RGBA(140, 90, 0, 1);
APP_Badge_ErrorFill = RGBA(253, 231, 231, 1);
APP_Badge_ErrorText = RGBA(150, 24, 24, 1);
APP_Badge_NeutralFill = RGBA(238, 240, 244, 1);
APP_Badge_NeutralText = RGBA(90, 98, 110, 1);

// ============================================================
// 4. BADGES — UM Switch no app inteiro. Nunca Switch inline na tela.
//    Default = o próprio valor: rótulo novo no optionset não vira vazio.
// ============================================================
BadgesChoiceName(_valor:Text):Text = Switch(_valor,
    Text(DataBase.Pedidos.choices.status.rascunho), "Rascunho",
    Text(DataBase.Pedidos.choices.status.aprovado), "Aprovado",
    _valor
);
BadgesChoiceFill(_valor:Text):Color = Switch(_valor,
    Text(DataBase.Pedidos.choices.status.rascunho), APP_Badge_WarningFill,
    Text(DataBase.Pedidos.choices.status.aprovado), APP_Badge_SuccessFill,
    APP_Badge_NeutralFill
);
BadgesChoiceColor(_valor:Text):Color = Switch(_valor,
    Text(DataBase.Pedidos.choices.status.rascunho), APP_Badge_WarningText,
    Text(DataBase.Pedidos.choices.status.aprovado), APP_Badge_SuccessText,
    APP_Badge_NeutralText
);

// ============================================================
// 5. UTILITÁRIOS que todo projeto acaba precisando
// ============================================================
// Coluna bit NÃO é boolean em contexto de propriedade (ver gotchas).
OptionSetBIT_Parse(_bit:Boolean):Boolean = Coalesce(_bit, false);

// Usuário logado como record do Dataverse (para lookups "criado por").
UsuarioSistemaAtual = LookUp(Usuários, 'Email Primário' = User().Email);

// Texto seguro para JSON: Coalesce(x, "") devolve Blank (ver gotchas).
TextoSeguro(_t:Text):Text = _t & "";
```

## Componentes que valem a pena no dia 1

- `cmpAppSidebar` — menu por área. Propriedades: `MenuItems` (Table de
  `{Titulo, Rota, Icone, Visivel}`), `TituloApp`, `ExibirSair`, `OnSairSelect`
  (evento — **precisa de `Default` não vazio**, gotcha `pa2231-evento-sem-default`).
- `cmpAppTopbar` — título + busca. Saída `TextoPesquisa`.
- `cmpLoading` — overlay com spinner, `Visible = ctxLoading`.

Componente com propriedade de entrada do tipo **Event** sempre com
`Default: =false`.

## Ordem de montagem

1. `App.Formulas` (acima) + conexões.
2. `scripts/schema_mirror.py` → `SCHEMA.md` — a lista de display names.
3. Componentes de casca (sidebar/topbar/loading).
4. Uma tela de **lista** completa: header AutoLayout + galeria + paginação +
   badges. Ela vira o molde; copie para as outras.
5. `CODE-REVIEW-TODO.md` vazio, com as seções.
6. `validate.py` antes do primeiro push.

## Modelagem — decidir cedo

- **Uma linha = uma entidade de negócio.** Se "a mesma pessoa" existe em várias
  linhas (uma por filial/grupo), todo `LookUp` por PK vira falha silenciosa.
  Resolva com N:N desde o começo (gotcha `medico-duplicado-casar-por-nome`).
- **Status é máquina de estados** e mora em **uma** tabela. Status derivado
  ("calculado mas alterado depois") se **calcula**, não se grava — dois campos
  para o mesmo fato desincronizam.
- **Invariante do servidor é chave alternativa**, não validação de tela. "Uma
  ordem por fechamento" só é verdade com chave alternativa.
- **Snapshot vs. referência:** valor que precisa sobreviver a mudança de preço
  é copiado (snapshot) no momento do fato, não lido por lookup.
