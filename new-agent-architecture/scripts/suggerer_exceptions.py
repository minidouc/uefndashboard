# -*- coding: utf-8 -*-
"""
suggerer_exceptions.py -- trie automatiquement les chevauchements et flottants du PLAN.
Remplace des heures de lecture par un agent : le modele (ou l'humain) ne fait que relire
la proposition.

Categories automatiques (chacune avec sa justification) :
  - volume d'environnement : ciel, eclairage global, post-process (non collisionnant) ;
  - revetement : item fin (Z <= 20 uu dans le plan) pose sur une surface (decal, flaque, marquage) ;
  - fixe sur structure : signalisation ou decor accroche a un mur ou une tour ;
  - A CORRIGER : tout le reste -> mission au level designer.

  python scripts/suggerer_exceptions.py
  -> design/level/overlaps_autorises.PROPOSITION.json + exceptions_flottants.PROPOSITION.json
Les validateurs n'utilisent QUE les fichiers sans '.PROPOSITION' : un humain ou le level
designer renomme apres relecture. Jamais d'acceptation automatique.
"""
import argparse
import json
import os
import re
import sys

STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, STUDIO)
from scripts.uefn.config import Projet, ecrire_json  # noqa: E402
from scripts.check_plan import ContextePlan  # noqa: E402
from validators import regles  # noqa: E402

DEVICES_ENV = ("Skydome", "PostProcess", "Light_Rig", "Fog", "Atmosphere")
FIXES = {"signalisation", "decor"}
SUPPORTS_STRUCTURE = {"structure", "plancher", "silhouette", "connecteur"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projet")
    a = ap.parse_args(argv)
    p = Projet(a.projet)
    ctx = ContextePlan(p)
    pl = ctx.placements()
    pre = tuple(x.upper() for x in p.pose.get("prefixes_en_dernier", []))
    env_cat = set(p.pose.get("categories_en_dernier", []))

    def est_env(i):
        it = pl[i]
        return it.get("categorie") in env_cat or (pre and i.upper().startswith(pre)) or \
            any(d in str(it.get("support", "")) for d in DEVICES_ENV)

    def est_fin(i):
        return (pl[i].get("dimensions_uu") or {}).get("Z", 999) <= 20

    sauve = ctx.overlaps_path
    ctx.overlaps_path = None  # on veut TOUS les chevauchements bruts
    v = regles.v_zero_overlap(ctx)
    ctx.overlaps_path = sauve
    env, regles_out, a_corriger, vus = set(), [], [], set()
    for x in v.violations:
        m = re.match(r"chevauchement (\S+) / (\S+)", x["detail"])
        if not m:
            continue
        i, j = m.groups()
        if (i, j) in vus or (j, i) in vus:
            continue
        vus.add((i, j))
        if est_env(i) or est_env(j):
            env.add(i if est_env(i) else j)
            continue
        ci, cj = pl[i].get("categorie"), pl[j].get("categorie")
        if est_fin(i) or est_fin(j):
            fin, support = (i, j) if est_fin(i) else (j, i)
            regles_out.append({"a": fin, "b": support, "justification": "revetement fin pose sur %s" % support})
        elif (ci in FIXES and cj in SUPPORTS_STRUCTURE) or (cj in FIXES and ci in SUPPORTS_STRUCTURE):
            regles_out.append({"a": i, "b": j, "justification": "%s fixe sur la structure (contact voulu)" % (i if ci in FIXES else j)})
        else:
            a_corriger.append([i, j])
    for e in sorted(env):
        regles_out.insert(0, {"a": e, "b": "*", "justification": "volume d'environnement non collisionnant (%s)" % pl[e].get("support")})

    base = os.path.dirname(p.chemin("overlaps_autorises"))
    ecrire_json(os.path.join(base, "overlaps_autorises.PROPOSITION.json"),
                {"genere_par": "suggerer_exceptions.py", "a_relire": True, "autorises": regles_out,
                 "a_corriger_par_level_designer": a_corriger})
    flott = [{"motif": e, "justification": "volume d'environnement"} for e in sorted(env)] + \
            [{"motif": i, "justification": "lumiere ponctuelle suspendue"} for i, it in pl.items()
             if "PointLight" in str(it.get("support", ""))]
    ecrire_json(os.path.join(base, "exceptions_flottants.PROPOSITION.json"),
                {"genere_par": "suggerer_exceptions.py", "a_relire": True, "exceptions": flott})
    print(json.dumps({"chevauchements_bruts": len(vus), "volumes_environnement": len(env),
                      "regles_proposees": len(regles_out), "a_corriger": len(a_corriger),
                      "exemples_a_corriger": a_corriger[:8], "dossier": base}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
