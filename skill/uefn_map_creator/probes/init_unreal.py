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


if unreal is not None:
    try:
        _rapport["capacites"] = _capacites()
    except Exception:
        pass



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


def _activer_toolsets_officiels():
    """Active les toolsets Python et C++ d'Epic si le demarrage les a omis."""
    try:
        from valkyrie_toolset import registration as _vreg
        _vreg.enable()
    except Exception:
        pass
    try:
        for nom_cls in ("DeviceToolset", "VerseToolset", "EntityToolset", "SessionToolset"):
            cls = getattr(unreal, nom_cls, None)
            if cls is not None:
                unreal.ToolsetRegistry.register_toolset_class(cls)
    except Exception:
        pass


def _demarrer_pont_mcp_secours():
    """Si le port 8000 n'est pas ouvert par ModelContextProtocol C++, ouvre un
    pont HTTP /mcp compatible sur 127.0.0.1:8000 deleguant sur le game thread."""
    import socket
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    import queue

    ancien = getattr(unreal, "_islandforge_mcp_bridge", None)
    if ancien is not None:
        try:
            ancien[0].shutdown()
            ancien[0].server_close()
        except Exception:
            pass
        try:
            unreal.unregister_slate_post_tick_callback(ancien[1])
        except Exception:
            pass
        unreal._islandforge_mcp_bridge = None

    # Verifier si le port 8000 ecoute deja (ex: serveur C++ natif)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.15)
    try:
        if s.connect_ex(("127.0.0.1", 8000)) == 0:
            s.close()
            return True
    finally:
        try:
            s.close()
        except Exception:
            pass

    file_taches = queue.Queue()
    en_attente = []
    _cache_schemas = {}

    def _completer_defauts(toolset_name, tool_name, arguments):
        args = dict(arguments or {})
        try:
            if not _cache_schemas:
                raw_all = unreal.ToolsetRegistry.get_all_toolset_json_schemas()
                for entry in (json.loads(raw_all) if raw_all else []):
                    if isinstance(entry, dict) and entry.get("name"):
                        _cache_schemas[entry["name"]] = entry
            ts_schema = _cache_schemas.get(toolset_name) or {}
            for t in ts_schema.get("tools") or []:

                tn = str(t.get("name", ""))
                if tn in (tool_name, "{}.{}".format(toolset_name, tool_name)) or tn.endswith("." + tool_name):
                    for cle_s in ("inputSchema", "input_schema", "parameters", "schema"):

                        in_s = t.get(cle_s)
                        if in_s:
                            break
                    else:
                        in_s = t
                    if isinstance(in_s, str):
                        in_s = json.loads(in_s)
                    props = (in_s.get("properties") if isinstance(in_s, dict) else None) or {}
                    for k, p in props.items():
                        if k not in args and isinstance(p, dict):
                            if "default" in p:
                                args[k] = p["default"]
                            elif p.get("type") == "array":
                                args[k] = []
                    break
        except Exception:
            pass
        return args

    def _executer_outil(toolset_name, tool_name, arguments):
        if toolset_name in ("IslandForgeProbe", "PythonTypes.IslandForgeProbe") and IslandForgeProbe is not None:
            fn = getattr(IslandForgeProbe, tool_name, None)
            if fn is not None:
                res_str = fn(**(arguments or {}))
                return False, {"content": [{"type": "text", "text": res_str}], "isError": False}
        payload = json.dumps(_completer_defauts(toolset_name, tool_name, arguments))
        ar = unreal.ToolsetRegistry.execute_tool(
            unreal.Name(toolset_name), unreal.Name(tool_name), payload)

        if ar.is_complete:
            err = getattr(ar, "error", "")
            txt = getattr(ar, "value", "") or err
            return False, {
                "content": [{"type": "text", "text": txt}],
                "isError": bool(err),
            }
        return True, ar

    def _tick_pont(_=None):
        # 1. Verifier les resultats asynchrones en cours (ex: VerseToolset.BuildAll)
        restants = []
        for ar, boite, evt in en_attente:
            try:
                if ar.is_complete:
                    err = getattr(ar, "error", "")
                    txt = getattr(ar, "value", "") or err
                    boite["res"] = {
                        "content": [{"type": "text", "text": txt}],
                        "isError": bool(err),
                    }
                    evt.set()
                else:
                    restants.append((ar, boite, evt))
            except Exception as exc:
                boite["res"] = {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                }
                evt.set()
        en_attente[:] = restants

        # 2. Depiler les nouvelles requetes RPC
        while not file_taches.empty():
            try:
                action, params, boite, evt = file_taches.get_nowait()
            except Exception:
                break
            try:
                if action == "list_toolsets":
                    raw_str = unreal.ToolsetRegistry.get_all_toolset_json_schemas()
                    schemas = json.loads(raw_str) if raw_str else []
                    if IslandForgeProbe is not None:
                        schemas.append({
                            "name": "IslandForgeProbe",
                            "description": "Sonde IslandForge (capacites editeur)",
                            "tools": ["sonder_capacites", "compter_acteurs"],
                        })
                    boite["res"] = {
                        "content": [{"type": "text", "text": json.dumps({"toolsets": schemas})}],
                        "isError": False,
                    }
                    evt.set()


                elif action == "describe_toolset":
                    ts = params.get("toolset_name", "")
                    raw = unreal.ToolsetRegistry.get_toolset_json_schema(unreal.Name(ts))
                    boite["res"] = {
                        "content": [{"type": "text", "text": raw or "{}"}],
                        "isError": not bool(raw),
                    }
                    evt.set()

                elif action == "call_tool":
                    est_async, val = _executer_outil(
                        params.get("toolset_name", ""),
                        params.get("tool_name", ""),
                        params.get("arguments", {}),
                    )
                    if est_async:
                        en_attente.append((val, boite, evt))
                    else:
                        boite["res"] = val
                        evt.set()
                else:
                    boite["res"] = {
                        "content": [{"type": "text", "text": "Action inconnue: " + str(action)}],
                        "isError": True,
                    }
                    evt.set()
            except Exception as exc:
                boite["res"] = {
                    "content": [{"type": "text", "text": traceback.format_exc()}],
                    "isError": True,
                }
                evt.set()

    def _appeler_gt(action, params, timeout=55.0):
        boite = {}
        evt = threading.Event()
        file_taches.put((action, params, boite, evt))
        if not evt.wait(timeout):
            return {
                "content": [{"type": "text", "text": "Timeout game thread"}],
                "isError": True,
            }
        return boite.get("res", {"content": [], "isError": True})

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            longueur = int(self.headers.get("Content-Length", "0"))
            corps = self.rfile.read(longueur).decode("utf-8", errors="replace")
            try:
                req = json.loads(corps) if corps else {}
            except Exception:
                req = {}
            methode = req.get("method", "")
            req_id = req.get("id")
            params = req.get("params") or {}
            sid = self.headers.get("Mcp-Session-Id") or "islandforge-mcp-session"

            if methode == "initialize":
                rep = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "unreal-mcp-islandforge", "version": "1.0"},
                    },
                }
            elif methode.startswith("notifications/"):
                rep = {"jsonrpc": "2.0", "result": {}}
            elif methode == "tools/call":
                nom = params.get("name", "")
                args = params.get("arguments") or {}
                res = _appeler_gt(nom, args)
                rep = {"jsonrpc": "2.0", "id": req_id, "result": res}
            else:
                rep = {"jsonrpc": "2.0", "id": req_id, "result": {}}

            data = json.dumps(rep, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Mcp-Session-Id", sid)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    try:
        serveur = ThreadingHTTPServer(("127.0.0.1", 8000), _Handler)
        tick_h = unreal.register_slate_post_tick_callback(_tick_pont)
        th = threading.Thread(target=serveur.serve_forever, daemon=True)
        th.start()
        unreal._islandforge_mcp_bridge = (serveur, tick_h, th)
        return True
    except Exception:
        return False


def _enregistrer():
    try:
        _activer_toolsets_officiels()
        from toolset_registry.registration import Registration
        resultat = Registration([IslandForgeProbe]).register()
        pont_ok = _demarrer_pont_mcp_secours()
        _etape("enregistrement_mcp", resultat,
               "register() a renvoye {} apres {} ticks (pont_8000={})".format(
                   resultat, _ticks[0], pont_ok))
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
elif DEFER_TICKS <= 0 and IslandForgeProbe is not None and _enregistrer():
    _fin("FIN_ENREGISTRE")
else:
    try:
        _handle[0] = unreal.register_slate_post_tick_callback(_sur_tick)
        _etape("callback_tick", _handle[0] is not None,
               "tentatives prevues aux ticks {}".format(list(_JALONS)))
    except Exception:
        _etape("callback_tick", False, traceback.format_exc())
        _fin("FIN_CALLBACK_IMPOSSIBLE")

