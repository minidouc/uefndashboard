# -*- coding: utf-8 -*-
"""
state.py -- SEUL ecrivain de l'etat du projet (les hooks bloquent toute autre ecriture).

Separation events / state (WP3 p.12) :
  state/state.json   : memoire de travail, PETITE (plafond 20 Ko), relue a chaque tour ;
  state/events.jsonl : historique append-only, jamais relu en entier (WP3 p.16).
Provenance (WP3 p.49) : chaque evenement porte sa source. Seules les sources
'validator', 'editor_readback' et 'human' peuvent faire avancer le projet.
Progression conditionnee a l'evaluation (WP5 p.11-12) : changer de phase ou valider un
lot exige un rapport de validation PASS ou une citation humaine.

Usage :
  python scripts/state.py show
  python scripts/state.py init
  python scripts/state.py event  --source agent_claim --quoi "..." [--preuve chemin]
  python scripts/state.py gate   --nom brief --citation "texte exact de l'utilisateur"
  python scripts/state.py phase  --vers DESIGN
  python scripts/state.py lot    --id lot_03 --statut VALIDE
  python scripts/state.py iterer                  (anti-boucle : STOP a 15)
  python scripts/state.py question                (budget : alerte 30, STOP 40)
  python scripts/state.py blocage --ouvrir "titre" | --fermer B-01 --preuve chemin
  python scripts/state.py derogation --sacrifie captures_multiples,spike_T6 --citation "..."
  python scripts/state.py next   --texte "prochaine action"
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.uefn.config import Projet, ecrire_json, lire_json, maintenant  # noqa: E402

PHASES = ["INIT", "CADRAGE", "DESIGN", "BUILD", "POLISH", "QA", "SHIPPED"]
SOURCES = ["validator", "editor_readback", "human", "script", "agent_claim"]
SOURCES_PROBANTES = {"validator", "editor_readback", "human"}
GATES = ["brief", "gdd", "archi", "ecriture_uefn", "derogation"]
# Gates requises pour ENTRER dans une phase
PREREQUIS_PHASE = {"DESIGN": ["brief"], "BUILD": ["gdd", "archi", "ecriture_uefn"]}
# Phases dont la SORTIE exige un rapport de validation PASS
SORTIE_SUR_VALIDATION = {"BUILD", "POLISH", "QA"}
CAP_ITERATIONS = 15
QUESTIONS_ALERTE, QUESTIONS_STOP = 30, 40
TAILLE_MAX_STATE = 20_000
# Ce qu'une derogation "mode rapide" ne peut JAMAIS sacrifier
NON_SACRIFIABLES = {"validateurs", "jauge_ram", "relecture_bornes", "preexistants",
                    "save_par_lot", "source_coordonnees", "trace", "rollback"}
SACRIFIABLES = {"spike_T6", "captures_multiples", "critique_trajectoire", "critique_visuelle",
                "golden_selftest_par_lot", "questions_cadrage"}


class Etat:
    def __init__(self, projet=None):
        self.p = projet or Projet()
        self.fichier = os.path.join(self.p.state_dir, "state.json")
        self.journal = os.path.join(self.p.state_dir, "events.jsonl")

    def lire(self):
        if not os.path.exists(self.fichier):
            raise SystemExit("Etat absent : lancer `python scripts/state.py init`")
        return lire_json(self.fichier)

    def ecrire(self, s):
        s["maj"] = maintenant()
        taille = len(json.dumps(s, ensure_ascii=False))
        if taille > TAILLE_MAX_STATE:
            raise SystemExit("STATE_TROP_GROS (%d o > %d) : deplacer le detail dans events.jsonl" % (taille, TAILLE_MAX_STATE))
        ecrire_json(self.fichier, s)

    def evenement(self, source, quoi, preuve=None, **extra):
        if source not in SOURCES:
            raise SystemExit("source inconnue %s (attendu %s)" % (source, SOURCES))
        e = {"ts_utc": maintenant(), "source": source, "quoi": quoi, "preuve": preuve}
        e.update(extra)
        os.makedirs(os.path.dirname(self.journal), exist_ok=True)
        with open(self.journal, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return e

    def rapport_validation(self):
        chemin = os.path.join(self.p.root, "qa", "validation", "latest.json")
        return (lire_json(chemin), chemin) if os.path.exists(chemin) else (None, chemin)


def cmd_init(et, a):
    if os.path.exists(et.fichier) and not a.force:
        raise SystemExit("state.json existe deja (utiliser --force pour reinitialiser)")
    et.ecrire({"$schema": "studio.state.v2", "projet": et.p.slug, "phase": a.phase,
               "mode": "NORMAL", "derogation": None,
               "compteurs": {"iterations_phase": 0, "questions_total": 0},
               "gates": {}, "lots": {}, "blocages_ouverts": [],
               "derniere_validation": None, "prochaine_action": None})
    et.evenement("script", "init phase=%s" % a.phase)
    print("OK etat initialise")


def cmd_show(et, a):
    s = et.lire()
    lots = s.get("lots", {})
    resume = {
        "phase": s["phase"], "mode": s["mode"], "compteurs": s["compteurs"],
        "gates": sorted(s["gates"]), "lots": {k: lots[k] for k in sorted(lots)[-12:]},
        "blocages_ouverts": [b["id"] + " " + b["titre"] for b in s["blocages_ouverts"]],
        "derniere_validation": s["derniere_validation"], "prochaine_action": s["prochaine_action"],
    }
    print(json.dumps(resume, ensure_ascii=False, indent=1))


def cmd_event(et, a):
    et.evenement(a.source, a.quoi, a.preuve)
    print("OK evenement journalise (%s)" % a.source)


def cmd_gate(et, a):
    if a.nom not in GATES:
        raise SystemExit("gate inconnue %s" % a.nom)
    if not a.citation or len(a.citation.strip()) < 2:
        raise SystemExit("GATE_REFUSEE : citation exacte de l'utilisateur obligatoire")
    s = et.lire()
    s["gates"][a.nom] = {"ts": maintenant(), "citation": a.citation, "perimetre": a.perimetre}
    et.ecrire(s)
    et.evenement("human", "gate %s accordee" % a.nom, citation=a.citation)
    print("OK gate %s" % a.nom)


def cmd_phase(et, a):
    s = et.lire()
    if a.vers not in PHASES:
        raise SystemExit("phase inconnue")
    i_cour, i_dest = PHASES.index(s["phase"]), PHASES.index(a.vers)
    if i_dest == i_cour + 1:
        manquantes = [g for g in PREREQUIS_PHASE.get(a.vers, []) if g not in s["gates"]]
        if manquantes:
            raise SystemExit("PHASE_REFUSEE : gates manquantes %s" % manquantes)
        if s["phase"] in SORTIE_SUR_VALIDATION:
            rap, chemin = et.rapport_validation()
            if not rap or rap.get("verdict") != "PASS":
                raise SystemExit("PHASE_REFUSEE : rapport de validation PASS requis (%s)" % chemin)
            if rap.get("integrite_validateurs") != "OK":
                raise SystemExit("PHASE_REFUSEE : validateurs alteres")
    elif i_dest > i_cour + 1:
        raise SystemExit("PHASE_REFUSEE : on ne saute pas de phase")
    # retour arriere toujours permis (QA qui echoue -> BUILD)
    ancienne = s["phase"]
    s["phase"], s["compteurs"]["iterations_phase"] = a.vers, 0
    et.ecrire(s)
    et.evenement("script", "phase %s -> %s" % (ancienne, a.vers))
    print("OK phase %s" % a.vers)


def cmd_lot(et, a):
    s = et.lire()
    if a.statut == "VALIDE":
        rap, chemin = et.rapport_validation()
        ok_lot = rap and rap.get("integrite_validateurs") == "OK" and \
            rap.get("par_lot", {}).get(a.id) == "PASS"
        if not ok_lot:
            raise SystemExit("LOT_REFUSE : %s n'est pas PASS dans %s" % (a.id, chemin))
        et.evenement("validator", "lot %s VALIDE" % a.id, chemin)
    else:
        et.evenement("script", "lot %s -> %s" % (a.id, a.statut), a.preuve)
    s["lots"][a.id] = a.statut
    et.ecrire(s)
    print("OK %s %s" % (a.id, a.statut))


def cmd_iterer(et, a):
    s = et.lire()
    s["compteurs"]["iterations_phase"] += 1
    n = s["compteurs"]["iterations_phase"]
    et.ecrire(s)
    if n >= CAP_ITERATIONS:
        et.evenement("script", "STOP anti-boucle : %d iterations en %s" % (n, s["phase"]))
        print("STOP : %d iterations dans la phase %s -> escalade utilisateur obligatoire" % (n, s["phase"]))
        sys.exit(3)
    print("OK iteration %d/%d" % (n, CAP_ITERATIONS))


def cmd_question(et, a):
    s = et.lire()
    s["compteurs"]["questions_total"] += 1
    n = s["compteurs"]["questions_total"]
    et.ecrire(s)
    if n >= QUESTIONS_STOP:
        print("STOP : budget de questions epuise (%d)" % n)
        sys.exit(3)
    print(("ALERTE " if n >= QUESTIONS_ALERTE else "OK ") + "question %d/%d" % (n, QUESTIONS_STOP))


def cmd_blocage(et, a):
    s = et.lire()
    if a.ouvrir:
        deja = 0
        if os.path.exists(et.journal):
            with open(et.journal, encoding="utf-8") as f:
                deja = sum(1 for l in f if '"blocage_ouvert"' in l)
        bid = "B-%02d" % (deja + 1)
        s["blocages_ouverts"].append({"id": bid, "titre": a.ouvrir[:160], "ts": maintenant()})
        et.evenement("script", "blocage ouvert", type="blocage_ouvert", id=bid, titre=a.ouvrir)
    else:
        if not a.preuve or not (os.path.exists(os.path.join(et.p.root, a.preuve)) or os.path.exists(a.preuve)):
            raise SystemExit("BLOCAGE_NON_LEVE : --preuve <fichier existant> obligatoire")
        s["blocages_ouverts"] = [b for b in s["blocages_ouverts"] if b["id"] != a.fermer]
        et.evenement("editor_readback", "blocage %s leve" % a.fermer, a.preuve)
    et.ecrire(s)
    print("OK")


def cmd_derogation(et, a):
    demandes = {x.strip() for x in a.sacrifie.split(",") if x.strip()}
    interdits = demandes & NON_SACRIFIABLES
    inconnus = demandes - SACRIFIABLES - NON_SACRIFIABLES
    if interdits:
        raise SystemExit("DEROGATION_REFUSEE : non sacrifiables %s" % sorted(interdits))
    if inconnus:
        raise SystemExit("DEROGATION_REFUSEE : controles inconnus %s (sacrifiables : %s)" % (sorted(inconnus), sorted(SACRIFIABLES)))
    if not a.citation:
        raise SystemExit("DEROGATION_REFUSEE : citation utilisateur obligatoire")
    s = et.lire()
    s["mode"] = "RAPIDE"
    s["derogation"] = {"ts": maintenant(), "sacrifie": sorted(demandes), "citation": a.citation,
                       "garde": sorted(NON_SACRIFIABLES)}
    s["gates"]["derogation"] = {"ts": maintenant(), "citation": a.citation}
    et.ecrire(s)
    et.evenement("human", "mode RAPIDE", sacrifie=sorted(demandes), citation=a.citation)
    print("OK mode RAPIDE ; sacrifie=%s ; garde=%s" % (sorted(demandes), sorted(NON_SACRIFIABLES)))


def cmd_next(et, a):
    s = et.lire()
    s["prochaine_action"] = a.texte[:300]
    et.ecrire(s)
    print("OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projet")
    sp = ap.add_subparsers(dest="cmd", required=True)
    x = sp.add_parser("init"); x.add_argument("--phase", default="INIT", choices=PHASES); x.add_argument("--force", action="store_true")
    sp.add_parser("show")
    x = sp.add_parser("event"); x.add_argument("--source", required=True, choices=SOURCES); x.add_argument("--quoi", required=True); x.add_argument("--preuve")
    x = sp.add_parser("gate"); x.add_argument("--nom", required=True); x.add_argument("--citation", required=True); x.add_argument("--perimetre")
    x = sp.add_parser("phase"); x.add_argument("--vers", required=True)
    x = sp.add_parser("lot"); x.add_argument("--id", required=True); x.add_argument("--statut", required=True, choices=["A_VALIDER", "VALIDE", "REJETE", "INTERROMPU", "ANNULE"]); x.add_argument("--preuve")
    sp.add_parser("iterer")
    sp.add_parser("question")
    x = sp.add_parser("blocage"); g = x.add_mutually_exclusive_group(required=True); g.add_argument("--ouvrir"); g.add_argument("--fermer"); x.add_argument("--preuve")
    x = sp.add_parser("derogation"); x.add_argument("--sacrifie", required=True); x.add_argument("--citation", required=True)
    x = sp.add_parser("next"); x.add_argument("--texte", required=True)
    a = ap.parse_args(argv)
    et = Etat(Projet(a.projet))
    globals()["cmd_" + a.cmd](et, a)


if __name__ == "__main__":
    main()
