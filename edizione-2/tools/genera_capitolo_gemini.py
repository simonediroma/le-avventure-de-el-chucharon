#!/usr/bin/env python3
"""
genera_capitolo_gemini.py — Illustrazioni di un nuovo capitolo nello stile della 2ª edizione.

Legge capitoli/capN.json (scritto da pipeline/generate_chapter.py) e genera con Gemini:
  assets/capN/p01.png        copertina con il nome del protagonista in lettering messicano
  assets/capN/p03|p06|p07|p10.png  illustrazioni a tutta pagina (quadrate, 2K)
  assets/capN/cornice.png    sfondo delle pagine di testo (4:3, decori in alto e in basso)
  assets/da-colorare/capN.png  pagina da colorare ricavata dalla copertina

A ogni chiamata passa come riferimento le illustrazioni della 2ª edizione (stile, El Chucharon,
lettering, cornici) e le immagini già generate per il capitolo (coerenza dei personaggi).

Uso:
  python tools/genera_capitolo_gemini.py cap6
  python tools/genera_capitolo_gemini.py cap6 --solo p07,p10      → rigenera solo alcune immagini
  python tools/genera_capitolo_gemini.py cap6 --nota p10="il papà tira fortissimo verso la TV"
"""
import argparse, io, json, os, sys, time
from pathlib import Path

from PIL import Image
from google import genai
from google.genai import types

DIR = Path(__file__).resolve().parent.parent
MODELS = ["gemini-3-pro-image", "gemini-3-pro-image-preview"]   # niente ripieghi su modelli più deboli

# Riferimenti della 2ª edizione (immagini a bassa risoluzione già nel repo)
REF_STILE = ["assets/cap4/img-003-002.png", "assets/cap3/img-004-003.png", "assets/cap2/img-003-002.png"]
REF_SIESTA = ["assets/cap1/img-008-007.png", "assets/cap5/img-006-005.png"]
REF_CHUCHARITO = ["assets/cap2/img-007-006.png", "assets/cap3/img-009-008.png", "assets/cap4/img-007-006.png"]
REF_COPERTINA = ["assets/cap3/img-001-000.png", "assets/cap4/img-001-000.png", "assets/cap2/img-001-000.png"]
REF_CORNICE = ["assets/cap4/img-004-003.png", "assets/cap2/img-004-003.png", "assets/cap5/img-004-003.png"]

STILE = """STYLE — MUST MATCH THE REFERENCE ILLUSTRATIONS OF THIS BOOK EXACTLY: warm watercolor and gouache
children's picture-book illustration, soft linework, Pixar-like expressive faces, large heads, warm golden
light, cream/amber palette, uncluttered background. Same rendering, same proportions, same level of detail.
Absolutely NO text, letters, numbers, speech bubbles, logos, crests or brand marks in the image."""

CHUCHARON = """EL CHUCHARON — the book's magic character, MUST look exactly like in the reference images:
he is a baby PACIFIER (dummy) that flies. Its mouth-shield is a golden-yellow cartoon face wearing a colorful
Mexican sombrero (straw yellow, red/green zigzag band), the pacifier RING forms two extremely long brown
mustaches, round orange nose, big expressive eyes. He is pacifier-sized, floating in the air.
He is NEVER a human or a little man: no body, no legs, no clothes.
- SIESTA state: sombrero pulled down over the eyes, mustaches long and drooping, sleepy.
- EL CHUCHARITO (transformed): sombrero pushed back onto his shoulders like a cape, mustaches pointing
  STRAIGHT UP, eyes wide open and sparkling, radiant, surrounded by warm swirls, sparkles and musical notes.
Adults never look at him."""


def carica(path, lato=1024):
    im = Image.open(DIR / path).convert("RGB"); im.thumbnail((lato, lato))
    buf = io.BytesIO(); im.save(buf, "PNG"); return buf.getvalue()


def parte_img(data, etichetta):
    return [types.Part(text=etichetta), types.Part(inline_data=types.Blob(mime_type="image/png", data=data))]


def anchor_personaggi(spec):
    righe = ["CHARACTERS — MUST BE IDENTICAL IN EVERY ILLUSTRATION OF THIS CHAPTER:"]
    for p in spec["people"]:
        righe.append(f"- {p['label_en']}: {p['appearance_en']} OUTFIT: {p['outfit_en']}")
    righe.append(f"SETTING — IDENTICAL IN EVERY ILLUSTRATION: {spec['setting_en']}")
    return "\n".join(righe)


