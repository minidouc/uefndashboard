# -*- coding: utf-8 -*-
"""Les regles d'acceptation, executables (WP4 p.20 : la validation est du code). FICHIER PROTEGE.

Chaque regle remonte aux preuves brutes. Aucune ne fait confiance a un champ declare.
"""
import fnmatch
import math
import os
from collections import deque

from ._commun import (STATUTS_LOT_VALIDABLES, Verdict, aabb, chevauchement_xy, contact,
                      egal_bounds, intersection_stricte)
from ._image import mesurer

OUTILS_POSE = {"SceneTools.add_to_scene_from_class", "SceneTools.add_to_scene_from_asset",
               "DeviceToolset.PlaceDevice"}


def _ok_preuve(pr, outil):
    return pr is not None and pr.get("outil") == outil and pr.get("rc") == 0


def _bornes_relues(pr, ref):
    """Bornes de l'acteur `ref` dans une preuve brute : get_actor_bounds individuel, ou
    find_actors groupe (une relecture par lot au lieu d'une par acteur). None si non prouve."""
    if _ok_preuve(pr, "ActorTools.get_actor_bounds"):
        if (pr.get("args") or {}).get("actor", {}).get("refPath") != ref:
            return None
        return (pr.get("payload") or {}).get("returnValue")
    if _ok_preuve(pr, "SceneTools.find_actors"):
        for e in (pr.get("payload") or {}).get("returnValue") or []:
            if isinstance(e, dict) and e.get("actorPath") == ref:
                return e.get("bounds")
    return None


# ------------------------------------------------------------------------------------------
def v_integrite(ctx):
    """Chaque acteur declare POSE a une preuve de pose ET une relecture de bornes identique."""
    v = Verdict("integrite_preuves")
    for lot in ctx.lots():
        lid = lot["lot_id"]
        if lot.get("statut") not in STATUTS_LOT_VALIDABLES:
            v.ko("statut de lot %s non validable" % lot.get("statut"), lid)
        for a in lot.get("acteurs", []):
            v.compte()
            ident = "%s#%s" % (a.get("id_placement"), a.get("segment", 0))
            if a.get("statut") != "POSE":
                v.ko("%s statut %s (non pose ou non relu)" % (ident, a.get("statut")), lid)
                continue
            pp = ctx.preuve(a.get("preuve_pose"))
            if pp is None or pp.get("outil") not in OUTILS_POSE or pp.get("rc") != 0:
                v.ko("%s : preuve de pose absente ou en erreur" % ident, lid)
            pb = ctx.preuve(a.get("preuve_bounds"))
            rv = _bornes_relues(pb, a.get("refPath"))
            if rv is None:
                v.ko("%s : relecture des bornes absente, en erreur ou portant sur un autre acteur" % ident, lid)
                continue
            if not egal_bounds(rv, a.get("bounds")):
                v.ko("%s : bornes declarees != bornes relues dans l'editeur (falsification ?)" % ident, lid)
            if not str(a.get("refPath", "")).startswith(ctx.level_ref_prefix):
                v.ko("%s : acteur hors du niveau cible" % ident, lid)
    return v


def v_persistance(ctx):
    """Save rc=0, niveau propre apres save, bornes du niveau relues apres save."""
    v = Verdict("persistance")
    for lot in ctx.lots():
        lid, c = lot["lot_id"], lot.get("cloture") or {}
        v.compte(3)
        ps = ctx.preuve((c.get("save") or {}).get("preuve"))
        if not _ok_preuve(ps, "AssetTools.save_assets") or not (ps.get("payload") or {}).get("returnValue"):
            v.ko("save du niveau non prouve", lid)
        pd = ctx.preuve((c.get("is_dirty") or {}).get("preuve"))
        if not _ok_preuve(pd, "AssetTools.is_dirty") or (pd.get("payload") or {}).get("returnValue") is not False:
            v.ko("niveau encore modifie apres save (is_dirty non prouve false)", lid)
        pb = ctx.preuve((c.get("bornes_niveau") or {}).get("preuve"))
        rv = (pb or {}).get("payload", {}) or {}
        rv = rv.get("returnValue") if isinstance(rv, dict) else None
        if not _ok_preuve(pb, "ActorTools.get_actor_bounds") or not rv:
            v.ko("bornes du niveau non relues apres save", lid)
        else:
            zmax_attendu = ctx.bornes["z"][1]
            if rv["max"]["z"] < zmax_attendu - 1:
                v.ko("bornes du niveau revenues a Z_max=%s (< %s attendu)" % (rv["max"]["z"], zmax_attendu), lid)
    return v


