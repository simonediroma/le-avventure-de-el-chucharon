#!/usr/bin/env python3
"""Genera per-canva/correzioni-testo.md: confronto parola per parola tra
testo-1a-edizione.md (testo attuale in Canva) e testo.md (2ª edizione)."""
import re, difflib
from pathlib import Path
DIR = Path(__file__).resolve().parent.parent

def sezioni(path):
    src = re.sub(r"<!--.*?-->", "", (DIR / path).read_text(), flags=re.S)
    out = {}
    for s in re.split(r"^## ", src, flags=re.M)[1:]:
        k, _, b = s.partition("\n")
        b = re.sub(r"\*+", "", b).replace("♪", "").replace("’", "'")
        b = re.sub(r"^> ", "", b, flags=re.M)
        out[k.strip()] = re.sub(r"\s+", " ", b).strip().split()
    return out

old, new = sezioni("testo-1a-edizione.md"), sezioni("testo.md")
TIT = {"1": "Capitolo 1 — Elena (prologo)", "2": "Capitolo 2 — Leo", "3": "Capitolo 3 — Sofia",
       "4": "Capitolo 4 — Marco", "5": "Capitolo 5 — Elena (finale)"}
out = ["# Correzioni al testo per Canva — 2ª edizione", "",
       "Per ogni pagina: **prima** (testo attuale in Canva) → **dopo** (2ª edizione), con qualche parola di contesto.",
       "Lo stile resta quello di Canva: le battute di dialogo in *grassetto corsivo* rimangono tali.",
       "I numeri di pagina sono quelli dentro ciascun file Canva del capitolo.", ""]
cur, tot, CTX, GAP = None, 0, 3, 4
for k, b in new.items():
    a = old.get(k, [])
    ops = [o for o in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if o[0] != "equal"]
    groups = []
    for o in ops:   # unisce modifiche separate da poche parole uguali
        if groups and o[1] - groups[-1][2] <= GAP:
            groups[-1] = (groups[-1][0], groups[-1][1], o[2], groups[-1][3], o[4])
        else:
            groups.append(o)
    if k[3] != cur:
        cur = k[3]; out += ["", f"## {TIT[cur]}", ""]
    p = int(k[6:])
    if not groups:
        out.append(f"**Pag. {p}** — nessuna modifica"); out.append(""); continue
    out.append(f"**Pag. {p}**"); out.append("")
    for _, i1, i2, j1, j2 in groups:
        x = " ".join(a[max(0, i1 - CTX):i2 + CTX]); y = " ".join(b[max(0, j1 - CTX):j2 + CTX])
        out += [f"- prima: «{x}»", f"  dopo:  «{y}»"]; tot += 1
    out.append("")
out += ["---", f"Totale: {tot} correzioni."]
(DIR / "per-canva" / "correzioni-testo.md").write_text("\n".join(out))
print(tot)
