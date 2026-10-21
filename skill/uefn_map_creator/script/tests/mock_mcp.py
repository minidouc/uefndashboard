#!/usr/bin/env python3
"""Serveur MCP de test : simule l'editeur UEFN pour verifier le CLI sans editeur.

Usage : python mock_mcp.py <port> [ok|error|slow]
  ok    : repond a tout, avec etat (acteurs, proprietes, bindings, fichiers .verse)
  error : isError=true sur tous les outils      -> code retour 1 TOOL_ERROR
  slow  : dort 5 s avant de repondre            -> code retour 3 TIMEOUT (UEFN_MCP_TIMEOUT=1)

Un appel MCP reel renvoie `{"content": [{"type": "text", "text": "{\"returnValue\": ...}"}]}`.
Ce mock reproduit cette enveloppe, et pour `CaptureViewport` un contenu de type `image`.

Comportement dynamique : si la variable `MOCK_STATE` pointe vers un fichier JSON, il est
relu a chaque requete et fusionne dans la configuration. Cles reconnues :
  session        etat renvoye par GetSessionStatus         (defaut "Disconnected")
  props          noms renvoyes par list_properties          (defaut voir DEFAULT_PROPS)
  symbols        motifs que Grep trouve                     (defaut ["GetGameState"])
  files          fichiers renvoyes par ListFiles
  bounds_size    taille de BASE renvoyee par get_actor_bounds, multipliee par l'echelle
                 de l'acteur (defaut [100, 100, 100] : le Cube moteur)
  build_diags    diagnostics renvoyes par BuildAll          (defaut [])
  build_log      lignes renvoyes par GetLogEntries(VerseBuild)
  drop_scale     get_actor_transform renvoie scale 1 (pour tester TRANSFORM_MISMATCH)
  prop_overrides {nom: valeur} forces a la relecture (pour tester PROPERTY_MISMATCH)
  ignore_yaw     PlaceDevice ignore le yaw demande (defaut true : quirk reel documente)
  fail_tools     noms d'outils qui repondent isError=true

Le mock n'execute que les scripts produits par le CLI (execute_tool_script) : il n'est pas
un bac a sable et ne doit jamais etre expose hors de 127.0.0.1.
"""
import base64
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1])
MODE = sys.argv[2] if len(sys.argv) > 2 else "ok"
STATE_FILE = os.environ.get("MOCK_STATE", "")

PNG_1PX = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
           "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
DEFAULT_PROPS = ["playerTeam", "visibleInGame", "enabledDuringPhase", "EnabledState"]
DEFAULT_FILES = ["/Fortnite.com (Fortnite)/Modules/creative.verse",
                 "/Fortnite.com (Fortnite)/Devices/game_manager_device.verse"]
BUILD_OK_LOG = [{"severity": "Info",
                 "message": "Verse build succeeded (0 errors, 0 warnings)",
                 "timestamp": "2026-10-20T19:00:00Z"}]

CFG = {"session": "Disconnected", "props": DEFAULT_PROPS, "symbols": ["GetGameState"],
       "files": DEFAULT_FILES, "bounds_size": [100.0, 100.0, 100.0], "build_diags": [],
       "build_log": BUILD_OK_LOG, "drop_scale": False, "ignore_yaw": True,
       "prop_overrides": {}, "fail_tools": []}

# etat simule de l'editeur
ACTORS = {}      # refPath -> {label, asset, xform, tags, kind}
PROPS = {}       # refPath -> {nom: valeur}
BINDINGS = {}    # refPath cible -> [ {sourceDevice, sourceEvent, targetFunction} ]
VERSE = {}       # chemin -> contenu
CVARS = {"ModelContextProtocol.PaginationPageSize": "0"}
NEXT_ID = [0]


def cfg():
  """Relit le fichier d'etat s'il existe : permet de changer un scenario sans relancer."""
  if STATE_FILE and os.path.exists(STATE_FILE):
    try:
      with open(STATE_FILE, "r", encoding="utf-8") as f:
        CFG.update(json.load(f))
    except (OSError, ValueError):
      pass
  return CFG


def new_ref(label: str) -> str:
  NEXT_ID[0] += 1
  return f"/Game/MockLevel.MockLevel:PersistentLevel.{label or 'Actor'}_{NEXT_ID[0]}"


def make_xform(loc=None, yaw=0.0, scale=None):
  loc = loc or {"x": 0.0, "y": 0.0, "z": 0.0}
  scale = scale or {"x": 1.0, "y": 1.0, "z": 1.0}
  return {"location": {k: float(loc.get(k, 0.0)) for k in "xyz"},
          "rotation": {"pitch": 0.0, "yaw": float(yaw), "roll": 0.0},
          "scale": {k: float(scale.get(k, 1.0)) for k in "xyz"}}


def actor(ref: str) -> dict | None:
  return ACTORS.get(ref)


