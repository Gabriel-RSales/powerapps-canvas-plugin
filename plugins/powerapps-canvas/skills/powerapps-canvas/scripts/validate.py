#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Valida um app Canvas (.pa.yaml) ANTES de abrir o Power Apps Studio.

Por que existe: nao ha validacao de Power Fx offline. Cada erro descoberto no
Studio custa um ciclo commit -> push -> merge -> abrir o Studio. Este script pega
a classe de erro que da para pegar sem o Studio:

  1. YAML invalido        - o Studio recusa o import (e a causa #1 e sempre a mesma:
                            escalar nao-quotado com ": " dentro)
  2. Nome de controle      - duplicado no app (o Studio renomeia em silencio)
  3. Token/UDF inexistente - IMCP_Xxx ou UDF que nao esta no App.Formulas
  4. Gotchas conhecidos    - regras de references/gotchas.yaml (data-driven)
  5. AutoLayout            - container sem LayoutMinHeight/Width (ver gotcha
                            autolayout-minsize)

Uso:
    python validate.py [raiz_do_repo] [--json] [--only ID] [--quiet]

Saida: exit 0 = limpo, 1 = ha ERROS, 2 = so avisos (com --strict vira 1).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import defaultdict

try:
    import yaml
except ImportError:
    sys.exit("pyyaml necessario: pip install pyyaml")

# O Studio exporta `Propriedade: =` (valor vazio). O pyyaml le o `=` solitario
# como a tag YAML 1.1 "value" e quebra. Sem isto, ~metade das telas falha.
yaml.SafeLoader.add_constructor(
    "tag:yaml.org,2002:value", lambda loader, node: loader.construct_scalar(node)
)

HERE = os.path.dirname(os.path.abspath(__file__))
GOTCHAS = os.path.join(HERE, "..", "references", "gotchas.yaml")

# Propriedades que todo controle tem; nao sao "desconhecidas" num componente.
PROPS_EMBUTIDAS = {
    "Height", "Width", "X", "Y", "Visible", "Fill", "DisplayMode",
    "TabIndex", "OnReset", "ZIndex",
}


class Achado:
    def __init__(self, nivel, regra, arquivo, linha, msg, fix=""):
        self.nivel, self.regra = nivel, regra
        self.arquivo, self.linha = arquivo, linha
        self.msg, self.fix = msg, fix

    def como_dict(self):
        return {
            "nivel": self.nivel, "regra": self.regra, "arquivo": self.arquivo,
            "linha": self.linha, "msg": self.msg, "fix": self.fix,
        }


def ler(caminho):
    with io.open(caminho, encoding="utf-8") as fh:
        return fh.read()


def mascara(texto, strings=False):
    """Apaga comentarios Power Fx (e opcionalmente strings), PRESERVANDO offsets.

    Sem isto o lint acusa a propria documentacao: o comentario em App.Formulas que
    ensina "nunca use DataBase.X.data" virava um ERRO database-indireto-nao-delega.
    Troca por espaco em vez de remover para os numeros de linha continuarem certos.
    Varre caractere a caractere porque "//" dentro de string (https://) nao e
    comentario, e aspas dentro de comentario nao abrem string.
    """
    saida = list(texto)
    i, n = 0, len(texto)
    aspas = None          # '"' = string; "'" = identificador Power Fx ('Nome Com Espaco')
    em_linha = em_bloco = False
    while i < n:
        c = texto[i]
        prox = texto[i + 1] if i + 1 < n else ""
        if em_linha:
            if c == "\n":
                em_linha = False
            else:
                saida[i] = " "
        elif em_bloco:
            if c == "*" and prox == "/":
                saida[i] = saida[i + 1] = " "
                i += 2
                em_bloco = False
                continue
            if c != "\n":
                saida[i] = " "
        elif aspas:
            if c == aspas:
                aspas = None
                if strings:
                    saida[i] = " "
            elif strings and c != "\n":
                saida[i] = " "
        else:
            if c == "/" and prox == "/":
                em_linha = True
                saida[i] = " "
            elif c == "/" and prox == "*":
                em_bloco = True
                saida[i] = saida[i + 1] = " "
                i += 2
                continue
            elif c in "\"'":
                aspas = c
                if strings:
                    saida[i] = " "
        i += 1
    return "".join(saida)


