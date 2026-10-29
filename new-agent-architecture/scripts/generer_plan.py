# -*- coding: utf-8 -*-
"""
generer_plan.py -- produit TOUT le plan d'une map a partir de quelques parametres, puis le
verifie (check_plan) et calcule les cameras. Zero coordonnee ecrite par un modele.

  python scripts/generer_plan.py --params '{"taille_uu": 10000, "couverts_par_moitie": 8}'
  python scripts/generer_plan.py --type parkour --params '{"plateformes": 40}'
  python scripts/generer_plan.py --liste            # generateurs et parametres disponibles

Le type par defaut est celui du profil du projet (config/profils/<profil>.json -> generateur).
Ecrase placements.json : refuse si le plan existe deja et que des lots sont poses (--forcer).
"""
import argparse
import glob
import importlib
import json
import os
import subprocess
import sys

STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, STUDIO)
from scripts.uefn.config import Projet  # noqa: E402
from scripts.generateurs.commun import Plan  # noqa: E402


def generateurs():
    return sorted(os.path.basename(f)[:-3] for f in glob.glob(os.path.join(STUDIO, "scripts", "generateurs", "*.py"))
                  if not os.path.basename(f).startswith(("_", "commun")))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projet")
    ap.add_argument("--type")
    ap.add_argument("--params", default="{}")
    ap.add_argument("--liste", action="store_true")
    ap.add_argument("--forcer", action="store_true")
    a = ap.parse_args(argv)
    if a.liste:
        print(json.dumps({g: importlib.import_module("scripts.generateurs." + g).DEFAUTS for g in generateurs()},
                         ensure_ascii=False, indent=1))
        return 0
    p = Projet(a.projet)
    typ = a.type or p.cfg.get("generateur")
    if typ not in generateurs():
        print("REFUS : generateur '%s' inconnu (disponibles : %s)" % (typ, generateurs()))
        return 4
    lots = glob.glob(os.path.join(p.build_dir, "lots", "lot_*.json"))
    if lots and not a.forcer:
        print("REFUS : %d lot(s) deja poses ; rollback d'abord ou --forcer (decision humaine)" % len(lots))
        return 4
    mod = importlib.import_module("scripts.generateurs." + typ)
    params = dict(mod.DEFAUTS, **json.loads(a.params))
    inconnus = set(json.loads(a.params)) - set(mod.DEFAUTS)
    if inconnus:
        print("REFUS : parametres inconnus %s (attendus : %s)" % (sorted(inconnus), sorted(mod.DEFAUTS)))
        return 4
    plan = Plan(p.slug, p.uefn["bornes_attendues"], graine=params.get("graine", 1))
    if "profil_validation" in mod.generer.__code__.co_varnames:
        mod.generer(plan, params, p.validation)
    else:
        mod.generer(plan, params)
    n = plan.ecrire(os.path.dirname(p.chemin("placements")), "generateurs/%s.py" % typ, params)

    env = dict(os.environ, STUDIO_PROJET=p.slug, PYTHONIOENCODING="utf-8")
    run = lambda *c: subprocess.run([sys.executable, *c], cwd=STUDIO, capture_output=True, text=True,  # noqa: E731
                                    encoding="utf-8", env=env)
    run("scripts/pose_lot.py", "plan", "--refaire")
    ck = run("scripts/check_plan.py")
    run("scripts/gen_cameras.py", "--forcer")
    verdicts = {}
    try:
        txt = ck.stdout[:ck.stdout.rfind("}") + 1]
        verdicts = {k: "%s (%d)" % (v["verdict"], v["violations"]) for k, v in json.loads(txt).items()}
    except ValueError:
        verdicts = {"erreur": ck.stdout[-300:] + ck.stderr[-300:]}
    print(json.dumps({"generateur": typ, "items": n, "verification_plan": verdicts,
                      "suite": "python scripts/pose_lot.py simuler 1" if ck.returncode == 0
                      else "corriger les parametres ou le generateur (check_plan --detail)"},
                     ensure_ascii=False, indent=1))
    return ck.returncode


if __name__ == "__main__":
    sys.exit(main())