def ref_of(args: dict, key: str = "actor"):
  v = args.get(key) or {}
  return v.get("refPath") if isinstance(v, dict) else None


def spawn(label: str, asset: str, xf: dict, kind: str, ignore_yaw: bool = False) -> dict:
  ref = new_ref(label)
  stored = make_xform(xf.get("location"), xf.get("rotation", {}).get("yaw", 0.0),
                      xf.get("scale"))
  if ignore_yaw:
    # Quirk reel : PlaceDevice ignore le yaw demande (0 demande, 90 relu).
    stored["rotation"]["yaw"] = 90.0
  ACTORS[ref] = {"label": label or "", "asset": asset, "xform": stored, "tags": [],
                 "kind": kind}
  return {"refPath": ref, "actorPath": ref, "label": label}


def tool(tool_name: str, args: dict):
  """Valeur renvoyee pour un outil. `None` = reponse vide (inconnu, pas absent)."""
  c = cfg()
  t = tool_name

  if t == "get_current_level":
    return "MockLevel"
  if t == "GetCVarValue":
    return CVARS.get(args.get("name", ""), "0")
  if t == "SetCVarValue":
    CVARS[args.get("name", "")] = str(args.get("value", ""))
    return CVARS[args.get("name", "")]
  if t == "GetSessionStatus":
    return c["session"]
  if t == "GetGameState":
    return {"state": "Mock"}

  if t == "add_to_scene_from_asset":
    return spawn(args.get("name", ""), args.get("asset_path", ""),
                 args.get("xform") or {}, "actor")
  if t == "PlaceDevice":
    return spawn("", (args.get("assetPath") or {}).get("refPath", ""),
                 args.get("transform") or {}, "device",
                 ignore_yaw=bool(c.get("ignore_yaw", True)))
  if t == "set_actor_transform":
    a = actor(ref_of(args))
    if a:
      a["xform"] = make_xform((args.get("xform") or {}).get("location"),
                              (args.get("xform") or {}).get("rotation", {}).get("yaw", 0.0),
                              (args.get("xform") or {}).get("scale"))
    return True
  if t == "get_actor_transform":
    a = actor(ref_of(args))
    if not a:
      return None
    xf = json.loads(json.dumps(a["xform"]))
    if c.get("drop_scale"):
      xf["scale"] = {"x": 1.0, "y": 1.0, "z": 1.0}
    return xf
  if t == "get_actor_bounds":
    a = actor(ref_of(args))
    if not a:
      return None
    size = [float(c["bounds_size"][i]) * a["xform"]["scale"][k]
            for i, k in enumerate("xyz")]
    loc = [a["xform"]["location"][k] for k in "xyz"]
    return {"min": {k: loc[i] - size[i] / 2.0 for i, k in enumerate("xyz")},
            "max": {k: loc[i] + size[i] / 2.0 for i, k in enumerate("xyz")},
            "isValid": True}
  if t == "set_label":
    a = actor(ref_of(args))
    if a:
      a["label"] = args.get("label", "")
    return True
  if t == "add_tag":
    a = actor(ref_of(args))
    if a and args.get("tag") not in a["tags"]:
      a["tags"].append(args.get("tag"))
    return True
  if t == "find_actors":
    name = args.get("name")
    tag = args.get("tag")
    out = []
    for ref, a in ACTORS.items():
      if name and name not in a["label"]:
        continue
      if tag and tag not in a["tags"]:
        continue
      out.append({"actorPath": ref, "refPath": ref, "label": a["label"],
                  "name": a["label"], "folderPath": "None"})
    return out
  if t == "remove_from_scene":
    return ACTORS.pop(ref_of(args), None) is not None

  if t == "list_properties":
    return [{"name": n} for n in c["props"]]
  if t == "set_properties":
    ref = ref_of(args, "instance")
    try:
      values = json.loads(args.get("values") or "{}")
    except ValueError:
      values = {}
    store = PROPS.setdefault(ref, {})
    overrides = c.get("prop_overrides") or {}
    for k, v in values.items():
      if isinstance(v, dict) and "teamIndex" in v and "teamType" not in v:
        # Quirk reel : l'enum complete est ajoutee a la relecture.
        v = {"teamType": "Any", **v}
      if k in overrides:
        # Simule un editeur qui normalise ou refuse une valeur : la relecture differe.
        v = overrides[k]
      store[k] = v
    return True
  if t == "get_properties":
    ref = ref_of(args, "instance")
    store = PROPS.get(ref, {})
    wanted = args.get("properties") or list(store)
    return json.dumps({k: store[k] for k in wanted if k in store})

  if t == "GetBindingOptions":
    return {"sourceEvents": ["OnTriggered", "OnEnabled"],
            "targetFunctions": ["Enable", "Disable", "Activate"]}
  if t == "AddEventBinding":
    dst = ref_of(args, "targetDevicePath")
    entry = {"sourceDevice": ref_of(args, "sourceDevicePath"),
             "sourceEvent": args.get("sourceEvent"),
             "targetFunction": args.get("targetFunction")}
    lst = BINDINGS.setdefault(dst, [])
    if entry not in lst:
      lst.append(entry)
    return True
  if t == "ListEventBindings":
    return BINDINGS.get(ref_of(args, "devicePath"), [])
  if t == "ListDeviceAssets":
    return [{"displayName": "Player Spawner Device",
             "assetPath": "/CRD_PlayerSpawn/ItemDefinitions/PID_CP_Devices_PlayerSpawner",
             "category": "Devices", "bIsVerseDevice": False}]

  if t == "ListFiles":
    return list(c["files"])
  if t == "Grep":
    pat = args.get("pattern", "")
    if pat and any(pat in s for s in c["symbols"]):
      return [{"path": c["files"][-1], "line": 1, "text": f"<{pat}>"}]
    return []
  if t == "ReadFile":
    return VERSE.get(args.get("path", ""))
  if t == "WriteFile":
    VERSE[args.get("path", "")] = args.get("content", "")
    return True
  if t == "BuildAll":
    return c["build_diags"]
  if t == "GetLogEntries":
    if args.get("category") == "VerseBuild":
      return c["build_log"]
    return [{"severity": "Info", "message": "mock log"}]

  if t == "SetCameraTransform":
    return True
  if t == "GetCameraTransform":
    return make_xform({"x": 1.0, "y": 2.0, "z": 3.0}, 0.0)

  if t == "find_assets":
    return [{"assetPath": "/Engine/BasicShapes/Cube.Cube", "assetName": "Cube"}]
  return None


