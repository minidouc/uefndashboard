# Sonde IslandForge - a copier dans <PROJET>/Content/Python/init_unreal.py
#
# Prouve trois choses, dans l'ordre :
#   1. un script de demarrage au niveau PROJET s'execute a l'ouverture de l'editeur ;
#   2. `unreal` et `toolset_registry` y sont importables (refuses dans le bac a
#      sable de ProgrammaticToolset.execute_tool_script) ;
#   3. un toolset personnalise s'enregistre et devient visible du serveur MCP.
#
# STRICTEMENT EN LECTURE. Ne cree ni acteur, ni asset, ni niveau, ni sauvegarde.
# Ne leve jamais d'exception au demarrage : tout est journalise dans un rapport.
#
# Rapport ecrit dans %TEMP%\sonde_islandforge.json, chemin egalement journalise
# sous le marqueur SONDE_ISLANDFORGE (lisible via LogsToolset.GetLogEntries).

import json
import os
import tempfile
import time
import traceback

MARQUEUR = "SONDE_ISLANDFORGE"
RAPPORT = os.path.join(tempfile.gettempdir(), "sonde_islandforge.json")

_rapport = {
    "marqueur": MARQUEUR,
    "horodatage": time.strftime("%Y-%m-%d %H:%M:%S"),
    "etapes": [],
    "chemin_rapport": RAPPORT,
}

unreal = None


def _journaliser(ligne):
    if unreal is None:
        return
    try:
        unreal.log("{} {}".format(MARQUEUR, ligne))
    except Exception:
        pass


def _etape(nom, ok, detail=""):
    detail = str(detail)[:600]
    _rapport["etapes"].append({"etape": nom, "ok": bool(ok), "detail": detail})
    _journaliser("{} ok={} {}".format(nom, bool(ok), detail))
    return bool(ok)


# --- 1. import unreal -------------------------------------------------------

try:
    import unreal  # noqa: F401
    _etape("import_unreal", True, "module `unreal` disponible")
except Exception:
    _etape("import_unreal", False, traceback.format_exc())

if unreal is not None:
    try:
        _etape("version_moteur", True, unreal.SystemLibrary.get_engine_version())
    except Exception:
        _etape("version_moteur", False, traceback.format_exc())
    try:
        _etape("chemin_projet", True, unreal.SystemLibrary.get_project_directory())
    except Exception:
        _etape("chemin_projet", False, traceback.format_exc())


# --- 2. inventaire des capacites (hasattr uniquement, aucune execution) -----

# Chemins pointes separes par des points : `Classe` ou `Classe.methode`.
_CIBLES = [
    "PointLight",
    "SpotLight",
    "RectLight",
    "DirectionalLight",
    "EditorActorSubsystem",
    "EditorLevelLibrary",
    "EditorAssetLibrary",
    "MaterialEditingLibrary",
    "EditorValidatorSubsystem",
    "EditorActorSubsystem.spawn_actor_from_class",
    "EditorLevelLibrary.spawn_actor_from_class",
    "StaticMeshComponent.create_dynamic_material_instance",
    "MaterialEditingLibrary.create_material_instance",
    "LandscapeProxy",
    "InstancedFoliageActor",
    "FoliageType",
    "HierarchicalInstancedStaticMeshComponent",
    "NiagaraSystem",
    "NiagaraComponent",
    "ToolsetDefinition",
]


def _resoudre(chemin):
    objet = unreal
    for partie in chemin.split("."):
        if not hasattr(objet, partie):
            return False
        objet = getattr(objet, partie)
    return True


def _capacites():
    return {
        "cibles": {c: _resoudre(c) for c in _CIBLES},
        "validateurs": sorted(
            n for n in dir(getattr(unreal, "EditorValidatorSubsystem", object))
            if "valid" in n.lower()
        )[:20] if hasattr(unreal, "EditorValidatorSubsystem") else [],
    }


# --- 3. toolset personnalise ------------------------------------------------

IslandForgeProbe = None

