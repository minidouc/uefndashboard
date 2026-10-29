# -*- coding: utf-8 -*-
"""
handoff.py -- contrat de mission entre l'orchestrateur et un sous-agent (studio.handoff.v2).

Une mission = UN fichier <projet>/handoff/H-<PHASE>-<NNN>__<de>__<vers>.json, verifie AVANT
d'etre confie (WP1 p.38 before_tool_callback) et a son retour.

  python scripts/handoff.py verifier <fichier.json>
  python scripts/handoff.py modele                    # imprime un squelette valide

Regles (WP3 p.18/23/45) : sortie seulement (pas de raisonnement), <= 4000 tokens, resume
<= 200 caracteres, un exemple de reference pour les roles de conception, des criteres
d'acceptation EXECUTABLES (validateur, script ou rubrique nommee), jamais "semble bon".
"""
import json
import os
import re
import sys

ROLES_CONCEPTION = {"directeur-creatif", "game-designer", "level-designer", "ux-ui-designer",
                    "narration", "audio"}
CHAMPS = ["$schema", "handoff_id", "de", "vers", "livrable", "resume", "entrees", "contraintes",
          "acceptance", "budget_tokens"]
ACCEPTANCE_OK = re.compile(r"^(validateur:|script:|rubrique:|schema:|humain:)")
MODELE = {
    "$schema": "studio.handoff.v2",
    "handoff_id": "H-DESIGN-001",
    "de": "orchestrateur",
    "vers": "level-designer",
    "livrable": "design/level/cameras.json",
    "resume": "Definir 8 cameras de preuve (une par strate + 2 nuit), cadrees sur les zones praticables.",
    "entrees": ["design/level/placements.json", "design/level/level-layout.md#strates"],
    "contraintes": {"interdit": ["modifier placements.json"], "bornes": {"z": [-256, 9000]}},
    "exemple_ref": "agents/Level_Designer/skill/exemples/grille-esplanade-21x21.json",
    "acceptance": ["schema:templates/cameras.schema.json", "script:python scripts/capture.py liste"],
    "budget_tokens": 4000,
}


def verifier(chemin):
    erreurs = []
    brut = open(chemin, encoding="utf-8").read()
    try:
        h = json.loads(brut)
    except ValueError as e:
        return ["JSON invalide : %s" % e]
    for c in CHAMPS:
        if c not in h:
            erreurs.append("champ manquant : %s" % c)
    if h.get("$schema") != "studio.handoff.v2":
        erreurs.append("$schema != studio.handoff.v2")
    if len(h.get("resume", "")) > 200:
        erreurs.append("resume > 200 caracteres (%d)" % len(h["resume"]))
    if len(brut) / 4 > h.get("budget_tokens", 4000):
        erreurs.append("handoff trop gros (~%d tokens) : externaliser dans un fichier et passer son chemin" % (len(brut) / 4))
    if h.get("vers") in ROLES_CONCEPTION and not h.get("exemple_ref"):
        erreurs.append("exemple_ref obligatoire pour un role de conception (few-shot)")
    acc = h.get("acceptance") or []
    if not acc:
        erreurs.append("acceptance vide")
    for a in acc:
        if not ACCEPTANCE_OK.match(str(a)):
            erreurs.append("critere non executable : %r (prefixes : validateur:/script:/rubrique:/schema:/humain:)" % a)
    if re.search(r"(je pense|il semble|j'ai decide de|raisonnement)", brut, re.I):
        erreurs.append("prose de raisonnement detectee : un handoff transporte un resultat, pas un processus")
    return erreurs


def main(argv):
    if argv[:1] == ["modele"]:
        print(json.dumps(MODELE, ensure_ascii=False, indent=2))
        return 0
    if len(argv) == 2 and argv[0] == "verifier":
        if not os.path.exists(argv[1]):
            print("fichier absent")
            return 4
        err = verifier(argv[1])
        print(json.dumps({"handoff": argv[1], "valide": not err, "erreurs": err}, ensure_ascii=False, indent=1))
        return 0 if not err else 1
    print(__doc__)
    return 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
