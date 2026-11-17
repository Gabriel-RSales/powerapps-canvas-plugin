#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Alimenta references/gotchas.yaml — o jeito de a skill nao errar duas vezes.

O ciclo: errou no Studio -> registra aqui -> o validate.py passa a pegar sozinho.

    # 1. registrar (com regra de lint, quando o erro e detectavel por texto)
    python gotcha.py add --id itemdisplaytext-isblank \\
        --title "ItemDisplayText nao aceita IsBlank" \\
        --symptom "The IsBlank function cannot be used in expressions on this property." \\
        --fix "Trocar IsBlank(x) por x = \\"\\" ou x > 0" \\
        --property ItemDisplayText --contains "IsBlank("

    # 2. conferir que a regra pega o caso real (e nao pega o resto do app)
    python validate.py <repo> --only itemdisplaytext-isblank

    # procurar antes de depurar
    python gotcha.py find "cannot be used in expressions"
    python gotcha.py list
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("pyyaml necessario: pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
ARQ = os.path.normpath(os.path.join(HERE, "..", "references", "gotchas.yaml"))


def carrega():
    if not os.path.exists(ARQ):
        return []
    with io.open(ARQ, encoding="utf-8") as fh:
        return yaml.safe_load(fh.read()) or []


def bloco_yaml(texto, recuo="    "):
    """Texto longo vira bloco ">-" para nao brigar com aspas e dois-pontos."""
    linhas, atual = [], ""
    for palavra in texto.split():
        if len(atual) + len(palavra) + 1 > 76:
            linhas.append(atual)
            atual = palavra
        else:
            atual = (atual + " " + palavra).strip()
    if atual:
        linhas.append(atual)
    if len(linhas) == 1 and ":" not in texto and "'" not in texto:
        return " %s" % linhas[0]
    return " >-\n" + "\n".join(recuo + l for l in linhas)


def cmd_add(args):
    dados = carrega()
    if any(g.get("id") == args.id for g in dados):
        sys.exit("Ja existe gotcha com id '%s'. Edite %s a mao." % (args.id, ARQ))
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", args.id):
        sys.exit("id deve ser slug minusculo com hifens (ex.: itemdisplaytext-isblank)")

    partes = ["\n- id: %s" % args.id,
              "  title:%s" % bloco_yaml(args.title, "    "),
              "  severity: %s" % args.severity]
    if args.symptom:
        partes.append("  symptom:%s" % bloco_yaml(args.symptom, "    "))
    if args.fix:
        partes.append("  fix:%s" % bloco_yaml(args.fix, "    "))
    if args.why:
        partes.append("  why:%s" % bloco_yaml(args.why, "    "))
    partes.append("  verified: %s" % (args.verified or dt.date.today().isoformat()))

    if args.contains or args.regex:
        partes.append("  rule:")
        if args.property:
            partes.append("    property: %s" % args.property)
        chave = "contains" if args.contains else "regex"
        valor = args.contains or args.regex
        if args.regex:
            try:
                re.compile(valor)
            except re.error as erro:
                sys.exit("regex invalida: %s" % erro)
        partes.append("    %s: %s" % (chave, yaml_escalar(valor)))

    with io.open(ARQ, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(partes) + "\n")

    # releitura: um YAML quebrado aqui derruba o validate.py inteiro
    try:
        novo = carrega()
    except yaml.YAMLError as erro:
        sys.exit("ESCREVI YAML INVALIDO em %s — corrija a mao:\n%s" % (ARQ, erro))
    assert any(g.get("id") == args.id for g in novo), "gravou mas nao releu"

    print("gotcha '%s' gravado (%d no total)" % (args.id, len(novo)))
    if args.contains or args.regex:
        print("confira a regra:  python validate.py <repo> --only %s" % args.id)
    else:
        print("sem regra de lint: fica como leitura obrigatoria em gotchas.yaml")


def yaml_escalar(valor):
    """Aspas simples, duplicando as internas — seguro para regex e para '#'."""
    return "'%s'" % valor.replace("'", "''")


def cmd_list(args):
    dados = carrega()
    com_regra = [g for g in dados if g.get("rule")]
    for g in dados:
        marca = "[lint]" if g.get("rule") else "      "
        print("%s %-34s %-8s %s" % (marca, g.get("id", "?"),
                                    g.get("severity", "?"), g.get("title", "")[:58]))
    print("\n%d gotchas, %d com lint automatico" % (len(dados), len(com_regra)))


def cmd_find(args):
    termo = args.termo.lower()
    achou = 0
    for g in carrega():
        campos = " ".join(str(g.get(k, "")) for k in
                          ("id", "title", "symptom", "fix", "why"))
        if termo in campos.lower():
            achou += 1
            print("\n=== %s  (%s, verificado %s)" % (
                g.get("id"), g.get("severity", "?"), g.get("verified", "?")))
            print("  %s" % g.get("title", ""))
            if g.get("symptom"):
                print("  sintoma: %s" % g["symptom"])
            if g.get("fix"):
                print("  conserto: %s" % g["fix"])
    if not achou:
        print("Nada para '%s'. Se o erro e novo, registre:\n"
              "  python gotcha.py add --id <slug> --title ... --symptom ... --fix ..."
              % args.termo)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="registrar um gotcha novo")
    a.add_argument("--id", required=True, help="slug minusculo com hifens")
    a.add_argument("--title", required=True, help="uma linha: o que esta errado")
    a.add_argument("--symptom", help="a mensagem EXATA do Studio/runtime")
    a.add_argument("--fix", help="o conserto")
    a.add_argument("--why", help="causa raiz, se apurada")
    a.add_argument("--severity", default="error", choices=["error", "warning"])
    a.add_argument("--verified", help="data (default: hoje)")
    a.add_argument("--property", help="limitar a regra a uma propriedade (ex. ItemDisplayText)")
    a.add_argument("--contains", help="regra: substring literal")
    a.add_argument("--regex", help="regra: expressao regular")
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("list", help="listar todos")
    l.set_defaults(func=cmd_list)

    f = sub.add_parser("find", help="procurar por sintoma/mensagem de erro")
    f.add_argument("termo")
    f.set_defaults(func=cmd_find)

    args = ap.parse_args()
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
