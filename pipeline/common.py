"""Utility condivise della pipeline del libro collaborativo."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "book" / "registry.json"
MODEL = "claude-opus-5-5"

# Campi del form (Issue Form GitHub e worker usano gli stessi titoli ###)
FIELDS = {
    "nome_bambino": "Nome del bambino o della bambina",
    "eta": "Età",
    "aspetto": "Com'è fatto/a (aspetto e vestiti)",
    "pain_point": "Il problema da risolvere (pain point)",
    "gancio_messico": "Il gancio con il Messico",
    "genitori": "Chi accompagna il bambino",
    "comicita_genitori": "La scena comica dei genitori",
    "ambientazione": "Dove si svolge la scena",
    "soluzione": "Come lo aiuta El Chucharito (facoltativo)",
    "autore": "Firma dell'autore della proposta",
}


def load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def save_registry(reg: dict) -> None:
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "bambino"


def parse_issue_body(body: str) -> dict:
    """Converte il body di un Issue Form (### Titolo\\n\\nvalore) in dict con chiavi FIELDS."""
    by_title = {}
    for block in re.split(r"^### ", body or "", flags=re.M)[1:]:
        title, _, value = block.partition("\n")
        value = value.strip()
        by_title[title.strip()] = "" if value == "_No response_" else value
    return {key: by_title.get(title, "") for key, title in FIELDS.items()}


def book_context(max_chars: int = 60_000) -> str:
    """Contesto canonico: config, Chucharon, capitoli esistenti (esempi di stile e struttura)."""
    parts = [
        "## book.config.json\n" + (ROOT / "book.config.json").read_text(encoding="utf-8"),
        "## Personaggio: Chucharon\n" + (ROOT / "characters" / "chucharon.md").read_text(encoding="utf-8"),
    ]
    for ch in load_registry()["chapters"]:
        src = ROOT / ch["source"]
        if src.exists():
            parts.append(f"## Capitolo esistente: {ch['title']} ({ch['kind']})\n" + src.read_text(encoding="utf-8"))
    return "\n\n".join(parts)[:max_chars]


def existing_children() -> list[str]:
    return [c["child"] for c in load_registry()["chapters"]]


def get_client():
    import anthropic
    return anthropic.Anthropic()


def parse_structured(system: str, user: str, schema, effort: str = "high", max_tokens: int = 32000):
    """Chiamata Claude con output strutturato (Pydantic) + fallback lato server sui rifiuti."""
    client = get_client()
    resp = client.beta.messages.parse(
        model=MODEL,
        max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": effort},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"Claude ha rifiutato la richiesta: {resp.stop_details}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Risposta troncata (max_tokens)")
    return resp.parsed_output
