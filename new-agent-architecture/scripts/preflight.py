# -*- coding: utf-8 -*-
"""
preflight.py -- "l'editeur est-il dans l'etat attendu ?" LECTURE SEULE, aucune ecriture.

Verifie : MCP joignable, bon niveau ouvert, bornes du niveau, RAM, et fixe la BASELINE des
acteurs preexistants (ceux qu'on ne doit jamais toucher) si elle n'existe pas encore.

  python scripts/preflight.py
  python scripts/preflight.py --baseline-depuis <fichier.json>   # reprise d'une baseline relue
Code retour : 0 pret | 2 editeur injoignable | 1 ecart a traiter (voir sortie)
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.uefn.config import Projet, ecrire_json, lire_json, maintenant  # noqa: E402
from scripts.uefn.mcp_gateway import Passerelle  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projet")
    ap.add_argument("--baseline-depuis", help="JSON avec une liste 'acteurs' [{name}] ou 'noms'")
    a = ap.parse_args(argv)
    p = Projet(a.projet)
    gw = Passerelle(p, script="preflight")
    rapport = {"ts_utc": maintenant(), "projet": p.slug, "ecarts": []}

    if not gw.ping():
        print(json.dumps({"pret": False, "raison": "OFFLINE : ouvrir UEFN et activer le MCP (%s)" % gw.url}))
        return 2

    r = gw.appel("SceneTools", "get_current_level", {}, etape="niveau_courant")
    niveau = json.dumps(r.valeur, ensure_ascii=False) if r.ok else None
    rapport["niveau"] = {"rc": r.rc, "valeur": r.valeur}
    if not r.ok or p.uefn["level_package"] not in (niveau or ""):
        rapport["ecarts"].append("niveau ouvert != %s" % p.uefn["level_package"])

    r = gw.appel("ActorTools", "get_actor_bounds",
                 {"actor": {"refPath": p.level_ref(p.uefn["level_bounds_actor"])}}, etape="bornes_niveau")
    rapport["bornes_niveau"] = r.valeur
    attendu = p.uefn["bornes_attendues"]
    if not r.ok or not r.valeur:
        rapport["ecarts"].append("bornes du niveau illisibles")
    elif r.valeur["max"]["z"] < attendu["z"][1] - 1:
        rapport["ecarts"].append("Z_max=%s < %s : resize LevelBounds a refaire (gate humaine)" % (r.valeur["max"]["z"], attendu["z"][1]))

    r = gw.appel("SceneTools", "find_actors", {"name": "", "collision_channels": []}, etape="inventaire_acteurs")
    acteurs = r.valeur or []
    rapport["nb_acteurs"] = len(acteurs)
    dossier = p.pose["dossier_outliner"]
    # set_actor_folder rend rc=0 sans effet : un acteur du studio est aussi un refPath enregistre dans
    # lots/lot_NN.json (les archives .annule_* ne comptent pas), plus le PlayerStart cree par un spawner pose
    refs = set()
    for f in glob.glob(os.path.join(p.build_dir, "lots", "lot_[0-9][0-9].json")):
        refs |= {x.get("refPath") for x in lire_json(f).get("acteurs", [])}
    spawner = any("Player_Spawner" in str(r) for r in refs)
    studio = [x for x in acteurs if isinstance(x, dict) and (
        str(x.get("folderPath", "")).startswith(dossier) or x.get("actorPath") in refs
        or (spawner and str(x.get("name", "")).startswith("PlayerStartCreative_GEN_VARIABLE")))]
    rapport["acteurs_studio"] = len(studio)

    base_chemin = os.path.join(p.build_dir, "baseline_preexistants.json")
    if not os.path.exists(base_chemin):
        if a.baseline_depuis:
            src = lire_json(a.baseline_depuis)
            noms = src.get("noms") or [x["name"] for x in src["acteurs"]]
            origine = a.baseline_depuis
        elif not r.ok:
            noms, origine = None, None
            rapport["ecarts"].append("find_actors en erreur : baseline impossible")
        else:
            noms = [x.get("name") for x in acteurs if isinstance(x, dict) and x not in studio]
            origine = r.preuve
            rapport["avertissement"] = ("baseline prise sur l'etat ACTUEL : tout acteur non studio deja present "
                                        "sera considere preexistant. Si un ancien run a pose des acteurs hors "
                                        "dossier, fournir --baseline-depuis.")
        if noms is not None:
            ecrire_json(base_chemin, {"ts_utc": maintenant(), "origine": origine, "noms": sorted(noms)})
    base = lire_json(base_chemin) if os.path.exists(base_chemin) else {"noms": []}
    presents = {x.get("name") for x in acteurs if isinstance(x, dict)}
    manquants = sorted(set(base["noms"]) - presents)
    hors = [x.get("name") for x in acteurs if isinstance(x, dict)
            and x.get("name") not in set(base["noms"]) and x not in studio]
    rapport["baseline"] = {"nb": len(base["noms"]), "manquants": manquants, "acteurs_hors_baseline_hors_studio": len(hors)}
    if manquants:
        rapport["ecarts"].append("%d preexistant(s) disparu(s)" % len(manquants))
    if hors:
        rapport["ecarts"].append("%d acteur(s) ni preexistants ni rangés dans %s (ancien run ?) -> rollback.py --hors-baseline"
                                 % (len(hors), dossier))

    rapport["ram"] = gw.jauge.mesurer(forcer=True)
    if rapport["ram"].get("statut") != "OK":
        rapport["ecarts"].append("jauge RAM %s" % rapport["ram"].get("statut"))

    rapport["pret"] = not rapport["ecarts"]
    ecrire_json(os.path.join(p.build_dir, "preflight.json"), rapport)
    print(json.dumps({k: rapport[k] for k in ("pret", "ecarts", "nb_acteurs", "acteurs_studio", "baseline")},
                     ensure_ascii=False, indent=1))
    return 0 if rapport["pret"] else 1


if __name__ == "__main__":
    sys.exit(main())
