#!/usr/bin/env python3
"""
da_colorare_gemini.py — Pagine da colorare della 2ª edizione generate con Gemini.

Per ogni capitolo passa a Gemini:
  1. la copertina a colori del capitolo (cosa disegnare)
  2. una pagina da colorare della 1ª edizione (come disegnarla: stile del tratto e cornice)
e salva il risultato in assets/da-colorare/capN.png.

Chiave: GEMINI_API_KEY, oppure Network secret dell'ambiente cloud sull'host
generativelanguage.googleapis.com con header x-goog-api-key (in quel caso basta un valore fittizio).

Uso:
  pip install google-genai pillow
  python tools/da_colorare_gemini.py                 → tutti i capitoli (cap2..cap5)
  python tools/da_colorare_gemini.py cap3 --varianti 3   → 3 proposte per Sofia (capN-v1.png…)
"""
import argparse, io, os, sys
from pathlib import Path

from PIL import Image
from google import genai
from google.genai import types

DIR = Path(__file__).resolve().parent.parent
MODELS = ["gemini-3-pro-image", "gemini-3-pro-image-preview", "gemini-3.1-flash-image", "gemini-2.5-flash-image"]

# copertina a colori (pagina 1) e riferimento di stile (pagina da colorare della 1ª ed.)
CAPITOLI = {
    "cap2": ("assets/cap2/img-001-000.png", "LEO"),
    "cap3": ("assets/cap3/img-001-000.png", "SOFIA"),
    "cap4": ("assets/cap4/img-001-000.png", "MARCO"),
    "cap5": ("assets/cap5/img-001-000.png", "ELENA"),
}
STILE = "assets/cap1/img-001-000.png"   # Chucharon da colorare con cornice messicana

PROMPT = """Image 1 is the full-color cover illustration of a chapter of a children's picture book.
Image 2 is a coloring page from the same book: use it ONLY as the reference for line style and the decorative border.

Create a BLACK-AND-WHITE COLORING PAGE version of Image 1 for children aged 2-6:
- Same composition, same characters, same poses, same objects, same setting as Image 1. Do not add or remove anything.
- Keep the chapter title lettering "{titolo}" at the bottom exactly as in Image 1, as hollow outlined letters ready to color.
- LINE ART ONLY: clean, smooth, continuous pure black outlines of uniform medium thickness, like Image 2. Closed shapes that are easy to color.
- Every area inside the outlines must be PURE WHITE (#FFFFFF). This is NOT a grayscale or pencil version:
  absolutely NO shading, NO gray tones, NO gradients, NO hatching, NO shadows, NO textures, NO color, NO filled black areas
  (hair, chair, shoes: outline only). Only black lines on white paper, like a printed coloring book.
- Simplify small background details; keep faces sweet and expressive, faithful to Image 1.
- Surround the drawing with a thin decorative Mexican-style border like the one in Image 2.
- White background, square format."""


def png_bytes(path, max_side=1536):
    im = Image.open(DIR / path).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO(); im.save(buf, "PNG"); return buf.getvalue()


def genera(client, model, cover, titolo, out):
    parts = [types.Part(inline_data=types.Blob(mime_type="image/png", data=png_bytes(cover))),
             types.Part(inline_data=types.Blob(mime_type="image/png", data=png_bytes(STILE))),
             types.Part(text=PROMPT.format(titolo=titolo))]
    cfg = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
    try:
        cfg.image_config = types.ImageConfig(aspect_ratio="1:1", image_size="2K")
    except Exception:
        pass
    r = client.models.generate_content(model=model, contents=parts, config=cfg)
    for c in r.candidates or []:
        for p in (getattr(c.content, "parts", None) or []):
            if getattr(p, "inline_data", None):
                Image.open(io.BytesIO(p.inline_data.data)).convert("L").save(out)
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capitoli", nargs="*", default=list(CAPITOLI))
    ap.add_argument("--varianti", type=int, default=1)
    ap.add_argument("--model")
    a = ap.parse_args()

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "via-proxy"))
    if a.model:
        model = a.model
    else:
        disp = {m.name.split("/")[-1] for m in client.models.list()}
        model = next((m for m in MODELS if m in disp), None)
        if not model:
            sys.exit("❌ nessun modello immagine disponibile")
    print(f"🎨 modello: {model}")

    outdir = DIR / "assets" / "da-colorare"; outdir.mkdir(parents=True, exist_ok=True)
    for cap in a.capitoli:
        cover, titolo = CAPITOLI[cap]
        for v in range(1, a.varianti + 1):
            out = outdir / (f"{cap}.png" if a.varianti == 1 else f"{cap}-v{v}.png")
            ok = genera(client, model, cover, titolo, out)
            print(f"{'✓' if ok else '✗'} {cap} → {out.relative_to(DIR)}")


if __name__ == "__main__":
    main()
