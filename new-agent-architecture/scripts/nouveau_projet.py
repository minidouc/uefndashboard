# -*- coding: utf-8 -*-
"""
nouveau_projet.py -- cree un projet complet en une commande (config, dossiers, etat).

  python scripts/nouveau_projet.py arene-neon --profil arene \
      --root "C:/Users/douco/Documents/Qoder/arene-neon" \
      --content-root /<guid-du-projet-uefn> --niveau MonNiveau

--content-root et --niveau se lisent dans UEFN (ou dans un message d'erreur du MCP, comme pour
corpo-plaza). Sans eux, le projet est cree mais l'ecriture dans l'editeur reste impossible
(preflight le signalera) : on peut deja concevoir et generer le plan.
"""
import argparse
import json
import os
import subprocess
import sys

STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, STUDIO)
from scripts.uefn.config import CONFIG_DIR, ecrire_json  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--profil", required=True,
                    choices=sorted(f[:-5] for f in os.listdir(os.path.join(CONFIG_DIR, "profils"))))
    ap.add_argument("--root", required=True)
    ap.add_argument("--content-root", default="UNKNOWN")
    ap.add_argument("--niveau", default="UNKNOWN")
    ap.add_argument("--bornes", default='{"x": [-12800, 12800], "y": [-12800, 12800], "z": [-256, 9000]}')
    ap.add_argument("--activer", action="store_true", help="en faire le projet actif de studio.json (humain)")
    a = ap.parse_args(argv)
    chemin = os.path.join(CONFIG_DIR, "projects", "%s.json" % a.slug)
    if os.path.exists(chemin):
        print("REFUS : le projet %s existe deja" % a.slug)
        return 4
    pkg = "%s/%s" % (a.content_root, a.niveau)
    cfg = {"$schema": "studio.project.v2", "slug": a.slug, "profil": a.profil, "root": a.root.replace("\\", "/"),
           "mcp_url": "http://127.0.0.1:8000/mcp",
           "uefn": {"content_root": a.content_root, "level_package": pkg,
                    "level_ref_prefix": "%s.%s:PersistentLevel." % (pkg, a.niveau),
                    "level_bounds_actor": "LevelBounds_0", "bornes_attendues": json.loads(a.bornes),
                    "import_folder": "%s/%s" % (a.content_root, a.slug)},
           "chemins": {"placements": "design/level/placements.json", "placements_supplementaires": [],
                       "overlaps_autorises": "design/level/overlaps_autorises.json",
                       "exceptions_flottants": "design/level/exceptions_flottants.json",
                       "cameras": "design/level/cameras.json", "build_dir": "build/studio", "state_dir": "state"}}
    ecrire_json(chemin, cfg)
    for d in ("brief", "design/level", "build/studio", "state", "qa", "tech/verse", "handoff"):
        os.makedirs(os.path.join(a.root, d), exist_ok=True)
    env = dict(os.environ, STUDIO_PROJET=a.slug)
    subprocess.run([sys.executable, "scripts/state.py", "init", "--phase", "CADRAGE"], cwd=STUDIO, env=env,
                   capture_output=True)
    print(json.dumps({"projet": a.slug, "profil": a.profil, "config": chemin, "racine": a.root,
                      "editeur": "a renseigner (content-root/niveau)" if "UNKNOWN" in pkg else pkg,
                      "suite": ["brief (directeur-creatif) -> gate brief",
                                "python scripts/generer_plan.py --params '{...}' (STUDIO_PROJET=%s)" % a.slug,
                                "gates gdd/archi/ecriture_uefn -> phase BUILD -> build_complet.py"]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
