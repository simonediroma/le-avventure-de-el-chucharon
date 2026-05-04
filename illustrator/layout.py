#!/usr/bin/env python3
"""
layout.py — Genera il PDF stampabile di "Le Avventure di Chucharon".

Legge le illustrazioni da output/, il testo da scenes/ (campo text_block)
e produce un PDF A4 landscape multi-pagina pronto per la stampa.

SETUP (una volta sola):
  pip install reportlab
  # Font consigliato (scarica da fonts.google.com/specimen/Nunito):
  #   Nunito-Regular.ttf  →  mettilo in illustrator/fonts/
  # Font bold per la copertina (opzionale):
  #   Nunito-Bold.ttf     →  mettilo in illustrator/fonts/

USO:
  python layout.py                                              → output/book.pdf
  python layout.py --font fonts/Nunito-Regular.ttf              → font corpo testo
  python layout.py --font-bold fonts/Nunito-Bold.ttf            → font bold sottotitolo
  python layout.py --font-title fonts/Pacifico-Regular.ttf      → font messicano per titolo
  python layout.py --font-size 13                               → dimensione testo
  python layout.py --text-color 0.1,0.1,0.1                    → colore testo (RGB 0-1)
  python layout.py --author "Nome Autore"                       → nome autore in copertina
  python layout.py --output stampa-finale.pdf                   → nome file output
  python layout.py --skip-missing                               → salta pagine senza immagine
  python layout.py --dry-run                                    → mostra lista pagine senza generare

FONT MESSICANO CONSIGLIATO (gratuito):
  Pacifico — fonts.google.com/specimen/Pacifico → Pacifico-Regular.ttf → illustrator/fonts/
"""

import argparse
import json
import re
from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader
except ImportError:
    print("❌ Pacchetto mancante. Esegui: pip install reportlab")
    raise SystemExit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
SCENES_DIR  = SCRIPT_DIR.parent / "scenes"
OUTPUT_DIR  = SCRIPT_DIR / "output"
FONTS_DIR   = SCRIPT_DIR / "fonts"

PAGE_W, PAGE_H = landscape(A4)   # punti: ~841.89 × 595.28  (297mm × 210mm)

# ---------------------------------------------------------------------------
# Zona testo — fissa per tutte le pagine (non varia con la quantità di testo)
# ---------------------------------------------------------------------------
TEXT_ZONE_H = PAGE_H * 0.26   # altezza zona testo: 26% pagina in basso
TEXT_PAD_X  = 18 * mm          # margine sinistro e destro
TEXT_PAD_Y  = 8 * mm           # distanza dal fondo pagina
TEXT_MAX_W  = PAGE_W - 2 * TEXT_PAD_X

# ---------------------------------------------------------------------------
# Ordine di stampa (26 pagine: copertina + 25 pagine interne)
# ---------------------------------------------------------------------------

SCENE_ORDER = [
    # Copertina libro
    "COVER",
    # Prologo
    "P-01", "P-02", "P-03", "P-04", "P-05",
    # Capitolo 1 — Leo
    "C1-00",
    "C1-01", "C1-02", "C1-03", "C1-04",
    # Capitolo 2 — Sofia
    "C2-00",
    "C2-01", "C2-02", "C2-03", "C2-04",
    # Capitolo 3 — Marco
    "C3-00",
    "C3-01", "C3-02", "C3-03", "C3-04",
    # Epilogo
    "E-00",
    "E-01",  "E-02",  "E-03",  "E-04",
]

# Pagine canzone: testo centrato, bold + pseudo-italic
SONG_PAGES = {"C1-03", "C2-03", "C3-03", "E-03"}

# Copertine di capitolo: solo il nome del bambino, centrato e grande
CHAPTER_COVER_PAGES = {"C1-00", "C2-00", "C3-00", "E-00"}

# ---------------------------------------------------------------------------
# Mappa ID → cartella output
# ---------------------------------------------------------------------------

def chapter_folder(scene_id: str) -> str:
    if scene_id == "COVER":        return "00-cover"
    if scene_id.startswith("P-"):  return "00-prologo"
    if scene_id.startswith("C1-"): return "01-leo"
    if scene_id.startswith("C2-"): return "02-sofia"
    if scene_id.startswith("C3-"): return "03-marco"
    if scene_id.startswith("E-"):  return "04-epilogo"
    return "other"

