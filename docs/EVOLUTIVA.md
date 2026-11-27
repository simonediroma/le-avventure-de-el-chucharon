# Libro collaborativo — architettura

```
 Sito (GitHub Pages)          Cloudflare Worker          GitHub Issues            GitHub Actions
 ┌───────────────────┐  POST  ┌────────────────┐  API   ┌──────────────┐  evento  ┌──────────────────────────┐
 │ form "Proponi"    │──────▶ │ anti-spam +    │──────▶ │ issue        │────────▶ │ valida-proposta.yml      │
 │ (o Issue Form GH) │        │ sanitizzazione │        │ "proposta"   │          │ Claude: 4 vincoli + safety│
 └───────────────────┘        └────────────────┘        └──────────────┘          │ → commento + etichetta   │
          ▲                                                    │ label "produci"   └──────────────────────────┘
          │                                                    ▼  (o AUTO_PRODUCE)
 ┌───────────────────┐  merge  ┌──────────────────┐      ┌────────────────────────────────────────────┐
 │ pubblica-sito.yml │◀─────── │ Pull request con │◀──── │ produci-capitolo.yml                       │
 │ publish.py → Pages│         │ revisione umana  │      │ Claude: testo + 5 scene (anchor visivi)    │
 └───────────────────┘         └──────────────────┘      │ Gemini: illustrazioni + auto-fix coerenza  │
                                                         │ ReportLab: anteprima PDF                   │
                                                         └────────────────────────────────────────────┘
```

## Flusso
1. **Proposta** — dal sito (worker → issue) oppure direttamente dall'Issue Form `.github/ISSUE_TEMPLATE/proposta-capitolo.yml`.
2. **Validazione automatica** (`pipeline/validate_proposal.py`) — Claude verifica: protagonista con nome, gancio Messico, pain point, genitori comici, sicurezza, originalità. Esito: `approvata` / `da-rivedere` (l'autore modifica l'issue e si rivalida da sola) / `respinta`.
3. **Produzione** (`pipeline/generate_chapter.py` + `illustrator/main.py`) — parte quando un maintainer mette l'etichetta `produci` (consigliato) o in automatico con la variabile di repo `AUTO_PRODUCE=true`. Genera `chapters/`, `scenes/C{n}-00..04.md` nello stesso formato degli altri capitoli, aggiorna `book/registry.json`, illustra con Gemini, apre una PR con anteprima PDF.
4. **Pubblicazione** — al merge su `master`, `pipeline/publish.py` crea immagini web, PDF per capitolo e `site/data/chapters.json`; deploy su GitHub Pages.
5. **PDF personalizzato** — il browser unisce `inizio.pdf` + capitoli scelti + `fine.pdf` con pdf-lib (nessun server).

`book/registry.json` è la fonte unica dell'ordine del libro: `layout.py` ora la legge (`--chapters`, `--scenes`, `--images-dir`).

## Setup (una volta)
| Cosa | Dove |
|---|---|
| `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | Settings → Secrets → Actions |
| GitHub Pages: source = GitHub Actions | Settings → Pages |
| Actions: "Allow GitHub Actions to create and approve pull requests" | Settings → Actions → General |
| (opz.) `AUTO_PRODUCE=true` | Settings → Variables → Actions |
| Worker: `cd worker && npx wrangler deploy`, poi `wrangler secret put GITHUB_TOKEN` (PAT fine-grained, solo Issues R/W su questo repo) e `TURNSTILE_SECRET` | Cloudflare |
| URL worker + Turnstile site key + link cartaceo | `site/config.js` |

Test locale: `python pipeline/publish.py && cd site && python -m http.server`.

## Dominio elchucharon.com
`site/CNAME` contiene `elchucharon.com` (dominio principale; `www` viene reindirizzato da GitHub).
DNS (pannello del registrar, proxy Cloudflare **disattivato** / "DNS only" finché GitHub non emette il certificato):

| Tipo | Nome | Valore |
|---|---|---|
| A | `@` | 185.199.108.153 |
| A | `@` | 185.199.109.153 |
| A | `@` | 185.199.110.153 |
| A | `@` | 185.199.111.153 |
| CNAME | `www` | `simonediroma.github.io` |

Poi: GitHub → Settings → Pages → Custom domain `elchucharon.com` → "Enforce HTTPS".
Consigliato: verificare il dominio in GitHub (Settings profilo → Pages → Add a domain, record TXT) contro i domain takeover.
Worker (facoltativo): rotta `api.elchucharon.com` in Cloudflare → aggiornare `proposalEndpoint` in `site/config.js`.

## Costi indicativi per capitolo
- Validazione Claude: pochi centesimi. Scrittura capitolo (effort high): ~0,30–0,80 €.
- 5 illustrazioni Gemini + auto-fix: dipende dal modello immagine (~1–3 €).
- Hosting: gratuito (Pages + Workers free tier).

## Cartaceo — opzioni da valutare
| Opzione | Personalizzazione capitoli | Spedizione | Note |
|---|---|---|---|
| **Lulu Print API** | Sì: si invia il PDF composto via API per ogni ordine | Mondo, gestita da Lulu | Ideale per "scegli i capitoli e ricevilo a casa". Serve checkout (Stripe) + webhook che chiama l'API. |
| **Gelato / Peecho** | Sì, via API | Produzione locale in IT/UE | Tempi rapidi in Europa, simile a Lulu. |
| **Amazon KDP** | No (edizione fissa) | Prime | Più semplice: pubblichi `libro-completo.pdf` come edizione standard. |

Proposta: partire con **KDP** per l'edizione fissa (link in `printUrl`) e, in fase 2, aggiungere
**Lulu/Gelato API + Stripe Checkout** in un secondo Worker: il sito invia la lista capitoli → il worker
compone il PDF (o lo riceve dal browser) → crea l'ordine di stampa dopo il pagamento.
Per la stampa servirà un PDF con abbondanza (bleed 3 mm) e copertina separata: estensione di `layout.py`.

## Note di sicurezza
- Il testo delle proposte è trattato come dato (prompt con istruzione esplicita + revisione umana in PR).
- Il body dell'issue passa ai workflow solo via variabile d'ambiente (niente injection nella shell).
- Il worker limita lunghezze, neutralizza `###` e `@menzioni`, verifica Turnstile.
- Licenze: contenuti CC BY-NC 4.0 verso il pubblico, concessione non esclusiva anche commerciale dai proponenti al titolare (`LICENSE-CONTENT.md`), codice MIT (`LICENSE`). Da validare con un legale prima della vendita.