def genera(client, model, parti, aspect, out, colore=True):
    cfg = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"],
                                      image_config=types.ImageConfig(aspect_ratio=aspect, image_size="2K"))
    for tentativo in range(3):
        try:
            r = client.models.generate_content(model=model, contents=parti, config=cfg)
        except Exception as e:                     # quota / errori temporanei
            print(f"   ⚠️  {e}"); time.sleep(10 * (tentativo + 1)); continue
        for c in r.candidates or []:
            for p in (getattr(c.content, "parts", None) or []):
                if getattr(p, "inline_data", None):
                    im = Image.open(io.BytesIO(p.inline_data.data))
                    out.parent.mkdir(parents=True, exist_ok=True)
                    (im.convert("RGB") if colore else im.convert("L")).save(out)
                    return True
        print("   ⚠️  risposta senza immagine, riprovo"); time.sleep(5)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cap")
    ap.add_argument("--solo", help="es. p01,p07,cornice,colorare")
    ap.add_argument("--nota", action="append", default=[], help='istruzione extra per una pagina: p10="..."')
    ap.add_argument("--model")
    a = ap.parse_args()

    spec = json.loads((DIR / "capitoli" / f"{a.cap}.json").read_text(encoding="utf-8"))
    note = dict(n.split("=", 1) for n in a.nota)
    note = {k.strip(): v.strip().strip('"') for k, v in note.items()}
    solo = set(a.solo.split(",")) if a.solo else None
    vuoi = lambda k: solo is None or k in solo

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "via-proxy"))
    disp = {m.name.split("/")[-1] for m in client.models.list()}
    model = a.model or next((m for m in MODELS if m in disp), None)
    if not model:
        sys.exit(f"❌ nessun modello tra {MODELS}; disponibili: {sorted(m for m in disp if 'image' in m)}")
    print(f"🎨 modello: {model}")

    cap, base = spec["cap"], DIR / "assets" / spec["cap"]
    anchors = anchor_personaggi(spec)
    fallite = []

    def refs_capitolo(escludi):
        """Immagini già generate del capitolo, per la coerenza dei personaggi."""
        out = []
        for k in ("p01", "p03", "p06", "p07", "p10"):
            f = base / f"{k}.png"
            if k != escludi and f.exists():
                out += parte_img(carica(f.relative_to(DIR), 768), f"Already approved illustration of THIS chapter ({k}): keep characters, outfits and room identical.")
        return out

    def scena(k, extra=""):
        stato = REF_CHUCHARITO if k in ("p07", "p10") else REF_SIESTA
        parti = []
        for r in REF_STILE:
            parti += parte_img(carica(r), "STYLE REFERENCE from this book:")
        for r in stato:
            parti += parte_img(carica(r), "EL CHUCHARON REFERENCE from this book:")
        if k == "p01":
            for r in REF_COPERTINA:
                parti += parte_img(carica(r), "CHAPTER COVER REFERENCE from this book (layout and title lettering):")
        parti += refs_capitolo(k)
        testo = [STILE, CHUCHARON, anchors, f"SCENE: {spec['scene'][k]}"]
        if k == "p01":
            testo.append(f'CHAPTER COVER: like the cover references, the child alone in the scene and, in the lower part, '
                         f'the name "{spec["nome"].upper()}" in the SAME decorative Mexican lettering (red letters with green '
                         f'outline, small flowers and stars), perfectly spelled. Keep the name and faces well inside the '
                         f'central 85% of the square (print safety margin). The name is the ONLY text allowed.')
        if extra:
            testo.append(f"MANDATORY FOR THIS PICTURE: {extra}")
        testo.append("Square format, full bleed, the whole scene composed inside the central 90% (print margins).")
        parti.append(types.Part(text="\n\n".join(testo)))
        return parti

    for k in ("p01", "p03", "p06", "p07", "p10"):
        if not vuoi(k):
            continue
        print(f"🖌️  {cap}/{k}")
        if not genera(client, model, scena(k, note.get(k, "")), "1:1", base / f"{k}.png"):
            fallite.append(k)

    if vuoi("cornice"):
        print(f"🖌️  {cap}/cornice")
        parti = []
        for r in REF_CORNICE:
            parti += parte_img(carica(r), "TEXT-PAGE BACKGROUND REFERENCE from this book:")
        parti.append(types.Part(text=(
            "Create a new text-page background for this book, in the SAME style as the references: a soft, pale, "
            "almost empty watercolor paper background, with a decorative watercolor border band ONLY along the top and "
            f"bottom edges (thin, about 12% of the height each), made of: {spec['frame_theme_en']}. The whole central "
            "area must stay light, clean and empty for printed text. NO text, NO letters, NO characters, NO logos. "
            "Landscape 4:3.")))
        if not genera(client, model, parti, "4:3", base / "cornice.png"):
            fallite.append("cornice")

    if vuoi("colorare"):
        print(f"🖌️  da-colorare/{cap}")
        sys.path.insert(0, str(DIR / "tools"))
        from da_colorare_gemini import PROMPT
        cover = base / "p01.png"
        parti = parte_img(carica(cover.relative_to(DIR), 1536), "Cover illustration:")
        parti.append(types.Part(text=PROMPT.format(titolo=spec["nome"].upper())))
        if not genera(client, model, parti, "1:1", DIR / "assets" / "da-colorare" / f"{cap}.png", colore=False):
            fallite.append("colorare")

    if fallite:
        sys.exit(f"❌ immagini non generate: {', '.join(fallite)}")
    print("✅ immagini generate")


if __name__ == "__main__":
    main()