def achar_src(raiz):
    """Todos os diretorios Src/ que contenham .pa.yaml (um por canvas app)."""
    encontrados = []
    for atual, dirs, arquivos in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", ".venv")]
        if os.path.basename(atual) == "Src" and any(a.endswith(".pa.yaml") for a in arquivos):
            encontrados.append(atual)
    return encontrados


def achar_schema(raiz):
    """Diretorios de schema do Dataverse exportado (entities/optionsets/...)."""
    dirs = {}
    for atual, subdirs, _ in os.walk(raiz):
        subdirs[:] = [d for d in subdirs if d not in (".git", "node_modules")]
        base = os.path.basename(atual)
        if base in ("entities", "optionsets", "entityrelationships") and base not in dirs:
            dirs[base] = atual
    return dirs


# --------------------------------------------------------------- 1. YAML
def valida_yaml(arquivos, achados):
    docs = {}
    for caminho, texto in arquivos.items():
        try:
            docs[caminho] = yaml.safe_load(texto)
        except yaml.YAMLError as erro:
            marca = getattr(erro, "problem_mark", None)
            linha = marca.line + 1 if marca else 0
            dica = ""
            if marca:
                bruta = texto.split("\n")[marca.line] if marca.line < len(texto.count("\n") + 1 and texto.split("\n")) else ""
                if ": " in bruta and bruta.strip().startswith(("=", "- ")) is False:
                    dica = ('Escalar nao-quotado com ": " dentro. Ponha a formula em bloco '
                            '"|-" ou tire o espaco do record inline ({chave:valor}).')
            achados.append(Achado(
                "ERRO", "yaml-invalido", caminho, linha,
                str(getattr(erro, "problem", erro)).strip(), dica))
    return docs


# ------------------------------------------------------- 2. nomes de controle
RE_CONTROLE = re.compile(r"^(\s+)- ([A-Za-z_]\w*):\s*$", re.M)


def valida_nomes(arquivos, achados, prefixos):
    vistos = defaultdict(list)
    for caminho, texto in arquivos.items():
        if os.path.basename(caminho) == "_EditorState.pa.yaml":
            continue
        for m in RE_CONTROLE.finditer(texto):
            linha = texto.count("\n", 0, m.start()) + 1
            vistos[m.group(2)].append((caminho, linha))

    for nome, locais in sorted(vistos.items()):
        if len(locais) > 1:
            onde = ", ".join("%s:%d" % (os.path.basename(a), l) for a, l in locais)
            achados.append(Achado(
                "ERRO", "nome-duplicado", locais[0][0], locais[0][1],
                "Controle '%s' definido %d vezes (%s)" % (nome, len(locais), onde),
                "Nome de controle e global no app. Renomeie um deles."))

    if not prefixos:
        return
    validos = tuple(prefixos)
    for nome, locais in sorted(vistos.items()):
        base = nome.lstrip("_")
        if base and not base.startswith(validos) and not base[0].isupper():
            achados.append(Achado(
                "AVISO", "nome-fora-do-padrao", locais[0][0], locais[0][1],
                "Controle '%s' nao comeca com prefixo conhecido (%s)" % (nome, "/".join(prefixos)),
                "Ver references/naming.md"))


# ------------------------------------------------------- 3. tokens e UDFs
RE_TOKEN_DEF = re.compile(r"^\s+([A-Z][A-Za-z0-9]*_\w+)\s*=", re.M)
RE_UDF_DEF = re.compile(r"^\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*:\s*\w+\s*=", re.M)


def detecta_prefixo_token(texto_app):
    contagem = defaultdict(int)
    for nome in RE_TOKEN_DEF.findall(texto_app):
        contagem[nome.split("_")[0]] += 1
    if not contagem:
        return None
    return max(contagem.items(), key=lambda kv: kv[1])[0]


