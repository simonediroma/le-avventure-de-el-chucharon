#!/usr/bin/env python3
"""
Chucharon Illustrator — genera illustrazioni per Le Avventure di Chucharon
usando Gemini via generate_content.

SETUP (una volta sola):
  pip install -r requirements.txt
  Windows:   $env:GEMINI_API_KEY = "la-tua-chiave"
  Mac/Linux: export GEMINI_API_KEY=la-tua-chiave
  Chiave su: https://aistudio.google.com/app/apikey

USO:
  python main.py                         genera tutto
  python main.py --chapter prologo       solo il prologo
  python main.py --only P-01,P-02        prompt specifici
  python main.py --dry-run               mostra cosa farebbe senza API
  python main.py --force                 rigenera immagini già esistenti
  python main.py --list-models           mostra modelli disponibili
  python main.py --regen-firsts          rigenera la prima immagine di ogni capitolo
                                         (esegui dopo una generazione completa per
                                          sfruttare il bootstrap visivo pieno)
  python main.py --consistency-check    valuta ogni immagine vs le regole dei personaggi
  python main.py --cross-check          confronta le immagini TRA LORO per personaggio e
                                         ambientazione — rileva outfit/mobili diversi
  python main.py --auto-fix             valuta (cross-check) + rigenera le inconsistenti
                                         usando quelle consistenti come contesto aggiuntivo

CONTESTO VISIVO (coerenza dei personaggi):
  Per ogni generazione, main.py passa automaticamente come contesto:
    1. Le reference canoniche dei personaggi presenti nella scena (references/)
    2. Tutte le immagini già generate per quel capitolo (output/capitolo/)

  Questo "memoria visiva" aiuta il modello a mantenere consistenza.
  Per disabilitare: --no-chapter-context

REFERENCE IMAGES (personaggi canonici):
  Dopo aver generato un'immagine che ti piace, salvala come riferimento:
    python main.py --save-ref CHU-01 chucharon
    python main.py --save-ref P-01 elena
    python main.py --save-ref P-01 style     (stile globale)

  Verifica reference attive: python main.py --list-refs
"""

import argparse
import json
import os
import re
import shutil
import time
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("❌ Pacchetto mancante. Esegui: pip install -r requirements.txt")
    raise SystemExit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR         = Path(__file__).parent
PROMPTS_FILE       = SCRIPT_DIR.parent / "illustration-prompts.md"
CHAR_TESTS_FILE    = SCRIPT_DIR.parent / "character-tests.md"
SETTING_TESTS_FILE = SCRIPT_DIR.parent / "setting-tests.md"
GEM_CTX_DIR        = SCRIPT_DIR.parent / "gem-context"
CONFIG_FILE        = SCRIPT_DIR / "generator.config.json"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_generator_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️  generator.config.json non valido ({e}) — uso defaults hardcoded")
    return {}

_CFG = load_generator_config()
BOOK_CONTEXT_FILE  = SCRIPT_DIR.parent / "book-context.md"
SCENES_DIR         = SCRIPT_DIR.parent / "scenes"
CHAPTERS_DIR       = SCRIPT_DIR.parent / "chapters"
OUTPUT_DIR         = SCRIPT_DIR / "output"
REFS_DIR           = SCRIPT_DIR / "references"
STATUS_FILE        = SCRIPT_DIR / "generation-status.json"

SETTING_KEYWORDS = _CFG.get("setting_keywords", {
    "parco":     ["playground", "parco", "slide", "swings", "seesaw", "salta-sasta",
                  "altalena", "scivolo", "vialetto"],
    "camera":    ["bed ", "bedroom", "letto", "linens", "tummy time", "parents' bed"],
    "soggiorno": ["living room", "soggiorno", "walnut", "sofa", "espadrilla", "noce"],
    "cucina":    ["kitchen", "cucina", "high chair", "seggiolone", "pappa", "bowl of"],
    "messico":   ["mexican landscape", "dirt road", "desert", "paesaggio messicano",
                  "mountains", "confine"],
    "piramide":  ["pyramid", "chichen", "itza", "maya", "piramide"],
})

CHAPTER_FOLDERS = {
    "PROLOGO":    "00-prologo",
    "CAPITOLO 1": "01-leo",
    "CAPITOLO 2": "02-sofia",
    "CAPITOLO 3": "03-marco",
    "EPILOGO":    "04-epilogo",
}

CHAPTER_FILTER_MAP = {
    "prologo": "PROLOGO",
    "cap1":    "CAPITOLO 1",
    "cap2":    "CAPITOLO 2",
    "cap3":    "CAPITOLO 3",
    "epilogo": "EPILOGO",
    "all":     None,
}

CHARACTER_KEYWORDS = {
    "chucharon": ["chucharon", "el chucharito", "chucharito", "pacifier", "ciuccio"],
    "elena":     ["elena", "elenita"],
    "leo":       ["leo"],
    "sofia":     ["sofia"],
    "marco":     ["marco"],
}

FAMILY_PARENTS = {
    "elena": ["dad-elena", "mom-elena"],
    "leo":   ["dad-leo",   "mom-leo"],
    "sofia": ["dad-sofia", "mom-sofia"],
    "marco": ["dad-marco", "mom-marco"],
}

# Quali altri capitoli contribuiscono al contesto visivo di ciascun capitolo.
# Prologo ed Epilogo condividono lo stesso parco, gli stessi personaggi (Elena +
# entrambi i genitori + Chucharon) → si aiutano a vicenda.
# I capitoli centrali (Leo, Sofia, Marco) hanno ambienti e bambini diversi:
# condividono solo Chucharon, ma le immagini delle famiglie altrui
# potrebbero confondere il modello → nessun cross-context.
CHAPTER_CROSS_CONTEXT: dict[str, list[str]] = _CFG.get("chapter_cross_context", {
    "00-prologo":  ["04-epilogo"],
    "01-leo":      [],
    "02-sofia":    [],
    "03-marco":    [],
    "04-epilogo":  ["00-prologo"],
})

SHARED_FOLDERS: list[str] = _CFG.get("shared_folders", [
    "characters/chucharon",
])

CHAPTER_BOOTSTRAP: dict[str, list[str]] = _CFG.get("chapter_bootstrap", {
    "00-prologo":  [],
    "01-leo":      ["00-prologo/P-03"],
    "02-sofia":    ["00-prologo/P-03", "01-leo/C1-03"],
    "03-marco":    ["00-prologo/P-03", "02-sofia/C2-03"],
    "04-epilogo":  [],
})

