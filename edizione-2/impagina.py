#!/usr/bin/env python3
"""
impagina.py — Genera il PDF di stampa KDP della 2ª edizione di
"Le Avventure de El Chucharon", senza Canva.

Input:
  pagine.json   ordine delle pagine, immagine e posizione (in pt, origine in alto a sx)
  testo.md      testo delle pagine (vedi convenzioni in testa al file)
  assets/       illustrazioni e sfondi estratti dal PDF della 1ª edizione
  fonts/        Open Sans (OFL) + DejaVu Sans per il simbolo ♪

Formato KDP (guida "Linee guida per l'invio della versione cartacea"):
  gabbia 8,5"×8,5" con smarginatura → pagina 8,625" × 8,75" (621×630 pt):
  +0,125" sui bordi superiore, inferiore ed esterno, nessuna abbondanza verso la rilegatura.
  Il disegno resta su una tela 630×630 (stesse coordinate della 1ª ed.) e ogni pagina
  viene ritagliata di 9 pt sul lato della rilegatura: sinistra per le dispari, destra per le pari.
  Nessuna trasparenza (alone disattivato), nessun metadato titolo.
La versione --web resta 630×630, senza ritaglio.

Uso:
  pip install reportlab pillow
  python impagina.py                       → output/chucharon-2a-edizione.pdf
  python impagina.py --solo cap3           → solo un capitolo (anteprima veloce)
  python impagina.py --font-size 15.5      → corpo del testo
  python impagina.py --guide               → mostra area di rifilo e margine di sicurezza
  python impagina.py --web                 → versione per il sito, con copertina (copertina/fronte.pdf)
"""
import argparse, io, json, re
from pathlib import Path

from PIL import Image, ImageFilter, ImageEnhance
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph

DIR = Path(__file__).parent
PAGE = 630.0                 # pt
BLEED = 9.0                  # 0,125" per lato
TEXT_X0, TEXT_X1 = 63.0, 567.0
TEXT_CENTER_Y = 300.0        # centro verticale del blocco testo (dall'alto), come in Canva
JPEG_Q = [92]   # qualità JPEG delle immagini (la versione web usa --web → 78)
WEB = [False]   # True con --web: niente ricampionamento (file leggero)
SIZE = [16.5]   # corpo corrente, usato da nota()

# ---------------------------------------------------------------- font
def registra_font():
    F = DIR / "fonts"
    pdfmetrics.registerFont(TTFont("OS", F / "OpenSans_400Regular.ttf"))
    pdfmetrics.registerFont(TTFont("OS-B", F / "OpenSans_700Bold.ttf"))
    pdfmetrics.registerFont(TTFont("OS-I", F / "OpenSans_400Regular_Italic.ttf"))
    pdfmetrics.registerFont(TTFont("OS-BI", F / "OpenSans_700Bold_Italic.ttf"))
    pdfmetrics.registerFont(TTFont("DJ-B", F / "DejaVuSans-Bold.ttf"))
    addMapping("OS", 0, 0, "OS"); addMapping("OS", 1, 0, "OS-B")
    addMapping("OS", 0, 1, "OS-I"); addMapping("OS", 1, 1, "OS-BI")

# ---------------------------------------------------------------- testo
def leggi_testo(path):
    """Ritorna {page_id: [blocchi]}; blocco = ('p', markup) | ('song', [righe])."""
    src = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    out = {}
    for sez in re.split(r"^## ", src, flags=re.M)[1:]:
        pid, _, body = sez.partition("\n")
        blocchi = []
        for par in re.split(r"\n\s*\n", body.strip()):
            righe = [r.strip() for r in par.strip().splitlines() if r.strip()]
            if not righe:
                continue
            if all(r.startswith(">") for r in righe):
                blocchi.append(("song", [r.lstrip("> ").strip() for r in righe]))
            else:
                blocchi.append(("p", " ".join(righe)))
        out[pid.strip()] = blocchi
    return out

