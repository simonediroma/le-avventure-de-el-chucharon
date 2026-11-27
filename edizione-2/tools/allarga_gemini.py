#!/usr/bin/env python3
"""
allarga_gemini.py — "Zoom out" di una pagina a tutta pagina: riduce l'illustrazione
dentro l'area di sicurezza KDP e fa continuare la scena verso i bordi a Gemini
(outpainting). Il centro viene poi ricomposto con l'originale ad alta risoluzione.

Uso: python tools/allarga_gemini.py cap4-p01  → assets/allargate/cap4-p01.png
Poi in pagine.json: "img": "assets/allargate/cap4-p01.png", "box": [0,0,630,630]
"""
import io, json, os, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from google import genai
from google.genai import types

DIR = Path(__file__).resolve().parent.parent
PAGE, SAFE = 630, 40          # 40 pt dal bordo pagina (> 36 richiesti) per sicurezza
OUT_PX = 3000                 # 630 pt → 343 ppi
MODEL = "gemini-3-pro-image"

PROMPT = """This square image is a children's picture-book illustration (warm watercolor style) that has been
shrunk and centered on a white canvas. Fill ONLY the white margins around it, extending the scene
naturally outward (same room, same floor, same walls, same light, same watercolor style), as if the
original illustration had been painted on a slightly larger sheet.
Do NOT change, redraw, move or restyle anything in the central illustration. Do not add new characters,
text or letters in the margins. No borders, no frames. Output a square image."""


def visibile(pg):
    im = Image.open(DIR / pg["img"]).convert("RGB")
    x0, t, x1, b = pg["box"]; sx = im.width / (x1 - x0); sy = im.height / (b - t)
    return im.crop((round(-x0 * sx), round(-t * sy), round((PAGE - x0) * sx), round((PAGE - t) * sy)))


def main(pid):
    pg = next(p for p in json.loads((DIR / "pagine.json").read_text())["pagine"] if p["id"] == pid)
    vis = visibile(pg)
    inner = round(OUT_PX * (PAGE - 2 * SAFE) / PAGE); off = (OUT_PX - inner) // 2
    centro = vis.resize((inner, inner), Image.LANCZOS)

    # tela per Gemini (1536 px): centro ridotto su bianco
    G = 1536; gi = round(G * inner / OUT_PX); go = (G - gi) // 2
    tela = Image.new("RGB", (G, G), "white"); tela.paste(centro.resize((gi, gi), Image.LANCZOS), (go, go))
    buf = io.BytesIO(); tela.save(buf, "PNG")

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "via-proxy"))
    cfg = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"],
                                      image_config=types.ImageConfig(aspect_ratio="1:1", image_size="2K"))
    r = client.models.generate_content(model=MODEL, config=cfg, contents=[
        types.Part(inline_data=types.Blob(mime_type="image/png", data=buf.getvalue())), types.Part(text=PROMPT)])
    gen = next(Image.open(io.BytesIO(p.inline_data.data)) for c in r.candidates for p in c.content.parts
               if getattr(p, "inline_data", None))

    # ricomposizione: bordi da Gemini, centro originale ad alta risoluzione con bordo sfumato
    out = gen.convert("RGB").resize((OUT_PX, OUT_PX), Image.LANCZOS)
    mask = Image.new("L", (inner, inner), 0); f = 24
    ImageDraw.Draw(mask).rectangle([f, f, inner - f, inner - f], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(f / 2))
    out.paste(centro, (off, off), mask)
    dst = DIR / "assets" / "allargate" / f"{pid}.png"; dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst); gen.save(dst.with_suffix(".gemini.png"))
    print(f"✓ {dst.relative_to(DIR)}")


if __name__ == "__main__":
    for pid in sys.argv[1:]:
        main(pid)