SETTING_REF_NAMES: dict[str, str] = _CFG.get("setting_ref_names", {
    "parco":     "park",
    "camera":    "bedroom",
    "soggiorno": "living-room",
    "cucina":    "kitchen",
    "messico":   "mexico",
    "piramide":  "pyramid",
})

IMAGE_MODELS = [
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
    "gemini-2.5-flash-image",
    "gemini-3-pro-preview",
    "nano-banana-pro-preview",
]

# ---------------------------------------------------------------------------
# Contesto personaggi (gem-context/)
# ---------------------------------------------------------------------------

def load_gem_context() -> dict[str, str]:
    ctx: dict[str, str] = {}
    # book-context.md — global visual Bible, loaded as "_global"
    if BOOK_CONTEXT_FILE.exists():
        ctx["_global"] = BOOK_CONTEXT_FILE.read_text(encoding="utf-8")
    # book narrative — all chapters concatenated (strips frontmatter)
    if CHAPTERS_DIR.exists():
        narrative_parts = []
        for f in sorted(CHAPTERS_DIR.glob("*.md")):
            text = f.read_text(encoding="utf-8")
            # Strip YAML frontmatter (---...---) if present
            if text.startswith("---"):
                end = text.find("\n---", 3)
                if end != -1:
                    text = text[end + 4:].strip()
            narrative_parts.append(text)
        if narrative_parts:
            ctx["_narrative"] = "\n\n---\n\n".join(narrative_parts)
    # per-character/setting specs from gem-context/
    if GEM_CTX_DIR.exists():
        for f in sorted(GEM_CTX_DIR.glob("*.md")):
            ctx[f.stem] = f.read_text(encoding="utf-8")
    return ctx


def detect_characters(prompt_text: str) -> list[str]:
    """Restituisce i nomi dei personaggi menzionati nel prompt, inclusi i genitori di famiglia."""
    lower = prompt_text.lower()
    chars = [
        char for char, keywords in CHARACTER_KEYWORDS.items()
        if any(kw in lower for kw in keywords)
    ]
    extra = []
    for char in chars:
        for parent_ref in FAMILY_PARENTS.get(char, []):
            if parent_ref not in extra:
                extra.append(parent_ref)
    return chars + extra


def build_enriched_prompt(
    scene_prompt: str,
    context: dict[str, str],
    aspect: str,
    characters: list[str] | None = None,
    text_block: str = "",
) -> str:
    parts = []

    # Global visual Bible (book-context.md) takes priority over stile-visivo.md
    global_style = context.get("_global") or context.get("stile-visivo")
    if global_style:
        parts.append(
            "=== MANDATORY VISUAL STYLE ===\n"
            + global_style
            + "\nIMPORTANT: Apply these rules to every detail. This illustration must look like "
              "it belongs to the same picture book as all others."
        )

    # Book narrative — full story text for deep character and tone context
    narrative = context.get("_narrative", "")
    if narrative:
        parts.append(
            "=== BOOK NARRATIVE (context only — do not illustrate all of it) ===\n"
            "Read this to understand each character's personality, physical description, emotional arc,\n"
            "and the tone of the story. Use it to make expressions, body language, and atmosphere precise.\n\n"
            + narrative
        )

    # Use frontmatter character list if available, otherwise keyword-detect from text
    chars = characters if characters is not None else detect_characters(scene_prompt)

    char_blocks = []
    for char in chars:
        spec_key = char
        if spec_key not in context:
            # Parent fallback: dad-leo / mom-elena → dad-generic / mom-generic
            if spec_key.startswith("dad-"):
                spec_key = "dad-generic"
            elif spec_key.startswith("mom-"):
                spec_key = "mom-generic"
        if spec_key in context:
            char_blocks.append(f"--- {char.upper()} ---\n" + context[spec_key])
    if char_blocks:
        parts.append(
            "=== CHARACTER REFERENCE (maintain exact appearance) ===\n"
            + "\n\n".join(char_blocks)
        )

    hints = {
        "9:16": "Vertical portrait orientation (9:16 aspect ratio), full bleed composition.",
        "3:4":  "Vertical portrait (3:4 aspect ratio), full bleed.",
        "1:1":  "Square format (1:1).",
        "4:3":  "Horizontal landscape (4:3).",
        "16:9": "Horizontal widescreen (16:9).",
    }
    if aspect in hints:
        parts.append(hints[aspect])

    # Page text — passed as narrative context, must NOT appear in the illustration
    if text_block:
        parts.append(
            "=== PAGE TEXT — DO NOT RENDER IN THE ILLUSTRATION ===\n"
            "The following Italian text will be printed on this page by an editor in post-production.\n"
            "DO NOT write, render, letter, or include any of this text inside the illustration itself.\n"
            "Use it ONLY as narrative context: it tells you the mood, the characters' emotions,\n"
            "what is happening on this page, and what the reader will feel.\n"
            "Let it guide composition, expressions, lighting, and atmosphere — but keep it invisible.\n\n"
            + text_block
        )

    parts.append("=== SCENE TO ILLUSTRATE ===\n" + scene_prompt)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Reference images (references/)
# ---------------------------------------------------------------------------

def load_references() -> dict[str, bytes]:
    if not REFS_DIR.exists():
        return {}
    return {
        f.stem: f.read_bytes()
        for f in REFS_DIR.glob("*.png")
    }


def save_reference(prompt_id: str, ref_name: str) -> bool:
    matches = list(OUTPUT_DIR.glob(f"**/{prompt_id}.png"))
    if not matches:
        print(f"❌ Immagine non trovata: {prompt_id}.png in {OUTPUT_DIR}")
        return False
    REFS_DIR.mkdir(exist_ok=True)
    dest = REFS_DIR / f"{ref_name}.png"
    shutil.copy2(matches[0], dest)
    print(f"✅ Reference salvata: {dest.name}  (da {matches[0].relative_to(SCRIPT_DIR)})")
    return True


def list_references():
    if not REFS_DIR.exists() or not list(REFS_DIR.glob("*.png")):
        print("📂 Nessuna reference image attiva.")
        print("   Genera prima alcune immagini, poi usa --save-ref per designarle.")
        return
    setting_ref_values = set(SETTING_REF_NAMES.values())
    print("\n📌 Reference images attive:\n")
    for f in sorted(REFS_DIR.glob("*.png")):
        if f.stem == "style":
            role = "stile globale"
        elif f.stem in setting_ref_values:
            role = f"ambientazione: {f.stem}"
        else:
            role = f"personaggio: {f.stem}"
        print(f"  {f.name:30s}  →  {role}  ({f.stat().st_size // 1024} KB)")
    print()


