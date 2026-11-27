/**
 * Cloudflare Worker — riceve le proposte dal sito (anche da chi non ha GitHub)
 * e le trasforma in un'issue "proposta" con lo stesso formato dell'Issue Form.
 *
 * Secrets/vars (wrangler):
 *   GITHUB_TOKEN      fine-grained PAT con permesso Issues: Read & Write sul solo repo
 *   GITHUB_REPO       es. "simonediroma/le-avventure-de-el-chucharon"
 *   ALLOWED_ORIGIN    origini ammesse separate da virgola, es. "https://elchucharon.com,https://www.elchucharon.com"
 *   TURNSTILE_SECRET  (facoltativo) secret Cloudflare Turnstile anti-spam
 *
 * Nota: l'evento creato con un PAT attiva regolarmente il workflow di validazione.
 */
const FIELDS = {
  nome_bambino: ["Nome del bambino o della bambina", 40, true],
  eta: ["Età", 30, true],
  aspetto: ["Com'è fatto/a (aspetto e vestiti)", 500, false],
  pain_point: ["Il problema da risolvere (pain point)", 800, true],
  gancio_messico: ["Il gancio con il Messico", 500, true],
  genitori: ["Chi accompagna il bambino", 30, true],
  comicita_genitori: ["La scena comica dei genitori", 800, true],
  ambientazione: ["Dove si svolge la scena", 120, true],
  soluzione: ["Come lo aiuta El Chucharito (facoltativo)", 500, false],
  autore: ["Firma dell'autore della proposta", 60, false],
};
const PARENTS = ["Mamma e papà", "Solo mamma", "Solo papà"];

export default {
  async fetch(req, env) {
    const allowed = (env.ALLOWED_ORIGIN || "").split(",").map((o) => o.trim()).filter(Boolean);
    const origin = req.headers.get("Origin") || "";
    if (allowed.length && origin && !allowed.includes(origin)) {
      return new Response("Origine non ammessa", { status: 403 });
    }
    const cors = {
      "Access-Control-Allow-Origin": allowed.length ? (origin || allowed[0]) : "*",
      Vary: "Origin",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    const json = (body, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "POST") return json({ error: "Metodo non consentito" }, 405);

    let data;
    try { data = await req.json(); } catch { return json({ error: "JSON non valido" }, 400); }

    if (env.TURNSTILE_SECRET) {
      const form = new FormData();
      form.append("secret", env.TURNSTILE_SECRET);
      form.append("response", String(data.turnstile || ""));
      form.append("remoteip", req.headers.get("CF-Connecting-IP") || "");
      const v = await (await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: form })).json();
      if (!v.success) return json({ error: "Verifica anti-spam fallita" }, 403);
    }

    const clean = {};
    for (const [key, [, max, required]] of Object.entries(FIELDS)) {
      // niente markdown attivo: rimuove intestazioni "###" e menzioni @ che altererebbero il parsing
      const v = String(data[key] ?? "").replace(/^#+\s*/gm, "").replace(/@/g, "@​").trim().slice(0, max);
      if (required && !v) return json({ error: `Campo obbligatorio mancante: ${FIELDS[key][0]}` }, 400);
      clean[key] = v;
    }
    if (!PARENTS.includes(clean.genitori)) return json({ error: "Valore 'genitori' non valido" }, 400);

    const body = Object.entries(FIELDS)
      .map(([k, [title]]) => `### ${title}\n\n${clean[k] || "_No response_"}`)
      .join("\n\n") + "\n\n### Consenso\n\n- [X] Accettati i termini per le proposte (LICENSE-CONTENT.md) dal form del sito";

    const gh = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/issues`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "chucharon-proposals-worker",
      },
      body: JSON.stringify({ title: `Proposta: ${clean.nome_bambino}`, body, labels: ["proposta"] }),
    });
    if (!gh.ok) return json({ error: "Impossibile registrare la proposta, riprova più tardi" }, 502);
    const issue = await gh.json();
    return json({ ok: true, url: issue.html_url, number: issue.number });
  },
};
