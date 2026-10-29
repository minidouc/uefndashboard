# -*- coding: utf-8 -*-
"""
Briques communes des generateurs de plan. Un generateur = une fonction qui recoit ~10
parametres (choisis par le modele) et produit TOUT placements.json par calcul.
Le modele ne voit jamais une coordonnee.

Conventions (alignees sur pose_lot.py et les validateurs) :
  - position = CENTRE de la boite ; dimensions en uu (100 uu = 1 m) ;
  - epaisseur des dalles = 256 uu (minimum d'une primitive) : la face du dessus est la cote voulue ;
  - rotation [pitch, yaw, roll] en degres, convention Unreal : pitch positif = l'avant (X) monte.
    A CONFIRMER visuellement a la premiere rampe posee (capture) : c'est la seule convention
    que les validateurs ne peuvent pas voir (une AABB est la meme pour +pitch et -pitch).
  - 'strate' = zone ou niveau de jeu (S0 = sol, S1, S2... par altitude) ;
  - categories : plancher, connecteur, structure, poi, decor, signalisation, environnement.
"""
import json
import math
import random

EP = 256  # epaisseur standard d'une dalle (= minimum de primitive : aucun rehaussement)
SPAWN = "PID_CP_Devices_PlayerSpawner"
CUBE = "PrimitiveTools.add_cube"


class Plan:
    def __init__(self, projet, bornes, graine=1):
        self.projet = projet
        self.bornes = bornes
        self.items = []
        self.exceptions_flottants = []
        self.overlaps_autorises = []
        self.rnd = random.Random(graine)
        self._ids = set()

    # ------------------------------------------------------------------ primitives
    def ajouter(self, iid, strate, categorie, centre, dims, support=CUBE, rot=(0, 0, 0), **extra):
        if iid in self._ids:
            raise ValueError("id en double : %s" % iid)
        self._ids.add(iid)
        it = {"id": iid, "strate": strate, "categorie": categorie,
              "position": [round(c, 1) for c in centre], "rotation_degres": [round(r, 2) for r in rot],
              "support": support, "dimensions_uu": {"X": round(dims[0], 1), "Y": round(dims[1], 1), "Z": round(dims[2], 1)}}
        it.update(extra)
        self.items.append(it)
        return it

    def dalle(self, iid, strate, x, y, z_dessus, lx, ly, categorie="plancher", **extra):
        """Surface praticable dont le DESSUS est a z_dessus."""
        return self.ajouter(iid, strate, categorie, (x, y, z_dessus - EP / 2), (lx, ly, EP), **extra)

    def bloc(self, iid, strate, categorie, x, y, z_bas, lx, ly, hz, **extra):
        """Volume pose AU SOL a z_bas (mur, tour, couvert, caisse)."""
        return self.ajouter(iid, strate, categorie, (x, y, z_bas + hz / 2), (lx, ly, hz), **extra)

    def rampe(self, iid, strate, x0, y0, z0, x1, y1, z1, largeur, relie=(), **extra):
        """Rampe praticable du point (x0,y0,z0) au point (x1,y1,z1) (cotes = dessus).
        relie : ids (ou motifs) des surfaces raccordees ; le raccord penetre ces surfaces par
        construction, il est donc declare comme chevauchement voulu (avec justification)."""
        for cible in relie:
            self.overlaps_autorises.append({"a": iid, "b": cible, "justification": "raccord de rampe sur %s" % cible})
        dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
        horiz = math.hypot(dx, dy)
        long_ = math.hypot(horiz, dz)
        pitch = math.degrees(math.atan2(dz, horiz))
        yaw = math.degrees(math.atan2(dy, dx))
        cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2 - EP / 2 * math.cos(math.radians(pitch))
        return self.ajouter(iid, strate, "connecteur", (cx, cy, cz), (long_, largeur, EP),
                            rot=(pitch, yaw, 0), **extra)

    def spawn(self, iid, strate, x, y, z_sol, yaw=0):
        return self.ajouter(iid, strate, "poi", (x, y, z_sol + 50), (100, 100, 100), support=SPAWN, rot=(0, yaw, 0))

    def flottant_voulu(self, motif, justification):
        self.exceptions_flottants.append({"motif": motif, "justification": justification})

    # ------------------------------------------------------------------ sortie
    def verifier_bornes(self):
        hors = []
        for it in self.items:
            for k, axe in enumerate("xyz"):
                d = it["dimensions_uu"]["XYZ"[k]] / 2
                lo, hi = self.bornes[axe]
                if it["position"][k] - d < lo - 1 or it["position"][k] + d > hi + 1:
                    hors.append(it["id"])
                    break
        return hors

    def ecrire(self, dossier_level, generateur, params):
        import os
        os.makedirs(dossier_level, exist_ok=True)
        hors = self.verifier_bornes()
        if hors:
            raise ValueError("items hors des bornes du niveau : %s" % hors[:10])
        doc = {"$schema": "uefn.placements.v1", "projet": self.projet, "unite": "uu (100 uu = 1 m)",
               "genere_par": generateur, "parametres": params, "bornes": self.bornes,
               "budget_acteurs": {"total_planifie": len(self.items)}, "placements": self.items, "gaps": []}
        ecrire(os.path.join(dossier_level, "placements.json"), doc)
        ecrire(os.path.join(dossier_level, "exceptions_flottants.json"),
               {"genere_par": generateur, "exceptions": self.exceptions_flottants})
        ecrire(os.path.join(dossier_level, "overlaps_autorises.json"),
               {"genere_par": generateur, "autorises": self.overlaps_autorises})
        return len(self.items)


def ecrire(chemin, doc):
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