# ---------------------------------------------------------------------------
# Contesto visivo per capitolo
# ---------------------------------------------------------------------------

def detect_setting(prompt_text: str) -> str | None:
    """Restituisce il nome dell'ambientazione rilevata nel prompt (chiave italiana)."""
    lower = prompt_text.lower()
    for setting, keywords in SETTING_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return setting
    return None


def build_context_images(
    refs: dict[str, bytes],
    chars: list[str],
    chapter_folder: str,
    current_id: str,
    setting: str | None = None,
    max_char_refs: int = 5,
    max_prev_images: int = 3,
    max_cross_images: int = 2,
) -> list[tuple[bytes, str]]:
    """
    Costruisce la lista etichettata di immagini di contesto per una generazione.
    Ogni elemento è (image_bytes, label) dove label descrive il ruolo dell'immagine.

    Ordine — dal più autorevole al più contestuale:
      1. Stile globale (references/style.png)
      2. Reference canonica dell'ambientazione (references/park.png ecc.)
      3. Reference CANONICHE dei personaggi — massima priorità per identità visiva
      4. Cartelle condivise tra tutti i capitoli (SHARED_FOLDERS — Chucharon)
      5. Immagini da capitoli cross-context (CHAPTER_CROSS_CONTEXT)
      6. Immagini già generate per questo capitolo
      7. Bootstrap: solo se primo del capitolo e nessuna prev
    """
    context: list[tuple[bytes, str]] = []

    # 1. Stile globale
    if "style" in refs:
        context.append((refs["style"], "global art style — match this style in every illustration"))

    # 2. Reference ambientazione
    if setting:
        ref_name = SETTING_REF_NAMES.get(setting)
        if ref_name and ref_name in refs:
            context.append((
                refs[ref_name],
                f"CANONICAL setting reference ({setting}) — "
                "the environment MUST match this image exactly: same colors, same furniture, same layout",
            ))

    # 3. Reference canoniche dei personaggi (massima autorità sull'identità visiva)
    # Include sia i protagonisti (CHARACTER_KEYWORDS) sia i genitori (FAMILY_PARENTS)
    all_known_chars = set(CHARACTER_KEYWORDS) | {
        p for parents in FAMILY_PARENTS.values() for p in parents
    }
    base_chars = [c for c in chars if c in all_known_chars]
    for char in base_chars[:max_char_refs]:
        if char in refs:
            context.append((
                refs[char],
                f"CANONICAL character reference: {char.upper()} — "
                f"your {char} MUST be visually identical to this image in every detail "
                "(colors, proportions, key features, clothing). "
                f"This overrides all other context. {char.upper()} appears EXACTLY ONCE.",
            ))

    # 4. Cartelle condivise tra tutti i capitoli (es. character tests di Chucharon)
    for shared in SHARED_FOLDERS:
        shared_dir = OUTPUT_DIR / shared
        if shared_dir.exists():
            shared_imgs = sorted(shared_dir.glob("*.png"), key=lambda f: f.stat().st_mtime)
            char_name = shared.split("/")[-1]
            for img_path in shared_imgs[:max_cross_images]:
                context.append((
                    img_path.read_bytes(),
                    f"consistency reference for {char_name} (from character tests) — "
                    "use for style consistency only; canonical reference above takes priority",
                ))

    # 5. Immagini da capitoli cross-context
    for cross_folder in CHAPTER_CROSS_CONTEXT.get(chapter_folder, []):
        cross_dir = OUTPUT_DIR / cross_folder
        if cross_dir.exists():
            cross_imgs = sorted(cross_dir.glob("*.png"), key=lambda f: f.stat().st_mtime)
            for img_path in cross_imgs[:max_cross_images]:
                context.append((
                    img_path.read_bytes(),
                    f"cross-chapter consistency reference (from {cross_folder}) — "
                    "maintain visual continuity with this chapter",
                ))

    # 6. Immagini già generate per questo capitolo (le più recenti)
    chapter_dir = OUTPUT_DIR / chapter_folder
    prev = []
    if chapter_dir.exists():
        prev = sorted(
            [f for f in chapter_dir.glob("*.png") if f.stem != current_id],
            key=lambda f: f.stat().st_mtime,
        )
        for img_path in prev[-max_prev_images:]:
            context.append((
                img_path.read_bytes(),
                f"previous illustration in this chapter ({img_path.stem}) — "
                "maintain visual continuity; canonical references above override this",
            ))

    # 7. Bootstrap: solo se è la prima immagine del capitolo (nessuna prev)
    # Ogni entry può essere:
    #   - un file PNG esplicito:  "00-prologo/P-03.png"
    #   - un file senza estensione: "00-prologo/P-03"  → prova con .png
    #   - una cartella: "selezione/bootstrap/elena/pro" → carica tutti i PNG dentro
    if not prev:
        for rel_path in CHAPTER_BOOTSTRAP.get(chapter_folder, []):
            boot_path = OUTPUT_DIR / rel_path
            boot_imgs: list[Path] = []
            if boot_path.is_dir():
                boot_imgs = sorted(boot_path.glob("*.png"), key=lambda f: f.name)
            elif boot_path.exists():
                boot_imgs = [boot_path]
            else:
                # prova aggiungendo .png
                with_ext = boot_path.with_suffix(".png")
                if with_ext.exists():
                    boot_imgs = [with_ext]
            for bp in boot_imgs:
                context.append((
                    bp.read_bytes(),
                    f"bootstrap reference ({bp.parent.name}/{bp.stem}) — "
                    "visual anchor for this chapter: match style, characters and setting",
                ))

    return context


# ---------------------------------------------------------------------------
# Modelli
# ---------------------------------------------------------------------------

def list_image_models(client):
    print("\n📋 Modelli con capacità immagine sull'account:\n")
    for m in client.models.list():
        name = getattr(m, "name", "")
        if any(k in name.lower() for k in ("imagen", "image", "nano-banana", "flash", "pro")):
            print(f"  {name}")
    print()


def detect_model(client) -> str | None:
    available = {m.name.split("/")[-1] for m in client.models.list()}
    for candidate in IMAGE_MODELS:
        if candidate in available:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Generazione
# ---------------------------------------------------------------------------

