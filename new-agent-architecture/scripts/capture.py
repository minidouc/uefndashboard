# -*- coding: utf-8 -*-
"""
capture.py -- captures de preuve, cameras definies PAR LE DESIGN (cameras.json), jamais
improvisees. Camera relue apres placement, PNG sur disque, mesures calculees.

  python scripts/capture.py liste
  python scripts/capture.py prendre S0 [--lot lot_02]
  python scripts/capture.py toutes

cameras.json (ecrit par le level designer) :
  {"cameras": {"S0": {"location": {...}, "rotation": {...}}, "nuit_S0": {...}, ...}}
Le jugement esthetique se fait ensuite par le sous-agent `critique` (rubrique), en lisant le PNG.
"""
import argparse
import json
import os
import shutil
import sys

STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, STUDIO)
from scripts.uefn.config import Projet, ecrire_json, lire_json, maintenant  # noqa: E402
from validators._image import mesurer  # noqa: E402


def cmd_liste(p, a):
    cams = lire_json(p.chemin("cameras"))["cameras"] if os.path.exists(p.chemin("cameras")) else {}
    requises = sorted(p.cfg["visuel"]["captures"])  # meme cle que run_all.py et gen_cameras.py
    print(json.dumps({"definies": sorted(cams), "requises": requises,
                      "manquantes_dans_cameras_json": [r for r in requises if r not in cams]}, ensure_ascii=False))
    return 0


def prendre(p, gw, nom, lot=None):
    cams = lire_json(p.chemin("cameras"))["cameras"]
    if nom not in cams:
        return {"nom": nom, "rc": 4, "erreur": "camera '%s' absente de cameras.json (a definir par le level designer)" % nom}
    cam = cams[nom]
    tr = {"location": cam["location"], "rotation": cam["rotation"], "scale": {"x": 1, "y": 1, "z": 1}}
    r = gw.appel("EditorAppToolset", "SetCameraTransform", {"transform": tr}, ecriture=True, etape="cam_%s" % nom)
    if not r.ok:
        return {"nom": nom, "rc": r.rc, "erreur": r.erreur}
    rl = gw.appel("EditorAppToolset", "GetCameraTransform", {}, etape="cam_%s_relue" % nom)
    rc = gw.appel("EditorAppToolset", "CaptureViewport", {"bShowUI": False}, etape="capture_%s" % nom)
    if not rc.ok or not rc.png:
        return {"nom": nom, "rc": rc.rc or 6, "erreur": rc.erreur or "aucune image dans la reponse"}
    dest_dir = os.path.join(p.build_dir, "captures")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "%s.png" % nom)
    shutil.copyfile(rc.png, dest)
    rel = lambda c: os.path.relpath(c, p.root).replace("\\", "/")  # noqa: E731
    entree = {"png": rel(dest), "lot": lot, "ts_utc": maintenant(), "camera_demandee": cam,
              "preuve_camera": rel(rl.preuve) if rl.ok else None, "preuve_capture": rel(rc.preuve),
              "mesures_indicatives": mesurer(dest)}
    idx_chemin = os.path.join(dest_dir, "index.json")
    idx = lire_json(idx_chemin) if os.path.exists(idx_chemin) else {}
    idx[nom] = entree
    ecrire_json(idx_chemin, idx)
    return {"nom": nom, "rc": 0, "png": dest, "mesures": entree["mesures_indicatives"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projet")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("liste")
    x = sp.add_parser("prendre"); x.add_argument("nom"); x.add_argument("--lot")
    sp.add_parser("toutes")
    a = ap.parse_args(argv)
    p = Projet(a.projet)
    if a.cmd == "liste":
        return cmd_liste(p, a)
    from scripts.uefn.mcp_gateway import Passerelle
    gw = Passerelle(p, ecriture=True, script="capture")
    if not gw.ping():
        print("ARRET : editeur injoignable")
        return 2
    noms = [a.nom] if a.cmd == "prendre" else sorted(p.cfg["visuel"]["captures"])
    res = [prendre(p, gw, n, getattr(a, "lot", None)) for n in noms]
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print("SUITE : faire juger les PNG par le sous-agent 'critique' (rubrique docs/rubrique-visuelle.md)")
    return 0 if all(r["rc"] == 0 for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
