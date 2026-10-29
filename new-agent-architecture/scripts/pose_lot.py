# -*- coding: utf-8 -*-
"""
pose_lot.py -- tache "poser le lot N" (WP2 p.18 : publier des TACHES, pas des appels d'API).

Le modele ne fournit JAMAIS une coordonnee : il choisit un numero de lot. Tout le reste
(positions, decoupe, supports) vient de placements.json, calcule ici en Python (WP2 p.9).

  python scripts/pose_lot.py plan                 # gele le decoupage en lots (lot_plan.json)
  python scripts/pose_lot.py simuler 3            # ce qui SERA fait, sans toucher l'editeur
  python scripts/pose_lot.py lot 3                # pose reelle (permission "ask" : l'humain approuve)

Par acteur : creation -> geometrie -> rangement dans le dossier CP_Studio/lot_NN (rollback borne).
Fin de lot : UNE relecture groupee (find_actors : bornes de tous les acteurs) -> save -> is_dirty
-> bornes du niveau. Toute erreur d'ecriture = ARRET immediat, lot INTERROMPU (WP4 p.20).
Le statut ecrit est POSE_TERMINEE, jamais VALIDE : seul validators/run_all.py valide.
"""
import argparse
import hashlib
import json
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.uefn.config import CONFIG_DIR, Projet, ecrire_json, lire_json, maintenant  # noqa: E402

SUPPORTS = lire_json(os.path.join(CONFIG_DIR, "supports.json"))
SURFACES = {"plancher", "connecteur"}


# ------------------------------------------------------------------------------ decoupe
def decouper(item, portee, z_min):
    """Liste des segments [(x, y, z, dx, dy, dz)] d'un item primitive. Pur calcul, deterministe."""
    x, y, z = (float(v) for v in item["position"])
    d = item.get("dimensions_uu") or {}
    dx, dy, dz = float(d.get("X", 100)), float(d.get("Y", 100)), float(d.get("Z", 100))
    pitch, yaw, roll = (float(v) for v in item.get("rotation_degres", [0, 0, 0]))
    nx, ny = max(1, math.ceil(dx / portee)), max(1, math.ceil(dy / portee))
    if (nx > 1 or ny > 1) and (abs(pitch) > 0.01 or abs(roll) > 0.01):
        raise ValueError("decoupe impossible avec pitch/roll non nuls (item incline trop grand)")
    sx, sy = dx / nx, dy / ny
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    segs = []
    for i in range(nx):
        for j in range(ny):
            ox, oy = -dx / 2 + sx * (i + 0.5), -dy / 2 + sy * (j + 0.5)
            # Z minimum de la primitive. Une SURFACE (plancher, connecteur) s'epaissit vers le
            # bas : son dessus reste a la cote prevue (avant : epaississement centre, sols
            # rehausses de ~125 uu, spawn enterre). Un OBJET pose dessus s'epaissit vers le haut :
            # sa base reste sur le sol (sinon il penetre la surface qui le porte).
            hz = max(dz, z_min)
            if hz == dz:
                zc = z
            elif item.get("categorie") in SURFACES:
                zc = (z + dz / 2) - hz / 2
            else:
                zc = (z - dz / 2) + hz / 2
            segs.append((x + ox * c - oy * s, y + ox * s + oy * c, zc, sx, sy, hz))
    return segs


def methode(item):
    sup = str(item.get("support", ""))
    if sup in SUPPORTS["devices"]:
        return "device", SUPPORTS["devices"][sup], None
    if sup == "PrimitiveTools.add_cylinder":
        return "cylindre", None, None
    if sup == "PrimitiveTools.add_cube":
        return "cube", None, None
    if sup.startswith("ASSET:"):
        return "asset", sup[len("ASSET:"):], None
    if any(sup.endswith(x) for x in SUPPORTS["repli_vers_cube"]["suffixes"]):
        return "cube", None, SUPPORTS["repli_vers_cube"]["raison"]
    return None, None, "support '%s' non mappe dans config/supports.json" % sup


def nb_acteurs(item, p):
    m, _, _ = methode(item)
    if m == "cube":
        try:
            return len(decouper(item, p.pose["portee_max_primitive_uu"], p.pose["z_min_primitive_uu"]))
        except ValueError:
            return 1
    return 1