def generate_with_gemini(
    client,
    model: str,
    prompt: str,
    output_path: Path,
    context_images: list[tuple[bytes, str]],
) -> bool:
    """
    Genera un'immagine con immagini di contesto etichettate.

    Ogni elemento di context_images è (image_bytes, label).
    Le etichette vengono usate nel preambolo testuale per indicare al modello
    il ruolo preciso di ciascuna immagine:
      - riferimenti CANONICI (massima autorità sull'identità dei personaggi)
      - riferimenti di continuità (contesto di stile, capitoli precedenti)

    Regole applicate a ogni generazione:
      - Ogni personaggio appare ESATTAMENTE UNA VOLTA
      - I riferimenti canonici hanno priorità assoluta su tutti gli altri
      - L'aspetto visivo di ogni personaggio non cambia mai tra un'illustrazione e l'altra
    """
    parts = []

    if context_images:
        # Passa tutte le immagini al modello nell'ordine stabilito
        for img_bytes, _label in context_images:
            parts.append(
                types.Part(
                    inline_data=types.Blob(mime_type="image/png", data=img_bytes)
                )
            )

        # Costruisce il registro delle immagini: ogni immagine ha un indice e una label
        image_index = "\n".join(
            f"  Image {i}: {label}"
            for i, (_, label) in enumerate(context_images, 1)
        )

        # Individua i personaggi con riferimento canonico per la regola di non-duplicazione
        canonical_chars = [
            label.split("CANONICAL character reference:")[1].split("—")[0].strip()
            for _, label in context_images
            if "CANONICAL character reference:" in label
        ]
        no_dup_rule = ""
        if canonical_chars:
            char_list = ", ".join(canonical_chars)
            no_dup_rule = (
                f"\n\nCHARACTER DUPLICATION RULE (strict — no exceptions):\n"
                f"  Characters in this scene: {char_list}\n"
                f"  Each character appears EXACTLY ONCE — no copies, no doubles, no repeated figures.\n"
                f"  If a character is shown in a reference image, draw them ONCE in this scene only.\n"
                f"  Do not add any character not listed in the scene description below."
            )

        full_text = (
            "REFERENCE IMAGES (in order):\n"
            + image_index
            + "\n\nGENERATION RULES:\n"
            "  1. CANONICAL references define the exact, permanent appearance of each character and setting.\n"
            "     They have absolute priority — your output MUST match them in colors, proportions, and features.\n"
            "  2. Consistency references (previous illustrations, cross-chapter) are secondary context.\n"
            "     If they conflict with a canonical reference, the canonical reference wins.\n"
            "  3. Maintain the same art style, line quality, and color palette throughout."
            + no_dup_rule
            + "\n\nSCENE TO GENERATE:\n\n"
            + prompt
        )
    else:
        full_text = prompt

    parts.append(types.Part(text=full_text))

    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        ),
    )

    for candidate in (response.candidates or []):
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        for part in (content.parts or []):
            if getattr(part, "inline_data", None) is not None:
                output_path.write_bytes(part.inline_data.data)
                return True
    return False


# ---------------------------------------------------------------------------
# Consistency check
# ---------------------------------------------------------------------------

EVAL_MODEL = "gemini-3-pro-preview"   # modello testuale per la valutazione (no image output)


def _extract_text(response) -> str | None:
    """Estrae il testo dalla risposta Gemini iterando su candidates/parts."""
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        for part in getattr(content, "parts", None) or []:
            if hasattr(part, "text") and part.text:
                return part.text.strip()
    return None


def _strip_json(raw: str) -> str:
    """Rimuove eventuali wrapper ```json ... ``` dalla risposta."""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()

CONSISTENCY_PROMPT_TEMPLATE = """\
You are a visual consistency checker for a children's picture book called "Le Avventure di Chucharon".

CHARACTER RULES (these are the ground truth — every illustration must follow them exactly):
{character_rules}

SCENE DESCRIPTION (what this illustration is supposed to show):
{scene_description}

TASK: Examine the illustration provided and check whether it correctly follows the character rules.
Focus only on characters present in the scene description.

For each character, verify:
- Correct visual appearance (proportions, colors, key features)
- Correct state (e.g. for Chucharon: normal/siesta vs El Chucharito transformation)
- Correct details (mustache direction, sombrero position, clothing, expressions)
- Each character appears EXACTLY ONCE — flag any duplication (two Chucharons, two dads, etc.)

Respond ONLY with a valid JSON object, no markdown, no extra text:
{{
  "consistent": true or false,
  "score": 0-10,
  "characters_checked": ["list of character names checked"],
  "issues": ["specific violation 1", "specific violation 2"],
  "notes": "one sentence summary"
}}
"""


def evaluate_consistency(
    client,
    image_bytes: bytes,
    scene_prompt: str,
    gem_context: dict[str, str],
) -> dict:
    """
    Chiede a Gemini di valutare se un'immagine è visivamente consistente
    con le regole dei personaggi. Restituisce un dict con consistent/score/issues.
    """
    chars = detect_characters(scene_prompt)
    base_chars = [c for c in chars if c in CHARACTER_KEYWORDS]

    # Costruisce il blocco regole solo per i personaggi presenti
    char_rules = "\n\n".join(
        f"--- {c.upper()} ---\n{gem_context[c]}"
        for c in base_chars if c in gem_context
    )
    if not char_rules:
        char_rules = "(no specific character rules available)"

    eval_prompt = CONSISTENCY_PROMPT_TEMPLATE.format(
        character_rules=char_rules,
        scene_description=scene_prompt[:600],  # tronca per non superare il contesto
    )

    parts = [
        types.Part(inline_data=types.Blob(mime_type="image/png", data=image_bytes)),
        types.Part(text=eval_prompt),
    ]

    try:
        response = client.models.generate_content(
            model=EVAL_MODEL,
            contents=parts,
        )
        raw = _extract_text(response)
        if not raw:
            return {"consistent": None, "score": None, "issues": ["empty response"], "notes": "eval error"}
        return json.loads(_strip_json(raw))
    except Exception as exc:
        return {"consistent": None, "score": None, "issues": [str(exc)], "notes": "eval error"}


