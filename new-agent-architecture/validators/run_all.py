# -*- coding: utf-8 -*-
"""
run_all.py -- porte de qualite (WP5 p.11-12 : evaluation-gated). FICHIER PROTEGE.

Ordre immuable :
  1. INTEGRITE : empreintes SHA-256 des validateurs == MANIFEST.json. Ecart => FAIL global.
  2. AUTO-TEST GOLDEN (WP4 : golden set) : chaque cas piege DOIT etre rejete par la regle
     attendue, le cas sain DOIT passer. Un validateur affaibli est detecte ici => FAIL global.
  3. VALIDATION REELLE du projet -> <projet>/qa/validation/<ts>.json + latest.json.

Le rapport est le SEUL moyen de faire passer un lot a VALIDE (scripts/state.py lot ...).

Usage : python validators/run_all.py [--projet slug] [--golden-seulement]
Code retour : 0 si verdict PASS, 1 sinon.
"""
import argparse
import hashlib
import json
import os
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(ICI)
sys.path.insert(0, STUDIO)

from scripts.uefn.config import Projet, ecrire_json, lire_json, maintenant  # noqa: E402
from validators._commun import Contexte  # noqa: E402
from validators import regles  # noqa: E402

MANIFEST = os.path.join(ICI, "MANIFEST.json")


def fichiers_proteges():
    out = []
    for base, _, fichiers in os.walk(ICI):
        if "__pycache__" in base:
            continue
        for f in fichiers:
            if f == "MANIFEST.json" or f.endswith(".pyc"):
                continue
            out.append(os.path.relpath(os.path.join(base, f), ICI).replace("\\", "/"))
    return sorted(out)


def empreinte(rel):
    h = hashlib.sha256()
    with open(os.path.join(ICI, rel), "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def verifier_integrite():
    if not os.path.exists(MANIFEST):
        return "ABSENT", ["MANIFEST.json absent : lancer tools/lock_validators.py (action humaine)"]
    attendu = lire_json(MANIFEST)["fichiers"]
    ecarts = []
    actuels = fichiers_proteges()
    for rel in sorted(set(attendu) | set(actuels)):
        if rel not in attendu:
            ecarts.append("fichier ajoute : %s" % rel)
        elif rel not in actuels:
            ecarts.append("fichier supprime : %s" % rel)
        elif empreinte(rel) != attendu[rel]:
            ecarts.append("fichier modifie : %s" % rel)
    return ("OK" if not ecarts else "ALTERE"), ecarts


def executer(ctx):
    resultats = [r(ctx).resultat() for r in regles.TOUTES]
    par_lot = {}
    for lot in ctx.lots():
        par_lot[lot["lot_id"]] = "PASS"
    for r in resultats:
        for viol in r["violations"]:
            if viol["lot"]:
                par_lot[viol["lot"]] = "FAIL"
    return resultats, par_lot


def contexte_golden(cas_dir):
    cfg = lire_json(os.path.join(ICI, "golden", "config_golden.json"))
    return Contexte(
        root=cas_dir, lots_dir=os.path.join(cas_dir, "lots"),
        placements=os.path.join(cas_dir, "placements.json"),
        baseline=os.path.join(cas_dir, "baseline_preexistants.json"),
        captures_index=os.path.join(cas_dir, "captures", "index.json"),
        cfg_validation=cfg["validation"], bornes_attendues=cfg["bornes"],
        level_ref_prefix=cfg["level_ref_prefix"],
        overlaps_autorises=os.path.join(cas_dir, "overlaps_autorises.json"),
        exceptions_flottants=os.path.join(cas_dir, "exceptions_flottants.json"),
        captures_requises=cfg["captures_requises"], seuils_visuels=cfg["seuils_visuels"])


def auto_test_golden():
    attendus = lire_json(os.path.join(ICI, "golden", "attendus.json"))
    echecs = []
    for cas, doit_echouer in attendus["cas"].items():
        cas_dir = os.path.join(ICI, "golden", "cas", cas)
        resultats, _ = executer(contexte_golden(cas_dir))
        fails = {r["validateur"] for r in resultats if r["verdict"] == "FAIL"}
        if not doit_echouer and fails:
            echecs.append("%s : le cas sain est rejete par %s" % (cas, sorted(fails)))
        for nom in doit_echouer:
            if nom not in fails:
                echecs.append("%s : %s ne detecte PAS le defaut -> validateur affaibli" % (cas, nom))
    return echecs


def contexte_projet(p):
    v = p.cfg["visuel"]
    return Contexte(
        root=p.root, lots_dir=os.path.join(p.build_dir, "lots"),
        placements=p.plans(),
        baseline=os.path.join(p.build_dir, "baseline_preexistants.json"),
        captures_index=os.path.join(p.build_dir, "captures", "index.json"),
        cfg_validation=p.validation, bornes_attendues=p.uefn["bornes_attendues"],
        level_ref_prefix=p.uefn["level_ref_prefix"],
        overlaps_autorises=p.chemin("overlaps_autorises"),
        exceptions_flottants=p.chemin("exceptions_flottants"),
        captures_requises=v["captures"], seuils_visuels=v["seuils"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projet")
    ap.add_argument("--golden-seulement", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()

    integrite, ecarts = verifier_integrite()
    golden = auto_test_golden() if integrite == "OK" else ["non execute (integrite %s)" % integrite]
    rapport = {"$schema": "studio.validation.v2", "ts_utc": maintenant(),
               "integrite_validateurs": integrite, "ecarts_integrite": ecarts,
               "auto_test_golden": "OK" if not golden else "ECHEC", "echecs_golden": golden}

    if a.golden_seulement:
        print(json.dumps(rapport, ensure_ascii=False, indent=1))
        return 0 if integrite == "OK" and not golden else 1

    p = Projet(a.projet)
    resultats, par_lot = executer(contexte_projet(p)) if integrite == "OK" and not golden else ([], {})
    pass_global = integrite == "OK" and not golden and resultats and all(r["verdict"] == "PASS" for r in resultats)
    rapport.update(projet=p.slug, verdict="PASS" if pass_global else "FAIL", par_lot=par_lot,
                   validateurs=resultats, duree_s=round(time.time() - t0, 2))
    dossier = os.path.join(p.root, "qa", "validation")
    ecrire_json(os.path.join(dossier, "%s.json" % time.strftime("%Y%m%dT%H%M%S")), rapport)
    ecrire_json(os.path.join(dossier, "latest.json"), rapport)

    # resume BORNE pour le contexte de l'orchestrateur (le detail reste sur disque)
    print(json.dumps({
        "verdict": rapport["verdict"], "integrite": integrite, "golden": rapport["auto_test_golden"],
        "par_lot": par_lot,
        "validateurs": {r["validateur"]: "%s (%d)" % (r["verdict"], r["nb_violations"]) for r in resultats},
        "exemples_violations": [vi["detail"] for r in resultats for vi in r["violations"][:2]][:10],
        "rapport": os.path.join(dossier, "latest.json"),
    }, ensure_ascii=False, indent=1))
    return 0 if pass_global else 1


if __name__ == "__main__":
    sys.exit(main())
