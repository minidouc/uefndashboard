# -*- coding: utf-8 -*-
"""
make_golden.py -- genere le GOLDEN SET des validateurs (WP4 p.26 : "Creating the Golden Set").

Un cas = un mini-projet complet (placements, lot, reponses MCP brutes, captures).
  - 'sain' et ses variantes legitimes DOIVENT passer ;
  - chaque cas piege DOIT etre rejete par la regle listee dans attendus.json.
run_all.py rejoue ce jeu AVANT toute validation reelle : un validateur qu'on aurait affaibli
(ex. corpo-plaza : chevauchement force a True) est detecte immediatement.

Action HUMAINE : apres generation, relancer tools/lock_validators.py.
"""
import copy
import json
import os
import random
import shutil
import sys

from PIL import Image, ImageDraw

STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLDEN = os.path.join(STUDIO, "validators", "golden")
PREFIX = "/Game/Golden.Golden:PersistentLevel."

# id, strate, categorie, bounds (min xyz, max xyz)
SCENE = [
    ("S0_SOL", "S0", "plancher", (-2000, -2000, -100), (2000, 2000, 0)),
    ("SPAWN_S0", "S0", "poi", (-50, -50, 0), (50, 50, 100)),
    ("S0_RAMPE_1", "S0", "connecteur", (1000, -200, 0), (2000, 200, 500)),
    ("S1_PLANCHER", "S1", "plancher", (2000, -1000, 400), (3000, 1000, 500)),
    ("S0_POTEAU", "S0", "structure", (-1000, 500, 0), (-900, 600, 800)),
    ("S0_LUM_1", "S0", "signalisation", (500, 1500, 1200), (550, 1550, 1250)),
]
EXCEPTIONS_FLOTTANTS = {"exceptions": [{"motif": "*_LUM_*", "justification": "lumiere ponctuelle suspendue"}]}
BASELINE = ["PRE_1", "PRE_2"]


def bornes(mn, mx):
    return {"min": dict(zip("xyz", mn)), "max": dict(zip("xyz", mx)), "isValid": True}


def item_plan(iid, strate, cat, mn, mx):
    centre = [(a + b) / 2 for a, b in zip(mn, mx)]
    return {"id": iid, "strate": strate, "categorie": cat, "position": centre,
            "rotation_degres": [0, 0, 0], "support": "PrimitiveTools.add_cube",
            "dimensions_uu": {"X": mx[0] - mn[0], "Y": mx[1] - mn[1], "Z": mx[2] - mn[2]}}


def png(chemin, mode):
    rnd = random.Random(42)
    if mode == "uniforme":
        Image.new("RGB", (640, 360), (40, 52, 70)).save(chemin)
        return
    fond = (12, 16, 30) if mode == "nuit" else (225, 228, 232)
    im = Image.new("RGB", (640, 360), fond)
    d = ImageDraw.Draw(im)
    for _ in range(140):
        x, y = rnd.randint(0, 600), rnd.randint(0, 330)
        w, h = rnd.randint(8, 60), rnd.randint(8, 90)
        if mode == "nuit":
            c = rnd.choice([(34, 230, 255), (255, 43, 214), (40, 50, 80), (70, 80, 110)])
        else:
            c = rnd.choice([(200, 205, 210), (150, 160, 170), (240, 240, 240), (180, 190, 200)])
        d.rectangle([x, y, x + w, y + h], fill=c)
    im.save(chemin)


