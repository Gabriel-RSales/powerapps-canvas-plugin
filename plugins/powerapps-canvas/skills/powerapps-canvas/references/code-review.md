# Code review e dívida técnica

Power Apps não tem linter nem PR review nativo. Sem um lugar para registrar
dívida, ela vira conhecimento oral e some. O padrão: **um arquivo
`CODE-REVIEW-TODO.md` na raiz do repo**, versionado junto com o app.

## Por que um arquivo, e não issues

A dívida de Canvas é quase sempre **transversal** ("os 7 filtros copiados",
"391 trocas de datasource") e **dependente de ordem** (consolidar o modelo
ANTES de trocar os lookups). Issue por item perde as duas coisas. O arquivo fica
ao lado do código, entra no diff e o agente lê antes de mexer.

## Formato de uma entrada

````markdown
### ⭐⭐⭐⭐⭐ `d2_medico` tem UMA LINHA POR GRUPO CLÍNICO — CORRIGIR O MODELO

O mesmo médico existe em vários registros. Consequência que já causou erro:

**Casar médico por PK (`id_medico.medico`) está errado neste modelo.** A regra
pode estar em qualquer linha do médico e o `LookUp` devolve `Blank()` em
silêncio. Em set/2026 eu "corrigi" 4 lookups de nome para PK argumentando
homônimos, e tive de reverter.

| Problema | Efeito |
|---|---|
| `id_nibo` e `crm` duplicados por linha | risco de divergirem entre as linhas |

**Ordem da migração** (trocar para PK antes de consolidar reintroduz a falha):
1. Criar `d2_medico_grupo_clinico` (N:N) e migrar o lookup.
2. Consolidar as linhas duplicadas (repontar 6 lookups — lista abaixo).
3. Só então trocar `id_medico.nome` → `id_medico.medico` e tirar os `Distinct`.
4. Chave alternativa para impedir duplicata nova.
````

Os elementos que fazem a entrada funcionar:

- **Severidade em estrelas** (⭐ a ⭐⭐⭐⭐⭐). Dívida de **modelo** é 5: ela se
  espalha por todas as telas e fica mais cara a cada semana.
- **O sintoma**, não só o diagnóstico — "devolve Blank em silêncio" é o que
  permite reconhecer o bug quando ele aparecer de novo.
- **A tentativa que falhou**, com data. Sem isso alguém repete.
- **A ordem**, quando há dependência. É o conteúdo mais valioso da entrada.
- **A lista exata** de pontos a repontar. Transforma "um dia a gente arruma" em
  tarefa executável.

## Marcações

| Marca | Significado |
|---|---|
| `🔴` | bloqueia deploy / abrir o Studio |
| `⭐`…`⭐⭐⭐⭐⭐` | severidade da dívida |
| `~~riscado~~ ✅ RESOLVIDO (data)` | resolvido — **mantenha no arquivo** |
| `### A confirmar` | hipótese não verificada no Studio |

Não apague o resolvido: ele é o registro de que a decisão foi tomada e por quê.
Risque e date.

## Rotina

**Antes de mexer numa tela:** leia a seção dela aqui e rode

```bash
python scripts/validate.py <repo>
```

**Ao terminar uma tarefa**, registre o que você viu e não consertou — dívida
vista e não anotada é dívida perdida. Inclua:

- o que ficou de fora do escopo e por quê;
- padrão que se repete e ainda não foi unificado (com a contagem: "6×");
- pendência de Dataverse que a tela já assume (coluna, chave alternativa,
  security role);
- dado legado que o modelo novo não alcança.

**Ao descobrir uma armadilha nova** (sintoma + conserto), ela não vai para o
TODO: vai para `gotchas.yaml` via `scripts/gotcha.py add`, para virar lint.
O TODO é para dívida; o gotchas é para armadilha.

## Revisar mudança de Canvas

O diff de `.pa.yaml` é ruidoso (o Studio reordena propriedades). Revise por
comportamento, nessa ordem:

1. `python scripts/validate.py <repo>` — zero `ERRO` antes de qualquer coisa.
2. **Contrato de navegação** mudou? Toda tela que faz `Navigate` para ela precisa
   passar os novos `ctx`.
3. **Escrita no Dataverse**: todo `Patch` novo tem as colunas que existem? (Confira
   contra o espelho: `scripts/schema_mirror.py`.)
4. **Delegação**: `Filter`/`LookUp` novo usa alias plano e função que delega?
5. **Estado**: alguma transição de status fica sem quem a dispare, ou dispara
   duas vezes?
6. **Permissão**: a tela passou a escrever numa tabela nova? O perfil que a usa
   tem Create/Write nela?
