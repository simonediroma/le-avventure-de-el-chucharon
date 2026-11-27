#!/usr/bin/env python3
"""
Prepara il sito statico (site/) dalla 2ª EDIZIONE (edizione-2/):
  site/pdf/<slug>.pdf            PDF web di ogni capitolo (impagina.py --web --solo capN-)
  site/pdf/inizio.pdf            copertina del libro + prologo
  site/pdf/fine.pdf              epilogo
  site/pdf/libro-completo.pdf    tutto il libro, nell'ordine di pagine.json
  site/media/<capN>/pXX.jpg      ogni pagina renderizzata, per galleria e lettore
  site/media/copertina.jpg       copertina del libro
  site/data/chapters.json        catalogo per galleria e "Crea il tuo libro"

Il browser compone il PDF personalizzato unendo inizio + capitoli scelti + fine (pdf-lib).

Prerequisito: edizione-2/assets-stampa/ (python edizione-2/tools/estrai_stampa.py, richiede poppler-utils).
USO:  python pipeline/publish.py [--width 1100] [--quality 80]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter

from common import ED2, ROOT, load_registry

SITE = ROOT / "site"
IMPAGINA = ED2 / "impagina.py"


def pdf_capitolo(cap: str, out) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(IMPAGINA), "--web", "--senza-copertina", "--solo", f"{cap}-",
                    "--output", str(out)], check=True, stdout=subprocess.DEVNULL)


def render(pdf, outdir, width: int, quality: int, prefix: str = "p") -> list[str]:
    outdir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(pdf))
    files = []
    for i in range(len(doc)):
        page = doc[i]
        img = page.render(scale=width / page.get_width()).to_pil().convert("RGB")
        f = outdir / f"{prefix}{i + 1:02d}.jpg"
        img.save(f, "JPEG", quality=quality, optimize=True, progressive=True)
        files.append(str(f.relative_to(SITE)))
    return files


def prima_a_colori(pages: list[str]) -> str:
    """Copertina della card: la prima pagina a colori (salta le pagine da colorare in bianco e nero)."""
    from PIL import Image, ImageStat
    for p in pages:
        sat = ImageStat.Stat(Image.open(SITE / p).convert("HSV")).mean[1]
        if sat > 25:
            return p
    return pages[0]


def unisci(parti, out) -> str:
    w = PdfWriter()
    for p in parti:
        w.append(PdfReader(str(p)))
    w.add_metadata({"/Title": "Le Avventure de El Chucharon"})
    with open(out, "wb") as f:
        w.write(f)
    return str(out.relative_to(SITE))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=1100)
    ap.add_argument("--quality", type=int, default=80)
    args = ap.parse_args()

    reg = load_registry()
    pdfdir = SITE / "pdf"
    copertina = ED2 / "copertina" / "fronte.pdf"
    catalog = {"cover": render(copertina, SITE / "media", args.width, args.quality, prefix="copertina-")[0],
               "chapters": []}

    for ch in reg["chapters"]:
        pdf = pdfdir / f"{ch['slug']}.pdf"
        pdf_capitolo(ch["id"], pdf)
        pages = render(pdf, SITE / "media" / ch["id"], args.width, args.quality)
        item = {k: ch.get(k) for k in ("id", "slug", "kind", "title", "child", "pain_point", "mexico_hook",
                                       "parents", "author", "issue")}
        item.update(pages=[{"image": p} for p in pages], cover=prima_a_colori(pages), pdf=str(pdf.relative_to(SITE)), ready=True)
        catalog["chapters"].append(item)
        print(f"✓ {ch['id']} {ch['title']} ({len(pages)} pagine)")

    by_id = {c["id"]: pdfdir / f"{c['slug']}.pdf" for c in reg["chapters"]}
    catalog["pdf"] = {
        "inizio": unisci([copertina, by_id["cap1"]], pdfdir / "inizio.pdf"),
        "fine": str(by_id["cap5"].relative_to(SITE)),
        "completo": unisci([copertina] + [by_id[c["id"]] for c in reg["chapters"]], pdfdir / "libro-completo.pdf"),
    }

    (SITE / "data").mkdir(parents=True, exist_ok=True)
    (SITE / "data" / "chapters.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Sito pronto: {len(catalog['chapters'])} capitoli → {SITE}")


if __name__ == "__main__":
    main()
