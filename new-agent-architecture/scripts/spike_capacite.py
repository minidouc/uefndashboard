# -*- coding: utf-8 -*-
"""
spike_capacite.py -- PROUVER une capacite avant de s'en servir (un appel, une preuve, un verdict).
C'est ici que se debloque la DA, l'echec n1 de corpo-plaza (0 texture appliquee).

  python scripts/spike_capacite.py palette PPID_CRP_Sunburst
      LECTURE SEULE. Liste les props legaux du pack cyberpunk Sunburst (348 selon l'inventaire)
      -> build/studio/spikes/palette_<filtre>.json : de VRAIS chemins d'assets que le level
      designer peut mettre dans placements.json ("support": "ASSET:<chemin>").

  python scripts/spike_capacite.py poser-asset <chemin_asset>
      1 acteur dans CP_Studio/spike, relecture des bornes, puis retrait + save.
      Prouve add_to_scene_from_asset sur un prop du pack (dimensions reelles mesurees).

  python scripts/spike_capacite.py import-texture <fichier.png>
      1 import vers <content_root>/CorpoPlaza (racine lue dans l'erreur du T6), puis
      verification d'existence. Outil 'a prouver' : autorise ici seulement.

  python scripts/spike_capacite.py proprietes <id_placement> [--filtre time]
      LECTURE SEULE. Noms reels des proprietes d'un acteur pose (jamais de propriete inventee).

  python scripts/spike_capacite.py regler <id_placement> <propriete> <valeur_json>
      1 set_properties (outil 'a prouver') + relecture avant/apres + save. PROUVE si la valeur relue change.

Chaque verdict -> build/studio/spikes/<nom>.json. Si PROUVE, l'humain deplace l'outil de
'ecritures_a_prouver' vers 'ecritures_prouvees' dans config/studio.json (avec la preuve).
"""
import argparse
import glob
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.uefn.config import Projet, ecrire_json, lire_json, maintenant  # noqa: E402
from scripts.uefn.mcp_gateway import Passerelle  # noqa: E402