# ------------------------------------------------------------------------------ plan
def sha_plans(p):
    h = hashlib.sha256()
    for c in p.plans():
        with open(c, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def charger_items(p):
    items = []
    for c in p.plans():
        items.extend(items_du_plan(lire_json(c)))
    return items


def items_du_plan(doc):
    """Items d'un plan, y compris le spawn declare a part (cle 'spawn') : sans lui, rien
    ne le posait (defaut corpo-plaza, ajoute a la main par l'ancien script)."""
    items = list(doc.get("placements", []))
    sp = doc.get("spawn")
    if sp and sp.get("id") and sp["id"] not in {i["id"] for i in items}:
        items.insert(0, {"id": sp["id"], "strate": sp.get("strate", "S-1"), "categorie": "poi",
                         "position": sp["position"], "rotation_degres": sp.get("rotation_degres", [0, 0, 0]),
                         "support": sp.get("support", "PID_CP_Devices_PlayerSpawner"),
                         "dimensions_uu": sp.get("dimensions_uu", {"X": 100, "Y": 100, "Z": 100})})
    return items


def cmd_plan(p, a):
    chemin = os.path.join(p.build_dir, "lot_plan.json")
    if os.path.exists(chemin) and not a.refaire:
        print("lot_plan.json existe deja (gele). --refaire pour le recalculer (decision humaine).")
        return 0
    ordre = p.pose["ordre_strates"]
    items = charger_items(p)

    derniers_cat = set(p.pose.get("categories_en_dernier", []))
    derniers_pre = tuple(x.upper() for x in p.pose.get("prefixes_en_dernier", []))

    # z_min des boites telles que posees : un appui commence toujours plus bas que ce qu'il porte,
    # donc trier par z_min pose les appuis avant (sinon le lot N echoue en flottants que le lot N+1
    # aurait resolus : corpo-plaza lot 2, 11 flottants dont les sols etaient au lot 3)
    from scripts.check_plan import ContextePlan
    z_min = {}
    for _, x in ContextePlan(p).acteurs_poses():
        iid = x["id_placement"]
        z_min[iid] = min(z_min.get(iid, float("inf")), x["bounds"]["min"]["z"])

    def rang(it):
        # 1) le spawn d'abord (minimum jouable), 2) du bas vers le haut, puis l'ordre des zones du profil,
        # 3) l'environnement (ciel, lumiere globale, post-process) a la fin
        if "SPAWN" in it["id"].upper() or "PlayerSpawner" in str(it.get("support", "")):
            return (-1, 0, 0)
        if it.get("categorie") in derniers_cat or (derniers_pre and it["id"].upper().startswith(derniers_pre)):
            return (1, 0, 0)
        st = it.get("strate")
        return (0, round(z_min.get(it["id"], 0)), ordre.index(st) if st in ordre else len(ordre))
    items.sort(key=rang)
    lots, courant, n = [], [], 0
    cap = p.pose["max_acteurs_par_lot"]
    for it in items:
        k = nb_acteurs(it, p)
        if courant and n + k > cap:
            lots.append(courant)
            courant, n = [], 0
        courant.append(it["id"])
        n += k
    if courant:
        lots.append(courant)
    doc = {"$schema": "studio.lot_plan.v1", "genere_le": maintenant(), "sha256_plans": sha_plans(p),
           "lots": {"lot_%02d" % (i + 1): ids for i, ids in enumerate(lots)}}
    ecrire_json(chemin, doc)
    print(json.dumps({"lots": len(lots), "items": len(items),
                      "acteurs_estimes": sum(nb_acteurs(i, p) for i in items), "plan": chemin}))
    return 0


# ------------------------------------------------------------------------------ pose
class Poseur:
    def __init__(self, p, lot_id, gw):
        self.p, self.lot_id, self.gw = p, lot_id, gw
        self.dossier = "%s/%s" % (p.pose["dossier_outliner"], lot_id)
        self.acteurs, self.gaps = [], []

    def rel(self, chemin):
        return os.path.relpath(chemin, self.p.root).replace("\\", "/") if chemin else None

    def _ecrire(self, ts, outil, args, etape):
        r = self.gw.appel(ts, outil, args, ecriture=True, etape=etape)
        if not r.ok:
            raise ArretLot("%s : rc=%s %s" % (etape, r.rc, r.erreur))
        return r

    @staticmethod
    def _ref(r):
        v = r.valeur
        ref = v.get("refPath") if isinstance(v, dict) else v
        if not ref:
            raise ArretLot("reponse sans refPath : etat INCONNU, relire l'editeur")
        return ref

    def _xform(self, x, y, z, item):
        pi, ya, ro = (float(v) for v in item.get("rotation_degres", [0, 0, 0]))
        return {"location": {"x": x, "y": y, "z": z}, "rotation": {"pitch": pi, "yaw": ya, "roll": ro},
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0}}

    def _enregistrer(self, item, k, ref, r_pose, support_reel, raison):
        self._ecrire("SceneTools", "set_actor_folder", {"actor": {"refPath": ref}, "folder_path": self.dossier},
                     "%s_s%d_dossier" % (item["id"], k))
        self.acteurs.append({"id_placement": item["id"], "segment": k, "refPath": ref, "statut": "POSE_NON_RELU",
                             "support_prevu": item.get("support"), "support_reel": support_reel,
                             "degrade": bool(raison), "raison_degrade": raison,
                             "preuve_pose": self.rel(r_pose.preuve), "preuve_bounds": None, "bounds": None})

    def poser(self, item):
        m, cible, raison = methode(item)
        iid = item["id"]
        if m is None:
            self.gaps.append({"id": iid, "raison": raison})
            return
        x, y, z = (float(v) for v in item["position"])
        if m == "device":
            r = self._ecrire("DeviceToolset", "PlaceDevice",
                             {"assetPath": {"refPath": cible}, "transform": self._xform(x, y, z, item)}, iid + "_device")
            self._enregistrer(item, 0, self._ref(r), r, item.get("support"), raison)
            return
        if m == "asset":
            r = self._ecrire("SceneTools", "add_to_scene_from_asset",
                             {"asset_path": cible, "name": "CP_" + iid, "xform": self._xform(x, y, z, item)}, iid + "_asset")
            self._enregistrer(item, 0, self._ref(r), r, "ASSET:" + cible, raison)
            return
        if m == "cylindre":
            d = item.get("dimensions_uu") or {}
            r = self._ecrire("SceneTools", "add_to_scene_from_class",
                             {"actor_type": {"refPath": SUPPORTS["class_acteur_vide"]}, "name": "CP_" + iid,
                              "xform": self._xform(x, y, z, item)}, iid + "_acteur")
            ref = self._ref(r)
            self._ecrire("PrimitiveTools", "add_cylinder",
                         {"actor": {"refPath": ref}, "name": "CP_%s_cyl" % iid,
                          "radius": max(10.0, float(d.get("X", 100)) / 2), "height": max(50.0, float(d.get("Z", 100)))},
                         iid + "_cylindre")
            self._enregistrer(item, 0, ref, r, "PrimitiveTools.add_cylinder", raison)
            return
        try:
            segs = decouper(item, self.p.pose["portee_max_primitive_uu"], self.p.pose["z_min_primitive_uu"])
        except ValueError as e:
            self.gaps.append({"id": iid, "raison": str(e)})
            return
        for k, (sx, sy, sz, dx, dy, dz) in enumerate(segs):
            nom = "CP_%s" % iid if len(segs) == 1 else "CP_%s_s%d" % (iid, k)
            r = self._ecrire("SceneTools", "add_to_scene_from_class",
                             {"actor_type": {"refPath": SUPPORTS["class_acteur_vide"]}, "name": nom,
                              "xform": self._xform(sx, sy, sz, item)}, "%s_s%d_acteur" % (iid, k))
            ref = self._ref(r)
            self._ecrire("PrimitiveTools", "add_cube",
                         {"actor": {"refPath": ref}, "name": nom + "_cube", "dimensions": {"x": dx, "y": dy, "z": dz}},
                         "%s_s%d_cube" % (iid, k))
            self._enregistrer(item, k, ref, r, "PrimitiveTools.add_cube", raison)

    def relire(self):
        """UNE relecture groupee : les bornes de chaque acteur viennent de l'editeur, jamais d'un calcul."""
        r = self.gw.appel("SceneTools", "find_actors", {"name": "", "collision_channels": []}, etape="releve_bornes")
        if not r.ok:
            raise ArretLot("relecture groupee impossible : %s" % r.erreur)
        par_chemin = {e.get("actorPath"): e.get("bounds") for e in (r.valeur or []) if isinstance(e, dict)}
        for a in self.acteurs:
            b = par_chemin.get(a["refPath"])
            a["preuve_bounds"] = self.rel(r.preuve)
            if b and b.get("isValid", True):
                a["bounds"], a["statut"] = b, "POSE"
            else:
                a["statut"] = "NON_RELU"
        return r

    def cloturer(self):
        c = {}
        pkg = self.p.uefn["level_package"]
        r = self._ecrire("AssetTools", "save_assets", {"asset_paths": [pkg]}, "cloture_save")
        c["save"] = {"rc": r.rc, "valeur": r.valeur, "preuve": self.rel(r.preuve)}
        r = self.gw.appel("AssetTools", "is_dirty", {"asset_path": pkg}, etape="cloture_is_dirty")
        c["is_dirty"] = {"rc": r.rc, "valeur": r.valeur, "preuve": self.rel(r.preuve)}
        r = self.gw.appel("ActorTools", "get_actor_bounds",
                          {"actor": {"refPath": self.p.level_ref(self.p.uefn["level_bounds_actor"])}},
                          etape="cloture_bornes_niveau")
        c["bornes_niveau"] = {"rc": r.rc, "valeur": r.valeur, "preuve": self.rel(r.preuve)}
        r = self.gw.appel("SceneTools", "find_actors", {"name": "", "collision_channels": []}, etape="cloture_find_actors")
        c["find_actors"] = {"rc": r.rc, "nb": len(r.valeur or []), "preuve": self.rel(r.preuve)}
        return c


