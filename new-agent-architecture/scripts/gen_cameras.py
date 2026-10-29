# -*- coding: utf-8 -*-
"""
gen_cameras.py -- calcule les cameras de preuve a partir du plan (aucun modele necessaire).

Pour chaque capture requise par le projet (config visuel.captures) :
  - nom = une zone du plan (ex. 'S0')         -> cadre cette zone ;
  - nom = 'nuit_<zone>' ou 'nuit_ensemble'     -> meme cadrage, prise apres le dernier lot ;
  - nom = 'ensemble'                           -> vue d'ensemble en hauteur ;
  - autre nom                                  -> laisse au level designer (signale).
Camera en diagonale, en hauteur, visee calculee vers le centre de la zone, bornee au niveau.
'apres_lot' = dernier lot du plan qui contient la zone (pour build_complet.py).

  python scripts/gen_cameras.py            # complete cameras.json sans ecraser l'existant
  python scripts/gen_cameras.py --forcer   # recalcule tout
"""
import argparse
import json
import math
import os
import sys

STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, STUDIO)
from scripts.uefn.config import Projet, ecrire_json, lire_json  # noqa: E402
from scripts.pose_lot import charger_items  # noqa: E402


def boite(items):
    mn = [math.inf] * 3
    mx = [-math.inf] * 3
    for it in items:
        d = it.get("dimensions_uu") or {}
        demi = [d.get("X", 100) / 2, d.get("Y", 100) / 2, d.get("Z", 100) / 2]
        for k in range(3):
            mn[k] = min(mn[k], it["position"][k] - demi[k])
            mx[k] = max(mx[k], it["position"][k] + demi[k])
    return mn, mx


def camera(mn, mx, bornes, intention, hauteur=0.45, recul=0.75, plafond=None):
    """Recul et hauteur proportionnels a la zone, plafonnes (`plafond` uu) pour rester lisible :
    une zone immense ne doit pas donner une vue satellite."""
    c = [(a + b) / 2 for a, b in zip(mn, mx)]
    w = max(mx[0] - mn[0], mx[1] - mn[1], 800)
    r, h = recul * w, hauteur * w
    if plafond:
        r, h = min(r, plafond), min(h, plafond * 0.4)
    pos = [c[0] - r, c[1] - r * 0.6, mx[2] + h]
    for k, axe in enumerate("xyz"):
        pos[k] = min(max(pos[k], bornes[axe][0] + 100), bornes[axe][1] - 100)
    dx, dy, dz = c[0] - pos[0], c[1] - pos[1], c[2] - pos[2]
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return {"location": {"x": round(pos[0]), "y": round(pos[1]), "z": round(pos[2])},
            "rotation": {"pitch": round(pitch, 1), "yaw": round(yaw, 1), "roll": 0.0},
            "intention": intention, "genere_par": "gen_cameras.py"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projet")
    ap.add_argument("--forcer", action="store_true")
    a = ap.parse_args(argv)
    p = Projet(a.projet)
    exclus = set(p.pose.get("categories_en_dernier", []))
    pre = tuple(x.upper() for x in p.pose.get("prefixes_en_dernier", []))
    items = [i for i in charger_items(p) if i.get("categorie") not in exclus
             and not (pre and i["id"].upper().startswith(pre))]
    zones = {}
    for it in items:
        zones.setdefault(it.get("strate"), []).append(it)
    plan_lots = os.path.join(p.build_dir, "lot_plan.json")
    lots = lire_json(plan_lots)["lots"] if os.path.exists(plan_lots) else {}
    dernier_lot = sorted(lots)[-1] if lots else None

    def apres(zone):
        ids = {i["id"] for i in zones.get(zone, [])}
        dans = [l for l, contenu in sorted(lots.items()) if ids & set(contenu)]
        return dans[-1] if dans else None

    chemin = p.chemin("cameras")
    doc = lire_json(chemin) if os.path.exists(chemin) and not a.forcer else {"cameras": {}}
    bornes = p.uefn["bornes_attendues"]
    ajoutees, a_definir = [], []
    for nom in p.cfg["visuel"]["captures"]:
        if nom in doc["cameras"]:
            continue
        base = nom[5:] if nom.startswith("nuit_") else nom
        if base == "ensemble":
            mn, mx = boite(items)
            cam = camera(mn, mx, bornes, "vue d'ensemble : echelle, verticalite, silhouette", hauteur=0.6, recul=0.6)
        elif base in zones:
            # cadrer ce qu'on parcourt (sols, connecteurs, points d'interet), pas les tours qui
            # traversent toutes les zones
            prat = set(p.validation.get("categories_praticables", [])) | {"poi"}
            cible = [i for i in zones[base] if i.get("categorie") in prat] or zones[base]
            mn, mx = boite(cible)
            cam = camera(mn, mx, bornes, "zone %s : surfaces praticables et decor de la zone" % base,
                         hauteur=0.3, recul=0.5, plafond=4000)
        else:
            a_definir.append(nom)
            continue
        cam["apres_lot"] = dernier_lot if (nom.startswith("nuit_") or base == "ensemble") else apres(base)
        doc["cameras"][nom] = cam
        ajoutees.append(nom)
    ecrire_json(chemin, doc)
    print(json.dumps({"ajoutees": ajoutees, "a_definir_par_level_designer": a_definir,
                      "fichier": chemin}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
