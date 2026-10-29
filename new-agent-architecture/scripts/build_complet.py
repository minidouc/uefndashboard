# -*- coding: utf-8 -*-
"""
build_complet.py -- TOUT le BUILD en une commande. Claude n'est rappele qu'en cas de probleme.
C'est le principal levier de vitesse et de cout : 1 tour de modele au lieu d'environ 5 par lot.

  python scripts/build_complet.py              # preflight -> check_plan -> lots -> captures -> validation
  python scripts/build_complet.py --strict     # s'arrete aussi sur un defaut geometrique
  python scripts/build_complet.py --jusqua 2   # seulement les 2 premiers lots (premier test)

Pour chaque lot non encore VALIDE : pose -> captures prevues apres ce lot -> validation.
  - defaut BLOQUANT (preuve, save, preexistants, coordonnees) : ARRET immediat ;
  - defaut geometrique (chevauchement, flottant) : note, on continue (sauf --strict) ;
  - lot PASS : enregistre VALIDE dans l'etat (provenance validator).
Sortie : un resume d'environ 15 lignes. Tout le detail est sur disque.
Prerequis : etat en phase BUILD (les gates humaines sont donc deja accordees).
"""
import argparse
import json
import os
import subprocess
import sys
import time

STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, STUDIO)
from scripts.uefn.config import Projet, lire_json  # noqa: E402
from scripts.state import Etat  # noqa: E402

BLOQUANTS = {"integrite_preuves", "persistance", "preexistants_intacts", "source_coordonnees"}


def lancer(args, projet):
    env = dict(os.environ, STUDIO_PROJET=projet, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable] + args, cwd=STUDIO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def json_final(texte):
    """Dernier objet JSON imprime par un script (les scripts finissent par un resume JSON)."""
    i = texte.find("{")
    while i >= 0:
        try:
            return json.loads(texte[i:])
        except ValueError:
            i = texte.find("{", i + 1)
    return {}