def md2rl(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<b><i>\1</i></b>", s)
    return s

def nota(s):
    return f'<font name="DJ-B" size="{SIZE[0]:.1f}">♪</font>'

def paragrafi(blocchi, size, leading):
    base = ParagraphStyle("t", fontName="OS", fontSize=size, leading=leading,
                          alignment=TA_JUSTIFY, textColor=(0, 0, 0))
    song = ParagraphStyle("s", parent=base, alignment=TA_LEFT)
    out = []
    for kind, val in blocchi:
        if kind == "p":
            out.append(Paragraph(md2rl(val), base))
        else:
            for i, r in enumerate(val):
                txt = f"<b><i>{md2rl(r)}</i></b>"
                if i == 0:
                    txt = nota(0) + " " + txt
                    out.append(Paragraph(txt, song))
                else:
                    txt = txt + " " + nota(0)
                    out.append(Paragraph(txt, ParagraphStyle("s2", parent=song, leftIndent=size * 1.15)))
    return out

def disegna_testo(c, blocchi, size, leading, halo):
    w = TEXT_X1 - TEXT_X0
    paras = paragrafi(blocchi, size, leading)
    hs = [p.wrap(w, PAGE)[1] for p in paras]
    tot = sum(hs)
    top = TEXT_CENTER_Y - tot / 2            # dall'alto
    if top < 95 or top + tot > 535:
        print(f"   ⚠️  testo lungo: occupa {tot:.0f}pt, sconfina sulle decorazioni")
    y = PAGE - top
    for p, h in zip(paras, hs):
        y -= h
        if halo:   # alone chiaro dietro al testo (sostituisce l'ombra di Canva)
            for dx, dy in [(-.7, 0), (.7, 0), (0, -.7), (0, .7), (-.5, -.5), (.5, .5), (-.5, .5), (.5, -.5)]:
                c.saveState(); c.setFillAlpha(0.55)
                p2 = Paragraph(p.text, ParagraphStyle("h", parent=p.style, textColor=(1, 1, 1)))
                p2.wrap(w, PAGE); p2.drawOn(c, TEXT_X0 + dx, y + dy)
                c.restoreState()
        p.drawOn(c, TEXT_X0, y)
    return tot

# ---------------------------------------------------------------- immagini
_cache = {}
MIN_PPI = 300   # requisito KDP
def immagine(path, w_pt=None, h_pt=None):
    """Converte in JPEG (RGB) in memoria; se la risoluzione effettiva in pagina è
    sotto i 300 PPI richiesti da KDP, ricampiona (Lanczos) fino a 300 PPI."""
    key = (path, w_pt)
    if key not in _cache:
        im = Image.open(path)
        if w_pt and not WEB[0]:
            ppi = im.width / (w_pt / 72)
            if ppi < MIN_PPI - 1:
                f = MIN_PPI / ppi
                im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
                print(f"   ↑ {Path(path).name}: {ppi:.0f} → {MIN_PPI} ppi")
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, "white")
            im = im.convert("RGBA"); bg.paste(im, mask=im.split()[3]); im = bg
        else:
            im = im.convert("RGB")
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=JPEG_Q[0], subsampling=0)
        buf.seek(0); _cache[key] = ImageReader(buf)
    return _cache[key]

def disegna_immagine(c, path, box):
    x0, t, x1, b = box
    c.drawImage(immagine(path, x1 - x0, b - t), x0, PAGE - b, width=x1 - x0, height=b - t)