# ---------------------------------------------------------------------------
# Lettura text_block dal frontmatter YAML
# ---------------------------------------------------------------------------

def read_text_block(scene_id: str) -> str:
    scene_file = SCENES_DIR / f"{scene_id}.md"
    if not scene_file.exists():
        return ""
    lines = scene_file.read_text(encoding="utf-8").split("\n")
    if not lines or lines[0].strip() != "---":
        return ""
    end = 1
    while end < len(lines) and lines[end].strip() != "---":
        end += 1
    i = 1
    while i < end:
        key, _, val = lines[i].partition(":")
        if key.strip() == "text_block" and val.strip() == "|":
            block = []
            i += 1
            while i < end:
                nl = lines[i]
                if nl and nl[0] not in (" ", "\t"):
                    break
                block.append(nl.strip())
                i += 1
            return "\n".join(block).strip()
        i += 1
    return ""

# ---------------------------------------------------------------------------
# Pulizia testo
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    # Rimuovi emoji musicali — ♪ non è presente in Helvetica/Nunito e stampa come quadratino.
    # Le pagine canzone sono già visivamente distinte (grassetto + corsivo) — il simbolo è ridondante.
    text = text.replace("🎵", "").replace("🎶", "")
    # \n viene preservato — senza di esso le righe si concatenano ("fine.Inizio")
    text = re.sub(r"[^\x20-\xFF\u0100-\u024F\u2018-\u201D\u2013\u2014\n]", "", text)
    return text


def fix_punctuation_spacing(text: str) -> str:
    """Assicura uno spazio dopo la punteggiatura di fine frase se mancante."""
    return re.sub(r'([.!?])([^\s\n])', r'\1 \2', text)


def draw_gradient_overlay(
    c: rl_canvas.Canvas,
    area_h: float,
    steps: int = 40,
    color: tuple = (0.97, 0.94, 0.88),
    max_alpha: float = 0.92,
) -> None:
    """
    Sfondo testo leggibile: zona solida in basso + sfumatura verso l'illustrazione in alto.
    - 65% inferiore: alpha pieno (max_alpha) — testo sempre leggibile
    - 35% superiore: sfuma da max_alpha a 0 — transizione morbida verso l'illustrazione
    """
    solid_frac = 0.65
    solid_h    = area_h * solid_frac
    fade_h     = area_h - solid_h
    strip_h    = area_h / steps

    for i in range(steps):
        frac = i / steps          # 0 = fondo pagina, 1 = cima area testo
        if frac < solid_frac:
            # Zona solida
            t = max_alpha
        else:
            # Sfumatura nella zona superiore
            progress = (frac - solid_frac) / (1.0 - solid_frac)  # 0→1 salendo
            t = max_alpha * (1.0 - progress) ** 1.6

        c.saveState()
        c.setFillAlpha(t)
        c.setFillColorRGB(*color)
        c.rect(0, i * strip_h, PAGE_W, strip_h + 1, fill=1, stroke=0)
        c.restoreState()