class Cas:
    def __init__(self, nom):
        self.nom = nom
        self.scene = [list(s) for s in SCENE]
        self.mutations_lot = []      # fonctions (lot, dir) appliquees apres generation
        self.trouver = BASELINE[:]
        self.save_rc = 0
        self.captures = {"S0": "nuit", "nuit_S0": "nuit"}
        self.overlaps = {"autorises": []}
        self.hors_plan = set()

    def generer(self):
        d = os.path.join(GOLDEN, "cas", self.nom)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(os.path.join(d, "calls"))
        os.makedirs(os.path.join(d, "lots"))
        os.makedirs(os.path.join(d, "captures"))
        seq = [0]

        def preuve(outil, args, valeur, rc=0):
            seq[0] += 1
            rel = "calls/%04d.json" % seq[0]
            ecrire(os.path.join(d, rel), {"outil": outil, "rc": rc, "args": args,
                                          "payload": {"returnValue": valeur}})
            return rel

        plan = [item_plan(*s) for s in self.scene if s[0] not in self.hors_plan]
        ecrire(os.path.join(d, "placements.json"), {"placements": plan})
        acteurs = []
        for iid, _, _, mn, mx in self.scene:
            ref = PREFIX + "CP_" + iid
            acteurs.append({
                "id_placement": iid, "segment": 0, "refPath": ref, "statut": "POSE",
                "support_prevu": "PrimitiveTools.add_cube", "support_reel": "PrimitiveTools.add_cube",
                "preuve_pose": preuve("SceneTools.add_to_scene_from_class", {"name": "CP_" + iid}, {"refPath": ref}),
                "preuve_bounds": preuve("ActorTools.get_actor_bounds", {"actor": {"refPath": ref}}, bornes(mn, mx)),
                "bounds": bornes(mn, mx)})
        noms = self.trouver + ["CP_" + s[0] for s in self.scene]
        lot = {"$schema": "studio.lot.v2", "lot_id": "lot_01", "statut": "POSE_TERMINEE",
               "acteurs": acteurs, "gaps": [],
               "cloture": {
                   "save": {"preuve": preuve("AssetTools.save_assets", {"asset_paths": ["/Game/Golden"]},
                                             self.save_rc == 0, rc=self.save_rc)},
                   "is_dirty": {"preuve": preuve("AssetTools.is_dirty", {"asset_path": "/Game/Golden"}, False)},
                   "bornes_niveau": {"preuve": preuve("ActorTools.get_actor_bounds",
                                                      {"actor": {"refPath": PREFIX + "LevelBounds_0"}},
                                                      bornes((-12800, -12800, -256), (12800, 12800, 9000)))},
                   "find_actors": {"preuve": preuve("SceneTools.find_actors", {"name": ""},
                                                    [{"name": n} for n in noms])}}}
        index = {}
        for nom, mode in self.captures.items():
            chemin = "captures/%s.png" % nom
            png(os.path.join(d, chemin), mode)
            loc = {"x": -1500.0, "y": 0.0, "z": 300.0}
            index[nom] = {"png": chemin, "lot": "lot_01", "camera_demandee": {"location": loc},
                          "preuve_camera": preuve("EditorAppToolset.GetCameraTransform", {},
                                                  {"location": loc, "rotation": {"pitch": -5, "yaw": 0, "roll": 0}})}
        for m in self.mutations_lot:
            m(lot, d)
        ecrire(os.path.join(d, "lots", "lot_01.json"), lot)
        ecrire(os.path.join(d, "captures", "index.json"), index)
        ecrire(os.path.join(d, "baseline_preexistants.json"), {"noms": BASELINE})
        ecrire(os.path.join(d, "overlaps_autorises.json"), self.overlaps)
        ecrire(os.path.join(d, "exceptions_flottants.json"), EXCEPTIONS_FLOTTANTS)


def ecrire(chemin, doc):
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)


def acteur(lot, iid):
    return next(a for a in lot["acteurs"] if a["id_placement"] == iid)


