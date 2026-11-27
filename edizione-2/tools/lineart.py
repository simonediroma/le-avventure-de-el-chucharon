#!/usr/bin/env python3
"""Converte un'illustrazione a colori in una pagina da colorare (line art B/N).
Uso: python lineart.py input.png output.png [--colors 14] [--min-area 120]
"""
import argparse, cv2, numpy as np

def lineart(src, k=10, min_area=350, width=2400, contrast=28.0):
    img = cv2.imread(src)
    h, w = img.shape[:2]
    s = width / max(h, w)
    img = cv2.resize(img, (int(w*s), int(h*s)), interpolation=cv2.INTER_CUBIC)
    # 1. appiattisce le pennellate dell'acquerello
    flat = cv2.pyrMeanShiftFiltering(img, 18, 36)
    flat = cv2.bilateralFilter(flat, 9, 60, 60)
    # 2. quantizza in k colori (spazio Lab)
    lab = cv2.cvtColor(flat, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    _, lbl, ctr = cv2.kmeans(lab, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 3, cv2.KMEANS_PP_CENTERS)
    lbl = lbl.reshape(flat.shape[:2]).astype(np.uint8)
    lbl = cv2.medianBlur(lbl, 11)
    # 3. confini tra regioni = linee, solo se i due colori sono davvero diversi
    #    (evita le linee sulle sfumature d'ombra dell'acquerello)
    far = np.linalg.norm(ctr[:, None, :] - ctr[None, :, :], axis=2) > contrast
    edges = np.zeros(lbl.shape, np.uint8)
    edges[:, 1:] |= far[lbl[:, 1:], lbl[:, :-1]]
    edges[1:, :] |= far[lbl[1:, :], lbl[:-1, :]]
    # 4. contorni scuri originali del disegno
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dark = cv2.adaptiveThreshold(cv2.GaussianBlur(gray, (5, 5), 0), 1, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 30)
    lines = ((edges | dark) * 255).astype(np.uint8)
    # 5. pulizia: rimuove frammenti piccoli
    n, cc, stats, _ = cv2.connectedComponentsWithStats(lines, 8)
    keep = np.zeros(n, bool); keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_area
    lines = (keep[cc] * 255).astype(np.uint8)
    lines = cv2.dilate(lines, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    lines = cv2.GaussianBlur(lines, (3, 3), 0)  # antialias
    return 255 - lines

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--colors", type=int, default=10)
    ap.add_argument("--min-area", type=int, default=350)
    ap.add_argument("--contrast", type=float, default=28.0)
    a = ap.parse_args()
    cv2.imwrite(a.dst, lineart(a.src, a.colors, a.min_area, contrast=a.contrast))
