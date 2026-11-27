#!/usr/bin/env python3
"""Estrae le illustrazioni ad alta risoluzione dai PDF "stampa" di Canva
(canva-stampa/*.pdf) in assets-stampa/capN/pXX.png, con la stessa numerazione
di pagine.json. Il prologo stampa non ha la pagina 1 (Chucharon da colorare).
Uso: python tools/estrai_stampa.py   (richiede poppler-utils: pdfimages)"""
import subprocess, tempfile, shutil
from pathlib import Path
DIR = Path(__file__).resolve().parent.parent
SRC = {"cap1": "prologo", "cap2": "leo-cap1", "cap3": "sofia-cap2", "cap4": "marco-cap3", "cap5": "epilogo"}
OFFSET = {"cap1": 1}           # pagina pagine.json = pagina PDF stampa + offset
HIRES = {"cap1": [2, 5, 6, 8, 11], "cap2": [1, 3, 6, 7, 10], "cap3": [1, 4, 5, 8, 9],
         "cap4": [1, 3, 6, 7, 10], "cap5": [1, 3, 6, 7, 10, 11]}
for cap, nome in SRC.items():
    pdf = DIR / "canva-stampa" / f"Printable - def - el chucharon-{nome}.pdf"
    out = DIR / "assets-stampa" / cap; out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        for p in HIRES[cap]:
            q = p - OFFSET.get(cap, 0)
            subprocess.run(["pdfimages", "-png", "-f", str(q), "-l", str(q), str(pdf), f"{t}/i"], check=True)
            shutil.move(next(Path(t).glob("i-*.png")), out / f"p{p:02d}.png")
            print(f"✓ {cap}/p{p:02d}.png")