def run_consistency_check(
    client,
    prompts: list[dict],
    gem_context: dict[str, str],
    threshold: int = 7,
) -> tuple[list[dict], list[dict]]:
    """
    Valuta tutte le immagini generate.
    Restituisce (consistent_list, inconsistent_list) dove ogni elemento
    è il dict del prompt arricchito con 'eval' e 'path'.
    """
    consistent   = []
    inconsistent = []

    print(f"\n🔍 Consistency check (soglia: {threshold}/10)\n")

    for p in prompts:
        img_path = OUTPUT_DIR / p["folder"] / f"{p['id']}.png"
        if not img_path.exists():
            print(f"  {p['id']:8s} ⏭️  non generata — skip")
            continue

        print(f"  {p['id']:8s} 🔎 ...", end=" ", flush=True)
        result = evaluate_consistency(client, img_path.read_bytes(), p["prompt"], gem_context)

        score     = result.get("score")
        consistent_flag = result.get("consistent")
        issues    = result.get("issues", [])
        notes     = result.get("notes", "")

        p_eval = {**p, "eval": result, "path": img_path}

        if consistent_flag is None:
            print(f"⚠️  errore valutazione: {issues[0] if issues else '?'}")
            inconsistent.append(p_eval)
        elif consistent_flag and (score is None or score >= threshold):
            print(f"✅ {score}/10  {notes}")
            consistent.append(p_eval)
        else:
            issues_str = " | ".join(issues[:2]) if issues else ""
            print(f"❌ {score}/10  {issues_str}")
            inconsistent.append(p_eval)

        time.sleep(1)  # evita rate limit sul modello testuale

    print(f"\n  ✅ Consistenti  : {len(consistent)}")
    print(f"  ❌ Inconsistenti: {len(inconsistent)}\n")
    return consistent, inconsistent


# ---------------------------------------------------------------------------
# Cross-image consistency check
# ---------------------------------------------------------------------------

CROSS_CHECK_PROMPT = """\
You are a visual consistency inspector for a children's picture book.

You are given {n} images that all feature the same subject: "{subject}".
{id_map}

Your task: check whether "{subject}" looks IDENTICAL across all images.

What to compare:
- Characters: same clothing, same colors, same proportions, same facial features, same key props
- Settings: same furniture, same room layout, same decorations, same color palette

Respond ONLY with valid JSON, no markdown:
{{
  "consistent": true or false,
  "score": 0-10,
  "differences": [
    {{"between": "Image A and Image B", "description": "specific visual difference"}}
  ],
  "inconsistent_ids": ["list of image IDs that differ from the majority — empty if all consistent"]
}}
"""


def evaluate_cross_consistency(
    client,
    images_with_ids: list[tuple[str, bytes]],
    subject: str,
) -> dict:
    """
    Confronta visivamente N immagini dello stesso soggetto (personaggio o ambientazione).
    Restituisce quali ID sono inconsistenti rispetto alla maggioranza.
    """
    if len(images_with_ids) < 2:
        return {"consistent": True, "score": 10, "differences": [], "inconsistent_ids": []}

    parts = []
    id_map_lines = []
    for idx, (img_id, img_bytes) in enumerate(images_with_ids, 1):
        parts.append(types.Part(inline_data=types.Blob(mime_type="image/png", data=img_bytes)))
        id_map_lines.append(f"  Image {idx} = {img_id}")

    id_map = "Image index mapping:\n" + "\n".join(id_map_lines)
    prompt_text = CROSS_CHECK_PROMPT.format(
        n=len(images_with_ids),
        subject=subject,
        id_map=id_map,
    )
    parts.append(types.Part(text=prompt_text))

    try:
        response = client.models.generate_content(model=EVAL_MODEL, contents=parts)
        raw = _extract_text(response)
        if not raw:
            return {"consistent": None, "score": None, "differences": [], "inconsistent_ids": []}
        return json.loads(_strip_json(raw))
    except Exception as exc:
        return {"consistent": None, "score": None, "differences": [str(exc)], "inconsistent_ids": []}


def run_cross_check(
    client,
    prompts: list[dict],
    threshold: int = 7,
) -> tuple[list[str], list[str]]:
    """
    Raggruppa le immagini generate per personaggio e per ambientazione,
    poi confronta visivamente ogni gruppo tra loro.
    Restituisce (consistent_ids, inconsistent_ids).
    """
    # Carica immagini disponibili
    available: dict[str, dict] = {}
    for p in prompts:
        img_path = OUTPUT_DIR / p["folder"] / f"{p['id']}.png"
        if img_path.exists():
            available[p["id"]] = {"path": img_path, "prompt": p["prompt"]}

    if not available:
        print("⚠️  Nessuna immagine generata da valutare.")
        return [], []

    # Raggruppa per personaggio e per ambientazione
    groups: dict[str, list[str]] = {}
    for pid, info in available.items():
        for char in detect_characters(info["prompt"]):
            if char in CHARACTER_KEYWORDS:
                groups.setdefault(char, []).append(pid)
        setting = detect_setting(info["prompt"])
        if setting:
            groups.setdefault(f"setting:{setting}", []).append(pid)

    # Solo gruppi con almeno 2 immagini
    groups = {k: v for k, v in groups.items() if len(v) >= 2}

    print(f"\n🔀 Cross-image consistency check (soglia: {threshold}/10)\n")

    inconsistent_ids: set[str] = set()

    for subject_key, ids in groups.items():
        label = subject_key.replace("setting:", "ambientazione: ")
        print(f"  📋 {label}  ({len(ids)} immagini: {', '.join(ids)})")

        images_with_ids = [(pid, available[pid]["path"].read_bytes()) for pid in ids]
        result = evaluate_cross_consistency(client, images_with_ids, label)

        score         = result.get("score")
        is_consistent = result.get("consistent")
        differences   = result.get("differences", [])
        bad_ids       = result.get("inconsistent_ids", [])

        if is_consistent is None:
            err = differences[0] if differences else "?"
            print(f"     ⚠️  errore: {err}")
        elif is_consistent and (score is None or score >= threshold):
            print(f"     ✅ {score}/10 — tutto consistente")
        else:
            print(f"     ❌ {score}/10")
            for diff in differences[:3]:
                between = diff.get("between", "")
                desc    = diff.get("description", str(diff))
                print(f"        → {between}: {desc}")
            for bid in bad_ids:
                if bid in available:
                    inconsistent_ids.add(bid)

        time.sleep(1)

    consistent_ids = [pid for pid in available if pid not in inconsistent_ids]

    print(f"\n  ✅ Consistenti  : {len(consistent_ids)}")
    print(f"  ❌ Inconsistenti: {len(inconsistent_ids)}")
    if inconsistent_ids:
        print(f"     IDs: {', '.join(sorted(inconsistent_ids))}\n")

    return consistent_ids, list(inconsistent_ids)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def load_status() -> dict:
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    return {}


