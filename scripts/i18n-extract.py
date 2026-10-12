"""Liste les textes français de index.html qui n'ont pas encore de traduction (i18n/en/*.json).
Sortie : i18n/todo.json {"markup": [...], "attrs": [...], "js": [...]} — clés au format du dictionnaire ({0}, {1}… pour les valeurs).
Usage : python scripts/i18n-extract.py [--stats]
"""
import html
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FR = re.compile(r"[éèêàùçôîûÉÈÀ]|\b(le|la|les|des|du|de|sur|pour|par|et|une|un|vs|moyenne|taux|période|données|aucun|aucune|chargement|erreur|jours?|mois|sites?|clics|leads?)\b", re.I)


def norm(x):
    return re.sub(r"\s+", " ", html.unescape(x)).strip()


def interp(x, pat):
    """Remplace chaque valeur variable (selon pat) par {0}, {1}…"""
    n = [0]

    def f(_):
        k = "{%d}" % n[0]
        n[0] += 1
        return k
    return pat.sub(f, x)


def existants():
    d = {}
    for f in sorted((RACINE / "i18n" / "en").glob("*.json")):
        d.update(json.loads(f.read_text(encoding="utf-8")))
    return {norm(k) for k in d}


def litteraux_js(js):
    """Littéraux de chaîne du JavaScript (apostrophes, guillemets, gabarits `...${x}...` avec {n} à la place des ${}),
    en ignorant commentaires et expressions régulières. Les chaînes imbriquées dans un ${...} sont aussi renvoyées."""
    out = []
    n = len(js)

    def regex_possible(i):
        j = i - 1
        while j >= 0 and js[j] in " \t\r\n":
            j -= 1
        return j < 0 or js[j] in "(,=:[!&|?{};+-*%<>~^" or js[max(0, j - 5):j + 1] in ("return",) 

    def chaine(i, q):
        buf = []
        i += 1
        while i < n and js[i] != q:
            if js[i] == "\\":
                c = js[i + 1]
                buf.append({"n": "\n", "t": "\t"}.get(c, c)); i += 2
            else:
                buf.append(js[i]); i += 1
        out.append("".join(buf))
        return i + 1

    def gabarit(i):
        buf, k = [], 0
        i += 1
        while i < n and js[i] != "`":
            if js[i] == "\\":
                buf.append(js[i + 1]); i += 2
            elif js[i] == "$" and js[i + 1:i + 2] == "{":
                i = code(i + 2, "}")
                buf.append("{%d}" % k); k += 1
            else:
                buf.append(js[i]); i += 1
        out.append("".join(buf))
        return i + 1

    def code(i, fin=None):
        depth = 0
        while i < n:
            c = js[i]
            if c in "'\"":
                i = chaine(i, c)
            elif c == "`":
                i = gabarit(i)
            elif c == "/" and js[i + 1:i + 2] == "/":
                i = js.find("\n", i)
                i = n if i < 0 else i
            elif c == "/" and js[i + 1:i + 2] == "*":
                i = js.find("*/", i) + 2
            elif c == "/" and regex_possible(i):
                i += 1
                cls = False
                while i < n and (js[i] != "/" or cls):
                    if js[i] == "\\":
                        i += 1
                    elif js[i] == "[":
                        cls = True
                    elif js[i] == "]":
                        cls = False
                    i += 1
                i += 1
            elif c == "{":
                depth += 1; i += 1
            elif c == "}":
                if fin == "}" and depth == 0:
                    return i + 1
                depth -= 1; i += 1
            else:
                i += 1
        return i

    code(0)
    return out


def main():
    s = (RACINE / "index.html").read_text(encoding="utf-8")
    a = s.index('<script type="text/x-dc"')
    tpl, js = s[:a], s[a:]
    tpl = re.sub(r"<style[\s\S]*?</style>|<script[\s\S]*?</script>", "", tpl)
    tpl = re.sub(r"<!--[\s\S]*?-->", "", tpl)
    deja = existants()
    markup, attrs, jsl = [], [], []
    for m in re.findall(r">([^<>]{2,}?)<", tpl):
        m = norm(interp(m, re.compile(r"\{\{[^}]*\}\}")))
        if re.search(r"[A-Za-zÀ-ÿ]{3}", re.sub(r"\{\d\}", "", m)) and m not in markup:
            markup.append(m)
    for m in re.findall(r'(?:title|placeholder|aria-label|alt)="([^"]{3,})"', tpl):
        m = norm(interp(m, re.compile(r"\{\{[^}]*\}\}")))
        if re.search(r"[A-Za-zÀ-ÿ]{3}", re.sub(r"\{\d\}", "", m)) and m not in attrs and m not in markup:
            attrs.append(m)
    js_code = js[js.index('>') + 1:js.rindex('</script>')]
    litt = [norm(x) for x in litteraux_js(js_code)]
    for x in litt:
        if x in jsl or x in markup or x in attrs:
            continue
        if re.search(r"=>|</|<\w|\w+:[^ ]*;|\bpx\b|^#|rgb\(|function|^\w+\s*=\s*|^\w+(\.\w+)+$|^[a-z0-9_-]+$|^[a-z]+[A-Z]\w*$|^https?:|^/|\.(js|json|css|png|html)$|^\d", x):
            continue
        if not re.search(r"[A-Za-zÀ-ÿ]{3}", re.sub(r"\{\d\}", "", x)) or len(x) < 3:
            continue
        jsl.append(x)
    todo = {"markup": [x for x in markup if x not in deja], "attrs": [x for x in attrs if x not in deja], "js": [x for x in jsl if x not in deja]}
    (RACINE / "i18n" / "todo.json").write_text(json.dumps(todo, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: len(v) for k, v in todo.items()}, "déjà traduits :", len(deja))
    return 0


if __name__ == "__main__":
    sys.exit(main())