def _noms_acteurs(liste):
    noms = set()
    for x in liste or []:
        if isinstance(x, dict):
            noms.add(x.get("name") or x.get("actorName") or x.get("refPath"))
        else:
            noms.add(str(x))
    return noms


def v_preexistants(ctx):
    """Les acteurs presents AVANT le studio sont tous encore la, recalcule depuis find_actors."""
    v = Verdict("preexistants_intacts")
    base = ctx.json_optionnel(ctx.baseline_path, None)
    if not base:
        v.ko("baseline des preexistants absente (%s) : lancer preflight.py" % ctx.baseline_path)
        return v
    attendus = set(base["noms"])
    for lot in ctx.lots():
        lid = lot["lot_id"]
        pf = ctx.preuve(((lot.get("cloture") or {}).get("find_actors") or {}).get("preuve"))
        v.compte()
        if not _ok_preuve(pf, "SceneTools.find_actors"):
            v.ko("find_actors de cloture absent ou en erreur", lid)
            continue
        presents = _noms_acteurs((pf.get("payload") or {}).get("returnValue"))
        manquants = sorted(attendus - presents)
        if manquants:
            v.ko("%d preexistant(s) disparu(s) : %s" % (len(manquants), manquants[:5]), lid)
    return v


def v_source_coordonnees(ctx):
    """Tout acteur vient de placements.json ET se trouve la ou le plan le met (anti-improvisation)."""
    v = Verdict("source_coordonnees")
    pl = ctx.placements()
    for lid, a in ctx.acteurs_poses():
        v.compte()
        it = pl.get(a.get("id_placement"))
        if it is None:
            v.ko("%s absent de placements.json" % a.get("id_placement"), lid)
            continue
        b = aabb(a["bounds"])
        cx, cy, cz = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2
        px, py, pz = it["position"]
        d = it.get("dimensions_uu") or {}
        demi_diag = math.hypot(d.get("X", 0), d.get("Y", 0)) / 2
        if math.hypot(cx - px, cy - py) > demi_diag + 300:
            v.ko("%s pose a %.0f uu de sa position prevue" % (it["id"], math.hypot(cx - px, cy - py)), lid)
        if abs(cz - pz) > d.get("Z", 0) / 2 + 400:
            v.ko("%s : Z relu %.0f incompatible avec le plan (%.0f)" % (it["id"], cz, pz), lid)
    return v


def _regles_autorisees(chemin, ctx, v, cle):
    doc = ctx.json_optionnel(chemin, {cle: []})
    regles = []
    for r in doc.get(cle, []):
        if not str(r.get("justification", "")).strip():
            v.ko("exception sans justification ignoree : %s" % r)
            continue
        regles.append(r)
    return regles


def v_zero_overlap(ctx):
    """Aucune penetration de volumes entre items differents, hors exceptions justifiees du design."""
    v = Verdict("zero_overlap")
    eps = ctx.cfg["tolerance_contact_uu"]
    regles = _regles_autorisees(ctx.overlaps_path, ctx, v, "autorises")
    acteurs = list(ctx.acteurs_poses())
    for i in range(len(acteurs)):
        li, ai = acteurs[i]
        bi = aabb(ai["bounds"])
        for j in range(i + 1, len(acteurs)):
            lj, aj = acteurs[j]
            if ai["id_placement"] == aj["id_placement"]:
                continue
            v.compte()
            if not intersection_stricte(bi, aabb(aj["bounds"]), eps):
                continue
            x, y = ai["id_placement"], aj["id_placement"]
            if any((fnmatch.fnmatch(x, r["a"]) and fnmatch.fnmatch(y, r["b"])) or
                   (fnmatch.fnmatch(y, r["a"]) and fnmatch.fnmatch(x, r["b"])) for r in regles):
                continue
            v.ko("chevauchement %s / %s" % (x, y), lj)
    return v


