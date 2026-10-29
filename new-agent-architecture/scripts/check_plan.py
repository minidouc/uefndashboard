# -*- coding: utf-8 -*-
"""
check_plan.py -- verifier le PLAN avant de poser quoi que ce soit (lecture seule, sans editeur).

Applique les regles geometriques des validateurs (chevauchements, flottants, accessibilite)
aux boites NOMINALES de placements.json. Un defaut trouve ici coute 0 appel MCP ; trouve
apres la pose, il coute un lot entier. Sert au level designer pour corriger le plan ou
declarer les exceptions justifiees (overlaps_autorises.json, exceptions_flottants.json).

  python scripts/check_plan.py [--detail]
"""
import argparse
import json
import math
import os
import sys

STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, STUDIO)
from scripts.uefn.config import Projet, lire_json  # noqa: E402
from scripts.pose_lot import decouper, methode  # noqa: E402
from validators._commun import Contexte  # noqa: E402
from validators import regles  # noqa: E402

BORNES = lire_json(os.path.join(STUDIO, "config", "bornes_devices.json"))


class ContextePlan(Contexte):
    """Contexte dont les 'acteurs' sont les boites nominales du plan (decoupe comprise)."""

    def __init__(self, p, sans_environnement=False):
        # sans_environnement : les volumes d'environnement (ciel, light rig : prefixes/categories
        # 'en_dernier') touchent tout ; comptes comme appuis, ils cachent de vrais flottants
        self.sans_env = sans_environnement
        super().__init__(root=p.root, lots_dir=None, placements=p.plans(), baseline=None,
                         captures_index=None, cfg_validation=p.validation,
                         bornes_attendues=p.uefn["bornes_attendues"], level_ref_prefix="",
                         overlaps_autorises=p.chemin("overlaps_autorises"),
                         exceptions_flottants=p.chemin("exceptions_flottants"))
        self.p = p

    def acteurs_poses(self):
        """Boites telles que l'editeur les pose (config/bornes_devices.json), pas telles que declarees."""
        mini = BORNES["primitives"]["min_uu"]
        spawns = {(lire_json(c).get("spawn") or {}).get("id") for c in self.p.plans()}
        env_cat = set(self.p.pose.get("categories_en_dernier", []))
        env_pre = tuple(x.upper() for x in self.p.pose.get("prefixes_en_dernier", []))
        for iid, it in self.placements().items():
            if self.sans_env and (it.get("categorie") in env_cat or (env_pre and iid.upper().startswith(env_pre))):
                continue
            m, sup, _ = methode(it)
            d = it.get("dimensions_uu") or {}
            x, y, z = it["position"]
            rot = it.get("rotation_degres", [0, 0, 0])
            if m == "cube":
                try:
                    segs = decouper(it, self.p.pose["portee_max_primitive_uu"], self.p.pose["z_min_primitive_uu"])
                except ValueError:
                    continue
                segs = [(sx, sy, sz, max(dx, mini), max(dy, mini), dz) for sx, sy, sz, dx, dy, dz in segs]
            elif m == "cylindre":  # Z minimum centre (pas de regle surface/objet a la pose)
                segs = [(x, y, z, max(d.get("X", 100), mini), max(d.get("Y", 100), mini), max(d.get("Z", 100), mini))]
            elif (str(it.get("support") or ("PID_CP_Devices_PlayerSpawner" if iid in spawns else "")) in BORNES["devices"]
                  or (m == "asset" and sup in BORNES.get("assets", {}))):
                # le spawn est declare a part, sans support : pose_lot lui donne le PlayerSpawner ;
                # un asset du pack a les bornes MESUREES (spike mesurer-assets), pas les dimensions declarees
                b = (BORNES["assets"][sup] if m == "asset"
                     else BORNES["devices"][str(it.get("support") or "PID_CP_Devices_PlayerSpawner")])
                c = [(lo + hi) / 2 for lo, hi in zip(b["min"], b["max"])]
                ya = math.radians(float(rot[1]))
                cx, cy = c[0] * math.cos(ya) - c[1] * math.sin(ya), c[0] * math.sin(ya) + c[1] * math.cos(ya)
                segs = [(x + cx, y + cy, z + c[2]) + tuple(hi - lo for lo, hi in zip(b["min"], b["max"]))]
            else:
                segs = [(x, y, z, d.get("X", 100), d.get("Y", 100), d.get("Z", 100))]
            for k, (x, y, z, dx, dy, dz) in enumerate(segs):
                yield "plan", {"id_placement": iid, "segment": k, "bounds": aabb_tournee(x, y, z, dx, dy, dz, rot)}


def aabb_tournee(x, y, z, dx, dy, dz, rot):
    """AABB monde d'une boite tournee (pitch autour de Y, yaw autour de Z, roll autour de X),
    comme get_actor_bounds la renverra : une rampe inclinee couvre bien un intervalle de Z."""
    import math
    p, ya, r = (math.radians(float(v)) for v in rot)
    cp, sp, cy, sy, cr, sr = math.cos(p), math.sin(p), math.cos(ya), math.sin(ya), math.cos(r), math.sin(r)
    pts = []
    for ex in (-dx / 2, dx / 2):
        for ey in (-dy / 2, dy / 2):
            for ez in (-dz / 2, dz / 2):
                y1, z1 = ey * cr - ez * sr, ey * sr + ez * cr          # roll (X)
                x2, z2 = ex * cp + z1 * sp, -ex * sp + z1 * cp         # pitch (Y)
                x3, y3 = x2 * cy - y1 * sy, x2 * sy + y1 * cy          # yaw (Z)
                pts.append((x + x3, y + y3, z + z2))
    mn = [min(q[i] for q in pts) for i in range(3)]
    mx = [max(q[i] for q in pts) for i in range(3)]
    return {"min": dict(zip("xyz", mn)), "max": dict(zip("xyz", mx))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projet")
    ap.add_argument("--detail", action="store_true")
    a = ap.parse_args(argv)
    p = Projet(a.projet)
    ctx = ContextePlan(p)
    res = [regles.v_zero_overlap(ctx).resultat(), regles.v_zero_flottant(ContextePlan(p, sans_environnement=True)).resultat(),
           regles.v_accessibilite(ctx).resultat()]
    print(json.dumps({r["validateur"]: {"verdict": r["verdict"], "violations": r["nb_violations"],
                                        "exemples": [v["detail"] for v in r["violations"][:(50 if a.detail else 6)]]}
                      for r in res}, ensure_ascii=False, indent=1))
    print("NB : boites telles que posees : primitives >= 256 uu par axe, devices aux bornes relues (config/bornes_devices.json).")
    return 0 if all(r["verdict"] == "PASS" for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
