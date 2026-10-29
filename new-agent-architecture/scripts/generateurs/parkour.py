# -*- coding: utf-8 -*-
"""Parcours de plateformes : depart (spawn), chaine montante, checkpoints reguliers, arrivee.
Les ecarts et montees ne depassent JAMAIS les capacites du profil (validation) : par defaut ce
sont celles de la marche, donc surement franchissables. Mesurer le vrai saut en playtest
puis l'augmenter dans le projet pour un parcours plus exigeant."""
import math

DEFAUTS = {"plateformes": 30, "checkpoint_tous_les": 8, "taille_plateforme_uu": 400,
           "ecart_uu": None, "montee_uu": None, "virage_max_deg": 50, "graine": 3}


def generer(plan, p, profil_validation):
    ecart = p["ecart_uu"] or profil_validation["saut_horizontal_max_uu"] * 0.9
    montee = p["montee_uu"] or profil_validation["marche_max_uu"] * 0.9
    ecart = min(ecart, profil_validation["saut_horizontal_max_uu"])
    montee = min(montee, profil_validation["marche_max_uu"])
    s = p["taille_plateforme_uu"]
    x, y, z, cap = 0.0, 0.0, 0.0, 0.0
    plan.dalle("S0_DEPART", "S0", x, y, z, 1200, 1200)
    plan.spawn("SPAWN_DEPART", "S0", x, y, z)
    demi_prec = 600  # demi-largeur de la dalle de depart
    occupees = [(0.0, 0.0, 1200)]
    for k in range(1, p["plateformes"] + 1):
        dernier = k == p["plateformes"]
        taille = s * (2 if dernier else 1)
        pas = demi_prec + ecart + taille / 2
        # direction : virage aleatoire borne ; si on sortirait du niveau ou recouvrirait une
        # plateforme deja posee, on essaie d'autres caps (jamais de "tassement" contre le bord)
        for essai in range(60):
            amplitude = p["virage_max_deg"] if essai < 20 else 180
            c = cap + math.radians(plan.rnd.uniform(-amplitude, amplitude))
            nx, ny = x + math.cos(c) * pas, y + math.sin(c) * pas
            dedans = (plan.bornes["x"][0] + 1000 < nx < plan.bornes["x"][1] - 1000 and
                      plan.bornes["y"][0] + 1000 < ny < plan.bornes["y"][1] - 1000)
            libre = all(abs(nx - px) > (taille + pt) / 2 + ecart / 2 or abs(ny - py) > (taille + pt) / 2 + ecart / 2
                        for px, py, pt in occupees[:-1])
            if dedans and libre:
                break
        else:
            raise ValueError("parcours bloque a la plateforme %d : reduire 'plateformes' ou agrandir le niveau" % k)
        cap, x, y = c, nx, ny
        z += montee
        occupees.append((x, y, taille))
        strate = "S%d" % min(4, int(z // 1000))
        if dernier:
            iid = "%s_ARRIVEE" % strate
        elif k % p["checkpoint_tous_les"] == 0:
            iid = "%s_CHECKPOINT_%02d" % (strate, k // p["checkpoint_tous_les"])
        else:
            iid = "%s_PLATEFORME_%02d" % (strate, k)
        plan.dalle(iid, strate, x, y, z, taille, taille, categorie="plancher")
        demi_prec = taille / 2
    plan.flottant_voulu("*_PLATEFORME_*", "plateforme de parkour suspendue (design du parcours)")
    plan.flottant_voulu("*_CHECKPOINT_*", "plateforme checkpoint suspendue (design du parcours)")
    plan.flottant_voulu("*_ARRIVEE", "plateforme d'arrivee suspendue (design du parcours)")
    return plan
