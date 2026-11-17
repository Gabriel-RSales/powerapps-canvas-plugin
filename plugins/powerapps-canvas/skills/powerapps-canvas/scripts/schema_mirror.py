#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera um ESPELHO em markdown do schema Dataverse a partir da solution exportada.

Por que existe: no Canvas voce escreve `ThisItem.'nome completo'` — o DISPLAY NAME,
nao o logical name. Errar o display name e o erro mais barato de cometer e o mais
caro de achar (o Studio so reclama quando voce abre a tela). Este script le os
.yml exportados e produz a lista exata de nomes utilizaveis, por tabela.

Tres coisas que so se descobre lendo os arquivos (e que este script resolve):
  * o nome que o Power Fx usa como "PK" e o display name do atributo
    `Type: primarykey` (ex.: d2_cirurgiaid -> `cirurgia`);
  * o ALVO de um lookup NAO esta no yml do atributo (LookupTypes vem vazio) —
    esta em entityrelationships/<nome>/entityrelationship.yml;
  * display name com espaco (ex.: `nome completo`) precisa de aspas simples no
    Power Fx; o script marca esses.

Uso:
    python schema_mirror.py <raiz_da_solution> [-o SCHEMA.md] [--json]

Onde <raiz_da_solution> e o diretorio que contem entities/ e optionsets/.
Os arquivos chegam ali via `pac solution export` + `pac solution unpack`
(ver SKILL.md, secao "Espelhar o banco").
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

try:
    import yaml
except ImportError:
    sys.exit("pyyaml necessario: pip install pyyaml")

# Colunas que o Dataverse cria sozinho — ruido em todo espelho.
SISTEMA = {
    "createdby", "createdon", "createdonbehalfby", "modifiedby", "modifiedon",
    "modifiedonbehalfby", "owningbusinessunit", "owningteam", "owninguser", "ownerid",
    "statecode", "statuscode", "importsequencenumber", "overriddencreatedon",
    "timezoneruleversionnumber", "utcconversiontimezonecode", "versionnumber",
    "exchangerate", "transactioncurrencyid",
}
# Tipos que viram "numero/texto/data" no Canvas sem distincao util.
APELIDO_TIPO = {
    "nvarchar": "texto", "ntext": "texto memo", "money": "moeda", "decimal": "decimal",
    "int": "inteiro", "float": "float", "double": "double", "bigint": "inteiro",
    "datetime": "data", "bit": "bit (Sim/Nao)", "picklist": "choice", "state": "choice",
    "status": "choice", "lookup": "lookup", "customer": "lookup", "owner": "lookup",
    "uniqueidentifier": "guid", "primarykey": "PK", "file": "file", "image": "image",
    "multiselectpicklist": "choice multi", "virtual": "virtual",
}


def ler_yaml(caminho):
    with io.open(caminho, encoding="utf-8") as fh:
        return yaml.safe_load(fh.read())


def cava(no, *chaves):
    """Desce por um dicionario aninhado sem estourar; '' se faltar algo."""
    atual = no
    for c in chaves:
        if not isinstance(atual, dict):
            return ""
        atual = atual.get(c)
    return atual if atual is not None else ""


def display_name(no):
    """O display name pode vir como dict unico OU lista (quando ha varios idiomas)."""
    alvo = cava(no, "displaynames", "displayname")
    if isinstance(alvo, list):
        alvo = alvo[0] if alvo else {}
    nome = cava(alvo, "@description")
    return nome if isinstance(nome, str) else ""


def le_relacionamentos(raiz):
    """(entidade_origem, atributo) -> entidade_alvo, lendo entityrelationships/."""
    mapa, base = {}, os.path.join(raiz, "entityrelationships")
    if not os.path.isdir(base):
        return mapa
    for nome in os.listdir(base):
        arq = os.path.join(base, nome, "entityrelationship.yml")
        if not os.path.exists(arq):
            continue
        try:
            rel = ler_yaml(arq).get("EntityRelationship", {})
        except Exception:
            continue
        origem = rel.get("ReferencingEntityName")
        attr = rel.get("ReferencingAttributeName")
        alvo = rel.get("ReferencedEntityName")
        if origem and attr and alvo:
            mapa[(origem, attr)] = alvo
    return mapa


def le_optionsets(raiz):
    """nome_do_optionset -> [(valor, rotulo_logico)]"""
    saida, base = {}, os.path.join(raiz, "optionsets")
    if not os.path.isdir(base):
        return saida
    for nome in sorted(os.listdir(base)):
        arq = os.path.join(base, nome, "optionset.yml")
        if not os.path.exists(arq):
            arq = next((os.path.join(base, nome, f)
                        for f in os.listdir(os.path.join(base, nome))
                        if f.endswith(".yml")), None)
        if not arq or not os.path.exists(arq):
            continue
        try:
            os_ = ler_yaml(arq).get("optionset", {})
        except Exception:
            continue
        opcoes = cava(os_, "options", "option")
        if isinstance(opcoes, dict):
            opcoes = [opcoes]
        itens = []
        for o in opcoes or []:
            rotulo = cava(o, "labels", "label")
            if isinstance(rotulo, list):
                rotulo = rotulo[0] if rotulo else {}
            itens.append((o.get("@value"), cava(rotulo, "@description")))
        saida[nome] = {
            "global": str(os_.get("IsGlobal", "")) == "1",
            "display": os_.get("@localizedName") or nome,
            "opcoes": itens,
        }
    return saida