def valida_tokens_udfs(arquivos, achados, caminho_app):
    if not caminho_app:
        return None
    texto_app = arquivos[caminho_app]
    prefixo = detecta_prefixo_token(texto_app)
    tokens = set(RE_TOKEN_DEF.findall(texto_app))
    udfs = set(RE_UDF_DEF.findall(texto_app))
    # funcoes nativas do Power Fx que casam com o padrao de UDF do projeto
    nativas = {
        "If", "Switch", "Text", "Value", "Sum", "Filter", "LookUp", "Sort", "ForAll",
        "With", "Patch", "Collect", "ClearCollect", "Set", "UpdateContext", "Navigate",
        "Notify", "IsBlank", "IsEmpty", "CountRows", "Coalesce", "Concat", "Distinct",
        "Date", "DateAdd", "Today", "Now", "Year", "Month", "Day", "Abs", "Round",
        "RoundDown", "RoundUp", "Min", "Max", "Left", "Right", "Mid", "Len", "Trim",
        "Substitute", "Sequence", "AddColumns", "ShowColumns", "RenameColumns",
        "FirstN", "LastN", "First", "Last", "Defaults", "Refresh", "Remove", "Select",
        "Reset", "Launch", "Back", "Proper", "Upper", "Lower", "IsMatch", "Match",
        "Choices", "Table", "Blank", "GUID", "Rand", "IsNumeric", "EOMonth", "ColorFade",
        "RGBA", "Char", "JSON", "ParseJSON", "IfError", "Errors", "SortByColumns",
        "GroupBy", "Ungroup", "AddMedia", "Param", "User", "Language", "StartsWith",
        "EndsWith", "Weekday", "Hour", "Minute", "Second", "Time", "DateDiff",
        "DateValue", "TimeValue", "DateTimeValue", "Power", "Sqrt", "Mod", "Int",
        "ColorValue", "EncodeUrl", "RemoveIf", "UpdateIf", "Relate", "Unrelate",
        "SaveData", "LoadData", "ClearData", "Clear", "Concatenate", "Split",
        "Replace", "Find", "Shuffle", "CountIf", "CountA", "Average", "StdevP",
        "VarP", "Index", "Exit", "Revert", "Validate", "DataSourceInfo", "Column",
        "Boolean", "Decimal", "Float", "Trace", "Assert", "SetFocus", "ShowError",
        "RequestHide", "ViewForm", "EditForm", "NewForm", "SubmitForm", "ResetForm",
        "Acceleration", "Compass", "Location", "Connection", "Host", "Self", "Parent",
        "ThisItem", "ThisRecord", "Enable", "Disable", "Copy", "Download", "Print",
    }
    for caminho, texto in arquivos.items():
        if caminho == caminho_app or os.path.basename(caminho) == "_EditorState.pa.yaml":
            continue
        sem_coment = mascara(texto)
        so_codigo = mascara(texto, strings=True)
        if prefixo:
            for m in re.finditer(r"\b(%s_\w+)\b" % prefixo, sem_coment):
                if m.group(1) not in tokens:
                    achados.append(Achado(
                        "ERRO", "token-inexistente", caminho,
                        texto.count("\n", 0, m.start()) + 1,
                        "Token '%s' nao existe em App.Formulas" % m.group(1),
                        "Defina em App.Formulas ou corrija o nome."))
        for m in re.finditer(r"(?<![.\w])([A-Z][A-Za-z0-9]{3,})\s*\(", so_codigo):
            nome = m.group(1)
            if nome in nativas or nome in udfs or nome in tokens:
                continue
            # so reclama do que PARECE UDF do projeto (CamelCase composto). O
            # lookbehind acima ja descarta `.Propriedade(` — propriedade custom de
            # componente (Self.OnSairSelect()) nao e UDF.
            if re.match(r"^[A-Z][a-z]+[A-Z]", nome):
                achados.append(Achado(
                    "AVISO", "udf-desconhecida", caminho,
                    texto.count("\n", 0, m.start()) + 1,
                    "'%s(' nao e UDF do App.Formulas nem funcao nativa conhecida" % nome,
                    "Se for UDF nova, defina em App.Formulas; se for nativa, "
                    "acrescente a lista 'nativas' deste script."))
    return prefixo