def main():
    cas, attendus = [], {}

    c = Cas("sain"); cas.append(c); attendus[c.nom] = []

    c = Cas("chevauchement_justifie")
    c.scene.append(["S0_CAISSE", "S0", "decor", (-980, 520, 0), (-920, 580, 100)])
    c.overlaps = {"autorises": [{"a": "S0_CAISSE", "b": "S0_POTEAU", "justification": "caisse adossee au poteau (design)"}]}
    cas.append(c); attendus[c.nom] = []

    def releve_groupee(sauf=None):
        def m(lot, d):
            entrees = [{"name": a["refPath"].split(".")[-1], "actorPath": a["refPath"], "bounds": a["bounds"]}
                       for a in lot["acteurs"] if a["id_placement"] != sauf]
            ecrire(os.path.join(d, "calls", "releve_lot.json"),
                   {"outil": "SceneTools.find_actors", "rc": 0, "args": {"name": ""},
                    "payload": {"returnValue": entrees}})
            for a in lot["acteurs"]:
                a["preuve_bounds"] = "calls/releve_lot.json"
        return m

    c = Cas("sain_releve_groupee"); c.mutations_lot.append(releve_groupee())
    cas.append(c); attendus[c.nom] = []

    c = Cas("releve_groupee_acteur_absent"); c.mutations_lot.append(releve_groupee(sauf="S0_POTEAU"))
    cas.append(c); attendus[c.nom] = ["integrite_preuves"]

    c = Cas("bornes_falsifiees")
    def falsifier(lot, d):
        acteur(lot, "S0_POTEAU")["bounds"]["max"]["z"] = 300
    c.mutations_lot.append(falsifier)
    cas.append(c); attendus[c.nom] = ["integrite_preuves"]

    c = Cas("acteur_non_relu")
    def non_relu(lot, d):
        a = acteur(lot, "S0_POTEAU"); a["statut"] = "NON_RELU"; a["preuve_bounds"] = None
    c.mutations_lot.append(non_relu)
    cas.append(c); attendus[c.nom] = ["integrite_preuves"]

    c = Cas("lot_interrompu")
    c.mutations_lot.append(lambda lot, d: lot.update(statut="INTERROMPU"))
    cas.append(c); attendus[c.nom] = ["integrite_preuves"]

    c = Cas("chevauchement")
    c.scene.append(["S0_CAISSE", "S0", "decor", (-980, 520, 0), (-920, 580, 100)])
    cas.append(c); attendus[c.nom] = ["zero_overlap"]

    c = Cas("exception_sans_justification")
    c.scene.append(["S0_CAISSE", "S0", "decor", (-980, 520, 0), (-920, 580, 100)])
    c.overlaps = {"autorises": [{"a": "S0_CAISSE", "b": "S0_POTEAU", "justification": ""}]}
    cas.append(c); attendus[c.nom] = ["zero_overlap"]

    c = Cas("flottant")
    c.scene.append(["S0_ENSEIGNE", "S0", "signalisation", (0, 1500, 1500), (100, 1600, 1600)])
    cas.append(c); attendus[c.nom] = ["zero_flottant"]

    c = Cas("groupe_flottant")
    c.scene.append(["S0_BLOC_A", "S0", "decor", (0, 1500, 1500), (100, 1600, 1600)])
    c.scene.append(["S0_BLOC_B", "S0", "decor", (0, 1500, 1600), (100, 1600, 1700)])
    cas.append(c); attendus[c.nom] = ["zero_flottant"]

    c = Cas("inaccessible")
    c.scene[3] = ["S1_PLANCHER", "S1", "plancher", (2000, -1000, 1400), (3000, 1000, 1500)]
    c.scene.append(["S1_PILIER", "S1", "structure", (2400, -100, 0), (2600, 100, 1400)])
    cas.append(c); attendus[c.nom] = ["accessibilite"]

    c = Cas("preexistant_supprime"); c.trouver = ["PRE_1"]
    cas.append(c); attendus[c.nom] = ["preexistants_intacts"]

    c = Cas("save_echoue"); c.save_rc = 1
    cas.append(c); attendus[c.nom] = ["persistance"]

    c = Cas("improvisation")
    c.scene.append(["S0_INVENTE", "S0", "decor", (-500, -500, 0), (-400, -400, 100)])
    c.hors_plan.add("S0_INVENTE")
    cas.append(c); attendus[c.nom] = ["source_coordonnees"]

    c = Cas("item_oublie")
    c.mutations_lot.append(lambda lot, d: lot["acteurs"].pop())
    cas.append(c); attendus[c.nom] = ["couverture_plan"]

    c = Cas("capture_mur"); c.captures = {"S0": "uniforme", "nuit_S0": "nuit"}
    cas.append(c); attendus[c.nom] = ["captures_visuelles"]

    c = Cas("nuit_en_plein_jour"); c.captures = {"S0": "nuit", "nuit_S0": "jour"}
    cas.append(c); attendus[c.nom] = ["captures_visuelles"]

    c = Cas("spawn_non_pose")
    c.mutations_lot.append(lambda lot, d: lot.update(acteurs=[a for a in lot["acteurs"] if a["id_placement"] != "SPAWN_S0"]))
    cas.append(c); attendus[c.nom] = ["gameplay"]

    c = Cas("capture_absente"); c.captures = {"S0": "nuit"}
    cas.append(c); attendus[c.nom] = ["captures_visuelles"]

    # le plan met le poteau ailleurs que la ou l'editeur le relit
    c = Cas("deplace_hors_plan")
    def plan_ailleurs(lot, d):
        p = os.path.join(d, "placements.json")
        doc = json.load(open(p, encoding="utf-8"))
        for it in doc["placements"]:
            if it["id"] == "S0_POTEAU":
                it["position"] = [1500, 1500, 400]
        ecrire(p, doc)
    c.mutations_lot.append(plan_ailleurs)
    cas.append(c); attendus[c.nom] = ["source_coordonnees"]

    for x in cas:
        x.generer()
    ecrire(os.path.join(GOLDEN, "attendus.json"), {"cas": attendus})
    ecrire(os.path.join(GOLDEN, "config_golden.json"), {
        "level_ref_prefix": PREFIX,
        "bornes": {"x": [-12800, 12800], "y": [-12800, 12800], "z": [-256, 9000]},
        "validation": {"tolerance_contact_uu": 5, "sol_z_uu": -100, "marche_max_uu": 120,
                       "saut_horizontal_max_uu": 200, "categories_praticables": ["plancher", "connecteur"],
                       "mots_non_praticables": ["GARDE", "RAIL", "MONTANT"],
                       "mots_connecteurs_verticaux": ["RAMPE", "ECHELLE", "GAINE", "ESCALIER", "ASCENSEUR"],
                       "gameplay_requis": [{"nom": "spawn", "motif": "SPAWN*", "min": 1}]},
        "captures_requises": {"S0": {}, "nuit_S0": {"luminance_max": 90, "couleurs_min": {"#22E6FF+#FF2BD6": 0.02}}},
        "seuils_visuels": {"contraste_min": 12, "bords_min": 4, "ecart_camera_max_uu": 100}})
    print("golden genere : %d cas -> %s" % (len(cas), GOLDEN))
    print("ACTION HUMAINE : relancer tools/lock_validators.py")


if __name__ == "__main__":
    sys.exit(main())
