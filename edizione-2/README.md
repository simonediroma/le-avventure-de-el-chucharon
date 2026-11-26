# 2ª edizione — impaginazione senza Canva

```bash
pip install reportlab pillow opencv-python-headless
python impagina.py            # → output/chucharon-2a-edizione.pdf (pronto per KDP)
python impagina.py --guide    # con linee di rifilo (rosso) e margine di sicurezza (blu)
python impagina.py --solo cap3
```

- `testo.md` — testo corretto, unica fonte: modifica qui e rilancia lo script.
- `pagine.json` — ordine pagine, immagine e posizione (pt, origine in alto a sinistra).
- `assets/capN/` — immagini estratte dal PDF della 1ª edizione (Canva).
- `assets/da-colorare/` — copertine dei capitoli in bianco e nero, generate con
  `tools/lineart.py` (OpenCV, nessuna AI).
- Formato: 8,75" × 8,75" = rifilo 8,5" quadrato con abbondanza, come la 1ª edizione.
- Font: Open Sans (al posto di Canva Sans, non distribuibile) + DejaVu Sans per ♪.

## Modifiche rispetto alla 1ª edizione
1. Refusi, punteggiatura e spagnolo corretti (vedi `git diff` storico o CHANGELOG in chat).
2. Nome uniformato: sempre **El Chucharon** (trasformato: **El Chucharito**).
3. Pagina 2 dei capitoli Leo, Sofia, Marco, Elena: la vecchia illustrazione da colorare
   è sostituita dalla versione in bianco e nero della copertina del capitolo.
4. Continuità: nel finale "quella prima *mattina* al parco" → "prima *sera*" (il prologo è al tramonto).
