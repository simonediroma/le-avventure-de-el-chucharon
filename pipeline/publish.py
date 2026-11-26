#!/usr/bin/env python3
"""
Prepara il sito statico (site/) a partire dal registro dei capitoli:
  site/media/<folder>/<ID>.jpg   illustrazioni compresse per il web (e per i PDF scaricabili)
  site/pdf/inizio.pdf            copertina + prologo
  site/pdf/<slug>.pdf            un PDF per ogni capitolo-storia
  site/pdf/fine.pdf              epilogo
  site/pdf/libro-completo.pdf    tutto il libro
  site/data/chapters.json        catalogo per galleria e "Crea il tuo libro"

Il browser compone il PDF personalizzato unendo inizio + capitoli scelti + fine (pdf-lib).

USO:  python pipeline/publish.py [--max-width 1600] [--quality 80] [--skip-pdf]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from PIL import Image

from common import ROOT, load_registry

SRC = ROOT / "illustrator" / "output"
SITE = ROOT / "site"
LAYOUT = ROOT / "illustrator" / "layout.py"


def export_image(folder: str, sid: str, max_w: int, quality: int) -> str | None:
    src = SRC / folder / f"{sid}.png"
    if not src.exists():
        return None
    dst = SITE / "media" / folder / f"{sid}.jpg"
    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
        dst.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    return f"media/{folder}/{sid}.jpg"


def read_text_block(sid: str) -> str:
    sys.path.insert(0, str(ROOT / "illustrator"))
    import layout  # noqa: E402
    return layout.read_text_block(sid)


def build_pdf(scenes: list[str], out_name: str) -> str:
    out = SITE / "pdf" / out_name
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(LAYOUT), "--scenes", ",".join(scenes),
                    "--images-dir", str(SITE / "media"), "--output", str(out), "--skip-missing"],
                   cwd=LAYOUT.parent, check=True, stdout=subprocess.DEVNULL)
    return f"pdf/{out_name}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-width", type=int, default=1600)
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--skip-pdf", action="store_true")
    args = ap.parse_args()

    reg = load_registry()
    export_image("00-cover", reg["cover"], args.max_width, args.quality)
    catalog = {"cover": "media/00-cover/COVER.jpg", "chapters": []}

    for ch in reg["chapters"]:
        pages = []
        for sid in ch["scenes"]:
            img = export_image(ch["folder"], sid, args.max_width, args.quality)
            pages.append({"id": sid, "image": img, "text": read_text_block(sid)})
        item = {k: ch.get(k) for k in ("slug", "kind", "title", "child", "pain_point", "mexico_hook",
                                       "parents", "author", "issue")}
        item["pages"] = pages
        item["ready"] = all(p["image"] for p in pages)
        catalog["chapters"].append(item)

    if not args.skip_pdf:
        core = {c["slug"]: c for c in reg["chapters"] if c["kind"] == "core"}
        catalog["pdf"] = {
            "inizio": build_pdf([reg["cover"]] + core["00-prologo"]["scenes"], "inizio.pdf"),
            "fine": build_pdf(core["04-epilogo"]["scenes"], "fine.pdf"),
            "completo": build_pdf([reg["cover"]] + [s for c in reg["chapters"] for s in c["scenes"]],
                                  "libro-completo.pdf"),
        }
        for item, ch in zip(catalog["chapters"], reg["chapters"]):
            if ch["kind"] == "story" and item["ready"]:
                item["pdf"] = build_pdf(ch["scenes"], f"{ch['slug']}.pdf")

    (SITE / "data").mkdir(parents=True, exist_ok=True)
    (SITE / "data" / "chapters.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Sito pronto: {len(catalog['chapters'])} capitoli → {SITE}")


if __name__ == "__main__":
    main()
