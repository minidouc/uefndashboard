# -*- coding: utf-8 -*-
"""
rollback.py -- retire UNIQUEMENT ce que le studio a pose. Jamais un acteur preexistant.

  python scripts/rollback.py --lot 3 --dry-run       # liste ce qui serait retire
  python scripts/rollback.py --lot 3                 # retire le dossier CP_Studio/lot_03
        # + les refPath enregistres dans lots/lot_03.json (set_actor_folder peut etre sans effet)
  python scripts/rollback.py --hors-baseline --dry-run
        # nettoyage d'un ANCIEN run (acteurs poses hors dossier) : retire tout acteur absent
        # de la baseline des preexistants. A utiliser une fois, apres verification du dry-run.

Permission "ask" : l'humain approuve chaque execution reelle.
Apres retrait : save -> find_actors -> verification que la baseline est intacte.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.uefn.config import Projet, ecrire_json, lire_json, maintenant  # noqa: E402
from scripts.uefn.mcp_gateway import Passerelle  # noqa: E402

PROTEGES = {"LevelBounds_0", "FortWorldSettings", "Brush_0", "WorldDataLayers", "WorldPartitionMiniMap"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projet")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--lot", type=int)
    g.add_argument("--hors-baseline", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    p = Projet(a.projet)
    base_chemin = os.path.join(p.build_dir, "baseline_preexistants.json")
    if not os.path.exists(base_chemin):
        print("REFUS : baseline absente, lancer preflight.py d'abord")
        return 4
    baseline = set(lire_json(base_chemin)["noms"]) | PROTEGES
    gw = Passerelle(p, ecriture=not a.dry_run, script="rollback")
    if not gw.ping():
        print("ARRET : editeur injoignable")
        return 2

    r = gw.appel("SceneTools", "find_actors", {"name": "", "collision_channels": []}, etape="avant")
    if not r.ok:
        print("ARRET : find_actors en erreur, rien retire")
        return 1
    acteurs = [x for x in r.valeur or [] if isinstance(x, dict)]
    lot_f = os.path.join(p.build_dir, "lots", "lot_%02d.json" % a.lot) if a.lot else None
    if a.lot:
        dossier = "%s/lot_%02d" % (p.pose["dossier_outliner"], a.lot)
        # set_actor_folder rend rc=0 sans effet : on cible aussi les refPath enregistres a la pose
        refs = {x.get("refPath") for x in lire_json(lot_f).get("acteurs", [])} if os.path.exists(lot_f) else set()
        cibles = [x for x in acteurs if str(x.get("folderPath", "")).startswith(dossier)
                  or x.get("actorPath") in refs]
    else:
        cibles = [x for x in acteurs if x.get("name") not in baseline]
    cibles = [x for x in cibles if x.get("name") not in baseline]  # double garde-fou
    print(json.dumps({"a_retirer": len(cibles), "exemples": [x.get("label") or x.get("name") for x in cibles[:10]],
                      "baseline_protegee": len(baseline)}, ensure_ascii=False))
    if a.dry_run:
        return 0
    if not cibles:
        # rien du lot n'est dans l'editeur (relu) : le lot peut etre archive
        if lot_f and os.path.exists(lot_f):
            os.replace(lot_f, "%s.annule_%s" % (lot_f, gw.run_id))  # hors du glob lot_*.json des validateurs
        return 0

    for x in cibles:
        rr = gw.appel("SceneTools", "remove_from_scene", {"actor": {"refPath": x["actorPath"]}},
                      ecriture=True, etape="retrait_%s" % x.get("name"))
        if not rr.ok and "not valid Actor" not in str(rr.erreur):
            print("ARRET au premier echec : %s (%s)" % (x.get("name"), rr.erreur))
            return 1
        # "not valid Actor" : deja retire avec son parent (PlayerStart d'un spawner) ; verifie par la relecture
    rs = gw.appel("AssetTools", "save_assets", {"asset_paths": [p.uefn["level_package"]]}, ecriture=True, etape="save")
    ra = gw.appel("SceneTools", "find_actors", {"name": "", "collision_channels": []}, etape="apres")
    presents = {x.get("name") for x in ra.valeur or [] if isinstance(x, dict)}
    manquants = sorted(set(lire_json(base_chemin)["noms"]) - presents)
    encore_la = sorted(x.get("name") for x in cibles if x.get("name") in presents)
    bilan = {"ts_utc": maintenant(), "retires": len(cibles) - len(encore_la), "save_rc": rs.rc,
             "preexistants_manquants": manquants, "cibles_encore_presentes": encore_la, "restants": len(presents)}
    if lot_f and os.path.exists(lot_f) and ra.ok and not encore_la:
        os.replace(lot_f, "%s.annule_%s" % (lot_f, gw.run_id))  # hors du glob lot_*.json des validateurs
    ecrire_json(os.path.join(gw.dir_run, "bilan_rollback.json"), bilan)
    print(json.dumps(bilan, ensure_ascii=False))
    return 0 if rs.ok and ra.ok and not manquants and not encore_la else 1


if __name__ == "__main__":
    sys.exit(main())
