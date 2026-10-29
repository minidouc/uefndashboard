# -*- coding: utf-8 -*-
"""Quartier urbain vertical : grille de blocs, tours de hauteurs variees, rues praticables,
passerelles aeriennes entre tours avec une rampe d'acces depuis la rue."""
DEFAUTS = {"blocs_x": 3, "blocs_y": 3, "taille_bloc_uu": 2400, "largeur_rue_uu": 1200,
           "hauteur_min_uu": 1500, "hauteur_max_uu": 6000, "passerelles": 3,
           "hauteur_passerelle_uu": 700, "graine": 11}


def generer(plan, p):
    b, r = p["taille_bloc_uu"], p["largeur_rue_uu"]
    pas = b + r
    nx, ny = p["blocs_x"], p["blocs_y"]
    lx, ly = nx * pas + r, ny * pas + r
    plan.dalle("S0_RUE", "S0", 0, 0, 0, lx, ly)
    x0, y0 = -lx / 2 + r + b / 2, -ly / 2 + r + b / 2
    tours = {}
    for i in range(nx):
        for j in range(ny):
            h = plan.rnd.randrange(p["hauteur_min_uu"], p["hauteur_max_uu"] + 1, 250)
            cx, cy = x0 + i * pas, y0 + j * pas
            plan.bloc("S0_TOUR_%d_%d" % (i, j), "S0", "structure", cx, cy, 0, b, b, h)
            tours[(i, j)] = (cx, cy, h)
    plan.spawn("SPAWN_RUE", "S0", -lx / 2 + r / 2, -ly / 2 + r / 2, 0, yaw=45)
    # passerelles : entre deux tours voisines en X, au-dessus de la rue ; rampe depuis la rue
    hp = p["hauteur_passerelle_uu"]
    candidats = [(i, j) for i in range(nx - 1) for j in range(ny)
                 if tours[(i, j)][2] > hp + 300 and tours[(i + 1, j)][2] > hp + 300]
    plan.rnd.shuffle(candidats)
    for k, (i, j) in enumerate(candidats[:p["passerelles"]]):
        cx = (tours[(i, j)][0] + tours[(i + 1, j)][0]) / 2
        cy = tours[(i, j)][1]
        larg = 400
        plan.dalle("S1_PASSERELLE_%d" % (k + 1), "S1", cx, cy, hp, r, larg, categorie="plancher")
        # rampe le long de la rue (axe Y), qui arrive sous l'extremite de la passerelle
        y_haut = cy - larg / 2
        long_ = hp * 4
        plan.rampe("S1_RAMPE_%d" % (k + 1), "S1", cx, y_haut - long_, 0, cx, y_haut, hp, min(400, r - 200),
                   relie=("S0_RUE", "S1_PASSERELLE_%d" % (k + 1)))
        # les passerelles s'appuient sur les tours (contact lateral) : pas de flottant
        plan.overlaps_autorises.append({"a": "S1_PASSERELLE_%d" % (k + 1), "b": "S0_TOUR_*",
                                        "justification": "passerelle encastree dans les facades"})
    return plan
