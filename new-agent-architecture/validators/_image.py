# -*- coding: utf-8 -*-
"""Mesures d'image deterministes (PIL seul). FICHIER PROTEGE.
Sert a refuser les captures inexploitables (mur en gros plan, image uniforme) et a verifier
les criteres mesurables du BRIEF du projet (luminosite, couleurs dominantes). Aucun style
n'est code ici : les couleurs a chercher viennent de la configuration du projet.
Le jugement esthetique reste a la critique visuelle (LLM-as-a-Judge, WP4 p.23)."""
import colorsys

from PIL import Image, ImageFilter, ImageStat

TAILLE = (320, 180)
TOLERANCE_TEINTE_DEG = 20
SAT_MIN, VAL_MIN = 110, 90  # pixel "colore" (0-255) : ni gris, ni noir


def teinte_hex(hexa):
    h = hexa.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360


def _ecart(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def mesurer(chemin_png, couleurs=()):
    """couleurs : liste de hex ('#22E6FF'). Retourne la fraction de pixels proches de chacune."""
    im = Image.open(chemin_png).convert("RGB")
    im.thumbnail(TAILLE)
    gris = im.convert("L")
    st = ImageStat.Stat(gris)
    bords = ImageStat.Stat(gris.filter(ImageFilter.FIND_EDGES)).mean[0]
    cibles = {c.upper(): teinte_hex(c) for c in couleurs}
    comptes = {c: 0 for c in cibles}
    n = sature = 0
    for h, s, v in im.convert("HSV").getdata():
        n += 1
        if s < SAT_MIN or v < VAL_MIN:
            continue
        sature += 1
        deg = h * 360 / 255
        for c, t in cibles.items():
            if _ecart(deg, t) <= TOLERANCE_TEINTE_DEG:
                comptes[c] += 1
    return {"luminance_moy": round(st.mean[0], 2), "contraste_std": round(st.stddev[0], 2),
            "densite_bords": round(bords, 2), "frac_saturee": round(sature / n, 4),
            "couleurs": {c: round(k / n, 4) for c, k in comptes.items()}}