SAFE = BLEED + 27     # 0,375" dentro il rifilo: area di sicurezza KDP (36 pt dal bordo)
def disegna_nei_margini(c, path, box, fondo):
    """Riduce la parte visibile della pagina dentro l'area di sicurezza KDP.
    fondo = "sfocato": l'illustrazione stessa, sfocata, riempie i bordi;
    fondo = "bianco": bordi bianchi (pagine da colorare)."""
    x0, t, x1, b = box
    im = Image.open(path).convert("RGB")
    sx, sy = im.width / (x1 - x0), im.height / (b - t)
    vis = im.crop((round(-x0 * sx), round(-t * sy), round((PAGE - x0) * sx), round((PAGE - t) * sy)))
    tmp = Path(path).with_name(Path(path).stem + "-margini")
    if fondo == "sfocato":
        bg = vis.resize((vis.width // 40, vis.height // 40), Image.BOX).filter(ImageFilter.GaussianBlur(4))
        bg = ImageEnhance.Brightness(bg).enhance(1.05).resize(vis.size, Image.LANCZOS)
        bgp = tmp.with_suffix(".bg.png"); bg.save(bgp)
        c.drawImage(immagine(str(bgp), PAGE, PAGE), 0, 0, width=PAGE, height=PAGE)
    fgp = tmp.with_suffix(".fg.png"); vis.save(fgp)
    w = PAGE - 2 * SAFE
    c.drawImage(immagine(str(fgp), w, w), SAFE, SAFE, width=w, height=w)

def guide(c):
    c.saveState(); c.setLineWidth(0.4)
    c.setStrokeColorRGB(1, 0, 0); c.rect(BLEED, BLEED, PAGE - 2 * BLEED, PAGE - 2 * BLEED)   # rifilo
    m = BLEED + 27  # 0,375" di sicurezza KDP
    c.setStrokeColorRGB(0, 0, 1); c.rect(m, m, PAGE - 2 * m, PAGE - 2 * m)
    c.restoreState()

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(DIR / "output" / "chucharon-2a-edizione.pdf"))
    ap.add_argument("--solo", help="prefisso id pagina, es. cap3")
    ap.add_argument("--font-size", type=float, default=16.5)
    ap.add_argument("--leading", type=float, default=None, help="interlinea in pt (default 1.36 × corpo)")
    ap.add_argument("--halo", action="store_true",
                    help="alone chiaro dietro al testo (usa trasparenze: NON per KDP)")
    ap.add_argument("--guide", action="store_true")
    ap.add_argument("--web", action="store_true",
                    help="versione per il sito: copertina in testa, immagini più leggere")
    ap.add_argument("--copertina", default=str(DIR / "copertina" / "fronte.pdf"))
    ap.add_argument("--senza-copertina", action="store_true",
                    help="con --web: non aggiunge la copertina (PDF dei singoli capitoli per il sito)")
    a = ap.parse_args()
    if a.web:
        JPEG_Q[0] = 78; WEB[0] = True
        if a.output == ap.get_default("output"):
            a.output = str(DIR / "output" / "chucharon-2a-edizione-web.pdf")

    registra_font()
    cfg = json.loads((DIR / "pagine.json").read_text(encoding="utf-8"))
    testi = leggi_testo(DIR / "testo.md")
    SIZE[0] = a.font_size
    leading = a.leading or round(a.font_size * 1.36, 2)

    out = Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    kdp = not a.web
    page_w = PAGE - BLEED if kdp else PAGE
    c = canvas.Canvas(str(out), pagesize=(page_w, PAGE), initialFontName="OS", initialFontSize=12)
    if not kdp:
        c.setTitle("Le Avventure de El Chucharon — 2ª edizione")
    usati = set()
    n = 0
    for pg in cfg["pagine"]:
        if a.solo and not pg["id"].startswith(a.solo):
            continue
        n += 1
        if kdp and n % 2 == 1:      # pagina destra: rilegatura a sinistra → taglia 9 pt a sinistra
            c.translate(-BLEED, 0)
        c.setFillColorRGB(1, 1, 1); c.rect(0, 0, PAGE, PAGE, stroke=0, fill=1)
        if "nei_margini" in pg and not a.web:
            disegna_nei_margini(c, DIR / pg["img"], pg["box"], pg["nei_margini"])
        else:
            disegna_immagine(c, DIR / pg["img"], pg["box"])
        if "testo" in pg:
            if pg["testo"] not in testi:
                raise SystemExit(f"❌ manca il testo per {pg['testo']} in testo.md")
            disegna_testo(c, testi[pg["testo"]], a.font_size, leading, a.halo)
            usati.add(pg["testo"])
        if a.guide:
            guide(c)
        c.showPage()
        print(f"✓ {pg['id']}")
    c.save()
    if a.web and not a.senza_copertina:
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter()
        w.append(PdfReader(a.copertina))          # pagina di copertina originale (vettoriale)
        w.append(PdfReader(str(out)))
        w.add_metadata({"/Title": "Le Avventure de El Chucharon — 2ª edizione"})
        with open(out, "wb") as f:
            w.write(f)
        print("✓ copertina in testa")
    if kdp:   # KDP: nessun metadato nel file
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter(clone_from=PdfReader(str(out)))
        if "/Info" in w._root_object:
            del w._root_object["/Info"]
        w._info = None
        with open(out, "wb") as f:
            w.write(f)
    orfani = set(testi) - usati
    if orfani and not a.solo:
        print(f"⚠️  testi non usati: {sorted(orfani)}")
    print(f"\n📄 {out}  ({out.stat().st_size / 1e6:.1f} MB)")

if __name__ == "__main__":
    main()