def draw_band_cream(c: rl_canvas.Canvas) -> None:
    """Riempie l'intera pagina con crema calda (base per entrambi gli stili)."""
    c.setFillColorRGB(0.97, 0.93, 0.83)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def draw_band_mexican(c: rl_canvas.Canvas,
                      band_x: float = 0, band_y: float = 0) -> None:
    """
    Bande con i colori della bandiera messicana: verde | bianco | rosso.
    Bordino dorato sul lato interno (verso l'immagine).

    band_x : larghezza bande sinistra/destra (da draw_fullbleed)
    band_y : altezza bande alto/basso
    Se entrambi 0 → fallback: strisce fisse di 36pt sui lati.
    """
    FLAG_GREEN = (0.00, 0.40, 0.27)   # verde bandiera messicana
    FLAG_WHITE = (0.97, 0.97, 0.94)   # bianco caldo
    FLAG_RED   = (0.80, 0.07, 0.15)   # rosso bandiera messicana
    GOLD       = (0.88, 0.62, 0.12)   # bordino dorato

    draw_band_cream(c)

    def _strip_v(x_left, sw):
        """Striscia verticale: verde | bianco | rosso + bordino dorato interno."""
        third  = sw / 3
        border = max(1.5, sw * 0.09)
        c.setFillColorRGB(*FLAG_GREEN)
        c.rect(x_left,           0, third, PAGE_H, fill=1, stroke=0)
        c.setFillColorRGB(*FLAG_WHITE)
        c.rect(x_left + third,   0, third, PAGE_H, fill=1, stroke=0)
        c.setFillColorRGB(*FLAG_RED)
        c.rect(x_left + 2*third, 0, third, PAGE_H, fill=1, stroke=0)
        # Bordino dorato sul lato verso l'immagine
        c.setFillColorRGB(*GOLD)
        if x_left < PAGE_W / 2:
            c.rect(x_left + sw - border, 0, border, PAGE_H, fill=1, stroke=0)
        else:
            c.rect(x_left, 0, border, PAGE_H, fill=1, stroke=0)

    def _strip_h(y_bot, sh):
        """Striscia orizzontale: verde | bianco | rosso + bordino dorato interno."""
        third  = sh / 3
        border = max(1.5, sh * 0.09)
        c.setFillColorRGB(*FLAG_GREEN)
        c.rect(0, y_bot,           PAGE_W, third, fill=1, stroke=0)
        c.setFillColorRGB(*FLAG_WHITE)
        c.rect(0, y_bot + third,   PAGE_W, third, fill=1, stroke=0)
        c.setFillColorRGB(*FLAG_RED)
        c.rect(0, y_bot + 2*third, PAGE_W, third, fill=1, stroke=0)
        c.setFillColorRGB(*GOLD)
        if y_bot < PAGE_H / 2:
            c.rect(0, y_bot + sh - border, PAGE_W, border, fill=1, stroke=0)
        else:
            c.rect(0, y_bot, PAGE_W, border, fill=1, stroke=0)

    if band_x > 1:
        _strip_v(0,               band_x)
        _strip_v(PAGE_W - band_x, band_x)
    if band_y > 1:
        _strip_h(0,               band_y)
        _strip_h(PAGE_H - band_y, band_y)
    if band_x <= 1 and band_y <= 1:
        _strip_v(0,             36)
        _strip_v(PAGE_W - 36,  36)


def draw_fullbleed(
    c: rl_canvas.Canvas,
    img_path: Path,
    band_style: str = "cream",
    fill_width: bool = False,
) -> None:
    """
    Disegna un'immagine a piena pagina mantenendo le proporzioni originali.

    fill_width=False (default) — modalità "contain": scala per il lato più vincolante,
        l'immagine intera è visibile, eventuali bande sopra/sotto o ai lati.
    fill_width=True  — scala sempre per larghezza piena (PAGE_W): nessuna banda
        laterale, eventuale ritaglio verticale centrato. Usato per le pagine canzone
        la cui immagine può avere proporzioni leggermente più verticali del foglio.
    """
    reader = ImageReader(str(img_path))
    iw, ih = reader.getSize()

    if fill_width:
        scale  = PAGE_W / iw          # larghezza sempre piena, senza bande laterali
    else:
        scale  = min(PAGE_W / iw, PAGE_H / ih)

    draw_w = iw * scale
    draw_h = ih * scale
    x = (PAGE_W - draw_w) / 2         # 0 se fill_width (nessuna banda laterale)
    y = (PAGE_H - draw_h) / 2         # negativo se l'immagine eccede in altezza → ritaglio centrato

    # Sfondo bande — passa le dimensioni reali per disegnare i motivi
    band_x = max(0.0, x)
    band_y = max(0.0, y)
    if band_style == "mexican":
        draw_band_mexican(c, band_x=band_x, band_y=band_y)
    else:
        draw_band_cream(c)

    c.drawImage(reader, x, y, width=draw_w, height=draw_h,
                mask="auto", preserveAspectRatio=True)