# ------------------------------------------------- 4. gotchas (data-driven)
def carrega_gotchas():
    if not os.path.exists(GOTCHAS):
        return []
    dados = yaml.safe_load(ler(GOTCHAS)) or []
    return [g for g in dados if isinstance(g, dict)]


def bloco_de_propriedades(texto):
    """Itera (nome_prop, valor, linha). Cobre `Prop: =expr` e `Prop: |-` em bloco."""
    linhas = texto.split("\n")
    i = 0
    while i < len(linhas):
        m = re.match(r"^(\s+)([A-Za-z_]\w*):\s*(.*)$", linhas[i])
        if not m:
            i += 1
            continue
        recuo, nome, resto = len(m.group(1)), m.group(2), m.group(3)
        if resto.strip() in ("|-", "|", ">-", ">"):
            corpo, j = [], i + 1
            while j < len(linhas) and (not linhas[j].strip()
                                       or len(linhas[j]) - len(linhas[j].lstrip()) > recuo):
                corpo.append(linhas[j])
                j += 1
            yield nome, "\n".join(corpo), i + 1
            i = j
        else:
            yield nome, resto, i + 1
            i += 1


def aplica_gotchas(arquivos, achados, gotchas, so_id=None):
    for caminho, bruto in arquivos.items():
        if os.path.basename(caminho) == "_EditorState.pa.yaml":
            continue
        # comentario mascarado, string PRESERVADA: regras como coalesce-string-vazia
        # dependem do literal "" para casar.
        texto = mascara(bruto)
        props = None
        for g in gotchas:
            regra = g.get("rule")
            if not regra or (so_id and g.get("id") != so_id):
                continue
            nivel = "ERRO" if g.get("severity", "error") == "error" else "AVISO"
            alvo_prop, padrao = regra.get("property"), regra.get("regex") or regra.get("contains")
            if not padrao:
                continue
            literal = "contains" in regra
            if alvo_prop:
                if props is None:
                    props = list(bloco_de_propriedades(texto))
                for nome, valor, linha in props:
                    if nome != alvo_prop:
                        continue
                    bate = padrao in valor if literal else re.search(padrao, valor)
                    if bate:
                        achados.append(Achado(nivel, g["id"], caminho, linha,
                                              g.get("title", g["id"]), g.get("fix", "")))
            else:
                it = ([(m.start(), None) for m in re.finditer(padrao, texto)] if not literal
                      else [(p, None) for p in _acha_todos(texto, padrao)])
                for pos, _ in it:
                    achados.append(Achado(nivel, g["id"], caminho,
                                          texto.count("\n", 0, pos) + 1,
                                          g.get("title", g["id"]), g.get("fix", "")))


def _acha_todos(texto, agulha):
    pos, saida = texto.find(agulha), []
    while pos != -1:
        saida.append(pos)
        pos = texto.find(agulha, pos + 1)
    return saida


# ------------------------------------------------------ 5. AutoLayout minsize
def valida_autolayout(arquivos, achados):
    """Container AutoLayout sem LayoutMinHeight/Width colapsa ou ignora o tamanho
    automatico. Ver gotcha autolayout-minsize."""
    for caminho, texto in arquivos.items():
        linhas = texto.split("\n")
        for i, linha in enumerate(linhas):
            m = re.match(r"^(\s+)- ([A-Za-z_]\w*):\s*$", linha)
            if not m:
                continue
            recuo, nome = len(m.group(1)), m.group(2)
            if i + 2 >= len(linhas):
                continue
            janela = "\n".join(linhas[i + 1:i + 3])
            if "Variant: AutoLayout" not in janela:
                continue
            fim = i + 1
            while fim < len(linhas) and (not linhas[fim].strip()
                                         or len(linhas[fim]) - len(linhas[fim].lstrip()) > recuo):
                fim += 1
            corpo = "\n".join(linhas[i:fim])
            props_diretas = [p for p, _, _ in bloco_de_propriedades(corpo)]
            vertical = "LayoutDirection.Vertical" in corpo
            precisa = "LayoutMinHeight" if vertical else "LayoutMinWidth"
            if precisa not in props_diretas:
                achados.append(Achado(
                    "AVISO", "autolayout-minsize", caminho, i + 1,
                    "Container AutoLayout '%s' (%s) sem %s" % (
                        nome, "vertical" if vertical else "horizontal", precisa),
                    "Defina %s: =10 (valor pequeno). Ver gotcha autolayout-minsize." % precisa))


