# -*- coding: utf-8 -*-
"""
demarrage.py -- hook SessionStart : injecte dans le contexte, a chaque session, le MINIMUM utile
(WP3 p.16 : history != context ; WP3 p.61 : stable dans les instructions, transitoire injecte).
  - etat compact du projet (state.py show) ;
  - integrite des validateurs ;
  - les lecons apprises (memoire procedurale, WP3) : docs/lecons.md, section "Regles actives".
Jamais l'historique complet.
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")  # Windows : sinon les accents arrivent casses dans le contexte
STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def run(args):
    try:
        r = subprocess.run([sys.executable] + args, cwd=STUDIO, capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        return (r.stdout or r.stderr).strip()[:2500]
    except Exception as e:  # noqa: BLE001
        return "indisponible : %s" % e


def lecons():
    chemin = os.path.join(STUDIO, "docs", "lecons.md")
    if not os.path.exists(chemin):
        return ""
    txt = open(chemin, encoding="utf-8").read()
    debut = txt.find("## Regles actives")
    fin = txt.find("\n## ", debut + 5)
    return txt[debut:fin if fin > 0 else None].strip()[:2500] if debut >= 0 else ""


print("=== ETAT DU PROJET (scripts/state.py show) ===")
print(run(["scripts/state.py", "show"]))
print("\n=== VALIDATEURS (integrite + golden) ===")
print(run(["validators/run_all.py", "--golden-seulement"]))
print("\n=== MEMOIRE PROCEDURALE ===")
print(lecons())