def wrap_text(lines: list[str], c: rl_canvas.Canvas,
              font_name: str, font_size: float, max_width: float) -> list[str]:
    """Spezza le righe troppo lunghe in più righe usando il word-wrap."""
    result = []
    for line in lines:
        words = line.split()
        if not words:
            continue
        current = ""
        for word in words:
            candidate = (current + " " + word).strip()
            if c.stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                if current:
                    result.append(current)
                # Se la singola parola è già troppo larga, la mettiamo comunque
                current = word
        if current:
            result.append(current)
    return result

# ---------------------------------------------------------------------------
# Registrazione font
# ---------------------------------------------------------------------------

def register_font(font_path: str | None, name_hint: str = "body") -> str:
    if font_path:
        p = Path(font_path)
        if not p.is_absolute():
            p = SCRIPT_DIR / p
        if p.exists():
            name = p.stem.replace("-", "").replace(" ", "")
            pdfmetrics.registerFont(TTFont(name, str(p)))
            print(f"✅ Font {name_hint}: {p.name} → '{name}'")
            return name
        print(f"⚠️  Font non trovato: {font_path} — uso Helvetica")
    return "Helvetica"

# ---------------------------------------------------------------------------
# Disegno copertina
# ---------------------------------------------------------------------------

def draw_cover(
    c: rl_canvas.Canvas,
    font_name: str,
    font_bold: str,
    font_title: str,
    font_size: float,
    text_color: tuple,
    author: str,
    band_style: str,
    skip_missing: bool,
    dry_run: bool,
) -> bool:
    img_path = OUTPUT_DIR / "00-cover" / "COVER.png"

    if dry_run:
        exists = "✅" if img_path.exists() else "❌ mancante"
        print(f"  {'COVER':8s} {exists}  [COPERTINA]  →  00-cover/COVER.png")
        return True

    # Sfondo
    if img_path.exists():
        draw_fullbleed(c, img_path, band_style)
    else:
        if skip_missing:
            print(f"  ⚠️  COVER: immagine mancante — saltata")
            return False
        draw_band_mexican(c) if band_style == "mexican" else draw_band_cream(c)

    # Nessun testo sulla copertina — il titolo viene aggiunto dall'autore in post-produzione

    print(f"  ✅ COVER")
    c.showPage()
    return True

# ---------------------------------------------------------------------------
# Disegno pagina normale
# ---------------------------------------------------------------------------