def save_status(status: dict):
    STATUS_FILE.write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Parser dei prompt
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Estrae il frontmatter YAML (---...---) da un file Markdown.
    Supporta:
      - key: value semplice
      - key: [a, b, c] inline array
      - key: |           YAML literal block scalar (multiriga)
          line one
          line two
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.split("\n")
    end = 1
    while end < len(lines) and lines[end].strip() != "---":
        end += 1
    body = "\n".join(lines[end + 1:]).strip()
    meta: dict = {}
    i = 1
    while i < end:
        line = lines[i]
        # Skip blank lines and indented lines (content of a block scalar)
        if not line.strip() or line[0] in (" ", "\t"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "|":
            # YAML literal block scalar — collect following indented lines
            block_lines = []
            i += 1
            while i < end:
                next_line = lines[i]
                # Empty lines inside the block are preserved
                if next_line and next_line[0] not in (" ", "\t"):
                    break  # back to root-level key
                block_lines.append(next_line.strip())
                i += 1
            meta[key] = "\n".join(block_lines).strip()
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            meta[key] = [x.strip() for x in inner.split(",")] if inner else []
            i += 1
        else:
            meta[key] = val
            i += 1
    return meta, body


def parse_scenes_dir() -> list[dict]:
    """
    Legge tutti i file *.md in scenes/ con frontmatter YAML.
    Ritorna una lista di prompt dict con metadata (characters, setting) dal frontmatter.
    Usato come sorgente principale al posto di illustration-prompts.md.
    """
    if not SCENES_DIR.exists():
        return []
    folder_to_chapter = {v: k for k, v in CHAPTER_FOLDERS.items()}
    results = []
    for f in sorted(SCENES_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(text)
        if not fm or not body:
            continue
        chapter_folder = fm.get("chapter_folder", "")
        chapter = folder_to_chapter.get(chapter_folder, chapter_folder.upper())
        results.append({
            "chapter":    chapter,
            "folder":     chapter_folder,
            "id":         fm.get("id", f.stem),
            "prompt":     body,
            "characters": fm.get("characters", []),   # lista esplicita dal frontmatter
            "setting":    fm.get("setting"),           # ambientazione esplicita dal frontmatter
            "text_block": fm.get("text_block", ""),   # testo della pagina (contesto narrativo)
        })
    return results


def parse_prompts(filepath: Path, source_type: str = "scenes") -> list[dict]:
    """source_type: 'scenes' | 'characters' | 'settings'"""
    content = filepath.read_text(encoding="utf-8")
    prompts = []
    current_chapter = None
    current_section = "characters"

    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        ch_match = re.match(r"^## ([A-ZÀÈÉÌÒÙ][A-ZÀÈÉÌÒÙa-z 0-9]+)", line)
        if ch_match:
            heading = ch_match.group(1).strip().upper()
            matched = False
            for key in CHAPTER_FOLDERS:
                if heading.startswith(key):
                    current_chapter = key
                    matched = True
                    break
            if not matched:
                current_section = heading.lower()
                current_chapter = "CHARACTERS"
            i += 1
            continue

        id_match = re.match(r"^\*\*([A-Z][A-Z0-9\-]+)\*\*\s*$", line.strip())
        if id_match and (current_chapter or current_section):
            prompt_id = id_match.group(1)
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                i += 1
            i += 1
            prompt_lines = []
            while i < len(lines) and lines[i].strip() != "```":
                prompt_lines.append(lines[i])
                i += 1
            prompt_text = "\n".join(prompt_lines).strip()
            if prompt_text:
                if current_chapter and current_chapter != "CHARACTERS":
                    folder = CHAPTER_FOLDERS[current_chapter]
                else:
                    prefix = source_type if source_type in ("characters", "settings") else "other"
                    folder = f"{prefix}/{current_section}"
                prompts.append({
                    "chapter": current_chapter or current_section.upper(),
                    "folder":  folder,
                    "id":      prompt_id,
                    "prompt":  prompt_text,
                })
            continue

        i += 1

    return prompts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Chucharon Illustrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--characters",  action="store_true",
                        help="Genera i test visivi dei personaggi (character-tests.md)")
    parser.add_argument("--settings",    action="store_true",
                        help="Genera le ambientazioni vuote (setting-tests.md)")
    parser.add_argument("--chapter",     choices=list(CHAPTER_FILTER_MAP.keys()), default="all")
    parser.add_argument("--only",        help="IDs separati da virgola, es: P-01,C1-02")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--force",       action="store_true")
    _def = _CFG.get("defaults", {})
    parser.add_argument("--delay",       type=float, default=_def.get("delay", 4.0))
    parser.add_argument("--aspect",      default=_def.get("aspect", "9:16"),
                        choices=["9:16", "1:1", "3:4", "4:3", "16:9"])
    parser.add_argument("--model",       help="Forza modello specifico")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--list-refs",   action="store_true",
                        help="Mostra le reference images attive")
    parser.add_argument("--save-ref",    nargs=2,
                        metavar=("PROMPT_ID", "REF_NAME"),
                        help="Salva un'immagine come reference canonica. "
                             "REF_NAME: style | chucharon | elena | leo | sofia | marco")
    parser.add_argument("--regen",          metavar="ID",
                        help="Rigenera una specifica immagine (es. P-01)")
    parser.add_argument("--refs",           metavar="ID,ID,...",
                        help="IDs delle immagini da usare come reference visive per --regen "
                             "(es. C1-03,E-02,P-03). Cercate in output/ automaticamente.")
    parser.add_argument("--regen-firsts",        action="store_true",
                        help="Rigenera la prima immagine di ogni capitolo con contesto pieno")
    parser.add_argument("--consistency-check",  action="store_true",
                        help="Valuta ogni immagine vs le regole testuali dei personaggi")
    parser.add_argument("--cross-check",        action="store_true",
                        help="Confronta le immagini tra loro per personaggio e ambientazione")
    parser.add_argument("--auto-fix",           action="store_true",
                        help="Valuta + rigenera le immagini inconsistenti automaticamente")
    parser.add_argument("--fix-rounds",         type=int, default=_def.get("fix_rounds", 2),
                        help="Numero massimo di round di auto-fix (default: 2)")
    parser.add_argument("--threshold",          type=int, default=_def.get("threshold", 7),
                        help="Soglia minima di consistenza 0-10 (default: 7)")
    parser.add_argument("--no-context",         action="store_true",
                        help="Non aggiunge il contesto testuale gem-context/ ai prompt")
    parser.add_argument("--no-chapter-context", action="store_true",
                        help="Non passa le immagini di capitolo come contesto visivo")
    parser.add_argument("--max-prev",    type=int, default=_def.get("max_prev", 3),
                        help="Numero massimo di immagini precedenti del capitolo da passare come contesto (default: 3)")
    parser.add_argument("--max-cross",   type=int, default=_def.get("max_cross", 2),
                        help="Numero massimo di immagini da capitoli cross-context (default: 2)")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not args.dry_run and not args.list_refs:
        print("❌ GEMINI_API_KEY non trovata.")
        print("   Windows:   $env:GEMINI_API_KEY = 'la-tua-chiave'")
        print("   Mac/Linux: export GEMINI_API_KEY=la-tua-chiave")
        raise SystemExit(1)

    if args.list_refs:
        list_references()
        raise SystemExit(0)

    if args.save_ref:
        prompt_id, ref_name = args.save_ref
        save_reference(prompt_id.upper(), ref_name.lower())
        raise SystemExit(0)

    client = genai.Client(api_key=api_key) if not args.dry_run else None

    if args.regen:
        target_id = args.regen.strip().upper()

        # Carica contesto e modello
        gem_context = {} if args.no_context else load_gem_context()
        refs        = load_references()
        model       = args.model or detect_model(client)
        if not model:
            print("❌ Nessun modello trovato. Esegui --list-models")
            raise SystemExit(1)

        # Trova il prompt corrispondente all'ID — prova prima scenes/
        all_p = parse_scenes_dir() or parse_prompts(PROMPTS_FILE, "scenes")
        target = next((p for p in all_p if p["id"] == target_id), None)
        if not target:
            print(f"❌ ID non trovato: {target_id}")
            raise SystemExit(1)

        out_path = OUTPUT_DIR / target["folder"] / f"{target_id}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Carica le reference esplicite passate con --refs
        explicit_refs: list[tuple[bytes, str]] = []
        if args.refs:
            ref_ids = [r.strip().upper() for r in args.refs.split(",")]
            missing = []
            for rid in ref_ids:
                matches = list(OUTPUT_DIR.glob(f"**/{rid}.png"))
                if matches:
                    explicit_refs.append((
                        matches[0].read_bytes(),
                        f"CANONICAL character reference: {rid} — "
                        "match this image exactly in colors, proportions, and features",
                    ))
                    print(f"  📎 ref: {rid}  ({matches[0].relative_to(OUTPUT_DIR)})")
                else:
                    missing.append(rid)
            if missing:
                print(f"  ⚠️  non trovate: {', '.join(missing)}")

        # Contesto automatico (canoniche + capitolo) come base
        # Usa frontmatter se disponibile, altrimenti keyword-detection come fallback
        chars   = target.get("characters") or detect_characters(target["prompt"])
        setting = target.get("setting")    or detect_setting(target["prompt"])
        auto_ctx = build_context_images(
            refs=refs, chars=chars,
            chapter_folder=target["folder"],
            current_id=target_id,
            setting=setting,
        )

        # Le reference esplicite vengono PRIMA — sono l'ancora principale
        context_imgs = explicit_refs + auto_ctx

        full_prompt = (
            build_enriched_prompt(
                target["prompt"], gem_context, args.aspect,
                characters=target.get("characters"),
                text_block=target.get("text_block", ""),
            )
            if gem_context else target["prompt"]
        )

        print(f"\n🖌️  Rigenero {target_id}  |  {len(explicit_refs)} refs esplicite + {len(auto_ctx)} auto-ctx  ...", end=" ", flush=True)
        try:
            ok = generate_with_gemini(client, model, full_prompt, out_path, context_imgs)
            print(f"✅  {out_path.relative_to(SCRIPT_DIR)}" if ok else "⚠️  risposta vuota")
        except Exception as exc:
            print(f"❌  {exc}")
        raise SystemExit(0)

    if args.list_models:
        if client:
            list_image_models(client)
        raise SystemExit(0)

    if args.dry_run:
        model = args.model or IMAGE_MODELS[0]
    elif args.model:
        model = args.model
    else:
        model = detect_model(client)
        if not model:
            print("❌ Nessun modello image-generation trovato.")
            print("   Esegui: python main.py --list-models")
            raise SystemExit(1)
        print(f"🤖 Modello: {model}")

    gem_context = {} if args.no_context else load_gem_context()
    if gem_context:
        print(f"📚 Contesto testuale: {', '.join(gem_context.keys())}")

    refs = load_references()
    if refs:
        print(f"📌 Reference canoniche: {', '.join(refs.keys())}")

    use_chapter_context = not args.no_chapter_context
    if use_chapter_context:
        active_cross = {k: v for k, v in CHAPTER_CROSS_CONTEXT.items() if v}
        cross_summary = ", ".join(f"{k}←→{v[0]}" for k, v in active_cross.items())
        print(f"🎞️  Contesto visivo: attivo  (prev={args.max_prev}, cross={args.max_cross})")
        if cross_summary:
            print(f"   Cross-context: {cross_summary}")
    else:
        print("⚠️  Contesto visivo capitolo: disabilitato (--no-chapter-context)")

    if args.characters:
        source_file = CHAR_TESTS_FILE
        if not source_file.exists():
            print(f"❌ File non trovato: {source_file}")
            raise SystemExit(1)
        all_prompts = parse_prompts(source_file, "characters")
        print(f"🎭 Modalità character test — {source_file.name}")
    elif args.settings:
        source_file = SETTING_TESTS_FILE
        if not source_file.exists():
            print(f"❌ File non trovato: {source_file}")
            raise SystemExit(1)
        all_prompts = parse_prompts(source_file, "settings")
        print(f"🏞️  Modalità setting test — {source_file.name}")
    else:
        # Prova prima scenes/ con frontmatter esplicito, poi illustration-prompts.md
        all_prompts = parse_scenes_dir()
        if all_prompts:
            print(f"📂 Sorgente: scenes/  ({len(all_prompts)} scene con frontmatter)")
        else:
            if not PROMPTS_FILE.exists():
                print(f"❌ File non trovato: {PROMPTS_FILE}")
                raise SystemExit(1)
            all_prompts = parse_prompts(PROMPTS_FILE, "scenes")
            print(f"📂 Sorgente: {PROMPTS_FILE.name}")

    print(f"📝 Prompt totali: {len(all_prompts)}")

    if args.regen_firsts:
        # Prende solo la prima immagine di ogni capitolo e forza la rigenerazione
        seen: set[str] = set()
        firsts = []
        for p in all_prompts:
            if p["folder"] not in seen:
                seen.add(p["folder"])
                firsts.append(p)
        all_prompts = firsts
        args.force = True
        print("🔁 Modalità regen-firsts: rigenero la prima immagine di ogni capitolo")

    if args.chapter != "all":
        all_prompts = [p for p in all_prompts if p["chapter"] == CHAPTER_FILTER_MAP[args.chapter]]
    if args.only:
        ids = {x.strip().upper() for x in args.only.split(",")}
        all_prompts = [p for p in all_prompts if p["id"] in ids]

    if not all_prompts:
        print("⚠️  Nessun prompt con i filtri indicati.")
        raise SystemExit(0)

    # --consistency-check: immagine vs regole testuali
    if args.consistency_check:
        run_consistency_check(client, all_prompts, gem_context, args.threshold)
        raise SystemExit(0)

    # --cross-check: immagine vs immagine per personaggio/ambientazione
    if args.cross_check:
        run_cross_check(client, all_prompts, args.threshold)
        raise SystemExit(0)

    # --auto-fix: cross-check + rigenera inconsistenti usando le consistenti come contesto
    if args.auto_fix:
        for fix_round in range(1, args.fix_rounds + 1):
            print(f"\n{'─'*48}")
            print(f"🔧 Auto-fix round {fix_round}/{args.fix_rounds}")
            consistent_ids, inconsistent_ids = run_cross_check(
                client, all_prompts, args.threshold
            )
            if not inconsistent_ids:
                print("✅ Tutte le immagini sono consistenti.")
                break

            # Le immagini consistenti diventano contesto aggiuntivo per le rigenerazioni
            consistent_imgs: list[tuple[bytes, str]] = [
                (
                    (OUTPUT_DIR / p["folder"] / f"{p['id']}.png").read_bytes(),
                    f"validated consistent reference: {p['id']} — "
                    "maintain visual continuity with this approved illustration",
                )
                for p in all_prompts
                if p["id"] in consistent_ids
                and (OUTPUT_DIR / p["folder"] / f"{p['id']}.png").exists()
            ]

            inconsistent = [p for p in all_prompts if p["id"] in inconsistent_ids]

            print(f"🖌️  Rigenero {len(inconsistent)} immagini inconsistenti...\n")
            for p in inconsistent:
                out_path = OUTPUT_DIR / p["folder"] / f"{p['id']}.png"
                print(f"  {p['id']:8s} 🖌️  ...", end=" ", flush=True)

                chars   = p.get("characters") or detect_characters(p["prompt"])
                setting = p.get("setting")    or detect_setting(p["prompt"])
                full_prompt = (
                    build_enriched_prompt(
                        p["prompt"], gem_context, args.aspect,
                        characters=p.get("characters"),
                        text_block=p.get("text_block", ""),
                    )
                    if gem_context else p["prompt"]
                )
                ctx = build_context_images(
                    refs=refs,
                    chars=chars,
                    chapter_folder=p["folder"],
                    current_id=p["id"],
                    setting=setting,
                    max_prev_images=args.max_prev,
                    max_cross_images=args.max_cross,
                )
                # Anteponi le immagini consistenti come ancore visive
                all_ctx = consistent_imgs + ctx

                try:
                    ok = generate_with_gemini(client, model, full_prompt, out_path, all_ctx)
                    print("✅" if ok else "⚠️  risposta vuota")
                except Exception as exc:
                    print(f"❌  {exc}")

                time.sleep(args.delay)

        raise SystemExit(0)

    print(f"🎨 Da generare: {len(all_prompts)}  |  aspect: {args.aspect}  |  delay: {args.delay}s\n")

    OUTPUT_DIR.mkdir(exist_ok=True)
    status = load_status()
    generated = skipped = failed = 0

    for i, p in enumerate(all_prompts, 1):
        out_dir  = OUTPUT_DIR / p["folder"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{p['id']}.png"

        prefix = f"[{i:02d}/{len(all_prompts)}] {p['id']:8s}"

        if out_path.exists() and not args.force:
            print(f"{prefix} ⏭️  già presente")
            skipped += 1
            continue

        print(f"{prefix} 🖌️  ...", end=" ", flush=True)

        if args.dry_run:
            chars = p.get("characters") or detect_characters(p["prompt"])
            setting = p.get("setting") or detect_setting(p["prompt"])
            print(f"OK (dry run)  personaggi: {chars or ['nessuno']}  setting: {setting or '?'}")
            continue

        # Prompt testuale arricchito
        # Usa la lista characters dal frontmatter se disponibile
        chars   = p.get("characters") or detect_characters(p["prompt"])
        setting = p.get("setting")    or detect_setting(p["prompt"])
        full_prompt = (
            build_enriched_prompt(
                p["prompt"], gem_context, args.aspect,
                characters=p.get("characters"),
                text_block=p.get("text_block", ""),
            )
            if gem_context else p["prompt"]
        )

        # Contesto visivo: ambientazione + personaggi + immagini precedenti del capitolo
        # In modalità --characters/--settings non aggiungere immagini "sorelle" della stessa
        # sezione: evita che test di bebè (es. SOF-02 — morde la scarpa) contaminino il
        # contesto dei genitori e attivino i safety filter di Gemini.
        context_imgs: list[tuple[bytes, str]] = []
        if use_chapter_context:
            is_test_mode = args.characters or args.settings
            context_imgs = build_context_images(
                refs=refs,
                chars=chars,
                chapter_folder=p["folder"],
                current_id=p["id"],
                setting=setting,
                max_prev_images=0 if is_test_mode else args.max_prev,
                max_cross_images=0 if is_test_mode else args.max_cross,
            )

        try:
            ok = generate_with_gemini(client, model, full_prompt, out_path, context_imgs)
            if ok:
                ctx_note = f"  +{len(context_imgs)} ctx" if context_imgs else ""
                print(f"✅  {out_path.relative_to(SCRIPT_DIR)}{ctx_note}")
                status[p["id"]] = "ok"
                generated += 1
            else:
                print("⚠️  risposta vuota")
                status[p["id"]] = "empty"
                failed += 1
        except Exception as exc:
            print(f"❌  {exc}")
            status[p["id"]] = f"error: {exc}"
            failed += 1

        save_status(status)

        if i < len(all_prompts):
            time.sleep(args.delay)

    print(f"\n{'─' * 48}")
    print(f"✅ Generate  : {generated}")
    print(f"⏭️  Saltate   : {skipped}")
    print(f"❌ Fallite   : {failed}")
    print(f"📁 Output    : {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
