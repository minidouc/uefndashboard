# -*- coding: utf-8 -*-
"""Arene de combat symetrique : sol, murs d'enceinte, spawns par equipe, couverts en miroir,
plateformes laterales surelevees avec rampes."""
DEFAUTS = {"taille_uu": 8000, "equipes": 2, "joueurs_par_equipe": 4, "couverts_par_moitie": 6,
           "plateformes_laterales": True, "hauteur_plateforme_uu": 600, "hauteur_murs_uu": 800, "graine": 7}


def generer(plan, p):
    t, h_mur = p["taille_uu"], p["hauteur_murs_uu"]
    demi = t / 2
    plan.dalle("S0_SOL", "S0", 0, 0, 0, t, t)
    for nom, x, y, lx, ly in (("NORD", 0, demi + 128, t + 512, 256), ("SUD", 0, -demi - 128, t + 512, 256),
                              ("EST", demi + 128, 0, 256, t), ("OUEST", -demi - 128, 0, 256, t)):
        plan.bloc("S0_MUR_" + nom, "S0", "structure", x, y, 0, lx, ly, h_mur)
    # spawns : une ligne par equipe, face a face (equipe A a l'ouest, B a l'est)
    n = p["joueurs_par_equipe"]
    for e, (x, yaw) in enumerate(((-demi + 600, 0), (demi - 600, 180))):
        for k in range(n):
            y = -demi * 0.6 + k * (1.2 * demi / max(1, n - 1))
            plan.spawn("SPAWN_E%d_%d" % (e + 1, k + 1), "S0", x, y, 0, yaw=yaw)
    # couverts : tires dans la moitie ouest (zone centrale libre, sans recouvrement), puis miroir
    poses, essais = [], 0
    while len(poses) < p["couverts_par_moitie"] and essais < 2000:
        essais += 1
        lx, ly = plan.rnd.choice((200, 400)), plan.rnd.choice((400, 800))
        x = plan.rnd.uniform(-demi + 1400, -500)
        y = plan.rnd.uniform(-demi + 600, demi - 600)
        if all(abs(x - a) > (lx + la) / 2 + 300 or abs(y - b) > (ly + lb) / 2 + 300 for a, b, la, lb in poses):
            poses.append((x, y, lx, ly))
    for k, (x, y, lx, ly) in enumerate(poses):
        hz = plan.rnd.choice((256, 400, 600))  # >= 256 : minimum d'une primitive
        plan.bloc("S0_COUVERT_O%d" % (k + 1), "S0", "structure", x, y, 0, lx, ly, hz)
        plan.bloc("S0_COUVERT_E%d" % (k + 1), "S0", "structure", -x, y, 0, lx, ly, hz)
    if p["plateformes_laterales"]:
        hp = p["hauteur_plateforme_uu"]
        for cote, sy in (("N", 1), ("S", -1)):
            yc = sy * (demi - 500)
            plan.dalle("S1_PLATEFORME_" + cote, "S1", 0, yc, hp, 2400, 800)
            # pilier sous la plateforme (pas de flottant) et rampe d'acces depuis le sol
            plan.bloc("S0_PILIER_" + cote, "S0", "structure", 0, yc, 0, 400, 400, hp - 256)
            plan.rampe("S1_RAMPE_" + cote, "S1", -1200 - hp * 4, yc, 0, -1200, yc, hp, 400,
                       relie=("S0_SOL", "S1_PLATEFORME_" + cote))
    return plan