# ------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", nargs="?", default=".", help="raiz do repo (default: .)")
    ap.add_argument("--json", action="store_true", help="saida JSON")
    ap.add_argument("--only", help="rodar so uma regra (id do gotcha)")
    ap.add_argument("--strict", action="store_true", help="aviso tambem falha")
    ap.add_argument("--quiet", action="store_true", help="so o resumo")
    args = ap.parse_args()

    raiz = os.path.abspath(args.raiz)
    dirs_src = achar_src(raiz)
    if not dirs_src:
        sys.exit("Nenhum diretorio Src/ com .pa.yaml abaixo de %s" % raiz)

    arquivos = {}
    for d in dirs_src:
        for nome in sorted(os.listdir(d)):
            if nome.endswith(".pa.yaml"):
                p = os.path.join(d, nome)
                arquivos[os.path.relpath(p, raiz)] = ler(p)
        comp = os.path.join(d, "Components")
        if os.path.isdir(comp):
            for nome in sorted(os.listdir(comp)):
                if nome.endswith(".pa.yaml"):
                    p = os.path.join(comp, nome)
                    arquivos[os.path.relpath(p, raiz)] = ler(p)

    caminho_app = next((k for k in arquivos if os.path.basename(k) == "App.pa.yaml"), None)
    achados = []
    gotchas = carrega_gotchas()

    if args.only:
        # Modo "testar UMA regra": nada mais roda, senao o achado que interessa
        # some no meio de centenas de avisos estruturais. E o modo usado logo
        # depois de `gotcha.py add`.
        if args.only not in {g.get("id") for g in gotchas}:
            sys.exit("Nao existe gotcha com id '%s' (veja: python gotcha.py list)" % args.only)
        prefixo = detecta_prefixo_token(arquivos[caminho_app]) if caminho_app else None
        aplica_gotchas(arquivos, achados, gotchas, args.only)
    else:
        valida_yaml(arquivos, achados)
        prefixo = valida_tokens_udfs(arquivos, achados, caminho_app)
        valida_nomes(arquivos, achados,
                     ["cnt", "gal", "lbl", "btn", "rec", "ico", "inp", "cmb", "cmp", "src",
                      "dtp", "chk", "pdf", "txt", "img", "tmr", "col", "var", "ctx"])
        aplica_gotchas(arquivos, achados, gotchas, None)
        valida_autolayout(arquivos, achados)

    erros = [a for a in achados if a.nivel == "ERRO"]
    avisos = [a for a in achados if a.nivel == "AVISO"]

    if args.json:
        print(json.dumps({
            "arquivos": len(arquivos), "prefixo_token": prefixo,
            "erros": len(erros), "avisos": len(avisos),
            "achados": [a.como_dict() for a in achados],
        }, ensure_ascii=False, indent=2))
    else:
        if not args.quiet:
            for a in sorted(achados, key=lambda x: (x.nivel != "ERRO", x.arquivo, x.linha)):
                print("%-5s %-22s %s:%d\n      %s" % (
                    a.nivel, a.regra, a.arquivo, a.linha, a.msg))
                if a.fix:
                    print("      -> %s" % a.fix)
        print("\n%d arquivos | prefixo de token: %s | %d ERRO(s), %d aviso(s)"
              % (len(arquivos), prefixo or "-", len(erros), len(avisos)))

    if erros:
        return 1
    if avisos:
        return 1 if args.strict else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