if unreal is not None and hasattr(unreal, "ToolsetDefinition"):
    try:
        from toolset_registry import tool_call

        @unreal.uclass()
        class IslandForgeProbe(unreal.ToolsetDefinition):
            """Sonde IslandForge : inventaire en lecture seule des capacites
            reelles de l'editeur, hors des 388 outils officiels."""

            @tool_call
            @staticmethod
            def sonder_capacites() -> str:
                """Inventaire des classes et methodes `unreal` disponibles.

                Returns:
                    JSON : chemins du projet, classes de lumiere, sous-systemes
                    editeur, materiau par instance, terrain et feuillage,
                    Niagara, validateurs.
                """
                retour = {
                    "chemin_projet": unreal.SystemLibrary.get_project_directory(),
                    "version_moteur": unreal.SystemLibrary.get_engine_version(),
                }
                retour.update(_capacites())
                return json.dumps(retour, indent=2, ensure_ascii=False)

            @tool_call
            @staticmethod
            def compter_acteurs(filtre_nom: str = "") -> str:
                """Compte les acteurs du niveau ouvert, regroupes par classe.

                Args:
                    filtre_nom: sous-chaine que le nom de classe doit contenir
                        (ex. 'Light'). Vide = tous les acteurs.
                Returns:
                    JSON : nom de classe -> nombre d'instances, plus le total.
                """
                sous_systeme = unreal.get_editor_subsystem(
                    unreal.EditorActorSubsystem)
                compte = {}
                for acteur in sous_systeme.get_all_level_actors():
                    nom = acteur.get_class().get_name()
                    if filtre_nom.lower() in nom.lower():
                        compte[nom] = compte.get(nom, 0) + 1
                return json.dumps(
                    {"total": sum(compte.values()), "par_classe": compte},
                    indent=2, ensure_ascii=False)

        _etape("classe_toolset", True, "IslandForgeProbe definie (2 outils)")
    except Exception:
        IslandForgeProbe = None
        _etape("classe_toolset", False, traceback.format_exc())
elif unreal is not None:
    _etape("classe_toolset", False,
           "unreal.ToolsetDefinition absent de ce build")


# --- 4. enregistrement differe aupres du serveur MCP ------------------------
# register() renvoie False SILENCIEUSEMENT si le registre n'est pas disponible :
# la valeur de retour est la seule preuve, jamais l'absence d'erreur.
#
# Au demarrage, le registre n'est PAS encore pret : les toolsets MCP d'Epic
# doivent d'abord lier le port 8000. Enregistrer a l'import echoue donc.
# On differe de DEFER_TICKS ticks de l'editeur (valeur observee chez un produit
# tiers qui fait la meme chose : 45).

DEFER_TICKS = int(os.environ.get("ISLANDFORGE_DEFER_TICKS", "45"))


def _ecrire_rapport():
    try:
        with open(RAPPORT, "w", encoding="utf-8") as f:
            json.dump(_rapport, f, indent=2, ensure_ascii=False)
    except Exception:
        _rapport["etapes"].append(
            {"etape": "ecriture_rapport", "ok": False,
             "detail": traceback.format_exc()[:600]})


def _fin(message):
    _reussies = sum(1 for e in _rapport["etapes"] if e["ok"])
    _rapport["resume"] = "{} - {} etapes reussies sur {}".format(
        message, _reussies, len(_rapport["etapes"]))
    _ecrire_rapport()
    _journaliser(_rapport["resume"] + " - rapport dans " + RAPPORT)


def _enregistrer():
    try:
        from toolset_registry.registration import Registration
        resultat = Registration([IslandForgeProbe]).register()
        _etape("enregistrement_mcp", resultat,
               "register() a renvoye {} apres {} ticks".format(
                   resultat, _ticks[0]))
        return bool(resultat)
    except Exception:
        _etape("enregistrement_mcp", False, traceback.format_exc())
        return False


# Rapport provisoire immediat : la preuve que le script s'est execute ne doit
# pas dependre de la reussite des etapes suivantes.
_rapport["differe_ticks"] = DEFER_TICKS
_fin("RAPPORT_PROVISOIRE (enregistrement pas encore tente)")

_ticks = [0]
_handle = [None]
_JALONS = (DEFER_TICKS, DEFER_TICKS * 2, DEFER_TICKS * 4, DEFER_TICKS * 8)


def _sur_tick(_=None):
    _ticks[0] += 1
    if _ticks[0] not in _JALONS:
        return
    if IslandForgeProbe is None:
        _etape("enregistrement_mcp", False,
               "toolset non defini, rien a enregistrer")
        _fin("FIN_SANS_TOOLSET")
    elif _enregistrer():
        _fin("FIN_ENREGISTRE")
    elif _ticks[0] >= _JALONS[-1]:
        _fin("FIN_ECHEC_ENREGISTREMENT")
    else:
        return
    try:
        unreal.unregister_slate_post_tick_callback(_handle[0])
    except Exception:
        pass
    _handle[0] = None


if unreal is None:
    _fin("FIN_SANS_UNREAL")
else:
    try:
        _handle[0] = unreal.register_slate_post_tick_callback(_sur_tick)
        _etape("callback_tick", _handle[0] is not None,
               "tentatives prevues aux ticks {}".format(list(_JALONS)))
    except Exception:
        _etape("callback_tick", False, traceback.format_exc())
        _fin("FIN_CALLBACK_IMPOSSIBLE")