def call_tool(toolset: str, tool_name: str, args: dict):
  """Contenu MCP d'un appel : enveloppe `returnValue`, image pour CaptureViewport."""
  if tool_name in cfg().get("fail_tools", []):
    return {"content": [{"type": "text",
                         "text": json.dumps({"error": f"boom du mock sur {tool_name}"})}],
            "isError": True}
  if tool_name == "CaptureViewport":
    return {"content": [{"type": "image", "mimeType": "image/png",
                         "data": base64.b64encode(base64.b64decode(PNG_1PX)).decode()}],
            "isError": False}
  if tool_name == "execute_tool_script":
    # Le script du CLI definit run() et appelle execute_tool(nom_complet, chaine_json).
    def execute_tool(full_name: str, args_json: str):
      sub = json.loads(args_json or "{}")
      res = tool(full_name.rsplit(".", 1)[-1], sub)
      if isinstance(res, dict) and res.get("isError"):
        raise RuntimeError(json.dumps(res))
      return {"returnValue": res}

    ns = {"execute_tool": execute_tool, "__name__": "mock_script"}
    try:
      exec(args.get("script", ""), ns)  # noqa: S102 - scripts generes par le CLI uniquement
      out = ns["run"]() if callable(ns.get("run")) else None
    except Exception as exc:  # un lot partiel ne doit pas perdre le reste
      out = {"placed": [], "errors": [["mock", f"{type(exc).__name__}: {exc}"]]}
    return {"content": [{"type": "text", "text": json.dumps(out)}], "isError": False}
  value = tool(tool_name, args or {})
  return {"content": [{"type": "text", "text": json.dumps({"returnValue": value})}],
          "isError": False}


class Handler(BaseHTTPRequestHandler):
  protocol_version = "HTTP/1.1"

  def log_message(self, *a):
    pass

  def _send(self, payload, status=200):
    body = json.dumps(payload).encode("utf-8")
    self.send_response(status)
    self.send_header("Content-Type", "application/json")
    self.send_header("Mcp-Session-Id", "mock-session")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def do_POST(self):
    n = int(self.headers.get("Content-Length", 0))
    try:
      req = json.loads(self.rfile.read(n) or b"{}")
    except ValueError:
      return self._send({"jsonrpc": "2.0", "error": {"message": "JSON invalide"}}, 400)
    method = req.get("method", "")
    if method == "initialize":
      return self._send({"jsonrpc": "2.0", "id": req.get("id"),
                         "result": {"protocolVersion": "2025-03-26"}})
    if "id" not in req:
      return self._send({"jsonrpc": "2.0", "result": {}})
    if MODE == "slow":
      time.sleep(5)
    if MODE == "error":
      return self._send({"jsonrpc": "2.0", "id": req["id"], "result": {
          "content": [{"type": "text", "text": '{"error": "boom du mock"}'}],
          "isError": True}})
    params = req.get("params", {}) or {}
    args = params.get("arguments", {}) or {}
    result = call_tool(args.get("toolset_name", ""), args.get("tool_name", ""),
                       args.get("arguments", {}) or {})
    return self._send({"jsonrpc": "2.0", "id": req["id"], "result": result})


if __name__ == "__main__":
  HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