def draw_page(
    c: rl_canvas.Canvas,
    scene_id: str,
    font_name: str,
    font_bold: str,
    font_size: float,
    text_color: tuple,
    overlay_color: tuple,
    overlay_alpha: float,
    band_style: str,
    skip_missing: bool,
    dry_run: bool,
) -> bool:
    folder = chapter_folder(scene_id)
    img_path = OUTPUT_DIR / folder / f"{scene_id}.png"
    is_song          = scene_id in SONG_PAGES
    is_chapter_cover = scene_id in CHAPTER_COVER_PAGES

    if dry_run:
        exists = "✅" if img_path.exists() else "❌ mancante"
        tag = " [CANZONE]" if is_song else (" [COPERTINA CAP.]" if is_chapter_cover else "")
        print(f"  {scene_id:8s} {exists}{tag}  →  {folder}/{scene_id}.png")
        return True

    # Sfondo
    if img_path.exists():
        # Le pagine canzone usano fill_width=True: l'immagine occupa sempre tutta la larghezza
        # senza bande laterali, con eventuale ritaglio verticale centrato.
        draw_fullbleed(c, img_path, band_style, fill_width=is_song)
    else:
        if skip_missing:
            print(f"  ⚠️  {scene_id}: immagine mancante — saltata")
            return False
        draw_band_mexican(c) if band_style == "mexican" else draw_band_cream(c)
        c.setFillColorRGB(0.55, 0.50, 0.45)
        c.setFont("Helvetica", 14)
        c.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 10,
                            f"[ {scene_id} — illustrazione non ancora generata ]")
        c.setFont("Helvetica", 10)
        c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 10,
                            "Genera le immagini con:  python main.py --force --aspect 4:3")

    # Testo
    raw = read_text_block(scene_id)
    if raw:
        # Pulizia per righe (preserva struttura)
        raw_lines = [clean_text(l) for l in raw.split("\n") if l.strip()]

        if is_chapter_cover:
            # Il nome è già nell'illustrazione (scritto in stile messicano dall'AI)
            # Nessun testo né overlay da layout.py — come la copertina del libro
            pass

        elif is_song:
            # Canzoncine: testo concatenato in paragrafo unico (come pagine normali)
            # così il wrap occupa tutta la larghezza. Stile bold + pseudo-italic.
            draw_gradient_overlay(c, TEXT_ZONE_H, color=overlay_color, max_alpha=overlay_alpha)
            c.setFillAlpha(1.0)
            avail_h       = TEXT_ZONE_H - TEXT_PAD_Y * 2
            paragraph     = fix_punctuation_spacing(" ".join(raw_lines))
            display_lines = [paragraph]
            use_font      = font_bold
            r, g, b = text_color
            c.setFillColorRGB(r, g, b)
            fs = font_size
            while fs > 7:
                lh    = fs * 1.5
                lines = wrap_text(display_lines, c, use_font, fs, TEXT_MAX_W)
                if len(lines) * lh <= avail_h:
                    break
                fs -= 0.5
            lh    = fs * 1.5
            lines = wrap_text(display_lines, c, use_font, fs, TEXT_MAX_W)
            y_last  = TEXT_PAD_Y
            y_first = y_last + (len(lines) - 1) * lh
            # Bold + pseudo-italic via skew del canvas (slant ~12°)
            skew = 0.21
            c.saveState()
            c.transform(1, 0, skew, 1, 0, 0)
            c.setFont(use_font, fs)
            for i, line in enumerate(lines):
                y = y_first - i * lh
                c.drawString(TEXT_PAD_X - y * skew, y, line)
            c.restoreState()

        else:
            # Testo normale: tutto su un paragrafo continuo, wrap per larghezza
            draw_gradient_overlay(c, TEXT_ZONE_H, color=overlay_color, max_alpha=overlay_alpha)
            c.setFillAlpha(1.0)
            avail_h      = TEXT_ZONE_H - TEXT_PAD_Y * 2
            paragraph    = fix_punctuation_spacing(" ".join(raw_lines))
            display_lines = [paragraph]
            use_font      = font_name
            r, g, b = text_color
            c.setFillColorRGB(r, g, b)
            fs = font_size
            while fs > 7:
                lh    = fs * 1.5
                lines = wrap_text(display_lines, c, use_font, fs, TEXT_MAX_W)
                if len(lines) * lh <= avail_h:
                    break
                fs -= 0.5
            lh    = fs * 1.5
            lines = wrap_text(display_lines, c, use_font, fs, TEXT_MAX_W)
            y_last  = TEXT_PAD_Y
            y_first = y_last + (len(lines) - 1) * lh
            c.setFont(use_font, fs)
            for i, line in enumerate(lines):
                y = y_first - i * lh
                c.drawString(TEXT_PAD_X, y, line)

    print(f"  ✅ {scene_id}")
    c.showPage()
    return True

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

CONFIG_FILE = SCRIPT_DIR / "layout.config.json"


