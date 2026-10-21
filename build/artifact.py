"""Copia dist/ in una cartella pubblicabile come Artifact su claude.ai: percorsi relativi, pagine piatte.

    npx astro build && python3 build/artifact.py dist <cartella>

La pagina iniziale perde doctype/head/body (li aggiunge la piattaforma), le pagine delle parole
diventano <slug>.html accanto a lei, _astro/ diventa risorse/ (i nomi con "_" sono riservati)."""
import re, shutil, sys, unicodedata
from pathlib import Path
from urllib.parse import unquote

DIST, OUT = Path(sys.argv[1]), Path(sys.argv[2])
if OUT.exists(): shutil.rmtree(OUT)
(OUT / "risorse").mkdir(parents=True)

def slug(s):
    s = unicodedata.normalize("NFD", s.lower().replace("'", "-"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

pagine = {p.parent.name: slug(p.parent.name) + ".html" for p in DIST.glob("*/index.html") if p.parent.name != "_astro"}

def link(m):
    attr, url = m.group(1), m.group(2)
    if url.startswith("/_astro/"): return f'{attr}="risorse/{url[8:].replace("_word_", "parola")}"'
    if url == "/favicon.svg": return f'{attr}="favicon.svg"'
    if url == "/": return f'{attr}="index.html"'
    if url.startswith("/#"): return f'{attr}="index.html{url[1:]}"'
    nome = unquote(url[1:].rstrip("/"))
    if nome in pagine: return f'{attr}="{pagine[nome]}"'
    return m.group(0)

def html(t): return re.sub(r'(href|src)="(/[^"]*)"', link, t)

for js in (DIST / "_astro").iterdir():
    t = js.read_text()
    if js.suffix == ".js":
        t = t.replace('"/data/', '"data/').replace("`/data/", "`data/")
        t = t.replace("_word_", "parola")
    (OUT / "risorse" / js.name.replace("_word_", "parola")).write_text(t)
for nome, file in pagine.items():
    (OUT / file).write_text(html((DIST / nome / "index.html").read_text()))
# la pagina principale: senza doctype/html/head/body, li aggiunge la piattaforma
t = html((DIST / "index.html").read_text())
head = re.search(r"<head>(.*)</head>", t, re.S).group(1)
body = re.search(r"<body[^>]*>(.*)</body>", t, re.S).group(1)
head = re.sub(r'<meta charset[^>]*>|<meta name="viewport"[^>]*>', "", head)
(OUT / "index.html").write_text(head + body)
shutil.copy(DIST / "favicon.svg", OUT / "favicon.svg")
d = OUT / "data" / "gold" / "esagoni"; d.mkdir(parents=True)
for f in ["data/bergamo.geojson", "data/gold/esagoni.geojson", "data/gold/atlante.json", "data/gold/commenti.json"]:
    shutil.copy(DIST / f, OUT / f)
for f in (DIST / "data/gold/esagoni").glob("*.json"): shutil.copy(f, d / f.name)
print(len(list(OUT.rglob("*.*"))), "file")