def captures_apres(p, lot_id):
    chemin = p.chemin("cameras")
    if not os.path.exists(chemin):
        return []
    return [n for n, c in lire_json(chemin)["cameras"].items() if c.get("apres_lot") == lot_id]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projet")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--jusqua", type=int)
    a = ap.parse_args(argv)
    p = Projet(a.projet)
    et = Etat(p)
    s = et.lire()
    if s["phase"] != "BUILD":
        print("REFUS : phase %s (le BUILD exige la phase BUILD et donc les gates humaines)" % s["phase"])
        return 4
    t0, journal = time.time(), []

    rc, out, err = lancer(["scripts/preflight.py"], p.slug)
    pf = json_final(out)
    if rc != 0:
        print(json.dumps({"arret": "preflight", "rc": rc, "ecarts": pf.get("ecarts") or (out or err)[-400:]},
                         ensure_ascii=False))
        return rc
    # un plan en FAIL ne se pose pas : 0 appel MCP au lieu d'un lot a retirer
    rc, out, err = lancer(["scripts/check_plan.py"], p.slug)
    if rc != 0:
        try:  # check_plan imprime une note apres son JSON
            ck = json.JSONDecoder().raw_decode(out[out.find("{"):])[0]
        except ValueError:
            ck = {}
        print(json.dumps({"arret": "check_plan", "rc": rc,
                          "defauts": {k: v.get("violations") for k, v in ck.items() if isinstance(v, dict)
                                      and v.get("verdict") == "FAIL"} or (out or err)[-400:],
                          "suite": "mission level-designer (check_plan.py --detail)"}, ensure_ascii=False))
        return rc
    if not os.path.exists(os.path.join(p.build_dir, "lot_plan.json")):
        lancer(["scripts/pose_lot.py", "plan"], p.slug)
    plan = lire_json(os.path.join(p.build_dir, "lot_plan.json"))["lots"]

    remarques = {}
    for i, lot_id in enumerate(sorted(plan), 1):
        if a.jusqua and i > a.jusqua:
            break
        if et.lire()["lots"].get(lot_id) == "VALIDE":
            continue
        if os.path.exists(os.path.join(p.build_dir, "lots", "%s.json" % lot_id)):
            print(json.dumps({"arret": lot_id, "raison": "lot deja pose mais non VALIDE : "
                              "python scripts/rollback.py --lot %d, puis relancer" % i}, ensure_ascii=False))
            return 1
        t = time.time()
        rc, out, err = lancer(["scripts/pose_lot.py", "lot", str(i)], p.slug)
        res = json_final(out)
        if rc != 0:
            et.evenement("script", "build_complet : %s %s" % (lot_id, res.get("statut")), res.get("fichier"))
            print(json.dumps({"arret": lot_id, "pose": res or (out or err)[-400:],
                              "suite": "lire 'arret', puis rollback.py --lot %d" % i}, ensure_ascii=False))
            return 1
        for nom in captures_apres(p, lot_id):
            lancer(["scripts/capture.py", "prendre", nom, "--lot", lot_id], p.slug)
        lancer(["validators/run_all.py"], p.slug)
        rap = lire_json(os.path.join(p.root, "qa", "validation", "latest.json"))
        if rap.get("integrite_validateurs") != "OK" or rap.get("auto_test_golden") != "OK":
            print(json.dumps({"arret": "validateurs", "integrite": rap.get("integrite_validateurs"),
                              "golden": rap.get("auto_test_golden")}, ensure_ascii=False))
            return 1
        du_lot = {}
        for v in rap["validateurs"]:
            n = sum(1 for x in v["violations"] if x["lot"] == lot_id)
            if n:
                du_lot[v["validateur"]] = n
        bloq = {k: n for k, n in du_lot.items() if k in BLOQUANTS}
        if bloq or (a.strict and du_lot):
            et.evenement("validator", "build_complet arrete sur %s" % lot_id, "qa/validation/latest.json")
            print(json.dumps({"arret": lot_id, "defauts": du_lot, "rapport": "qa/validation/latest.json",
                              "suite": "corriger la cause, rollback.py --lot %d, relancer" % i}, ensure_ascii=False))
            return 1
        if rap["par_lot"].get(lot_id) == "PASS":
            lancer(["scripts/state.py", "lot", "--id", lot_id, "--statut", "VALIDE"], p.slug)
        else:
            lancer(["scripts/state.py", "lot", "--id", lot_id, "--statut", "A_VALIDER"], p.slug)
            remarques[lot_id] = du_lot
        journal.append("%s %s %.0fs acteurs=%s degrades=%s" % (lot_id, rap["par_lot"].get(lot_id), time.time() - t,
                                                              res.get("acteurs"), res.get("degrades")))

    # captures restantes (celles sans 'apres_lot') puis validation finale
    cams = lire_json(p.chemin("cameras"))["cameras"] if os.path.exists(p.chemin("cameras")) else {}
    for nom, c in cams.items():
        if not c.get("apres_lot"):
            lancer(["scripts/capture.py", "prendre", nom], p.slug)
    lancer(["validators/run_all.py"], p.slug)
    rap = lire_json(os.path.join(p.root, "qa", "validation", "latest.json"))
    print(json.dumps({
        "verdict_global": rap["verdict"], "duree_min": round((time.time() - t0) / 60, 1),
        "lots": journal, "defauts_geometriques_par_lot": remarques,
        "validateurs": {v["validateur"]: v["nb_violations"] for v in rap["validateurs"] if v["nb_violations"]},
        "suite": "sous-agent critique sur build/studio/captures/ puis gate humaine DA" if rap["verdict"] == "PASS"
                 else "lire qa/validation/latest.json (Grep cible) et traiter le premier validateur en FAIL",
    }, ensure_ascii=False, indent=1))
    return 0 if rap["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
