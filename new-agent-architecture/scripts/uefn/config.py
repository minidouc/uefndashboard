# -*- coding: utf-8 -*-
"""Chargement de la configuration studio + projet. Aucune valeur inventee : une cle
absente leve une erreur explicite plutot qu'un defaut silencieux."""
import json
import os
import time

STUDIO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(STUDIO, "config")


def lire_json(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def ecrire_json(chemin, doc):
    os.makedirs(os.path.dirname(os.path.abspath(chemin)), exist_ok=True)
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    os.replace(tmp, chemin)  # ecriture atomique : jamais de JSON tronque
    return chemin


def maintenant():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def fusion(base, dessus):
    """Fusion recursive : le projet surcharge son profil cle par cle (listes remplacees)."""
    out = dict(base)
    for k, v in dessus.items():
        out[k] = fusion(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def charger_avec_profil(cfg_projet):
    """Un projet = un profil de map (exploration, arene, parkour...) + ses propres reglages."""
    nom = cfg_projet.get("profil")
    if not nom:
        return cfg_projet
    chemin = os.path.join(CONFIG_DIR, "profils", "%s.json" % nom)
    if not os.path.exists(chemin):
        raise SystemExit("Profil inconnu : %s (profils : %s)" % (nom, sorted(
            f[:-5] for f in os.listdir(os.path.join(CONFIG_DIR, "profils")))))
    return fusion(lire_json(chemin), cfg_projet)


class Projet:
    """Vue sur un projet : chemins resolus depuis config/projects/<slug>.json."""

    def __init__(self, slug=None):
        self.studio = lire_json(os.path.join(CONFIG_DIR, "studio.json"))
        slug = slug or os.environ.get("STUDIO_PROJET") or self.studio["projet_actif"]
        chemin = os.path.join(CONFIG_DIR, "projects", "%s.json" % slug)
        if not os.path.exists(chemin):
            raise SystemExit("Projet inconnu : %s (attendu %s)" % (slug, chemin))
        self.cfg = charger_avec_profil(lire_json(chemin))
        self.slug = slug
        self.root = self.cfg["root"]
        self.uefn = self.cfg["uefn"]
        self.pose = self.cfg["pose"]
        self.ram = self.cfg["ram_gate"]
        self.validation = self.cfg["validation"]

    def chemin(self, cle):
        return os.path.join(self.root, self.cfg["chemins"][cle])

    @property
    def build_dir(self):
        return self.chemin("build_dir")

    @property
    def state_dir(self):
        return self.chemin("state_dir")

    def plans(self):
        """Plan principal + plans supplementaires (ex. delta nuit), chemins absolus."""
        sup = self.cfg["chemins"].get("placements_supplementaires", [])
        return [self.chemin("placements")] + [os.path.join(self.root, s) for s in sup]

    def level_ref(self, nom_acteur):
        return self.uefn["level_ref_prefix"] + nom_acteur