def verdict(p, nom, doc):
    doc["ts_utc"] = maintenant()
    chemin = ecrire_json(os.path.join(p.build_dir, "spikes", "%s.json" % nom), doc)
    print(json.dumps({k: doc[k] for k in doc if k not in ("assets",)}, ensure_ascii=False)[:1500])
    print("verdict ecrit : %s" % chemin)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--projet")
    sp = ap.add_subparsers(dest="cmd", required=True)
    x = sp.add_parser("palette"); x.add_argument("filtre")
    x = sp.add_parser("poser-asset"); x.add_argument("chemin")
    x = sp.add_parser("import-texture"); x.add_argument("fichier")
    x = sp.add_parser("proprietes"); x.add_argument("id_placement"); x.add_argument("--filtre", default="")
    x = sp.add_parser("regler"); x.add_argument("id_placement"); x.add_argument("propriete"); x.add_argument("valeur")
    x = sp.add_parser("compiler-verse"); x.add_argument("fichier"); x.add_argument("--dest", required=True)
    x = sp.add_parser("mesurer-assets"); x.add_argument("choix")
    x = sp.add_parser("parametres-materiau"); x.add_argument("chemin")
    x = sp.add_parser("lire"); x.add_argument("ref"); x.add_argument("propriete")
    x = sp.add_parser("materiau"); x.add_argument("--parent", required=True); x.add_argument("--param", required=True)
    x.add_argument("--texture", required=True); x.add_argument("--composant", required=True); x.add_argument("--nom", required=True)
    x.add_argument("--scalaire", action="append", default=[], help="NOM=VALEUR (ex. 'Global Emissive Intensity=0')")
    a = ap.parse_args(argv)
    p = Projet(a.projet)
    gw = Passerelle(p, ecriture=a.cmd not in ("palette", "proprietes", "parametres-materiau", "lire"),
                    script="spike_%s" % a.cmd)
    if not gw.ping():
        print("ARRET : editeur injoignable")
        return 2

    if a.cmd == "palette":
        r = gw.appel("AssetTools", "find_assets", {"name": a.filtre}, etape="palette")
        assets = r.valeur or []
        verdict(p, "palette_%s" % a.filtre, {"capacite": "enumeration palette", "rc": r.rc, "erreur": r.erreur,
                                             "nb": len(assets), "assets": assets, "preuve": r.preuve})
        return r.rc

    if a.cmd == "poser-asset":
        loc = {"x": 0.0, "y": 0.0, "z": 0.0}
        r = gw.appel("SceneTools", "add_to_scene_from_asset",
                     {"asset_path": a.chemin, "name": "CP_SPIKE_ASSET", "xform": {"location": loc}},
                     ecriture=True, etape="spike_pose")
        ref = (r.valeur or {}).get("refPath") if isinstance(r.valeur, dict) else r.valeur
        doc = {"capacite": "SceneTools.add_to_scene_from_asset", "asset": a.chemin, "rc_pose": r.rc,
               "erreur": r.erreur, "preuve_pose": r.preuve}
        if r.ok and ref:
            gw.appel("SceneTools", "set_actor_folder", {"actor": {"refPath": ref}, "folder_path": "CP_Studio/spike"},
                     ecriture=True, etape="spike_dossier")
            b = gw.appel("ActorTools", "get_actor_bounds", {"actor": {"refPath": ref}}, etape="spike_bornes")
            doc["bounds_relus"], doc["preuve_bounds"] = b.valeur, b.preuve
            rm = gw.appel("SceneTools", "remove_from_scene", {"actor": {"refPath": ref}}, ecriture=True, etape="spike_retrait")
            sv = gw.appel("AssetTools", "save_assets", {"asset_paths": [p.uefn["level_package"]]}, ecriture=True, etape="spike_save")
            doc["nettoyage"] = {"retrait_rc": rm.rc, "save_rc": sv.rc}
        doc["verdict"] = "PROUVE" if r.ok and doc.get("bounds_relus") else "ECHEC"
        verdict(p, "poser_asset", doc)
        return 0 if doc["verdict"] == "PROUVE" else 1

    if a.cmd == "import-texture":
        src = os.path.abspath(a.fichier)
        nom = os.path.splitext(os.path.basename(src))[0]
        r = gw.appel("TextureTools", "import_file",
                     {"folder_path": p.uefn["import_folder"], "asset_name": nom, "source_file": src},
                     ecriture=True, etape="spike_import", spike=True)
        chemin = "%s/%s" % (p.uefn["import_folder"], nom)
        e = gw.appel("AssetTools", "exists", {"path": chemin}, etape="spike_existe")
        doc = {"capacite": "TextureTools.import_file", "source": src, "dossier": p.uefn["import_folder"],
               "rc_import": r.rc, "erreur": r.erreur, "existe_apres": e.valeur, "preuves": [r.preuve, e.preuve],
               "verdict": "PROUVE" if r.ok and e.valeur else "ECHEC",
               "suite_si_prouve": "spike suivant : creer/assigner un materiau utilisant la texture (outil a identifier)"}
        verdict(p, "import_texture", doc)
        return 0 if doc["verdict"] == "PROUVE" else 1

    if a.cmd in ("proprietes", "regler"):
        # l'acteur vise est un acteur POSE par le studio (refPath enregistre dans lots/lot_NN.json)
        ref = None
        for f in sorted(glob.glob(os.path.join(p.build_dir, "lots", "lot_[0-9][0-9].json"))):
            for x in lire_json(f).get("acteurs", []):
                if x.get("id_placement") == a.id_placement:
                    ref = x.get("refPath")
        if not ref:
            print("ARRET : %s absent des lots poses" % a.id_placement)
            return 4
    if a.cmd == "proprietes":
        # LECTURE SEULE : noms reels des proprietes, pour ne jamais en inventer
        r = gw.appel("ObjectTools", "list_properties", {"instance": {"refPath": ref}}, etape="proprietes")
        noms = r.valeur if isinstance(r.valeur, list) else []
        garde = [n for n in noms if a.filtre.lower() in json.dumps(n, ensure_ascii=False).lower()]
        verdict(p, "proprietes_%s" % a.id_placement, {"capacite": "ObjectTools.list_properties", "acteur": ref,
                                                       "rc": r.rc, "erreur": r.erreur, "nb": len(noms),
                                                       "filtre": a.filtre, "extrait": garde[:40], "preuve": r.preuve})
        return r.rc
    if a.cmd == "regler":
        # 1 ecriture (outil 'a prouver'), puis relecture : PROUVE seulement si la valeur relue a change
        av = gw.appel("ObjectTools", "get_properties", {"instance": {"refPath": ref}, "properties": [a.propriete]},
                      etape="avant")
        r = gw.appel("ObjectTools", "set_properties", {"instance": {"refPath": ref},
                                                       "values": json.dumps({a.propriete: json.loads(a.valeur)})},
                     ecriture=True, etape="spike_set", spike=True)
        ap_ = gw.appel("ObjectTools", "get_properties", {"instance": {"refPath": ref}, "properties": [a.propriete]},
                       etape="apres")
        sv = gw.appel("AssetTools", "save_assets", {"asset_paths": [p.uefn["level_package"]]}, ecriture=True,
                      etape="spike_save")
        doc = {"capacite": "ObjectTools.set_properties", "acteur": ref, "propriete": a.propriete,
               "demande": a.valeur, "avant": av.valeur, "apres": ap_.valeur, "rc_set": r.rc, "erreur": r.erreur,
               "save_rc": sv.rc, "preuves": [av.preuve, r.preuve, ap_.preuve, sv.preuve]}
        doc["verdict"] = "PROUVE" if r.ok and ap_.ok and sv.ok and ap_.valeur != av.valeur else "ECHEC"
        verdict(p, "regler_%s_%s" % (a.id_placement, a.propriete), doc)
        return 0 if doc["verdict"] == "PROUVE" else 1

    if a.cmd == "compiler-verse":
        # 1) compiler l'etat ACTUEL : si l'outil est bloque ou deja en erreur, on ne copie rien
        r0 = gw.appel("VerseToolset", "BuildAll", {}, ecriture=True, etape="build_avant", spike=True)
        doc = {"capacite": "VerseToolset.BuildAll", "rc_avant": r0.rc, "erreur_avant": r0.erreur,
               "sortie_avant": r0.valeur, "preuves": [r0.preuve]}
        if r0.ok:
            # 2) copie du fichier dans le dossier Verse du projet (disque), puis compilation
            os.makedirs(os.path.dirname(a.dest), exist_ok=True)
            shutil.copyfile(os.path.abspath(a.fichier), a.dest)
            r1 = gw.appel("VerseToolset", "BuildAll", {}, ecriture=True, etape="build_apres", spike=True)
            doc.update({"copie": a.dest, "rc_apres": r1.rc, "erreur_apres": r1.erreur, "sortie_apres": r1.valeur})
            doc["preuves"].append(r1.preuve)
        # rc=0 veut dire « compilation lancee » ; le code n'est bon que sans diagnostic de severite Error
        erreurs = [d for d in (doc.get("sortie_apres") or []) if isinstance(d, dict) and d.get("severity") == "Error"]
        doc["outil_prouve"] = doc.get("rc_apres") == 0
        doc["nb_erreurs"] = len(erreurs)
        doc["verdict"] = "PROUVE" if doc["outil_prouve"] and not erreurs else "ECHEC"
        verdict(p, "compiler_verse", doc)
        return 0 if doc["verdict"] == "PROUVE" else 1

    if a.cmd == "materiau":
        # chaine complete, arret a la premiere etape en echec ; chaque ecriture est relue
        mi = "%s/%s.%s" % (p.uefn["import_folder"], a.nom, a.nom)
        doc = {"capacite": "materiau sur composant", "parent": a.parent, "texture": a.texture, "instance": mi,
               "composant": a.composant, "etapes": {}}

        def etape(nom, r):
            doc["etapes"][nom] = {"rc": r.rc, "erreur": r.erreur, "valeur": r.valeur, "preuve": r.preuve}
            return r.ok
        ex = gw.appel("AssetTools", "exists", {"path": mi.rsplit(".", 1)[0]}, etape="mi_existe")
        if ex.ok and ex.valeur:  # deja creee par une tentative precedente : on ne la recree pas
            ok = etape("create", ex)
        else:
            ok = etape("create", gw.appel("MaterialInstanceTools", "create",
                                          {"folder_path": p.uefn["import_folder"], "asset_name": a.nom,
                                           "parent": {"refPath": a.parent}}, ecriture=True, etape="mi_create", spike=True))
        ok = ok and etape("set_texture", gw.appel("MaterialInstanceTools", "set_texture_parameter",
                                                  {"instance": {"refPath": mi}, "name": a.param,
                                                   "value": {"refPath": a.texture}},
                                                  ecriture=True, etape="mi_texture", spike=True))
        # get_texture_parameter est INCONNU (lecture bloquee) : relecture par get_properties, VERIFIE
        ok = ok and etape("relu_texture", gw.appel("ObjectTools", "get_properties",
                                                   {"instance": {"refPath": mi}, "properties": ["TextureParameterValues"]},
                                                   etape="mi_relue"))
        ok = ok and a.texture.rsplit(".", 1)[-1] in str(doc["etapes"]["relu_texture"]["valeur"])
        for s in a.scalaire:  # ex. couper l'emission d'un parent emissif ; relu par get_scalar_parameter (VERIFIE)
            nom, val = s.rsplit("=", 1)
            ok = ok and etape("scalaire_%s" % nom, gw.appel("MaterialInstanceTools", "set_scalar_parameter",
                                                            {"instance": {"refPath": mi}, "name": nom, "value": float(val)},
                                                            ecriture=True, etape="mi_scalaire", spike=True))
            ok = ok and etape("relu_%s" % nom, gw.appel("MaterialInstanceTools", "get_scalar_parameter",
                                                        {"instance": {"refPath": mi}, "name": nom}, etape="mi_scalaire_relu"))
        ok = ok and etape("save_mi", gw.appel("AssetTools", "save_assets", {"asset_paths": [mi.rsplit(".", 1)[0]]},
                                              ecriture=True, etape="mi_save"))
        ok = ok and etape("appliquer", gw.appel("ObjectTools", "set_properties",
                                                {"instance": {"refPath": a.composant},
                                                 "values": json.dumps({"OverrideMaterials": [{"refPath": mi}]})},
                                                ecriture=True, etape="appliquer", spike=True))
        ok = ok and etape("relu_composant", gw.appel("ObjectTools", "get_properties",
                                                     {"instance": {"refPath": a.composant},
                                                      "properties": ["OverrideMaterials"]}, etape="composant_relu"))
        ok = ok and etape("save_niveau", gw.appel("AssetTools", "save_assets", {"asset_paths": [p.uefn["level_package"]]},
                                                  ecriture=True, etape="niveau_save"))
        relu = str((doc["etapes"].get("relu_composant") or {}).get("valeur"))
        doc["verdict"] = "PROUVE" if ok and a.nom in relu else "ECHEC"
        verdict(p, "materiau_%s" % a.nom, doc)
        return 0 if doc["verdict"] == "PROUVE" else 1

    if a.cmd == "lire":
        # LECTURE SEULE : une propriete d'un objet, par refPath (acteur, composant ou asset)
        r = gw.appel("ObjectTools", "get_properties", {"instance": {"refPath": a.ref}, "properties": [a.propriete]},
                     etape="lire")
        print(json.dumps({"rc": r.rc, "erreur": r.erreur, "valeur": r.valeur}, ensure_ascii=False)[:2000])
        return r.rc

    if a.cmd == "parametres-materiau":
        # LECTURE SEULE : noms et types reels des parametres d'un materiau parent candidat
        r = gw.appel("MaterialInstanceTools", "list_parameters", {"material": {"refPath": a.chemin}}, etape="parametres")
        verdict(p, "parametres_%s" % a.chemin.rsplit(".", 1)[-1], {"capacite": "MaterialInstanceTools.list_parameters",
                                                                  "materiau": a.chemin, "rc": r.rc, "erreur": r.erreur,
                                                                  "parametres": r.valeur, "preuve": r.preuve})
        return r.rc

    if a.cmd == "mesurer-assets":
        # chaque asset choisi : 1 pose au pivot (0,0,0), relecture des bornes, retrait ; bornes RELATIVES au pivot
        assets = lire_json(a.choix)["assets"]
        mesures, echecs = {}, {}
        for i, chemin in enumerate(assets):
            r = gw.appel("SceneTools", "add_to_scene_from_asset",
                         {"asset_path": chemin, "name": "CP_MESURE_%02d" % i, "xform": {"location": {"x": 0.0, "y": 0.0, "z": 0.0}}},
                         ecriture=True, etape="mesure_%02d_pose" % i)
            ref = (r.valeur or {}).get("refPath") if isinstance(r.valeur, dict) else r.valeur
            if not (r.ok and ref):
                echecs[chemin] = r.erreur
                continue
            b = gw.appel("ActorTools", "get_actor_bounds", {"actor": {"refPath": ref}}, etape="mesure_%02d_bornes" % i)
            rm = gw.appel("SceneTools", "remove_from_scene", {"actor": {"refPath": ref}}, ecriture=True,
                          etape="mesure_%02d_retrait" % i)
            v = b.valeur if isinstance(b.valeur, dict) else {}
            if b.ok and v.get("isValid", True) and "min" in v:
                mesures[chemin] = {"min": [round(v["min"][k]) for k in "xyz"], "max": [round(v["max"][k]) for k in "xyz"],
                                   "preuve": b.preuve, "retrait_rc": rm.rc}
            else:
                echecs[chemin] = "bornes illisibles"
            if not rm.ok:
                echecs[chemin] = "RETRAIT ECHOUE : %s" % rm.erreur
                break  # un acteur de mesure reste dans le niveau : arret
        sv = gw.appel("AssetTools", "save_assets", {"asset_paths": [p.uefn["level_package"]]}, ecriture=True, etape="save")
        doc = {"capacite": "mesure des bornes d'assets", "nb": len(assets), "mesures": mesures, "echecs": echecs,
               "save_rc": sv.rc, "verdict": "PROUVE" if mesures and not any("RETRAIT" in str(e) for e in echecs.values()) else "ECHEC"}
        verdict(p, "mesures_assets", doc)
        return 0 if doc["verdict"] == "PROUVE" else 1
    return 4


if __name__ == "__main__":
    sys.exit(main())