class ArretLot(Exception):
    pass


def cmd_lot(p, a):
    plan = lire_json(os.path.join(p.build_dir, "lot_plan.json"))
    if plan["sha256_plans"] != sha_plans(p):
        print("REFUS : placements.json a change depuis le gel du plan de lots. Decision humaine requise (plan --refaire).")
        return 4
    lot_id = "lot_%02d" % a.numero
    ids = plan["lots"].get(lot_id)
    if not ids:
        print("REFUS : %s absent du plan" % lot_id)
        return 4
    items = {i["id"]: i for i in charger_items(p)}
    sortie = os.path.join(p.build_dir, "lots", "%s.json" % lot_id)
    if os.path.exists(sortie) and not a.dry_run:
        print("REFUS : %s existe deja. Rollback d'abord (scripts/rollback.py --lot %d)." % (sortie, a.numero))
        return 4

    if a.dry_run:
        apercu = []
        for iid in ids:
            m, cible, raison = methode(items[iid])
            apercu.append({"id": iid, "methode": m, "acteurs": nb_acteurs(items[iid], p), "degrade": raison})
        n = sum(x["acteurs"] for x in apercu)
        print(json.dumps({"lot": lot_id, "items": len(ids), "acteurs": n,
                          "appels_ecriture_estimes": 3 * n + 1,
                          "gaps": [x for x in apercu if x["methode"] is None],
                          "degrades": sum(1 for x in apercu if x["degrade"] and x["methode"])},
                         ensure_ascii=False, indent=1))
        return 0

    from scripts.uefn.mcp_gateway import Passerelle
    gw = Passerelle(p, ecriture=True, script="pose_%s" % lot_id)
    if not gw.ping():
        print("ARRET : editeur injoignable, rien n'a ete ecrit")
        return 2
    ps = Poseur(p, lot_id, gw)
    statut, arret = "POSE_TERMINEE", None
    cloture = {}
    try:
        for iid in ids:
            ps.poser(items[iid])
        ps.relire()
        cloture = ps.cloturer()
        if any(a_["statut"] != "POSE" for a_ in ps.acteurs):
            statut = "INCOMPLET"
    except ArretLot as e:
        statut, arret = "INTERROMPU", str(e)
    doc = {"$schema": "studio.lot.v2", "lot_id": lot_id, "projet": p.slug, "run_id": gw.run_id,
           "ts_utc": maintenant(), "statut": statut, "arret": arret, "items": ids,
           "acteurs": ps.acteurs, "gaps": ps.gaps, "cloture": cloture,
           "dossier_outliner": ps.dossier}
    ecrire_json(sortie, doc)
    print(json.dumps({"lot": lot_id, "statut": statut, "arret": arret, "acteurs": len(ps.acteurs),
                      "non_relus": sum(1 for x in ps.acteurs if x["statut"] != "POSE"),
                      "gaps": len(ps.gaps), "degrades": sum(1 for x in ps.acteurs if x["degrade"]),
                      "fichier": sortie, "suite": "python validators/run_all.py"}, ensure_ascii=False))
    return 0 if statut == "POSE_TERMINEE" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--projet")
    sp = ap.add_subparsers(dest="cmd", required=True)
    x = sp.add_parser("plan"); x.add_argument("--refaire", action="store_true")
    x = sp.add_parser("lot"); x.add_argument("numero", type=int); x.add_argument("--dry-run", action="store_true")
    x = sp.add_parser("simuler"); x.add_argument("numero", type=int)
    a = ap.parse_args(argv)
    if a.cmd == "simuler":
        a.cmd, a.dry_run = "lot", True
    p = Projet(a.projet)
    return cmd_plan(p, a) if a.cmd == "plan" else cmd_lot(p, a)


if __name__ == "__main__":
    sys.exit(main())
