# -*- coding: utf-8 -*-
"""
lock_validators.py -- ACTION HUMAINE UNIQUEMENT (le hook bloque son execution par un agent).

Recalcule les empreintes SHA-256 de validators/ et ecrit validators/MANIFEST.json.
A lancer apres avoir modifie un validateur ou regenere le golden set, PUIS verifier :
    python validators/run_all.py --golden-seulement
Le MANIFEST est versionne dans git : toute modification se voit dans le diff.
"""
import hashlib
import json
import os
import sys

STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, STUDIO)
from validators.run_all import ICI, MANIFEST, empreinte, fichiers_proteges  # noqa: E402
from scripts.uefn.config import maintenant  # noqa: E402


def main():
    doc = {"$schema": "studio.validators.manifest.v1", "genere_le": maintenant(),
           "fichiers": {rel: empreinte(rel) for rel in fichiers_proteges()}}
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    global_h = hashlib.sha256(json.dumps(doc["fichiers"], sort_keys=True).encode()).hexdigest()
    print("MANIFEST ecrit : %d fichiers, empreinte globale %s" % (len(doc["fichiers"]), global_h[:16]))
    print("Verifier maintenant : python validators/run_all.py --golden-seulement")


if __name__ == "__main__":
    main()