def load_config() -> dict:
    """Legge layout.config.json se esiste, altrimenti ritorna un dict vuoto."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️  layout.config.json non valido ({e}) — uso defaults")
    return {}


def main() -> None:
    cfg = load_config()

    parser = argparse.ArgumentParser(
        description="Genera il PDF stampabile del libro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--font",         default=cfg.get("font"),
                        help="Font TTF corpo (es. fonts/Nunito-Regular.ttf)")
    parser.add_argument("--font-bold",    default=cfg.get("font_bold"),
                        help="Font TTF bold per sottotitolo (es. fonts/Nunito-Bold.ttf)")
    parser.add_argument("--font-title",   default=cfg.get("font_title"),
                        help="Font TTF messicano per titolo copertina (es. fonts/Pacifico-Regular.ttf)")
    parser.add_argument("--font-size",    type=float, default=cfg.get("font_size", 12.0),
                        help="Dimensione testo base (default: 12)")
    parser.add_argument("--text-color",   default=cfg.get("text_color", "0.12,0.10,0.08"),
                        help="Colore testo RGB 0-1 (default: marrone scuro)")
    parser.add_argument("--author",       default=cfg.get("author", ""),
                        help="Nome autore per la copertina")
    parser.add_argument("--output",       default=cfg.get("output"),
                        help="Nome file PDF (default: output/book.pdf)")
    parser.add_argument("--band-style",    default=cfg.get("band_style", "cream"),
                        choices=["cream", "mexican"],
                        help="Stile bande laterali: cream (crema) o mexican (pattern azteco)")
    parser.add_argument("--overlay-color", default=cfg.get("overlay_color", "0.97,0.94,0.88"),
                        help="Colore sfumatura testo RGB 0-1 (default: crema calda)")
    parser.add_argument("--overlay-alpha", type=float, default=cfg.get("overlay_alpha", 0.80),
                        help="Opacità max sfumatura 0-1 (default: 0.80)")
    parser.add_argument("--skip-missing", action="store_true",
                        help="Salta pagine senza illustrazione")
    parser.add_argument("--dry-run",      action="store_true",
                        help="Mostra le pagine senza generare il PDF")
    args = parser.parse_args()

    try:
        text_color = tuple(float(x) for x in args.text_color.split(","))
        if len(text_color) != 3:
            raise ValueError
    except ValueError:
        print("⚠️  Formato --text-color non valido — uso default")
        text_color = (0.12, 0.10, 0.08)

    try:
        overlay_color = tuple(float(x) for x in args.overlay_color.split(","))
        if len(overlay_color) != 3:
            raise ValueError
    except ValueError:
        print("⚠️  Formato --overlay-color non valido — uso default")
        overlay_color = (0.97, 0.94, 0.88)

    if args.dry_run:
        print(f"\n📋 Dry run — {len(SCENE_ORDER)} pagine:\n")
        for sid in SCENE_ORDER:
            if sid == "COVER":
                draw_cover(None, "", "", "", 0, text_color, "", args.band_style, False, dry_run=True)
            else:
                draw_page(None, sid, "", "", 0, text_color, overlay_color, args.overlay_alpha,
                          args.band_style, False, dry_run=True)
        missing = sum(
            1 for sid in SCENE_ORDER
            if not (OUTPUT_DIR / chapter_folder(sid) / f"{sid}.png").exists()
        )
        print(f"\n{'─'*48}")
        print(f"Presenti: {len(SCENE_ORDER) - missing}/{len(SCENE_ORDER)}"
              + (f"  |  Mancanti: {missing}" if missing else ""))
        return

    out_path = Path(args.output) if args.output else OUTPUT_DIR / "book.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    font_name  = register_font(args.font,       "corpo")
    font_bold  = register_font(args.font_bold,  "bold")  if args.font_bold  else font_name
    font_title = register_font(args.font_title, "title") if args.font_title else font_bold

    print(f"\n📖 Generazione PDF")
    print(f"   Output : {out_path}")
    print(f"   Pagine : {len(SCENE_ORDER)}  (copertina libro + 4 copertine capitolo + 21 pagine)")
    print(f"   Formato: A4 landscape (297×210mm)")
    print(f"   Font   : {font_name}  {args.font_size}pt\n")

    c = rl_canvas.Canvas(str(out_path), pagesize=landscape(A4))
    c.setTitle("Le Avventure di Chucharon")

    generated = 0
    for scene_id in SCENE_ORDER:
        if scene_id == "COVER":
            ok = draw_cover(c, font_name, font_bold, font_title, args.font_size, text_color,
                            args.author, args.band_style, args.skip_missing, dry_run=False)
        else:
            ok = draw_page(c, scene_id, font_name, font_bold, args.font_size, text_color,
                           overlay_color, args.overlay_alpha, args.band_style,
                           args.skip_missing, dry_run=False)
        if ok:
            generated += 1

    c.save()

    size_kb = out_path.stat().st_size // 1024
    print(f"\n{'─'*48}")
    print(f"✅ PDF generato: {out_path.resolve()}")
    print(f"   {generated} pagine  |  {size_kb} KB")
    if size_kb > 50_000:
        print("   💡 Per email/web comprimi con: ghostscript -dPDFSETTINGS=/ebook")


if __name__ == "__main__":
    main()