def v_zero_flottant(ctx):
    """Chaque acteur est relie au sol par une chaine de contacts (un groupe qui ne touche que
    lui-meme flotte aussi). Exceptions justifiees du design : lumieres, ciel, post-process."""
    v = Verdict("zero_flottant")
    eps = ctx.cfg["tolerance_contact_uu"]
    sol = ctx.cfg["sol_z_uu"]
    regles = _regles_autorisees(ctx.flottants_path, ctx, v, "exceptions")
    acteurs = list(ctx.acteurs_poses())
    boites = [aabb(a["bounds"]) for _, a in acteurs]
    exempte = [any(fnmatch.fnmatch(a["id_placement"], r["motif"]) for r in regles) for _, a in acteurs]
    ancres = [i for i, b in enumerate(boites) if b[2] <= sol + eps]
    vus, file = set(ancres), deque(ancres)
    while file:
        i = file.popleft()
        for j in range(len(boites)):
            if j not in vus and not exempte[j] and contact(boites[i], boites[j], eps):
                vus.add(j)
                file.append(j)
    for i, (lid, a) in enumerate(acteurs):
        v.compte()
        if i not in vus and not exempte[i]:
            v.ko("%s flotte (z_min=%.0f, aucune chaine de contact vers le sol)" % (a["id_placement"], boites[i][2]), lid)
    return v


def v_accessibilite(ctx):
    """Depuis le spawn, on atteint chaque strate praticable en marchant (bornes RELUES, pas le plan)."""
    v = Verdict("accessibilite")
    cfg, pl = ctx.cfg, ctx.placements()
    marche, saut = cfg["marche_max_uu"], cfg["saut_horizontal_max_uu"]
    exclus = [m.upper() for m in cfg.get("mots_non_praticables", [])]
    vert = [m.upper() for m in cfg["mots_connecteurs_verticaux"]]

    def praticable(iid):
        it = pl.get(iid, {})
        return it.get("categorie") in cfg["categories_praticables"] and not any(m in iid.upper() for m in exclus)

    noeuds, spawn = [], None
    for _, a in ctx.acteurs_poses():
        if "SPAWN" in a["id_placement"].upper():
            spawn = aabb(a["bounds"])
        elif praticable(a["id_placement"]):
            rot = pl.get(a["id_placement"], {}).get("rotation_degres") or [0, 0, 0]
            incline = abs(float(rot[0])) > 1 or abs(float(rot[2])) > 1   # rampe/escalier par sa pente
            noeuds.append((a["id_placement"], aabb(a["bounds"]),
                           incline or any(m in a["id_placement"].upper() for m in vert)))
    requises = {it["strate"] for iid, it in pl.items() if praticable(iid)}
    v.compte(len(noeuds))
    if spawn is None:
        v.ko("spawn non pose ou non relu")
        return v

    def lien(u, w):
        (_, bu, cu), (_, bw, cw) = u, w
        if not chevauchement_xy(bu, bw, saut):
            return False
        if cu and cw:
            return bu[2] - marche <= bw[5] and bw[2] - marche <= bu[5]
        if cu:
            return bu[2] - marche <= bw[5] <= bu[5] + marche
        if cw:
            return bw[2] - marche <= bu[5] <= bw[5] + marche
        return abs(bu[5] - bw[5]) <= marche

    depart = [i for i, n in enumerate(noeuds)
              if chevauchement_xy(n[1], spawn, saut) and abs(n[1][5] - spawn[2]) <= marche]
    vus, file = set(depart), deque(depart)
    while file:
        i = file.popleft()
        for j in range(len(noeuds)):
            if j not in vus and lien(noeuds[i], noeuds[j]):
                vus.add(j)
                file.append(j)
    atteintes = {pl[noeuds[i][0]]["strate"] for i in vus}
    if not depart:
        v.ko("aucune surface praticable sous le spawn")
    for s in sorted(requises - atteintes):
        v.ko("strate %s inaccessible depuis le spawn" % s)
    return v


def v_couverture(ctx):
    """Tout item du plan est pose OU declare en gap justifie ; gaps <= 15 % (on ne reduit pas le scope)."""
    v = Verdict("couverture_plan")
    pl = ctx.placements()
    poses = {a["id_placement"] for _, a in ctx.acteurs_poses()}
    gaps = {}
    for lot in ctx.lots():
        for g in lot.get("gaps", []):
            if str(g.get("raison", "")).strip():
                gaps[g["id"]] = g["raison"]
    v.compte(len(pl))
    manquants = [i for i in pl if i not in poses and i not in gaps]
    if manquants:
        v.ko("%d item(s) ni poses ni declares en gap : %s" % (len(manquants), manquants[:8]))
    if pl and len([g for g in gaps if g not in poses]) > 0.15 * len(pl):
        v.ko("gaps > 15 %% du plan (%d/%d) : le scope se reduit" % (len(gaps), len(pl)))
    return v


