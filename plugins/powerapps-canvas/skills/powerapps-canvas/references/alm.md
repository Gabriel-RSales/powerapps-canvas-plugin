# ALM — Studio, Git, solution e deploy

## A regra que mais custa caro

**Quando alguém está editando no Studio, o Studio é a fonte da verdade.** O
export dele desce direto para o branch e **sobrescreve** o `.pa.yaml`.

| Situação | O que fazer |
|---|---|
| Correção que a pessoa vai fazer **no Studio** | Entregue só o Power Fx para colar (**sem o `=` inicial** — a barra de fórmulas já assume) e **não** edite o arquivo |
| Correção aplicada **no repo** | Commit + **push ANTES** de a pessoa abrir o Studio |
| Já editei o arquivo e ela vai abrir o Studio | Avise que há mudança local não commitada, para ela decidir |

Foi assim que um commit inteiro sumiu neste projeto: o export do Studio veio de
um branch que não o tinha. Quando for mexer, confira primeiro:

```bash
git fetch origin && git status --porcelain
git log --oneline HEAD..origin/main          # o que o Studio já mandou
```

## Loop de validação (é caro — consolide antes)

```
editar .pa.yaml
  -> python scripts/validate.py <repo>        # local, segundos
  -> commit + push
  -> merge no branch que o Studio lê
  -> abrir no Studio                          # única validação de Power Fx
```

Não existe compilador de Power Fx offline. O `validate.py` pega YAML, nome
duplicado, token/UDF inexistente e os gotchas conhecidos — o resto só o Studio
diz. Por isso: **junte as mudanças e valide em lote**, nunca uma por vez.

## Solution: export e unpack

Os `.yml` de `entities/`, `optionsets/` e `entityrelationships/` que o
`schema_mirror.py` lê vêm daqui.

> ⚠️ Os comandos `pac` abaixo **não** foram executados ao escrever esta skill
> (exigem autenticação num ambiente). Eles são o fluxo já usado no projeto de
> origem e estão aqui como referência — confirme os nomes antes de rodar.
> O que **foi** verificado é o consumo dos arquivos pelo `schema_mirror.py`.

```bash
pac auth create --environment <url-do-ambiente>
pac solution export --path ./build/Solution.zip --name <NomeDaSolution> --managed false
pac solution unpack --zipfile ./build/Solution.zip --folder ./Main/<NomeDaSolution> --packagetype Unmanaged
```

Depois, regenere o espelho:

```bash
python scripts/schema_mirror.py ./Main/<NomeDaSolution> -o SCHEMA.md
```

> O repo é um **retrato**, não o ambiente. Se o espelho divergir do que o app
> usa, o ambiente tem a verdade — reexporte (gotcha
> `export-desatualizado-vs-ambiente`).

## Variáveis de ambiente (environment variables)

Tudo que muda entre DEV/HML/PROD vira variável de ambiente, **nunca** valor fixo
dentro da ação do fluxo:

- site e biblioteca do SharePoint;
- caminho da pasta de modelos e de documentos;
- nome do arquivo de cada template Word;
- tokens/ids de sistemas externos (via Key Vault quando for segredo).

Motivo prático: numa solution **managed** o fluxo não é editável no destino. Se
o caminho do template estiver fixo na ação, não há como apontar para o arquivo
do ambiente novo sem desempacotar o zip. Com variável de ambiente, é um valor na
importação.

## Conector Word / documentos

O mapeamento de campos (`dynamicFileSchema`) usa os **IDs dos content controls
gravados dentro do .docx**. Consequências:

- copiar o arquivo mantém os IDs → o mapeamento sobrevive;
- recriar o template do zero gera IDs novos → remapear tudo;
- o designer **zera** o mapeamento quando você troca o arquivo pela interface.

Ao colar o `dynamicFileSchema` no designer: texto **com** aspas, array **sem**
(gotcha `dynamicfileschema-aspas-no-array`).

## Security roles

Checklist antes de PROD — a pergunta certa é "quem clica, e em que tabela isso
escreve?":

- [ ] cada perfil tem **Create/Read/Write** nas tabelas que suas telas escrevem;
- [ ] tela que cria registro numa tabela de **outra área** (ex.: Comercial
      criando um registro financeiro) — o perfil tem Create lá?
- [ ] privilégio dos **fluxos** (rodam como o invocador ou como dono?);
- [ ] acesso às **variáveis de ambiente** e conexões;
- [ ] gate de UI por perfil **não é segurança** — é conveniência. A segurança é
      a security role.

## Checklist de deploy

- [ ] `validate.py` sem `ERRO`
- [ ] colunas/optionsets/chaves alternativas novas criadas no ambiente destino
- [ ] espelho regenerado e conferido contra o que o app usa
- [ ] variáveis de ambiente preenchidas no destino
- [ ] conexões e referências de conexão religadas
- [ ] templates (.docx) presentes na biblioteca do destino
- [ ] security roles atribuídas
- [ ] dado legado compatível com as regras novas (status, vínculos)
- [ ] `CODE-REVIEW-TODO.md` atualizado com o que ficou pendente
