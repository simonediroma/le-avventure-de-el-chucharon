#!/usr/bin/env python3
"""
da_colorare_gemini.py — Pagine da colorare della 2ª edizione generate con Gemini.

Per ogni capitolo passa a Gemini la copertina a colori (ritagliata come appare in pagina)
e chiede la stessa immagine in solo contorno nero, senza cornice; salva il risultato in assets/da-colorare/capN.png.

Chiave: GEMINI_API_KEY, oppure Network secret dell'ambiente cloud sull'host
generativelanguage.googleapis.com con header x-goog-api-key (in quel caso basta un valore fittizio).

Uso:
  pip install google-genai pillow
  python tools/da_colorare_gemini.py                 → tutti i capitoli (cap2..cap5)
  python tools/da_colorare_gemini.py cap3 --varianti 3   → 3 proposte per Sofia (capN-v1.png…)
"""
import argparse, io, json, os, sys
from pathlib import Path

from PIL import Image
from google import genai
from google.genai import types

DIR = Path(__file__).resolve().parent.parent
MODELS = ["gemini-3-pro-image", "gemini-3-pro-image-preview", "gemini-3.1-flash-image", "gemini-2.5-flash-image"]

# titolo del capitolo; la copertina è la pagina capN-p01 di pagine.json
CAPITOLI = {"cap2": "LEO", "cap3": "SOFIA", "cap4": "MARCO", "cap5": "ELENA"}

PROMPT = """The image is the full-color cover illustration of a chapter of a children's picture book.

Create a BLACK-AND-WHITE COLORING PAGE version of this exact image for children aged 2-6:
- Same composition, same characters, same poses, same objects, same setting as the image. Do not add or remove anything.
- Keep the chapter title lettering "{titolo}" at the bottom exactly as in the image, as hollow outlined letters ready to color.
- LINE ART ONLY: clean, smooth, continuous pure black outlines of uniform medium thickness. Closed shapes that are easy to color.
- Every area inside the outlines must be PURE WHITE (#FFFFFF). This is NOT a grayscale or pencil version:
  absolutely NO shading, NO gray tones, NO gradients, NO hatching, NO shadows, NO textures, NO color, NO filled black areas
  (hair, chair, shoes: outline only). Only black lines on white paper, like a printed coloring book.
- Simplify small background details; keep faces sweet and expressive, faithful to the image.
- NO border, NO frame, NO decorative edge: the drawing fills the whole square edge to edge, exactly like the original.
- Square format."""


def copertina(cap):
    """Ritaglia la copertina sulla parte visibile in pagina (630x630 pt)."""
    pg = next(p for p in json.loads((DIR / "pagine.json").read_text())["pagine"] if p["id"] == f"{cap}-p01")
    im = Image.open(DIR / pg["img"]).convert("RGB")
    x0, t, x1, b = pg["box"]; sx = im.width / (x1 - x0); sy = im.height / (b - t)
    return im.crop((round(-x0 * sx), round(-t * sy), round((630 - x0) * sx), round((630 - t) * sy)))


def png_bytes(im, max_side=1536):
    im = im.copy()
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO(); im.save(buf, "PNG"); return buf.getvalue()


def genera(client, model, cap, titolo, out):
    parts = [types.Part(inline_data=types.Blob(mime_type="image/png", data=png_bytes(copertina(cap)))),
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
        titolo = CAPITOLI[cap]
        for v in range(1, a.varianti + 1):
            out = outdir / (f"{cap}.png" if a.varianti == 1 else f"{cap}-v{v}.png")
            ok = genera(client, model, cap, titolo, out)
            print(f"{'✓' if ok else '✗'} {cap} → {out.relative_to(DIR)}")


if __name__ == "__main__":
    main()