def v_visuel(ctx):
    """Captures exploitables : existent, camera relue au bon endroit, image non uniforme, puis
    criteres MESURABLES propres a chaque capture, venus du brief du projet :
      {"luminance_max": 90, "luminance_min": 0, "couleurs_min": {"#22E6FF+#FF2BD6": 0.02}}
    (aucun style code en dur ; le gout reste a la critique visuelle)."""
    v = Verdict("captures_visuelles")
    idx = ctx.json_optionnel(ctx.captures_index_path, {})
    s = ctx.seuils
    requises = ctx.captures_requises
    if isinstance(requises, list):
        requises = {n: {} for n in requises}
    for nom, crit in requises.items():
        crit = crit or {}
        v.compte()
        e = idx.get(nom)
        if not e:
            v.ko("capture requise absente : %s" % nom)
            continue
        lid = e.get("lot")
        png = e.get("png")
        png = png if png and os.path.isabs(png) else os.path.join(ctx.root, png or "")
        if not os.path.exists(png) or os.path.getsize(png) == 0:
            v.ko("%s : PNG absent du disque" % nom, lid)
            continue
        pc = ctx.preuve(e.get("preuve_camera"))
        if not _ok_preuve(pc, "EditorAppToolset.GetCameraTransform"):
            v.ko("%s : position camera non relue" % nom, lid)
        else:
            loc = ((pc.get("payload") or {}).get("returnValue") or {}).get("location") or {}
            dem = e.get("camera_demandee", {}).get("location", {})
            try:
                ecart = math.dist([loc["x"], loc["y"], loc["z"]], [dem["x"], dem["y"], dem["z"]])
            except KeyError:
                ecart = float("inf")
            if ecart > s.get("ecart_camera_max_uu", 100):
                v.ko("%s : camera relue a %.0f uu de la position demandee" % (nom, ecart), lid)
        groupes = crit.get("couleurs_min", {})
        couleurs = sorted({c for g in groupes for c in g.split("+")})
        m = mesurer(png, couleurs)
        if m["contraste_std"] < s["contraste_min"] or m["densite_bords"] < s["bords_min"]:
            v.ko("%s : image quasi uniforme (contraste %.1f, bords %.1f) -> mur en gros plan ou vide"
                 % (nom, m["contraste_std"], m["densite_bords"]), lid)
        if "luminance_max" in crit and m["luminance_moy"] > crit["luminance_max"]:
            v.ko("%s : trop clair (luminance %.0f > %s)" % (nom, m["luminance_moy"], crit["luminance_max"]), lid)
        if "luminance_min" in crit and m["luminance_moy"] < crit["luminance_min"]:
            v.ko("%s : trop sombre (luminance %.0f < %s)" % (nom, m["luminance_moy"], crit["luminance_min"]), lid)
        for groupe, mini in groupes.items():
            frac = sum(m["couleurs"].get(c.upper(), 0) for c in groupe.split("+"))
            if frac < mini:
                v.ko("%s : couleurs %s trop rares (%.3f < %s)" % (nom, groupe, frac, mini), lid)
    return v


def v_gameplay(ctx):
    """Elements de jeu obligatoires du TYPE de map (profil) : ex. arene = >= 8 spawns,
    parkour = checkpoints. Compte les items POSES et RELUS, pas ceux du plan."""
    v = Verdict("gameplay")
    poses = {a["id_placement"] for _, a in ctx.acteurs_poses()}
    supports = {a["id_placement"]: str(a.get("support_reel", "")) for _, a in ctx.acteurs_poses()}
    for r in ctx.cfg.get("gameplay_requis", []):
        v.compte()
        n = sum(1 for i in poses if (r.get("motif") and fnmatch.fnmatch(i, r["motif"])) or
                (r.get("support") and r["support"] in supports.get(i, "")))
        if n < r["min"]:
            v.ko("%s : %d pose(s), minimum %d (%s)" % (r.get("nom", r.get("motif")), n, r["min"],
                                                    r.get("raison", "profil de map")))
    return v


TOUTES = [v_integrite, v_persistance, v_preexistants, v_source_coordonnees, v_zero_overlap,
          v_zero_flottant, v_accessibilite, v_couverture, v_visuel, v_gameplay]
