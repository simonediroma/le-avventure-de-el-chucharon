# Le Avventure de El Chucharon

Libro illustrato **collaborativo** per bambini piccoli, da leggere insieme a mamma e papà.

El Chucharon è un ciuccio messicano volante che ha perso la sua bambina, Elena. Di tappa in tappa aiuta
altri bambini ad affrontare le sfide della crescita: si toglie il sombrero, diventa **El Chucharito** e
canta sulle note de *La Cucaracha*. Ogni storia lascia il bambino con un sorriso e il genitore con un
respiro di sollievo.

- 🌐 **Sito:** https://elchucharon.com: leggi i capitoli, scarica il PDF, crea la tua edizione
- 📕 **Copia cartacea:** https://www.amazon.it/dp/B0H63PYG5S

## Proponi un capitolo
Chiunque può proporre una nuova avventura dal sito, **senza account**. Ogni capitolo ha 4 ingredienti:

1. un **protagonista con un nome** (da 0 a 18 anni);
2. un **gancio con il Messico** detto da un genitore, che fa arrivare El Chucharon;
3. un **problema** (pain point) che El Chucharito risolve;
4. i **genitori** (o solo mamma, o solo papà) che rendono la scena comica.

La proposta viene validata automaticamente da Claude. Se è approvata, testo e illustrazioni vengono
prodotti nello stesso stile del libro, rivisti a mano e pubblicati sul sito.

## Come funziona
| Fase | Dove |
|---|---|
| Proposta | `site/` (form) → `worker/` (Cloudflare) → issue GitHub con etichetta `proposta` |
| Validazione | `.github/workflows/valida-proposta.yml` → `pipeline/validate_proposal.py` |
| Produzione | etichetta `produci` → `pipeline/generate_chapter.py` (Claude, testo) + `edizione-2/tools/genera_capitolo_gemini.py` (Gemini, illustrazioni) → pull request |
| Correzioni | workflow **Rigenera illustrazioni** (branch, capitolo, immagini, nota) |
| Pubblicazione | merge su `master` → `pipeline/publish.py` (`edizione-2/impagina.py`) → GitHub Pages |

Il riferimento per testo, stile e impaginazione è la **2ª edizione** (`edizione-2/`): `testo.md`, `pagine.json`,
`impagina.py`. Ogni nuovo capitolo segue la stessa scaletta di 10 pagine (copertina con il nome, pagina da colorare,
illustrazioni a tutta pagina, pagine di testo su cornice a tema) e viene inserito prima dell'epilogo.
Metadati per il sito: `book/registry.json`. Architettura e setup: [`docs/EVOLUTIVA.md`](docs/EVOLUTIVA.md).

Anteprima locale:
```bash
pip install -r pipeline/requirements.txt
python edizione-2/tools/estrai_stampa.py   # una volta: illustrazioni 300 DPI dai PDF Canva (poppler-utils)
python pipeline/publish.py && cd site && python -m http.server
```

## Licenze
- **Testi, personaggi e illustrazioni:** © 2026 Simone Razzano, distribuiti al pubblico con licenza
  [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.it). Uso commerciale solo con autorizzazione.
  Dettagli e **termini per chi propone un capitolo**: [`LICENSE-CONTENT.md`](LICENSE-CONTENT.md).
- **Codice** (pipeline, sito, worker, workflow): [MIT](LICENSE).