def le_entidades(raiz, relacoes):
    saida, base = [], os.path.join(raiz, "entities")
    if not os.path.isdir(base):
        sys.exit("Nao achei entities/ em %s" % raiz)
    for logico in sorted(os.listdir(base)):
        dir_ent = os.path.join(base, logico)
        arq_ent = os.path.join(dir_ent, "entity.yml")
        if not os.path.isdir(dir_ent) or not os.path.exists(arq_ent):
            continue
        try:
            ent = ler_yaml(arq_ent).get("Entity", {}).get("EntityInfo", {}).get("entity", {})
        except Exception:
            ent = {}
        loc = cava(ent, "LocalizedNames", "LocalizedName")
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        amigavel = cava(loc, "@description") or logico

        colunas, pk = [], ""
        dir_attr = os.path.join(dir_ent, "attributes")
        if os.path.isdir(dir_attr):
            for arq in sorted(os.listdir(dir_attr)):
                if not arq.endswith(".yml"):
                    continue
                try:
                    a = ler_yaml(os.path.join(dir_attr, arq)).get("attribute", {})
                except Exception:
                    continue
                nome_fisico = a.get("PhysicalName") or a.get("@PhysicalName") or arq[:-4]
                curto = nome_fisico.lower()
                tipo = (a.get("Type") or "").lower()
                nome_exibido = display_name(a)
                if tipo == "primarykey":
                    pk = nome_exibido or nome_fisico
                    continue
                if curto in SISTEMA or curto.endswith("_base"):
                    continue
                if not nome_exibido:
                    continue
                col = {
                    "display": nome_exibido,
                    "logico": nome_fisico,
                    "tipo": APELIDO_TIPO.get(tipo, tipo or "?"),
                    "obrigatorio": (a.get("RequiredLevel") or "none") not in ("none", ""),
                }
                if tipo in ("lookup", "customer", "owner"):
                    col["alvo"] = relacoes.get((logico, nome_fisico), "?")
                if tipo in ("picklist", "state", "status", "multiselectpicklist"):
                    col["optionset"] = (a.get("OptionSetName")
                                        or cava(a, "optionset", "@Name") or "")
                colunas.append(col)
        saida.append({"logico": logico, "display": amigavel, "pk": pk, "colunas": colunas})
    return saida


def para_markdown(entidades, optionsets, raiz):
    L = []
    L.append("# Espelho do schema Dataverse\n")
    L.append("_Gerado por `scripts/schema_mirror.py` a partir de `%s`._\n" % raiz)
    L.append("_NAO editar a mao: rode o script de novo depois de `pac solution export`._\n")
    L.append("\n> No Canvas use o **display name** (coluna _Nome_), nunca o logico. "
             "Nome com espaco exige aspas simples: `ThisItem.'nome completo'`.\n")
    L.append("\n## Tabelas\n")
    for e in entidades:
        com_espaco = [c["display"] for c in e["colunas"] if " " in c["display"]]
        L.append("\n### `%s` — %s\n" % (e["logico"], e["display"]))
        L.append("\n**PK (Power Fx):** `%s`" % (e["pk"] or "?"))
        if com_espaco:
            L.append("  ·  ⚠️ display name com espaco (usar aspas simples): %s"
                     % ", ".join("`'%s'`" % n for n in com_espaco))
        L.append("\n\n| Nome (display) | Tipo | Detalhe | Logico |\n|---|---|---|---|\n")
        for c in sorted(e["colunas"], key=lambda x: x["display"]):
            detalhe = ""
            if "alvo" in c:
                detalhe = "-> `%s`" % c["alvo"]
            elif c.get("optionset"):
                detalhe = "optionset `%s`" % c["optionset"]
            if c["obrigatorio"]:
                detalhe = (detalhe + " · obrigatorio").strip(" ·")
            L.append("| `%s` | %s | %s | `%s` |\n"
                     % (c["display"], c["tipo"], detalhe, c["logico"]))
    if optionsets:
        L.append("\n## Optionsets\n")
        L.append("\n> No Canvas, referencie pelo nome LOGICO da opcao, nunca pelo numero.\n")
        for nome, os_ in sorted(optionsets.items()):
            escopo = "global" if os_["global"] else "local"
            L.append("\n### `%s` (%s)\n\n" % (nome, escopo))
            L.append(", ".join("`%s`" % r for _, r in os_["opcoes"] if r) or "_sem opcoes_")
            L.append("\n")
    return "".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", help="diretorio com entities/ e optionsets/")
    ap.add_argument("-o", "--out", help="arquivo .md de saida (default: stdout)")
    ap.add_argument("--json", action="store_true", help="saida JSON em vez de markdown")
    args = ap.parse_args()

    raiz = os.path.abspath(args.raiz)
    relacoes = le_relacionamentos(raiz)
    optionsets = le_optionsets(raiz)
    entidades = le_entidades(raiz, relacoes)

    if args.json:
        saida = json.dumps({"entidades": entidades, "optionsets": optionsets},
                           ensure_ascii=False, indent=2)
    else:
        saida = para_markdown(entidades, optionsets, os.path.basename(raiz))

    if args.out:
        with io.open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(saida)
        n_col = sum(len(e["colunas"]) for e in entidades)
        print("%s: %d tabelas, %d colunas, %d optionsets, %d relacionamentos"
              % (args.out, len(entidades), n_col, len(optionsets), len(relacoes)))
    else:
        print(saida)


if __name__ == "__main__":
    sys.exit(main())
