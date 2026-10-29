# -*- coding: utf-8 -*-
"""Socle commun des validateurs. FICHIER PROTEGE (hooks + empreinte MANIFEST.json).

Principe : un validateur ne fait JAMAIS confiance a ce qu'un lot DECLARE. Il remonte aux
preuves brutes (reponses MCP sur disque) et recalcule. Un champ declare sans preuve = FAIL.
"""
import glob
import json
import os

STATUTS_LOT_VALIDABLES = {"POSE_TERMINEE"}


def lire(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


class Contexte:
    """Tout ce qu'un validateur lit. Construit depuis un projet reel ou un cas golden."""

    def __init__(self, root, lots_dir, placements, baseline, captures_index, cfg_validation,
                 bornes_attendues, level_ref_prefix, overlaps_autorises=None,
                 exceptions_flottants=None, captures_requises=None, seuils_visuels=None):
        self.root = root
        self.lots_dir = lots_dir
        self.placements_path = placements
        self.baseline_path = baseline
        self.captures_index_path = captures_index
        self.cfg = cfg_validation
        self.bornes = bornes_attendues
        self.level_ref_prefix = level_ref_prefix
        self.overlaps_path = overlaps_autorises
        self.flottants_path = exceptions_flottants
        self.captures_requises = captures_requises or []
        self.seuils = seuils_visuels or {}
        self._cache = {}

    # --- chargements -------------------------------------------------------------------
    def lots(self):
        if "lots" not in self._cache:
            out = []
            for f in sorted(glob.glob(os.path.join(self.lots_dir, "lot_*.json"))):
                d = lire(f)
                d["_fichier"] = f
                out.append(d)
            self._cache["lots"] = out
        return self._cache["lots"]

    def placements(self):
        """Plan de pose fusionne (plan principal + deltas). Un id en double = erreur explicite."""
        if "pl" not in self._cache:
            chemins = self.placements_path if isinstance(self.placements_path, list) else [self.placements_path]
            pl = {}
            for c in chemins:
                doc = lire(c)
                items = list(doc.get("placements", []))
                sp = doc.get("spawn")  # spawn declare a part dans le plan : il fait partie du plan
                if sp and sp.get("id") and sp["id"] not in {i["id"] for i in items}:
                    items.append({"id": sp["id"], "strate": sp.get("strate", "S-1"), "categorie": "poi",
                                  "position": sp["position"],
                                  "dimensions_uu": sp.get("dimensions_uu", {"X": 100, "Y": 100, "Z": 100})})
                for i in items:
                    if i["id"] in pl:
                        raise ValueError("id en double dans les plans : %s" % i["id"])
                    pl[i["id"]] = i
            self._cache["pl"] = pl
        return self._cache["pl"]

    def json_optionnel(self, chemin, defaut):
        return lire(chemin) if chemin and os.path.exists(chemin) else defaut

    def preuve(self, chemin_rel):
        """Charge une reponse MCP brute. None si absente."""
        if not chemin_rel:
            return None
        p = chemin_rel if os.path.isabs(chemin_rel) else os.path.join(self.root, chemin_rel)
        return lire(p) if os.path.exists(p) else None

    def acteurs_poses(self):
        """(lot_id, acteur) pour chaque acteur POSE avec bounds, lots validables uniquement."""
        for lot in self.lots():
            for a in lot.get("acteurs", []):
                if a.get("statut") == "POSE" and a.get("bounds"):
                    yield lot["lot_id"], a


# --- geometrie -------------------------------------------------------------------------
def aabb(b):
    return (b["min"]["x"], b["min"]["y"], b["min"]["z"], b["max"]["x"], b["max"]["y"], b["max"]["z"])


def intersection_stricte(a, b, eps):
    """Volumes qui se penetrent de plus de eps sur les 3 axes (un simple contact ne compte pas)."""
    return all(min(a[i + 3], b[i + 3]) - max(a[i], b[i]) > eps for i in range(3))


def contact(a, b, eps):
    """Boites qui se touchent ou se penetrent (ecart <= eps sur chaque axe)."""
    return all(max(a[i], b[i]) - min(a[i + 3], b[i + 3]) <= eps for i in range(3))


def chevauchement_xy(a, b, eps):
    return all(min(a[i + 3], b[i + 3]) - max(a[i], b[i]) > -eps for i in range(2))


def egal_bounds(b1, b2, tol=0.5):
    try:
        return all(abs(x - y) <= tol for x, y in zip(aabb(b1), aabb(b2)))
    except (KeyError, TypeError):
        return False


class Verdict:
    def __init__(self, nom):
        self.nom = nom
        self.violations = []  # {"lot": id|None, "detail": str}
        self.controles = 0

    def ko(self, detail, lot=None):
        self.violations.append({"lot": lot, "detail": detail})

    def compte(self, n=1):
        self.controles += n

    def resultat(self):
        return {"validateur": self.nom, "verdict": "PASS" if not self.violations else "FAIL",
                "controles": self.controles, "nb_violations": len(self.violations),
                "violations": self.violations[:50]}
