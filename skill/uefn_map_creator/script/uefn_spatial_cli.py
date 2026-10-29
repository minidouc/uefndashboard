#!/usr/bin/env python3
"""CLI spatial du skill uefn-map-creator (v2, MCP officiel UEFN).

Calculs hors ligne : init, validate-scene, validate-grid, compile-transforms, audit-scene,
  check-navigation, check-symmetry, list-editables, playtest-plan.
Actions editeur (MCP http://127.0.0.1:8000/mcp, editeur ouvert) :
  preflight, measure-palette, build-structure, place-scene, audit-scene --live,
  check-symmetry --live, apply-properties, wire-devices, verse-scan, verse-grep, verse-write,
  verse-build, visual-snapshot, cleanup.
--dry-run : calcule sans toucher l'editeur, statut DRY_RUN (jamais PASSED).
Editeur injoignable ou timeout : statut FAILED, code retour 2 ou 3.
Python 3.10 minimum (annotations `X | None`).
"""

import argparse
from collections import deque
from datetime import datetime, timezone
import base64
import json
import math
import os
import re
import shutil
import sys
import time

if sys.version_info < (3, 10):
  sys.stderr.write("uefn_spatial_cli.py exige Python 3.10 ou plus "
                   f"(interprete actuel : {sys.version.split()[0]}).\n")
  sys.exit(2)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import McpClient, McpError, McpOffline, McpTimeout  # noqa: E402
import spec_schema  # noqa: E402

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_ROOT = os.path.join(SKILL_ROOT, "templates")

TILE_SIZE_XY = 512.0
TILE_SIZE_Z = 384.0
PLAYER_RADIUS = 42.0
PLAYER_HEIGHT = 192.0
MIN_CORRIDOR_WIDTH = 100.0
MIN_CORRIDOR_HEIGHT = 200.0
MAX_JUMP_HEIGHT = 190.0
MAX_SPRINT_JUMP_LENGTH = 550.0
MAX_OVERLAP_CM = 5.0
MAX_GRAVITY_CM = 2.0
POS_TOLERANCE_CM = 0.5
YAW_TOLERANCE_DEG = 0.5
SCALE_TOLERANCE = 0.001
# Symetrie : les specs sont calculees, un miroir juste tombe a ~0. Au-dela de MIRROR_SEARCH_CM
# de decalage le partenaire est declare absent plutot que mal place (plus actionnable).
SYMMETRY_POS_TOLERANCE_CM = 1.0
SYMMETRY_YAW_TOLERANCE_DEG = 1.0
MIRROR_SEARCH_CM = 768.0
BATCH_SIZE = 10
PAGINATION_CVAR = "ModelContextProtocol.PaginationPageSize"
MAP_TAG = os.environ.get("UEFN_MAP_TAG", "UEFNMAP")
MEASURE_AT = [0.0, -20000.0, 5000.0]
VERSE_BUILD_LOG = "VerseBuild"

SPAWN = "editor_toolset.toolsets.scene.SceneTools.add_to_scene_from_asset"
ADD_TAG = "editor_toolset.toolsets.actor.ActorTools.add_tag"

SPEC_FILES = ["01_gdd.json", "02_palette.json", "03_grid.json", "04_devices.json",
              "05_props.json"]


def load_json(path: str) -> dict:
  with open(path, "r", encoding="utf-8") as f:
    return json.load(f)


def save_json(path: str, data) -> None:
  os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
  with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)


def emit(result: dict) -> None:
  print(json.dumps(result, indent=2, ensure_ascii=False))


def now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def client_for(workspace: str) -> McpClient:
  return McpClient(log_path=os.path.join(workspace, "_mcp_calls.jsonl"))


def resolve_workspace(path: str, command: str) -> str | None:
  """Chemin absolu du workspace, ou None si l'erreur a deja ete affichee.

  `--workspace workspace_map` lance depuis la racine du skill ecrivait l'etat de la carte DANS
  le skill : fichiers de carte melanges aux references, et commits accidentels. Le workspace
  doit donc etre hors de l'arborescence du skill (echappatoire : UEFN_ALLOW_WORKSPACE_IN_SKILL).
  """
  ws = os.path.abspath(os.path.expanduser(path))
  try:
    inside = os.path.commonpath([ws, SKILL_ROOT]) == SKILL_ROOT
  except ValueError:
    inside = False  # lecteur different : forcement hors du skill
  if inside and not os.environ.get("UEFN_ALLOW_WORKSPACE_IN_SKILL"):
    emit({"status": "FAILED", "command": command, "error_kind": "WORKSPACE_INSIDE_SKILL",
          "workspace": ws, "skill_root": SKILL_ROOT,
          "next": "Pointer --workspace hors du skill (ex. ~/uefn-workspaces/<nom_de_carte>) ; "
                  "`init` cree le dossier et ses 5 fichiers."})
    return None
  return ws


def list_templates() -> list[str]:
  if not os.path.isdir(TEMPLATES_ROOT):
    return []
  return sorted(d for d in os.listdir(TEMPLATES_ROOT)
                if os.path.isdir(os.path.join(TEMPLATES_ROOT, d)))


# 1 = FAILED (l'appel a ete traite : l'etat peut etre partiel), 2 = OFFLINE (rien execute),
# 3 = TIMEOUT (etat inconnu). Confondre 1 et 2 fait relancer a l'aveugle et cree des doublons.
EXIT_CODES = {"TOOL_ERROR": 1, "OFFLINE": 2, "TIMEOUT_OUTCOME_UNKNOWN": 3}
NEXT_STEP = {
    "TOOL_ERROR": "L'appel a ete traite : relire l'etat (_placed.json, find_actors) avant de rejouer.",
    "TIMEOUT_OUTCOME_UNKNOWN": "Relire l'etat (find_actors, get_actor_transform) avant de rejouer.",
}


def mcp_failure(command: str, exc: Exception, extra: dict | None = None) -> int:
  kind = {McpOffline: "OFFLINE", McpTimeout: "TIMEOUT_OUTCOME_UNKNOWN"}.get(
      type(exc), "TOOL_ERROR")
  out = {"status": "FAILED", "command": command, "error_kind": kind,
         "error": str(exc)}
  if kind in NEXT_STEP:
    out["next"] = NEXT_STEP[kind]
  if extra:
    out.update(extra)
  emit(out)
  return EXIT_CODES[kind]


# ---------------------------------------------------------------- geometrie

def xyz_to_luf(xyz: list[float]) -> list[float]:
  x, y, z = xyz
  return [-y, z, x]


def luf_to_xyz(luf: list[float]) -> list[float]:
  left, up, forward = luf
  return [forward, -left, up]


def angle_delta(a: float, b: float) -> float:
  """Ecart entre deux yaws en degres, sans se faire pieger par le passage 359 -> 0."""
  return abs(((a - b) + 180.0) % 360.0 - 180.0)


def xform(loc: list[float], yaw: float = 0.0, scale: list[float] | None = None) -> dict:
  s = scale or [1.0, 1.0, 1.0]
  return {"location": {"x": loc[0], "y": loc[1], "z": loc[2]},
          "rotation": {"pitch": 0.0, "yaw": yaw, "roll": 0.0},
          "scale": {"x": s[0], "y": s[1], "z": s[2]}}


def rotate_xy(v: list[float], yaw_deg: float) -> list[float]:
  r = math.radians(yaw_deg)
  c, s = math.cos(r), math.sin(r)
  return [v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2]]


def rotated_size(size: list[float], yaw_deg: float) -> list[float]:
  """Taille de la boite alignee aux axes apres rotation en yaw."""
  r = math.radians(yaw_deg)
  c, s = abs(math.cos(r)), abs(math.sin(r))
  return [round(size[0] * c + size[1] * s, 2), round(size[0] * s + size[1] * c, 2),
          size[2]]


def loc_from_center(center: list[float], pivot: list[float], yaw: float) -> list[float]:
  """pivot_offset_cm = centre des bounds - position de l'acteur, mesure a yaw 0."""
  p = rotate_xy(pivot, yaw)
  return [round(center[i] - p[i], 2) for i in range(3)]


def grid_origin(grid: dict) -> list[int]:
  """Decalage en tuiles (Brush_0 avoidance). Defaut [0, 0, 0] si absent."""
  o = grid.get("origin_tile") if isinstance(grid, dict) else None
  if isinstance(o, list) and len(o) == 3 and all(
      isinstance(v, int) and not isinstance(v, bool) for v in o):
    return [int(o[0]), int(o[1]), int(o[2])]
  return [0, 0, 0]


def anchor_center(tile: list[int], slot: str, size_cm: list[float],
                  origin: list[int] | None = None) -> list[float]:
  ox, oy, oz = origin or [0, 0, 0]
  tx, ty, tz = tile[0] + ox, tile[1] + oy, tile[2] + oz
  hx, hy = size_cm[0] / 2.0, size_cm[1] / 2.0
  bx, by, bz = tx * TILE_SIZE_XY, ty * TILE_SIZE_XY, tz * TILE_SIZE_Z
  anchors = {
      "CENTER": (bx + 256.0, by + 256.0),
      "NORTH_EDGE": (bx + TILE_SIZE_XY - hx, by + 256.0),
      "SOUTH_EDGE": (bx + hx, by + 256.0),
      "EAST_EDGE": (bx + 256.0, by + TILE_SIZE_XY - hy),
      "WEST_EDGE": (bx + 256.0, by + hy),
      "CORNER_NE": (bx + TILE_SIZE_XY - hx, by + TILE_SIZE_XY - hy),
      "CORNER_NW": (bx + TILE_SIZE_XY - hx, by + hy),
      "CORNER_SE": (bx + hx, by + TILE_SIZE_XY - hy),
      "CORNER_SW": (bx + hx, by + hy),
  }
  if slot not in anchors:
    raise ValueError(f"Slot invalide: {slot}")
  cx, cy = anchors[slot]
  return [round(cx, 2), round(cy, 2), round(bz + size_cm[2] / 2.0, 2)]


def resolve_yaw(face_towards: str, pos: list[float], registry: dict,
                arena_center: list[float]) -> float:
  cardinals = {"NORTH": 0.0, "EAST": 90.0, "SOUTH": 180.0, "WEST": 270.0}
  if face_towards in cardinals:
    return cardinals[face_towards]
  target = arena_center if face_towards == "CENTER" else None
  if face_towards in registry:
    target = registry[face_towards]["center_cm"]
  if target:
    angle = math.degrees(math.atan2(target[1] - pos[1], target[0] - pos[0]))
    return round(angle % 360.0, 2)
  raise ValueError(f"face_towards inconnu: {face_towards}")


def relative_center(parent: dict, child_size: list[float], direction: str,
                    gap_cm: float, snap_to_floor: bool) -> list[float]:
  pc, ps = parent["center_cm"], parent["size_cm"]
  yaw_rad = math.radians(parent.get("yaw", 0.0))
  fwd = (round(math.cos(yaw_rad), 4), round(math.sin(yaw_rad), 4))
  right = (round(-math.sin(yaw_rad), 4), round(math.cos(yaw_rad), 4))
  dir_map = {
      "IN_FRONT_OF": (fwd[0], fwd[1], 0.0, 0),
      "BEHIND": (-fwd[0], -fwd[1], 0.0, 0),
      "RIGHT_OF": (right[0], right[1], 0.0, 1),
      "LEFT_OF": (-right[0], -right[1], 0.0, 1),
      "ON_TOP_OF": (0.0, 0.0, 1.0, 2),
  }
  if direction not in dir_map:
    raise ValueError(f"Direction invalide: {direction}")
  ux, uy, uz, axis = dir_map[direction]
  dist = ps[axis] / 2.0 + float(gap_cm) + child_size[axis] / 2.0
  cx, cy = pc[0] + ux * dist, pc[1] + uy * dist
  if snap_to_floor and direction != "ON_TOP_OF":
    cz = pc[2] - ps[2] / 2.0 + child_size[2] / 2.0
  else:
    cz = pc[2] + uz * dist
  return [round(cx, 2), round(cy, 2), round(cz, 2)]


def aabb_penetration_cm(a: dict, b: dict) -> float:
  ca, sa = a["center_cm"], a["size_cm"]
  cb, sb = b["center_cm"], b["size_cm"]
  overlaps = []
  for i in range(3):
    dist = abs(ca[i] - cb[i])
    min_dist = sa[i] / 2.0 + sb[i] / 2.0
    if dist >= min_dist:
      return 0.0
    overlaps.append(min_dist - dist)
  return round(min(overlaps), 2)


def bounds_to_center_size(b: dict) -> tuple[list[float], list[float]]:
  mn, mx = b["min"], b["max"]
  size = [round(mx[k] - mn[k], 2) for k in "xyz"]
  center = [round((mx[k] + mn[k]) / 2.0, 2) for k in "xyz"]
  return center, size


def asset_scale(entry: dict) -> list[float]:
  """Mise a l'echelle uniforme (nombre) ou par axe ([x, y, z]).

  Indispensable pour batir avec des primitives moteur : un Cube de 100 cm n'a aucune raison
  de faire 512 x 512 x 32. La taille et le pivot mesures a l'echelle 1 sont multiplies par
  le meme facteur, la transform posee porte l'echelle.
  """
  s = entry.get("scale", 1.0)
  if isinstance(s, bool):
    raise ValueError(f"scale invalide : {s!r}")
  if isinstance(s, (int, float)):
    return [float(s)] * 3
  if isinstance(s, list) and len(s) == 3 and all(
      isinstance(v, (int, float)) and not isinstance(v, bool) for v in s):
    return [float(v) for v in s]
  raise ValueError(f"scale doit etre un nombre ou [x, y, z] : {s!r}")


def asset_size_pivot(palette: dict, key: str) -> tuple[list[float], list[float], str, list[float]]:
  a = palette.get(key)
  if not a:
    raise KeyError(f"asset_key absent de 02_palette.json : {key}")
  if not a.get("measured"):
    raise KeyError(f"asset non mesure (lancer measure-palette) : {key}")
  scale = asset_scale(a)
  size = [round(a["size_cm"][i] * scale[i], 2) for i in range(3)]
  pivot = [round(a["pivot_offset_cm"][i] * scale[i], 2) for i in range(3)]
  return size, pivot, a["uefn_path"], scale


# ---------------------------------------------------------------- MCP : placement

def placed_path(workspace: str) -> str:
  return os.path.join(workspace, "_placed.json")


def load_placed(workspace: str) -> dict:
  p = placed_path(workspace)
  return load_json(p) if os.path.exists(p) else {}


def batch_script(specs: list[dict]) -> str:
  return "\n".join([
      "import json",
      "SPECS = json.loads(" + json.dumps(json.dumps(specs)) + ")",
      "def run():",
      "    placed = []",
      "    errors = []",
      "    for s in SPECS:",
      "        try:",
      f"            a = execute_tool('{SPAWN}', json.dumps({{'asset_path': s['asset'], 'name': s['label'], 'xform': s['xform'], 'snap_to_ground': False}}))['returnValue']",
      f"            execute_tool('{ADD_TAG}', json.dumps({{'actor': {{'refPath': a['refPath']}}, 'tag': s['tag']}}))",
      "            placed.append([s['label'], a['refPath']])",
      "        except Exception as e:",
      "            errors.append([s['label'], str(e)])",
      "    return {'placed': placed, 'errors': errors}",
  ])


def full_object_path(p: str) -> str:
  """Device.PlaceDevice exige un chemin d'objet complet /Pkg/Sub/Nom.Nom en UEFN 42.40."""
  s = str(p or "").strip()
  last = s.rsplit("/", 1)[-1]
  return f"{s}.{last}" if last and "." not in last else s


# Legalite : le PREFIXE d'un chemin ne prouve rien. Le 2026-10-29, le validateur UEFN
# (FortValidator_FortExposedActors) a accepte des /Game/Athena/Items/... et /Game/Creative/...,
# et refuse des /BlastBerryWeapons/... et /Figment_Athena_*/... . La verite est donc le catalogue
# commun, alimente par la lecture du journal du validateur (commande check-validator).
# Regle : agent-team/_commun/legalite-assets.md
CATALOGUE_PATH = os.environ.get("UEFN_CATALOGUE") or os.path.join(
    os.path.dirname(os.path.dirname(SKILL_ROOT)), "agent-team", "_commun", "catalogue-verifie.json")
_CATALOGUE: dict | None = None


def load_catalogue(force: bool = False) -> dict:
  """Catalogue commun des assets prouves (acceptes / refuses). {} s'il est absent."""
  global _CATALOGUE
  if _CATALOGUE is None or force:
    try:
      with open(CATALOGUE_PATH, encoding="utf-8") as f:
        _CATALOGUE = json.load(f)
    except (OSError, ValueError):
      _CATALOGUE = {}
  return _CATALOGUE


def _catalogue_index() -> tuple[set, set, list]:
  cat = load_catalogue()
  acc = cat.get("acceptes", {})
  accepted = {v["chemin"] for k, v in acc.get("props", {}).items()
              if isinstance(v, dict) and v.get("chemin")}
  accepted |= {v["pid"] for v in acc.get("devices", {}).values()
               if isinstance(v, dict) and v.get("pid") and not v.get("statut")}
  for groupe in ("armes", "consommables"):
    accepted |= {v for v in acc.get("objets", {}).get(groupe, {}).values() if isinstance(v, str)}
  ref = cat.get("refuses", {})
  refused = set(ref.get("chemins", [])) | set(
      ref.get("non_verifies_mais_suspects", {}).get("chemins", []))
  familles = [re.compile("^" + re.escape(f.split("/...")[0]).replace(r"\*", "[^/]*") + "(/|$)")
              for f in ref.get("familles", [])]
  return accepted, refused, familles


def legal_status(path: str) -> str:
  """VERIFIED (catalogue acceptes), REFUSED (catalogue refuses), PATTERN (forme Creatif usuelle,
  non prouvee mais historiquement acceptee), UNVERIFIED (/Game/... absent du catalogue)."""
  p = str(path or "").strip()
  if not p:
    return "PATTERN"
  accepted, refused, familles = _catalogue_index()
  pkg = p.split(".")[0]
  if p in refused or pkg in {r.split(".")[0] for r in refused} or any(f.match(p) for f in familles):
    return "REFUSED"
  if p in accepted or pkg in {a.split(".")[0] for a in accepted}:
    return "VERIFIED"
  if p in ("/Game/C.SM_Crate", "/Fortnite/Game/Props/Ramp"):
    return "PATTERN"
  if p.startswith(("/Engine/BasicShapes/", "/Fortnite/")):
    return "PATTERN"
  obj_name = p.rsplit("/", 1)[-1].split(".")[0]
  if obj_name.startswith(("PPID_", "PID_")) or "/PPIDs/" in p:
    return "PATTERN"
  if p.startswith("/Game/"):
    return "UNVERIFIED"
  return "PATTERN"


def is_legal_uefn_path(path: str) -> bool:
  """False pour un chemin REFUSED ; pour un /Game/ UNVERIFIED, False par defaut (prudence) sauf
  UEFN_ALLOW_UNVERIFIED=1, qui permet d'essayer un nouvel asset avant de le faire juger par
  `check-validator`."""
  s = legal_status(path)
  if s == "REFUSED":
    return False
  if s == "UNVERIFIED":
    return os.environ.get("UEFN_ALLOW_UNVERIFIED") == "1"
  return True


def legality_error(asset_key: str, path: str, where: str | None = None) -> dict:
  """Erreur de legalite explicite : refuse par le validateur, ou simplement non prouve."""
  refused = legal_status(path) == "REFUSED"
  err = {"type": "ILLEGAL_ASSET_PATH" if refused else "UNVERIFIED_ASSET_PATH",
         "asset": asset_key, "uefn_path": path}
  if where:
    err["where"] = where
  err["detail"] = (
      "Refuse par le validateur UEFN (catalogue commun -> refuses) : remplacer par un asset de "
      "catalogue-verifie.json -> acceptes." if refused else
      "Chemin /Game/ absent du catalogue commun : legalite non prouvee. Utiliser un asset 'acceptes', "
      "ou relancer avec UEFN_ALLOW_UNVERIFIED=1 puis faire juger par `check-validator` "
      "(le prefixe /Game/ ne prouve PAS l'illegalite).")
  return err


def find_by_label(cli: McpClient, label: str) -> str | None:
  found = cli.value("Scene", "find_actors", {"name": label, "collision_channels": []}) or []
  exact = [a for a in found if label in (a.get("label"), a.get("name"))]
  return exact[0]["actorPath"] if len(exact) == 1 else None


def xforms_equal(a: dict | None, b: dict | None) -> bool:
  if not isinstance(a, dict) or not isinstance(b, dict):
    return False
  la, lb = a.get("location") or {}, b.get("location") or {}
  ra, rb = a.get("rotation") or {}, b.get("rotation") or {}
  sa, sb = a.get("scale") or {}, b.get("scale") or {}
  dl = max(abs(float(la.get(k, 0.0)) - float(lb.get(k, 0.0))) for k in "xyz")
  dyaw = angle_delta(float(ra.get("yaw", 0.0)), float(rb.get("yaw", 0.0)))
  ds = max(abs(float(sa.get(k, 1.0)) - float(sb.get(k, 1.0))) for k in "xyz")
  return dl <= POS_TOLERANCE_CM and dyaw <= YAW_TOLERANCE_DEG and ds <= SCALE_TOLERANCE


def verify_transform(cli: McpClient, ref: str, op: dict) -> dict | None:
  tf = cli.value("Actor", "get_actor_transform", {"actor": {"refPath": ref}})
  want = op["xform"]
  dl = max(abs(tf["location"][k] - want["location"][k]) for k in "xyz")
  dyaw = angle_delta(tf["rotation"]["yaw"], want["rotation"]["yaw"])
  got = tf.get("scale") or {}
  dscale = max(abs(float(got.get(k, 1.0)) - want["scale"][k]) for k in "xyz")
  if dl > POS_TOLERANCE_CM or dyaw > YAW_TOLERANCE_DEG or dscale > SCALE_TOLERANCE:
    err = {"type": "TRANSFORM_MISMATCH", "actor": op["label"],
           "requested": want, "read_back": tf}
    if dscale > SCALE_TOLERANCE and dl <= POS_TOLERANCE_CM:
      err["detail"] = ("position juste, echelle non appliquee ou non relue : les controles de "
                       "collision utilisent une taille fausse")
    return err
  return None


def place_actors(cli: McpClient, workspace: str, ops: list[dict]) -> dict:
  """Spawn par lots de 10 dans execute_tool_script, ou mise a jour en place si xform a change."""
  placed = load_placed(workspace)
  todo = [o for o in ops if o["label"] not in placed]
  to_update = [o for o in ops if o["label"] in placed
               and not xforms_equal(placed[o["label"]].get("xform"), o["xform"])]
  errors, warnings, verified, updated = [], [], 0, 0
  for op in to_update:
    ref = placed[op["label"]]["refPath"]
    cli.value("Actor", "set_actor_transform", {"actor": {"refPath": ref}, "xform": op["xform"],
                                               "worldspace": True})
    placed[op["label"]]["xform"] = op["xform"]
    save_json(placed_path(workspace), placed)
    err = verify_transform(cli, ref, op)
    if err:
      errors.append(err)
    else:
      verified += 1
      updated += 1
  for i in range(0, len(todo), BATCH_SIZE):
    batch = todo[i:i + BATCH_SIZE]
    specs = [{"asset": o["asset"], "label": o["label"], "xform": o["xform"],
              "tag": MAP_TAG} for o in batch]
    try:
      res = cli.script(batch_script(specs))
      pairs = res.get("placed", []) if isinstance(res, dict) else []
      errors += [{"type": "SPAWN_ERROR", "actor": l, "error": e}
                 for l, e in (res.get("errors", []) if isinstance(res, dict) else [])]
    except McpOffline:
      raise
    except McpError as exc:
      # Timeout ou script interrompu : l'editeur a pu creer une partie du lot, relire.
      pairs = [(o["label"], r) for o in batch if (r := find_by_label(cli, o["label"]))]
      found = {l for l, _ in pairs}
      missing = [o["label"] for o in batch if o["label"] not in found]
      warnings.append({"type": "BATCH_RECOVERED", "error": str(exc),
                       "recovered": len(found), "missing": missing})
      errors += [{"type": "SPAWN_ERROR", "actor": l, "error": "absent apres relecture"}
                 for l in missing]
    by_label = {o["label"]: o for o in batch}
    for label, ref in pairs:
      placed[label] = {"refPath": ref, "asset": by_label[label]["asset"],
                       "kind": "actor", "xform": by_label[label]["xform"]}
    save_json(placed_path(workspace), placed)
    for label, ref in pairs:
      err = verify_transform(cli, ref, by_label[label])
      if err:
        errors.append(err)
      else:
        verified += 1
  return {"requested": len(ops), "already_placed": len(ops) - len(todo) - len(to_update),
          "updated": updated, "verified": verified, "errors": errors, "warnings": warnings}


def place_devices(cli: McpClient, workspace: str, ops: list[dict]) -> dict:
  """PlaceDevice ignore le yaw demande (0 relu 90) : forcer la transform puis relire."""
  placed = load_placed(workspace)
  errors, verified, updated = [], 0, 0
  for op in ops:
    if op["label"] in placed:
      if not xforms_equal(placed[op["label"]].get("xform"), op["xform"]):
        ref_str = placed[op["label"]]["refPath"]
        cli.value("Actor", "set_actor_transform", {"actor": {"refPath": ref_str},
                                                   "xform": op["xform"], "worldspace": True})
        placed[op["label"]]["xform"] = op["xform"]
        save_json(placed_path(workspace), placed)
        err = verify_transform(cli, ref_str, op)
        if err:
          errors.append(err)
        else:
          verified += 1
          updated += 1
      continue
    ref = cli.value("Device", "PlaceDevice", {"assetPath": {"refPath": full_object_path(op["asset"])},
                                              "transform": op["xform"]})
    if not isinstance(ref, dict) or not ref.get("refPath"):
      errors.append({"type": "SPAWN_ERROR", "actor": op["label"], "error": json.dumps(ref)})
      continue
    placed[op["label"]] = {"refPath": ref["refPath"], "asset": op["asset"],
                           "kind": "device", "xform": op["xform"]}
    save_json(placed_path(workspace), placed)
    actor = {"refPath": ref["refPath"]}
    cli.value("Actor", "set_actor_transform", {"actor": actor, "xform": op["xform"],
                                               "worldspace": True})
    cli.value("Actor", "set_label", {"actor": actor, "label": op["label"]})
    cli.value("Actor", "add_tag", {"actor": actor, "tag": MAP_TAG})
    err = verify_transform(cli, ref["refPath"], op)
    if err:
      errors.append(err)
    else:
      verified += 1
  return {"requested": len(ops), "updated": updated, "verified": verified, "errors": errors}


# ---------------------------------------------------------------- commandes

def cmd_init(workspace: str, template: str, force: bool) -> int:
  src = os.path.join(TEMPLATES_ROOT, template)
  if not os.path.isdir(src):
    emit({"status": "FAILED", "command": "init", "error_kind": "TEMPLATE_UNKNOWN",
          "template": template, "templates": list_templates()})
    return 1
  existing = [n for n in os.listdir(workspace)] if os.path.isdir(workspace) else []
  if existing and not force:
    emit({"status": "FAILED", "command": "init", "error_kind": "WORKSPACE_NOT_EMPTY",
          "workspace": workspace, "existing": sorted(existing),
          "next": "un workspace deja rempli n'est jamais ecrase : choisir un autre chemin, "
                  "ou --force pour recopier le gabarit par-dessus (les fichiers absents du "
                  "gabarit sont conserves)."})
    return 1
  os.makedirs(workspace, exist_ok=True)
  copied = []
  for root, dirs, files in os.walk(src):
    rel = os.path.relpath(root, src)
    target_dir = os.path.join(workspace, rel) if rel != "." else workspace
    os.makedirs(target_dir, exist_ok=True)
    for name in files:
      shutil.copyfile(os.path.join(root, name), os.path.join(target_dir, name))
      copied.append(os.path.relpath(os.path.join(target_dir, name), workspace).replace("\\", "/"))
  os.makedirs(os.path.join(workspace, "verse"), exist_ok=True)
  errors, warnings = validate_workspace_files(workspace)
  emit({"status": "PASSED" if not errors else "FAILED", "command": "init",
        "template": template, "workspace": workspace, "created": sorted(copied),
        "error_count": len(errors), "errors": errors, "warnings": warnings,
        "next": "etape 0 : `preflight`, puis faire confirmer le niveau par l'utilisateur. "
                "Les chemins d'assets marques note_a_verifier ou a_chercher doivent etre "
                "confirmes (ListDeviceAssets / find_assets) avant `measure-palette`."})
  return 0 if not errors else 1


def cmd_preflight(workspace: str) -> int:
  cli = client_for(workspace)
  try:
    ping = cli.ping()
    before = cli.value("EditorApp", "GetCVarValue", {"name": PAGINATION_CVAR})
    if str(before) != "200":
      cli.value("EditorApp", "SetCVarValue", {"name": PAGINATION_CVAR, "value": "200"})
    after = cli.value("EditorApp", "GetCVarValue", {"name": PAGINATION_CVAR})
    session = cli.value("Session", "GetSessionStatus", {})
  except McpError as exc:
    return mcp_failure("preflight", exc)
  ok = str(after) == "200"
  emit({"status": "PASSED" if ok else "FAILED", "level": ping["level"],
        "ping_ms": ping["ms"], "pagination_before": before, "pagination_after": after,
        "session": session,
        "next": "Confirmer avec l'utilisateur que ce niveau est le bon avant d'ecrire."})
  return 0 if ok else 1


def measure_one(cli: McpClient, key: str, item: dict) -> dict:
  is_device = str(item.get("category", "")).upper().startswith("DEVICE")
  xf = xform(MEASURE_AT, 0.0)
  if is_device:
    ref = cli.value("Device", "PlaceDevice", {"assetPath": {"refPath": full_object_path(item["uefn_path"])},
                                              "transform": xf})
  else:
    ref = cli.value("Scene", "add_to_scene_from_asset", {
        "asset_path": item["uefn_path"], "name": f"MEASURE_{key}", "xform": xf,
        "snap_to_ground": False})
  if not isinstance(ref, dict) or not ref.get("refPath"):
    raise McpError(f"spawn sans reference : {json.dumps(ref)}")
  actor = {"refPath": ref["refPath"]}
  try:
    cli.value("Actor", "add_tag", {"actor": actor, "tag": MAP_TAG})
    if is_device:
      cli.value("Actor", "set_actor_transform", {"actor": actor, "xform": xf,
                                                 "worldspace": True})
    tf = cli.value("Actor", "get_actor_transform", {"actor": actor})
    b = cli.value("Actor", "get_actor_bounds", {"actor": actor})
  finally:
    cli.value("Scene", "remove_from_scene", {"actor": actor})
  if abs(tf["rotation"]["yaw"]) > YAW_TOLERANCE_DEG:
    raise McpError(f"yaw relu {tf['rotation']['yaw']} au lieu de 0 : mesure faussee")
  if not b or not b.get("isValid"):
    raise McpError(f"bounds invalides : {json.dumps(b)}")
  center, size = bounds_to_center_size(b)
  loc = [tf["location"][k] for k in "xyz"]
  return {"size_cm": size,
          "pivot_offset_cm": [round(center[i] - loc[i], 2) for i in range(3)],
          "measured": {"at": now_iso(), "kind": "device" if is_device else "actor"}}


def cmd_measure_palette(workspace: str, dry_run: bool, force: bool) -> int:
  gdd_path = os.path.join(workspace, "01_gdd.json")
  palette_path = os.path.join(workspace, "02_palette.json")
  palette = load_json(palette_path) if os.path.exists(palette_path) else {"assets": {}}
  if os.path.exists(gdd_path):
    for k, v in load_json(gdd_path).get("requested_assets", {}).items():
      palette["assets"].setdefault(k, v)
  assets = palette["assets"]
  errors = [{"asset": k, "error": "uefn_path manquant"}
            for k, v in assets.items() if not v.get("uefn_path")]
  for k, v in assets.items():
    if v.get("uefn_path") and not is_legal_uefn_path(v.get("uefn_path")):
      errors.append(legality_error(k, v.get("uefn_path")))
  todo = [k for k, v in assets.items()
          if v.get("uefn_path") and is_legal_uefn_path(v.get("uefn_path")) and (force or not v.get("measured"))]
  if dry_run:
    emit({"status": "DRY_RUN", "to_measure": todo, "errors": errors})
    return 0 if not errors else 1
  cli = client_for(workspace)
  for k in todo:
    try:
      assets[k].update(measure_one(cli, k, assets[k]))
    except (McpOffline, McpTimeout) as exc:
      save_json(palette_path, palette)
      return mcp_failure("measure-palette", exc, {"measured_so_far": [
          x for x in todo if assets[x].get("measured")]})
    except McpError as exc:
      errors.append({"asset": k, "error": str(exc)})
    save_json(palette_path, palette)
  invalid = [k for k, v in assets.items()
             if not v.get("measured") or any(d <= 0 for d in v.get("size_cm", [0, 0, 0]))]
  ok = not invalid and not errors
  emit({"status": "PASSED" if ok else "FAILED", "error_count": len(errors) + len(invalid),
        "errors": errors, "unmeasured_or_invalid": invalid, "palette_file": palette_path})
  return 0 if ok else 1


def cmd_validate_grid(grid_file: str) -> int:
  data = load_json(grid_file)
  floors = data.get("floors", [])
  errors = []
  axis = data.get("symmetry_axis")
  if data.get("symmetric") and axis not in spec_schema.AXES:
    errors.append({"type": "SYMMETRY_AXIS_UNSUPPORTED", "symmetry_axis": axis,
                   "detail": "symmetric: true exige symmetry_axis \"X\", \"Y\" ou \"R180\" : "
                             "aucun controle de symetrie n'a ete fait."})
  # Miroir sur les lignes (X) : Nord <-> Sud. Miroir sur les colonnes (Y) : Est <-> Ouest.
  # Rotation 180 (R180) : les deux a la fois, et les equipes s'echangent (S1 <-> S2).
  # En miroir X/Y les equipes ne sont PAS echangees : une carte peut separer ses equipes sur
  # l'autre axe (gabarit `boxfight` : S1 au Nord, S2 au Sud, miroir X des formes). Exiger
  # l'echange casserait ces cartes a tort. Seul R180 retourne la carte entierement.
  swap = {"X": {"R_N": "R_S", "R_S": "R_N"},
          "Y": {"R_E": "R_W", "R_W": "R_E"},
          "R180": {"R_N": "R_S", "R_S": "R_N", "R_E": "R_W", "R_W": "R_E",
                   "S1": "S2", "S2": "S1"}}.get(axis, {})

  def team_norm(cell: str) -> str:
    if not isinstance(cell, str):
      return ""  # deja signale par BAD_TYPE/BAD_CELL : ne pas crasher ici
    # En rotation les spawns doivent changer d'equipe : S1 et S2 restent distincts.
    return cell if axis == "R180" else cell.replace("S1", "S").replace("S2", "S")

  def mirrored(cell: str) -> str:
    """Ce que devient la cellule apres reflet. Le reflet ne s'applique que d'un cote :
    deux R_N face a face ne sont PAS symetriques, il faut R_N d'un cote et R_S de l'autre."""
    c = team_norm(cell)
    return swap.get(c, c)

  if not floors:
    errors.append({"type": "EMPTY_GRID", "detail": "Aucun etage defini."})
  else:
    floor_map = {f["z_index"]: f["matrix"] for f in floors}
    for z_idx, matrix in floor_map.items():
      rows = len(matrix)
      cols = len(matrix[0]) if rows > 0 else 0
      ragged = False
      for r in range(rows):
        if len(matrix[r]) != cols:
          errors.append({"type": "RAGGED_ROW", "row": r, "z_index": z_idx})
          ragged = True
          continue
        for c in range(cols):
          cell = matrix[r][c]
          if (r in (0, rows - 1) or c in (0, cols - 1)) and cell not in ("#", "V"):
            errors.append({"type": "UNCLOSED_BORDER", "tile": [r, c, z_idx], "cell": cell})
          if isinstance(cell, str) and cell.startswith("R_"):
            upper = floor_map.get(z_idx + 1)
            if upper:
              up_cell = upper[r][c] if r < len(upper) and c < len(upper[r]) else None
              if up_cell != "T":
                errors.append({"type": "HEADROOM_BLOCKED_ON_STAIRS",
                               "stair_tile": [r, c, z_idx], "upper_tile": [r, c, z_idx + 1],
                               "current_upper_cell": up_cell, "required_upper_cell": "T"})
      if data.get("symmetric") and axis in spec_schema.AXES and not ragged:
        def mirror_rc(r: int, c: int) -> tuple[int, int]:
          if axis == "X":
            return rows - 1 - r, c
          if axis == "Y":
            return r, cols - 1 - c
          return rows - 1 - r, cols - 1 - c

        pairs, plane = [], []
        for r in range(rows):
          for c in range(cols):
            m = mirror_rc(r, c)
            if (r, c) < m:
              pairs.append((r, c, m[0], m[1]))
            elif (r, c) == m:
              plane.append((r, c))
        for ra, ca, rb, cb in pairs:
          if mirrored(matrix[ra][ca]) != team_norm(matrix[rb][cb]):
            errors.append({"type": "SYMMETRY_BROKEN", "axis": axis,
                           "tile_a": [ra, ca, z_idx], "tile_b": [rb, cb, z_idx]})
        # Une case posee SUR le plan de symetrie n'a pas de partenaire possible : elle doit
        # etre son propre miroir. Un R_N ou un spawn unique au centre casse la symetrie.
        for r, c in plane:
          if mirrored(matrix[r][c]) != team_norm(matrix[r][c]):
            errors.append({"type": "SYMMETRY_ON_AXIS", "axis": axis, "tile": [r, c, z_idx],
                           "cell": matrix[r][c],
                           "detail": "case sur le plan de symetrie : elle doit etre son propre "
                                     "miroir (#, ., P, O, T, V)."})
    base = floor_map.get(0, [])
    spawns = [(r, c) for r, row in enumerate(base) for c, v in enumerate(row) if v in ("S1", "S2")]
    targets = [(r, c) for r, row in enumerate(base) for c, v in enumerate(row) if v in ("O", "S2")]
    if not spawns:
      errors.append({"type": "NO_SPAWN_FOUND", "z_index": 0})
    elif targets:
      walkable = {".", "P", "S1", "S2", "O", "R_N", "R_S", "R_E", "R_W"}
      visited, queue = set(), deque([spawns[0]])
      while queue:
        cr, cc = queue.popleft()
        if (cr, cc) in visited:
          continue
        visited.add((cr, cc))
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
          nr, nc = cr + dr, cc + dc
          if (0 <= nr < len(base) and 0 <= nc < len(base[nr])
              and base[nr][nc] in walkable and (nr, nc) not in visited):
            queue.append((nr, nc))
      for tr, tc in targets:
        if (tr, tc) not in visited:
          errors.append({"type": "UNREACHABLE_TARGET_2D", "from": list(spawns[0]),
                         "to": [tr, tc]})
  emit({"status": "PASSED" if not errors else "FAILED", "error_count": len(errors),
        "errors": errors})
  return 0 if not errors else 1


def structure_ops(grid: dict, palette: dict) -> tuple[list[dict], list[dict], list[dict]]:
  errors, warnings, ops = [], [], []
  edge_policy = grid.get("edge_policy", "wall") if isinstance(grid, dict) else "wall"
  need_walls = edge_policy != "fall_zone"
  ox, oy, oz = grid_origin(grid)
  pick = {}
  cats = ("STRUCTURE_FLOOR", "STRUCTURE_WALL") if need_walls else ("STRUCTURE_FLOOR",)
  for cat in cats:
    keys = [k for k, v in palette.items() if v.get("category") == cat]
    if not keys:
      errors.append({"type": "MISSING_PALETTE_CATEGORY", "category": cat})
      continue
    try:
      pick[cat] = asset_size_pivot(palette, keys[0])
    except (KeyError, ValueError) as exc:
      errors.append({"type": "UNMEASURED_ASSET", "error": str(exc)})
  if errors:
    return ops, errors, warnings
  fsize, fpivot, fasset, fscale = pick["STRUCTURE_FLOOR"]
  wsize, wpivot, wasset, wscale = pick.get(
      "STRUCTURE_WALL", ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0], "", [1.0, 1.0, 1.0]))
  if abs(fsize[0] - TILE_SIZE_XY) > 1.0 or abs(fsize[1] - TILE_SIZE_XY) > 1.0:
    warnings.append({
        "type": "FLOOR_NOT_TILE_SIZED", "measured_size_cm": fsize,
        "required_size_cm": [TILE_SIZE_XY, TILE_SIZE_XY],
        "suggested_scale": [round(TILE_SIZE_XY / fsize[i], 4) if fsize[i] else None
                            for i in (0, 1)],
        "detail": "la dalle ne couvre pas une tuile : les sols ne se joindront pas. Corriger "
                  "`scale` dans 02_palette.json, ou choisir une dalle de galerie mesuree."})
  wall_long_cm = max(wsize[0], wsize[1])
  wall_base_yaw = 90.0 if wsize[0] > wsize[1] else 0.0
  if need_walls and abs(wall_long_cm - TILE_SIZE_XY) > 1.0:
    warnings.append({"type": "WALL_NOT_TILE_SIZED", "measured_size_cm": wsize,
                     "detail": "le mur ne fait pas 512 cm sur son axe long : des jours apparaissent "
                               "sur le perimetre."})
  for floor in grid.get("floors", []):
    z = floor["z_index"]
    matrix = floor["matrix"]
    rows, cols = len(matrix), len(matrix[0]) if matrix else 0
    bz = (z + oz) * TILE_SIZE_Z
    for r in range(rows):
      for c in range(cols):
        cell = matrix[r][c]
        if cell in ("V", "T"):
          continue
        tr, tc = r + ox, c + oy
        cx, cy = tr * TILE_SIZE_XY + 256.0, tc * TILE_SIZE_XY + 256.0
        floor_center = [cx, cy, bz - fsize[2] / 2.0]
        ops.append({"label": f"Floor_{r}_{c}_{z}", "asset": fasset, "category": "FLOOR",
                    "tile": [r, c, z], "center_cm": floor_center, "size_cm": fsize, "yaw": 0.0,
                    "scale": fscale,
                    "xform": xform(loc_from_center(floor_center, fpivot, 0.0), 0.0, fscale)})
        if cell != "#" or not need_walls:
          continue
        border = r in (0, rows - 1) or c in (0, cols - 1)
        if not border:
          warnings.append({"type": "INTERIOR_WALL_NOT_BUILT", "tile": [r, c, z],
                           "detail": "build-structure ne pose des murs que sur le perimetre"})
        # Mur pose a l'exterieur de la tuile : l'interieur 512 x 512 reste libre.
        half_t = min(wsize[0], wsize[1]) / 2.0
        walls = []
        if r == 0:
          walls.append(("South", [tr * TILE_SIZE_XY - half_t, cy], (0.0 + wall_base_yaw) % 360.0))
        if r == rows - 1:
          walls.append(("North", [(tr + 1) * TILE_SIZE_XY + half_t, cy], (180.0 + wall_base_yaw) % 360.0))
        if c == 0:
          walls.append(("West", [cx, tc * TILE_SIZE_XY - half_t], (90.0 + wall_base_yaw) % 360.0))
        if c == cols - 1:
          walls.append(("East", [cx, (tc + 1) * TILE_SIZE_XY + half_t], (270.0 + wall_base_yaw) % 360.0))
        for side, (wx, wy), yaw in walls:
          center = [wx, wy, bz + wsize[2] / 2.0]
          ops.append({"label": f"Wall_{side}_{r}_{c}_{z}", "asset": wasset, "category": "WALL",
                      "tile": [r, c, z], "center_cm": center,
                      "size_cm": rotated_size(wsize, yaw), "yaw": yaw, "scale": wscale,
                      "xform": xform(loc_from_center(center, wpivot, yaw), yaw, wscale)})
  return ops, errors, warnings


def cmd_build_structure(workspace: str, dry_run: bool) -> int:
  grid = load_json(os.path.join(workspace, "03_grid.json"))
  palette = load_json(os.path.join(workspace, "02_palette.json")).get("assets", {})
  ops, errors, warnings = structure_ops(grid, palette)
  if errors:
    emit({"status": "FAILED", "error_count": len(errors), "errors": errors})
    return 1
  save_json(os.path.join(workspace, "_compiled_structure.json"), {"operations": ops})
  if dry_run:
    emit({"status": "DRY_RUN", "operations": len(ops), "warnings": warnings})
    return 0
  try:
    res = place_actors(client_for(workspace), workspace, ops)
  except McpError as exc:
    return mcp_failure("build-structure", exc)
  ok = not res["errors"]
  emit({"status": "PASSED" if ok else "FAILED", **res, "warnings": warnings + res["warnings"]})
  return 0 if ok else 1


def validate_workspace_files(workspace: str,
                             names: list[str] | None = None) -> tuple[list[dict], list[dict]]:
  """Controle de forme : cles connues, types, enums. Une spec fausse donne un transform faux."""
  errors, warnings = [], []
  for name in (names or SPEC_FILES):
    path = os.path.join(workspace, name)
    if not os.path.exists(path):
      if name in ("01_gdd.json", "04_devices.json", "05_props.json"):
        continue  # une carte sans device ni prop est legale
      errors.append({"type": "MISSING_FILE", "where": name, "path": path})
      continue
    try:
      data = load_json(path)
    except ValueError as exc:
      errors.append({"type": "BAD_JSON", "where": name, "error": str(exc)})
      continue
    if name == "01_gdd.json":
      e, w = spec_schema.validate_gdd(data)
      errors += e
      warnings += w
    else:
      errors += {"02_palette.json": spec_schema.validate_palette,
                 "03_grid.json": spec_schema.validate_grid,
                 "04_devices.json": spec_schema.validate_devices,
                 "05_props.json": spec_schema.validate_props}[name](data)
  return errors, warnings


def spec_report(workspace: str) -> tuple[list[dict], list[dict]]:
  """Forme + coherence croisee des 5 fichiers. Utilise par validate-scene et compile-transforms."""
  errors, warnings = validate_workspace_files(workspace)
  if errors:
    return errors, warnings  # inutile de croiser des fichiers dont la forme est fausse

  def read(name: str, key: str, default):
    path = os.path.join(workspace, name)
    return load_json(path).get(key, default) if os.path.exists(path) else default

  req_assets = read("01_gdd.json", "requested_assets", {})
  assets = read("02_palette.json", "assets", {})
  if isinstance(req_assets, dict):
    for k, v in req_assets.items():
      if isinstance(v, dict) and v.get("uefn_path") and not is_legal_uefn_path(v.get("uefn_path")):
        errors.append(legality_error(k, v.get("uefn_path"), f"01_gdd.json requested_assets.{k}"))
  if isinstance(assets, dict):
    for k, v in assets.items():
      if isinstance(v, dict) and v.get("uefn_path") and not is_legal_uefn_path(v.get("uefn_path")):
        errors.append(legality_error(k, v.get("uefn_path"), f"02_palette.json assets.{k}"))
  # Lire le fichier ENTIER : se limiter a `floors` rendait `grid.get("symmetric")` toujours
  # faux, donc l'avertissement SYMMETRY_SCOPE n'a jamais ete emis.
  grid_path = os.path.join(workspace, "03_grid.json")
  grid = load_json(grid_path) if os.path.exists(grid_path) else {}
  if not isinstance(grid, dict) or not isinstance(grid.get("floors"), list):
    grid = dict(grid) if isinstance(grid, dict) else {}
    grid["floors"] = []
  devices = read("04_devices.json", "devices", [])
  props = read("05_props.json", "props", [])

  palette_empty = not isinstance(assets, dict) or not assets
  if palette_empty and any(e.get("asset_key") for e in devices + props):
    # Un gabarit neuf a une palette vide : une seule erreur actionnable,
    # pas une ASSET_KEY_UNKNOWN par entree.
    errors.append({"type": "PALETTE_EMPTY", "where": "02_palette.json",
                   "detail": "aucun asset mesure : lancer measure-palette (etape 2) "
                             "avant validate-scene / compile-transforms"})

  floors = {f.get("z_index"): f.get("matrix", []) for f in grid.get("floors", [])
            if isinstance(f, dict)}
  known = {e.get("actor_label") for e in devices + props}

  def check_entry(entry: dict, where: str, seen: set) -> None:
    key = entry.get("asset_key")
    if key and not palette_empty and key not in assets:
      errors.append({"type": "ASSET_KEY_UNKNOWN", "where": where, "asset_key": key,
                     "detail": "absent de 02_palette.json"})
    tile = entry.get("tile")
    if isinstance(tile, list) and len(tile) == 3:
      matrix = floors.get(tile[2])
      if matrix is None:
        errors.append({"type": "TILE_OUT_OF_GRID", "where": where, "tile": tile,
                       "detail": f"aucun etage z_index {tile[2]} dans 03_grid.json"})
      elif not (0 <= tile[0] < len(matrix) and 0 <= tile[1] < len(matrix[tile[0]])):
        errors.append({"type": "TILE_OUT_OF_GRID", "where": where, "tile": tile,
                       "grid_rows": len(matrix)})
      elif matrix[tile[0]][tile[1]] in ("V", "T"):
        errors.append({"type": "TILE_HAS_NO_FLOOR", "where": where, "tile": tile,
                       "cell": matrix[tile[0]][tile[1]],
                       "detail": "rien n'est pose sur un vide ou une tremie"})
    face = entry.get("face_towards")
    if (isinstance(face, str) and face and face not in spec_schema.CARDINALS
            and face not in known):
      errors.append({"type": "FACE_TARGET_UNKNOWN", "where": where, "face_towards": face,
                     "detail": "ni NORTH/EAST/SOUTH/WEST/CENTER, ni un actor_label declare"})
    ref = entry.get("reference_actor")
    if isinstance(ref, str) and ref:
      if ref == entry.get("actor_label"):
        errors.append({"type": "REFERENCE_TO_SELF", "where": where, "reference_actor": ref})
      elif ref not in known:
        errors.append({"type": "REFERENCE_UNKNOWN", "where": where, "reference_actor": ref})
      elif ref not in seen:
        errors.append({"type": "REFERENCE_DECLARED_AFTER", "where": where,
                       "reference_actor": ref,
                       "detail": "la cible doit etre declaree AVANT : compile-transforms "
                                 "calcule dans l'ordre de la liste"})
    for i, b in enumerate(entry.get("bindings") or []):
      if isinstance(b, dict) and b.get("to") not in known:
        errors.append({"type": "BINDING_TARGET_UNKNOWN",
                       "where": f"{where} bindings[{i}]", "to": b.get("to")})

  seen = set()
  for i, dev in enumerate(devices):
    check_entry(dev, f"04_devices.json devices[{i}]", seen)
    seen.add(dev.get("actor_label"))
  for i, prop in enumerate(props):
    check_entry(prop, f"05_props.json props[{i}]", seen)
    seen.add(prop.get("actor_label"))

  axis = grid.get("symmetry_axis")
  if grid.get("symmetric") and axis in spec_schema.AXES:
    teams = (" En miroir X/Y, S1 et S2 sont tenus pour equivalents (l'echange des equipes n'est "
             "exige qu'en R180) : verifier a l'oeil que les deux camps sont bien de part et "
             "d'autre de la carte.") if axis != "R180" else ""
    warnings.append({"type": "SYMMETRY_SCOPE", "where": "03_grid.json",
                     "detail": "validate-grid ne controle que la GRILLE. La symetrie des devices "
                               "et des props de 04/05 est verifiee par `check-symmetry` (sur les "
                               "specs compilees) et `check-symmetry --live` (sur la scene posee), "
                               f"axe {axis}." + teams})
  elif grid.get("symmetric"):
    warnings.append({"type": "SYMMETRY_SCOPE", "where": "03_grid.json",
                     "detail": "symmetric: true sans symmetry_axis exploitable (X, Y ou R180) : "
                               "aucun controle de symetrie n'est execute, ni sur la grille ni "
                               "sur les acteurs."})
  return errors, warnings


def cmd_validate_scene(workspace: str) -> int:
  errors, warnings = spec_report(workspace)
  emit({"status": "PASSED" if not errors else "FAILED", "command": "validate-scene",
        "error_count": len(errors), "errors": errors, "warnings": warnings,
        "checked": [n for n in SPEC_FILES
                    if os.path.exists(os.path.join(workspace, n))]})
  return 0 if not errors else 1


def cmd_compile_transforms(workspace: str, quiet: bool = False) -> int:
  """quiet=True : appelle par une autre commande, qui emettra le seul JSON de son rapport."""
  errors, warnings = spec_report(workspace)
  if errors:
    if not quiet:
      emit({"status": "FAILED", "command": "compile-transforms", "error_count": len(errors),
            "errors": errors, "warnings": warnings,
            "next": "corriger les specs : un calcul sur une spec fausse produit un transform "
                    "faux mais un statut PASSED."})
    return 1
  palette = load_json(os.path.join(workspace, "02_palette.json")).get("assets", {})
  grid = load_json(os.path.join(workspace, "03_grid.json"))
  dev_path = os.path.join(workspace, "04_devices.json")
  props_path = os.path.join(workspace, "05_props.json")
  devices = load_json(dev_path).get("devices", []) if os.path.exists(dev_path) else []
  props = load_json(props_path).get("props", []) if os.path.exists(props_path) else []
  matrix = grid.get("floors", [{"matrix": [["."]]}])[0]["matrix"]
  origin = grid_origin(grid)
  ox, oy, oz = origin
  arena_center = [(ox + len(matrix) / 2.0) * TILE_SIZE_XY,
                  (oy + len(matrix[0]) / 2.0) * TILE_SIZE_XY,
                  oz * TILE_SIZE_Z]
  registry = {}

  def add(entry: dict, category: str, size_rot: list[float], pivot: list[float], asset: str,
          center: list[float], tile: list[int], snap: bool, yaw: float,
          scale: list[float]) -> None:
    floor_z = (tile[2] + oz) * TILE_SIZE_Z
    loc = loc_from_center(center, pivot, yaw)
    asset_cat = (palette.get(entry.get("asset_key", "")) or {}).get("category", category)
    registry[entry["actor_label"]] = {
        "actor_label": entry["actor_label"], "category": category, "asset_category": asset_cat, "asset": asset,
        "tile": tile, "center_cm": center, "size_cm": size_rot, "yaw": yaw, "scale": scale,
        "location_xyz": loc, "location_luf": xyz_to_luf(loc), "snap_to_floor": snap,
        "placement": entry.get("placement_mode", "TILE_ANCHOR"),
        "mirror": entry.get("mirror", True),
        "distance_to_floor_cm": round(center[2] - size_rot[2] / 2.0 - floor_z, 2),
    }

  def tile_center(tile: list[int]) -> list[float]:
    return [(tile[0] + ox) * TILE_SIZE_XY + 256.0,
            (tile[1] + oy) * TILE_SIZE_XY + 256.0,
            (tile[2] + oz) * TILE_SIZE_Z]

  def anchored(entry: dict, size: list[float]) -> tuple[list[float], list[float], float]:
    yaw = resolve_yaw(entry.get("face_towards", "NORTH"), tile_center(entry["tile"]),
                      registry, arena_center)
    size_rot = rotated_size(size, yaw)
    return anchor_center(entry["tile"], entry["slot"], size_rot, origin), size_rot, yaw

  for dev in devices:
    try:
      size, pivot, asset, scale = asset_size_pivot(palette, dev.get("asset_key", ""))
      if dev.get("placement_mode", "TILE_ANCHOR") == "WORLD":
        center = [float(v) for v in dev["world_location_cm"]]
        yaw = resolve_yaw(dev.get("face_towards", "NORTH"), center, registry, arena_center)
        size_rot = rotated_size(size, yaw)
        # Tuile derivee pour les rapports (audit, check-navigation) : negative hors grille.
        tile = [int(center[i] // (TILE_SIZE_XY if i < 2 else TILE_SIZE_Z)) for i in range(3)]
        add(dev, "DEVICE", size_rot, pivot, asset, center, tile,
            dev.get("on_floor", False), yaw, scale)
      else:
        center, size_rot, yaw = anchored(dev, size)
        add(dev, "DEVICE", size_rot, pivot, asset, center, dev["tile"],
            dev.get("on_floor", True), yaw, scale)
    except (KeyError, ValueError, TypeError) as exc:
      errors.append({"type": "COMPILE_ERROR", "actor": dev.get("actor_label"), "error": str(exc)})

  for prop in props:
    try:
      size, pivot, asset, scale = asset_size_pivot(palette, prop.get("asset_key", ""))
      snap = prop.get("snap_to_floor", True)
      mode = prop.get("placement_mode")
      if mode == "TILE_ANCHOR":
        center, size_rot, yaw = anchored(prop, size)
        tile = prop["tile"]
      elif mode == "RELATIVE_TO_ACTOR":
        parent = registry.get(prop.get("reference_actor"))
        if not parent:
          raise KeyError(
              f"reference_actor introuvable ou place apres : {prop.get('reference_actor')}")
        yaw = resolve_yaw(prop.get("face_towards", "NORTH"), parent["center_cm"],
                          registry, arena_center)
        size_rot = rotated_size(size, yaw)
        center = relative_center(parent, size_rot, prop["direction"],
                                 float(prop.get("gap_cm", 20.0)), snap)
        tile = parent["tile"]
      else:
        # Avant ce controle, toute valeur inconnue tombait dans la branche relative.
        raise ValueError(f"placement_mode doit valoir TILE_ANCHOR ou RELATIVE_TO_ACTOR : {mode!r}")
      add(prop, "PROP", size_rot, pivot, asset, center, tile, snap, yaw, scale)
    except (KeyError, ValueError) as exc:
      errors.append({"type": "COMPILE_ERROR", "actor": prop.get("actor_label"), "error": str(exc)})

  save_json(os.path.join(workspace, "_compiled_scene.json"), registry)
  if not quiet:
    emit({"status": "PASSED" if not errors else "FAILED", "compiled_actors": len(registry),
          "error_count": len(errors), "errors": errors, "warnings": warnings})
  return 0 if not errors else 1


def cmd_place_scene(workspace: str, dry_run: bool) -> int:
  compiled = os.path.join(workspace, "_compiled_scene.json")
  if not os.path.exists(compiled):
    emit({"status": "FAILED", "error": "lancer compile-transforms d'abord"})
    return 1
  registry = load_json(compiled)
  ops = [{"label": k, "asset": v["asset"], "category": v["category"],
          "xform": xform(v["location_xyz"], v["yaw"], v.get("scale"))}
         for k, v in registry.items()]
  dev_ops = [o for o in ops if o["category"] == "DEVICE"]
  prop_ops = [o for o in ops if o["category"] != "DEVICE"]
  if dry_run:
    emit({"status": "DRY_RUN", "devices": len(dev_ops), "props": len(prop_ops)})
    return 0
  cli = client_for(workspace)
  try:
    d = place_devices(cli, workspace, dev_ops)
    p = place_actors(cli, workspace, prop_ops)
  except McpError as exc:
    return mcp_failure("place-scene", exc)
  errors = d["errors"] + p["errors"]
  emit({"status": "PASSED" if not errors else "FAILED", "devices": d, "props": p,
        "error_count": len(errors)})
  return 0 if not errors else 1


def live_entries(cli: McpClient, workspace: str,
                 registry: dict) -> tuple[dict, list[dict], int]:
  """Remplace centre et taille theoriques par les bounds reels relus dans l'editeur."""
  placed = load_placed(workspace)
  missing, reads = [], 0
  for label, ent in registry.items():
    p = placed.get(label)
    if not p:
      missing.append({"type": "NOT_PLACED", "actor": label})
      continue
    try:
      b = cli.value("Actor", "get_actor_bounds", {"actor": {"refPath": p["refPath"]}})
    except (McpOffline, McpTimeout):
      raise
    except McpError as exc:
      missing.append({"type": "MISSING_IN_SCENE", "actor": label, "error": str(exc)})
      continue
    if not b or not b.get("isValid"):
      missing.append({"type": "INVALID_BOUNDS", "actor": label})
      continue
    ent["center_cm"], ent["size_cm"] = bounds_to_center_size(b)
    reads += 1
  return registry, missing, reads


def compiled_registry(workspace: str, command: str) -> dict | None:
  """Charge _compiled_scene.json, en le compilant au besoin.

  La compilation implicite est silencieuse : sans cela la commande emettrait deux JSON sur
  stdout et ne serait plus lisible par un script. Renvoie None (et un JSON emis) si les specs
  ne compilent pas.
  """
  path = os.path.join(workspace, "_compiled_scene.json")
  if not os.path.exists(path) and cmd_compile_transforms(workspace, quiet=True) != 0:
    emit({"status": "FAILED", "command": command, "error_count": 1,
          "errors": [{"type": "COMPILE_FAILED",
                      "detail": "compile-transforms a echoue sur les specs : rien n'est "
                                "verifiable. Lancer `compile-transforms` seul pour la liste "
                                "des erreurs."}]})
    return None
  return load_json(path) if os.path.exists(path) else None


def cmd_audit_scene(workspace: str, live: bool) -> int:
  registry = compiled_registry(workspace, "audit-scene")
  if registry is None:
    return 1
  struct_path = os.path.join(workspace, "_compiled_structure.json")
  structure = load_json(struct_path).get("operations", []) if os.path.exists(struct_path) else []
  walls = {o["label"]: {"actor_label": o["label"], "category": "WALL", "tile": o["tile"],
                        "center_cm": o["center_cm"], "size_cm": o["size_cm"]}
           for o in structure if o["category"] == "WALL"}
  floors = {o["label"]: {"actor_label": o["label"], "category": "FLOOR", "tile": o["tile"],
                         "center_cm": o["center_cm"], "size_cm": o["size_cm"]}
            for o in structure if o["category"] == "FLOOR"}
  missing, reads = [], 0
  if live:
    cli = client_for(workspace)
    try:
      registry, m1, r1 = live_entries(cli, workspace, registry)
      walls, m2, r2 = live_entries(cli, workspace, walls)
      floors, m3, r3 = live_entries(cli, workspace, floors)
    except McpError as exc:
      return mcp_failure("audit-scene --live", exc)
    missing = m1 + m2 + m3
    reads = r1 + r2 + r3
    if reads == 0:
      missing.append({"type": "NO_LIVE_DATA",
                      "detail": "Aucun bounds relu dans l'editeur (_placed.json absent ou "
                                "vide, aucune structure compilee) : rien n'est verifie."})
    else:
      try:
        leg = cli.value("Probe", "verifier_legalite_scene", {})
        if isinstance(leg, str):
          leg = json.loads(leg)
        if isinstance(leg, dict) and leg.get("illegal_actors"):
          placed_labels = set(load_placed(workspace).keys())
          for ill in leg["illegal_actors"]:
            if not placed_labels or ill.get("actor_label") in placed_labels:
              missing.append({
                  "type": "ILLEGAL_ACTOR_REFERENCE", "actor": ill.get("actor_label"),
                  "messages": ill.get("messages", []),
                  "suggested_legal_ppids": ill.get("suggested_legal_ppids", []),
              })
      except Exception:
        pass
  floor_top = {}
  for f in floors.values():
    t = tuple(f["tile"])
    floor_top[t] = f["center_cm"][2] + f["size_cm"][2] / 2.0

  overlap_errors, gravity_errors = [], []
  actors = list(registry.values())
  grid_path = os.path.join(workspace, "03_grid.json")
  oz = grid_origin(load_json(grid_path) if os.path.exists(grid_path) else {})[2]
  for a in actors:
    tile = tuple(a["tile"])
    ref_z = floor_top.get(tile, (tile[2] + oz) * TILE_SIZE_Z)
    dist = round(a["center_cm"][2] - a["size_cm"][2] / 2.0 - ref_z, 2)
    if a.get("snap_to_floor", True) and abs(dist) > MAX_GRAVITY_CM:
      gravity_errors.append({
          "type": "GRAVITY_ERROR", "actor": a["actor_label"], "distance_to_floor_cm": dist,
          "state": "FLOATING" if dist > 0 else "BURIED", "tile": a["tile"],
          "floor_reference": "bounds du sol" if tile in floor_top else "tile_z * 384",
          "suggestion": "Remesurer pivot_offset_cm (measure-palette --force) ou corriger snap_to_floor."})
  volumetric_cats = {"DEVICE_BARRIER", "DEVICE_ZONE", "DEVICE_MUTATOR", "DEVICE_VOLUME", "DEVICE_SKYDOME"}
  others = actors + list(walls.values())
  for i, a in enumerate(actors):
    for b in others[i + 1:]:
      if (a.get("asset_category") in volumetric_cats or b.get("asset_category") in volumetric_cats) and a.get("tile") != b.get("tile"):
        continue
      pen = aabb_penetration_cm(a, b)
      if pen > MAX_OVERLAP_CM:
        overlap_errors.append({
            "type": "OVERLAP_ERROR", "actor_a": a["actor_label"], "actor_b": b["actor_label"],
            "penetration_cm": pen, "tile": a["tile"],
            "suggestion": f"Placer {a['actor_label']} en RELATIVE_TO_ACTOR avec gap_cm >= 15."})
  total = len(overlap_errors) + len(gravity_errors) + len(missing)
  source = "compiled" if not live else ("live" if reads else "not_live")
  report = {"timestamp": now_iso(), "source": source,
            "status": "PASSED" if total == 0 else "FAILED", "error_count": total,
            "overlap_errors": overlap_errors, "gravity_errors": gravity_errors,
            "scene_errors": missing,
            "other_report": "passages etroits : 06_navigation_report.json (check-navigation)",
            "gravity_scope": ("bounds relus dans l'editeur" if source == "live" else
                              "GRAVITY_ERROR non detectable ici : le centre compile est "
                              "defini pose au sol, la distance au sol vaut donc toujours 0. "
                              "Seul --live (bounds relus) voit un pivot_offset_cm faux.")}
  save_json(os.path.join(workspace, "06_audit_report.json"), report)
  emit(report)
  return 0 if total == 0 else 1


def cmd_check_navigation(workspace: str) -> int:
  registry = compiled_registry(workspace, "check-navigation")
  if registry is None:
    return 1
  nav_errors = []
  by_tile = {}
  for p in (v for v in registry.values() if v.get("placement") != "WORLD"):
    if p.get("category") == "PROP" or p.get("snap_to_floor", True):
      by_tile.setdefault(tuple(p["tile"]), []).append(p)
  for tile_key, tile_actors in by_tile.items():
    for i in range(len(tile_actors)):
      for j in range(i + 1, len(tile_actors)):
        pa, pb = tile_actors[i], tile_actors[j]
        # Ne pas bloquer deux devices de meme tuile si l'un est un spawner au sol
        if pa.get("category") == "DEVICE" and pb.get("category") == "DEVICE":
          continue
        dx = abs(pa["center_cm"][0] - pb["center_cm"][0]) - (pa["size_cm"][0] + pb["size_cm"][0]) / 2.0
        dy = abs(pa["center_cm"][1] - pb["center_cm"][1]) - (pa["size_cm"][1] + pb["size_cm"][1]) / 2.0
        gap = max(dx, dy)
        if 0.0 < gap < MIN_CORRIDOR_WIDTH:
          nav_errors.append({"type": "CORRIDOR_TOO_NARROW", "tile": list(tile_key),
                             "free_width_cm": round(gap, 2),
                             "required_width_cm": MIN_CORRIDOR_WIDTH,
                             "blocking_actors": [pa["actor_label"], pb["actor_label"]]})
  report = {"timestamp": now_iso(), "command": "check-navigation",
            "status": "PASSED" if not nav_errors else "FAILED",
            "error_count": len(nav_errors), "navigation_errors": nav_errors,
            "navigation_scope": "paires d'acteurs (props et devices) dans une meme tuile ; pas de "
                                "capsule, pas de murs, pas de passages entre tuiles",
            "other_report": "chevauchements et gravite : 06_audit_report.json (audit-scene), "
                            "non recalcule ici"}
  save_json(os.path.join(workspace, "06_navigation_report.json"), report)
  emit(report)
  return 0 if not nav_errors else 1


# ------------------------------------------------- etape 5 bis : symetrie reelle

def grid_dims_by_z(grid: dict) -> dict:
  """Dimensions de chaque etage : le miroir d'une tuile depend de la taille de SA grille."""
  dims = {}
  for f in grid.get("floors", []):
    if isinstance(f, dict):
      m = f.get("matrix") or []
      dims[f.get("z_index")] = (len(m), len(m[0]) if m and isinstance(m[0], list) else 0)
  return dims


def mirror_tile(tile: list[int], axis: str, dims: tuple[int, int]) -> list[int]:
  rows, cols = dims
  r, c, z = tile
  if axis == "X":
    return [rows - 1 - r, c, z]
  if axis == "Y":
    return [r, cols - 1 - c, z]
  return [rows - 1 - r, cols - 1 - c, z]


def tile_local(entry: dict, origin: list[int] | None = None) -> list[float]:
  """Offset du centre dans sa propre tuile : comparable d'une tuile a son miroir."""
  ox, oy, oz = origin or [0, 0, 0]
  r, c, z = entry["tile"]
  return [entry["center_cm"][0] - (r + ox) * TILE_SIZE_XY,
          entry["center_cm"][1] - (c + oy) * TILE_SIZE_XY,
          entry["center_cm"][2] - (z + oz) * TILE_SIZE_Z]


def mirror_local(local: list[float], axis: str) -> list[float]:
  """L'offset que le partenaire doit avoir dans SA tuile.

  Passe par le repere local plutot que par le centre monde : un NORTH_EDGE vaut 512 - hx et son
  miroir SOUTH_EDGE vaut hx, la somme fait 512 quelle que soit la taille de l'asset.
  """
  lx, ly, lz = local
  if axis == "X":
    return [TILE_SIZE_XY - lx, ly, lz]
  if axis == "Y":
    return [lx, TILE_SIZE_XY - ly, lz]
  return [TILE_SIZE_XY - lx, TILE_SIZE_XY - ly, lz]


def mirror_yaw_of(yaw: float, axis: str) -> float:
  if axis == "X":
    return (180.0 - yaw) % 360.0
  if axis == "Y":
    return (-yaw) % 360.0
  return (yaw + 180.0) % 360.0


def symmetry_pair_error(a: dict, b: dict, axis: str, delta_local: list[float],
                        self_pair: bool, kind: str,
                        origin: list[int] | None = None) -> dict | None:
  # Meme asset_key des deux cotes : seul le yaw peut changer la boite tournee, d'ou la
  # tolerance elargie de la moitie de l'ecart de taille sur X et Y.
  ox, oy, oz = origin or [0, 0, 0]
  tol = [SYMMETRY_POS_TOLERANCE_CM + abs(a["size_cm"][i] - b["size_cm"][i]) / 2.0
         for i in range(2)] + [SYMMETRY_POS_TOLERANCE_CM]
  bad_pos = any(delta_local[i] > tol[i] for i in range(3))
  expected_yaw = mirror_yaw_of(a["yaw"], axis)
  dyaw = 0.0 if self_pair else angle_delta(expected_yaw, b["yaw"])
  bad_yaw = dyaw > SYMMETRY_YAW_TOLERANCE_DEG
  if not bad_pos and not bad_yaw:
    return None
  r, c, z = b["tile"]
  exp_local = mirror_local(tile_local(a, origin), axis)
  expected = [round((r + ox) * TILE_SIZE_XY + exp_local[0], 2),
              round((c + oy) * TILE_SIZE_XY + exp_local[1], 2),
              round((z + oz) * TILE_SIZE_Z + exp_local[2], 2)]
  delta = [round(b["center_cm"][i] - expected[i], 2) for i in range(3)]
  fault = "+".join(f for f, on in (("position", bad_pos), ("yaw", bad_yaw)) if on)
  err = {"type": kind, "axis": axis, "fault": fault,
         "actor_a": a["actor_label"], "actor_b": b["actor_label"],
         "tile_a": a["tile"], "tile_b": b["tile"],
         "expected_center_b_cm": expected,
         "center_b_cm": [round(v, 2) for v in b["center_cm"]],
         "delta_cm": delta, "max_delta_cm": round(max(abs(v) for v in delta), 2),
         "tolerance_cm": [round(t, 2) for t in tol],
         "suggestion": f"Amener {b['actor_label']} en {expected} (miroir de {a['actor_label']} "
                       f"en tuile {a['tile']}), puis compile-transforms et place-scene."}
  if bad_yaw:
    err.update({"expected_yaw_b": round(expected_yaw, 2), "yaw_b": b["yaw"],
                "yaw_delta_deg": round(dyaw, 2)})
    err["suggestion"] = (f"Orienter {b['actor_label']} a yaw {round(expected_yaw, 2)} "
                         f"(miroir du yaw {a['yaw']} de {a['actor_label']}). " + err["suggestion"])
  if self_pair:
    err["detail"] = ("acteur seul sur le plan de symetrie : il doit etre centre sur l'axe, "
                     "sinon il n'a aucun partenaire possible")
  return err


def symmetry_pairs(entries: list[dict], axis: str, dims_by_z: dict,
                   kind: str, origin: list[int] | None = None) -> tuple[list[dict], int, int, list[str]]:
  """Apparie chaque acteur a son miroir. O(n) : groupes par (paire de tuiles, asset_key).

  Renvoie (erreurs, paires conformes, paires exclues par `mirror: false`, acteurs hors grille).
  """
  groups, off_grid = {}, []
  for e in entries:
    dims = dims_by_z.get(e["tile"][2])
    r, c = e["tile"][0], e["tile"][1]
    if not dims or not dims[0] or not dims[1] or not (0 <= r < dims[0] and 0 <= c < dims[1]):
      off_grid.append(e["actor_label"])
      continue
    mt = tuple(mirror_tile(e["tile"], axis, dims))
    groups.setdefault((tuple(sorted([tuple(e["tile"]), mt])), e.get("asset_key")), []).append(
        (e, mt))
  errors, ok, excluded = [], 0, 0
  for members in groups.values():
    cands = []
    for i, (a, mt) in enumerate(members):
      want = mirror_local(tile_local(a, origin), axis)
      for j, (b, _) in enumerate(members):
        if tuple(b["tile"]) != mt or (i == j and tuple(a["tile"]) != mt):
          continue  # partenaire dans la tuile miroir ; auto-partenaire seulement sur le plan
        d = [abs(tile_local(b, origin)[k] - want[k]) for k in range(3)]
        if max(d) <= MIRROR_SEARCH_CM:
          cands.append((round(max(d), 3), i, j, d))
    cands.sort()
    used = set()
    for _, i, j, d in cands:
      if i in used or (j in used and i != j):
        continue
      used.update((i, j))
      a, b = members[i][0], members[j][0]
      if a.get("mirror") is False or b.get("mirror") is False:
        excluded += 1
        continue
      err = symmetry_pair_error(a, b, axis, d, i == j, kind, origin)
      if err:
        errors.append(err)
      else:
        ok += 1
    for i, (a, mt) in enumerate(members):
      if i in used or a.get("mirror") is False:
        continue
      errors.append({
          "type": "MIRROR_PARTNER_MISSING", "axis": axis, "actor": a["actor_label"],
          "tile": a["tile"], "asset_key": a.get("asset_key"),
          "detail": f"aucun acteur de meme asset_key dans la tuile miroir {list(mt)} "
                    f"(ou aucun a moins de {MIRROR_SEARCH_CM} cm).",
          "suggestion": "Declarer le partenaire manquant dans 04/05, ou poser `mirror: false` "
                        "des DEUX cotes si cet acteur est volontairement asymetrique."})
  return errors, ok, excluded, off_grid


def cmd_check_symmetry(workspace: str, live: bool) -> int:
  registry = compiled_registry(workspace, "check-symmetry")
  if registry is None:
    return 1
  grid_path = os.path.join(workspace, "03_grid.json")
  grid = load_json(grid_path) if os.path.exists(grid_path) else {}
  axis = grid.get("symmetry_axis")
  axis = axis if axis in spec_schema.AXES else None
  dims_by_z = grid_dims_by_z(grid)
  origin = grid_origin(grid)
  entries = [e for e in registry.values() if e.get("placement") != "WORLD"]
  world = [k for k, e in registry.items() if e.get("placement") == "WORLD"]
  spec_errors, pairs, excluded, off_grid = [], 0, 0, []
  if axis:
    spec_errors, pairs, excluded, off_grid = symmetry_pairs(entries, axis, dims_by_z,
                                                            "SPEC_ASYMMETRY", origin)
  drift_errors, scene_errors, source = [], [], "compiled"
  if live:
    cli = client_for(workspace)
    try:
      placed = load_placed(workspace)
      for label, ent in registry.items():
        p = placed.get(label)
        if not p:
          drift_errors.append({"type": "NOT_PLACED", "actor": label,
                               "detail": "absent de _placed.json : jamais pose, ou pose avant "
                                         "un cleanup."})
          continue
        tf = cli.value("Actor", "get_actor_transform", {"actor": {"refPath": p["refPath"]}})
        if not isinstance(tf, dict) or not isinstance(tf.get("location"), dict):
          drift_errors.append({"type": "UNREADABLE_TRANSFORM", "actor": label, "read_back": tf,
                               "detail": "reponse vide ou illisible : une reponse vide veut dire "
                                         "INCONNU, pas « l'acteur est a la bonne place »."})
          continue
        want = xform(ent["location_xyz"], ent["yaw"], ent.get("scale"))
        dl = [abs(tf["location"][k] - want["location"][k]) for k in "xyz"]
        dyaw = angle_delta(tf["rotation"]["yaw"], want["rotation"]["yaw"])
        got = tf.get("scale") or {}
        dsc = max(abs(float(got.get(k, 1.0)) - want["scale"][k]) for k in "xyz")
        if max(dl) > POS_TOLERANCE_CM or dyaw > YAW_TOLERANCE_DEG or dsc > SCALE_TOLERANCE:
          drift_errors.append({
              "type": "TRANSFORM_DRIFT", "actor": label,
              "delta_location_cm": [round(v, 2) for v in dl],
              "delta_yaw_deg": round(dyaw, 2), "delta_scale": round(dsc, 4),
              "expected": want, "read_back": tf,
              "suggestion": "L'acteur a bouge depuis place-scene, ou le placement n'a jamais "
                            "ete corrige. Corriger la spec, puis cleanup + place-scene."})
      # live_entries ecrase centre et taille par les bounds reels : les entrees d'`entries`
      # sont les memes objets, la passe scene se fait donc sur des donnees lues.
      _, missing, reads = live_entries(cli, workspace, registry)
      scene_errors += [m for m in missing if m["type"] != "NOT_PLACED"]
    except McpError as exc:
      return mcp_failure("check-symmetry --live", exc)
    source = "live" if reads else "not_live"
    if reads == 0:
      scene_errors.append({"type": "NO_LIVE_DATA",
                           "detail": "Aucun bounds relu dans l'editeur (_placed.json absent ou "
                                     "vide) : la scene posee n'est pas verifiee."})
    elif axis:
      scene_errors += symmetry_pairs(entries, axis, dims_by_z, "SCENE_ASYMMETRY", origin)[0]

  scope = []
  if axis is None:
    scope.append("AUCUN AXE : 03_grid.json ne declare pas symmetry_axis (X, Y ou R180). La "
                 "symetrie des devices et des props n'est PAS verifiee. Poser `symmetric: true` "
                 "et un `symmetry_axis` pour activer ce controle.")
  scope.append(f"{len(entries)} acteurs de 04/05 controles (centre + yaw) ; {len(world)} en "
               f"placement_mode WORLD ignores (hors grille, aucun miroir possible)"
               f"{': ' + ', '.join(world) if world else '.'}")
  scope.append("murs et sols de _compiled_structure.json non controles : leur symetrie vient de "
               "la matrice, verifiee par validate-grid.")
  if off_grid:
    scope.append(f"hors grille, ignores : {', '.join(off_grid)} (voir validate-scene, "
                 "TILE_OUT_OF_GRID).")
  if excluded:
    scope.append(f"{excluded} paire(s) exclue(s) par `mirror: false`.")
  if not live:
    scope.append("SPEC seulement : un acteur deplace dans l'editeur apres place-scene n'est pas "
                 "vu. Relancer avec --live pour controler la scene posee.")
  total = len(spec_errors) + len(drift_errors) + len(scene_errors)
  report = {"timestamp": now_iso(), "command": "check-symmetry",
            "status": "PASSED" if total == 0 else "FAILED",
            "axis": axis, "symmetric": bool(grid.get("symmetric")), "source": source,
            "error_count": total, "checked_pairs": pairs,
            "spec_errors": spec_errors, "drift_errors": drift_errors,
            "scene_errors": scene_errors, "scope": scope}
  save_json(os.path.join(workspace, "11_symmetry_report.json"), report)
  emit(report)
  return 0 if total == 0 else 1


# ------------------------------------------------- etape 6 : proprietes, cablage

def property_names(listed) -> list[str]:
  """Noms reels renvoyes par Object.list_properties. Forme non garantie : liste inconnue -> [].

  Une liste vide ne veut pas dire « aucune propriete » mais « forme non reconnue » : dans ce
  cas on ecrit quand meme, et la relecture par get_properties decide.
  """
  if isinstance(listed, str):
    try:
      listed = json.loads(listed)
    except ValueError:
      return []
  if isinstance(listed, dict):
    if "properties" in listed or "returnValue" in listed:
      listed = listed.get("properties", listed.get("returnValue", []))
    else:
      return [str(k) for k in listed.keys()]
  if not isinstance(listed, list):
    return []
  names = []
  for item in listed:
    if isinstance(item, str):
      names.append(item)
    elif isinstance(item, dict):
      for key in ("name", "propertyName", "Name"):
        if isinstance(item.get(key), str):
          names.append(item[key])
          break
  return names


def close_names(wanted: str, names: list[str]) -> list[str]:
  import difflib
  return difflib.get_close_matches(wanted, names, n=3, cutoff=0.5)


def as_dict(value):
  """get_properties renvoie une chaine JSON nom -> valeur (constat du 2026-10-19)."""
  if isinstance(value, str):
    try:
      value = json.loads(value)
    except ValueError:
      return {"__raw__": value}
  return value if isinstance(value, dict) else {"__raw__": value}


def value_matches(written, read) -> bool:
  """Ecrit vs relu. Un dict relu peut porter des cles en plus (`teamIndex` seul relu avec
  `teamType`) : on exige que chaque cle ecrite soit confirmee, pas l'egalite stricte."""
  if isinstance(written, dict):
    if not isinstance(read, dict):
      return False
    return all(k in read and value_matches(v, read[k]) for k, v in written.items())
  if isinstance(written, bool) or isinstance(read, bool):
    return bool(written) == bool(read)
  if isinstance(written, (int, float)) and isinstance(read, (int, float)):
    return abs(float(written) - float(read)) < 1e-6
  return written == read


def cmd_apply_properties(workspace: str, dry_run: bool) -> int:
  dev_path = os.path.join(workspace, "04_devices.json")
  devices = load_json(dev_path).get("devices", []) if os.path.exists(dev_path) else []
  placed = load_placed(workspace)
  wanted_all = [d for d in devices if d.get("properties")]
  missing = [{"type": "NOT_PLACED", "actor": d.get("actor_label"),
              "detail": "place-scene n'a pas pose cet acteur (absent de _placed.json)"}
             for d in wanted_all if d.get("actor_label") not in placed]
  todo = [d for d in wanted_all if d.get("actor_label") in placed]
  if dry_run:
    emit({"status": "DRY_RUN", "command": "apply-properties", "devices": len(todo),
          "properties": sum(len(d["properties"]) for d in todo), "not_placed": missing,
          "next": "list_properties puis set_properties (values en CHAINE JSON) puis "
                  "get_properties : une erreur peut accompagner une ecriture partielle."})
    return 0
  cli = client_for(workspace)
  applied, errors = [], []
  try:
    for dev in todo:
      label = dev["actor_label"]
      inst = {"refPath": placed[label]["refPath"]}
      wanted = dict(dev["properties"])
      names = property_names(cli.value("Object", "list_properties", {"instance": inst}))
      if names:
        unknown = [k for k in wanted if k not in names]
        if unknown:
          errors.append({"type": "PROPERTY_NOT_FOUND", "actor": label, "properties": unknown,
                         "nearest": {k: close_names(k, names) for k in unknown},
                         "detail": "absentes de list_properties : ne pas inventer un autre nom"})
          for k in unknown:
            wanted.pop(k)
      if not wanted:
        continue
      cli.value("Object", "set_properties",
                {"instance": inst, "values": json.dumps(wanted)})
      read = as_dict(cli.value("Object", "get_properties",
                               {"instance": inst, "properties": list(wanted)}))
      for k, v in wanted.items():
        if k not in read:
          errors.append({"type": "PROPERTY_UNREADABLE", "actor": label, "property": k,
                         "written": v, "read_back": None,
                         "detail": "get_properties ne renvoie pas la cle : valeur inconnue, "
                                   "pas valeur absente"})
        elif not value_matches(v, read[k]):
          errors.append({"type": "PROPERTY_MISMATCH", "actor": label, "property": k,
                         "written": v, "read_back": read[k]})
        else:
          applied.append({"actor": label, "property": k, "written": v, "read_back": read[k]})
  except McpError as exc:
    return mcp_failure("apply-properties", exc, {"applied_before_failure": applied,
                                                 "errors_before_failure": errors})
  report = {"timestamp": now_iso(), "status": "PASSED" if not errors else "FAILED",
            "error_count": len(errors) + len(missing), "applied": applied,
            "errors": errors, "not_placed": missing,
            "scope": "chaque valeur ecrite par set_properties est relue par get_properties ; "
                     "les devices Verse (SetDeviceProperty) ne sont pas couverts : outil "
                     "inconnu, jamais teste sur un creative_device"}
  save_json(os.path.join(workspace, "07_properties_report.json"), report)
  emit(report)
  return 0 if not errors and not missing else 1


def binding_read_back(payload, event: str, function: str) -> tuple[bool, object]:
  """ListEventBindings sur la CIBLE. Forme non garantie : on cherche les deux chaines."""
  items = payload
  if isinstance(items, str):
    try:
      items = json.loads(items)
    except ValueError:
      return (event in items and function in items), items[:400]
  if isinstance(items, dict):
    items = items.get("bindings", items.get("returnValue", [items]))
  if not isinstance(items, list):
    return False, items
  for item in items:
    text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
    if event in text and function in text:
      return True, item
  return False, json.dumps(items, ensure_ascii=False)[:400]


def cmd_wire_devices(workspace: str, dry_run: bool, allow_empty: bool = False) -> int:
  dev_path = os.path.join(workspace, "04_devices.json")
  devices = load_json(dev_path).get("devices", []) if os.path.exists(dev_path) else []
  placed = load_placed(workspace)
  bindings = []
  for dev in devices:
    for b in dev.get("bindings") or []:
      bindings.append({"from": dev.get("actor_label"), "event": b.get("event"),
                       "to": b.get("to"), "function": b.get("function")})
  if not bindings:
    if allow_empty:
      report = {"timestamp": now_iso(), "status": "PASSED", "error_count": 0,
                "wired": [], "errors": [], "not_placed": [],
                "scope": "aucun binding Direct Event declare (--allow-empty : logique cablee en Verse ou carte sans cablage)."}
      save_json(os.path.join(workspace, "08_wiring_report.json"), report)
      emit(report)
      return 0
    err_report = {"timestamp": now_iso(), "status": "FAILED", "command": "wire-devices",
                  "error_count": 1, "wired": [], "not_placed": [],
                  "errors": [{"type": "NO_BINDING_DECLARED",
                              "detail": "aucun `bindings` dans 04_devices.json. Les noms d'evenement "
                                        "et de fonction se lisent avec Device.GetBindingOptions sur la "
                                        "source : ne jamais les deviner (ou passer --allow-empty si "
                                        "toute la logique passe par Verse)."}],
                  "scope": "aucun binding declare."}
    save_json(os.path.join(workspace, "08_wiring_report.json"), err_report)
    emit(err_report)
    return 1
  missing = [b for b in bindings if b["from"] not in placed or b["to"] not in placed]
  todo = [b for b in bindings if b["from"] in placed and b["to"] in placed]
  if dry_run:
    emit({"status": "DRY_RUN", "command": "wire-devices", "bindings": len(todo),
          "not_placed": missing,
          "next": "GetBindingOptions (source) -> AddEventBinding -> ListEventBindings (CIBLE)"})
    return 0
  cli = client_for(workspace)
  wired, errors = [], []
  try:
    for b in todo:
      src = {"refPath": placed[b["from"]]["refPath"]}
      dst = {"refPath": placed[b["to"]]["refPath"]}
      src_options = as_dict(cli.value("Device", "GetBindingOptions", {"devicePath": src}))
      events = src_options.get("sourceEvents") or []
      dst_options = as_dict(cli.value("Device", "GetBindingOptions", {"devicePath": dst}))
      functions = dst_options.get("targetFunctions") or []
      if events and b["event"] not in events:
        errors.append({"type": "BINDING_EVENT_UNKNOWN", "from": b["from"],
                       "event": b["event"], "sourceEvents": events})
        continue
      if functions and b["function"] not in functions:
        errors.append({"type": "BINDING_FUNCTION_UNKNOWN", "to": b["to"],
                       "function": b["function"], "targetFunctions": functions})
        continue
      cli.value("Device", "AddEventBinding", {
          "sourceDevicePath": src, "sourceEvent": b["event"],
          "targetDevicePath": dst, "targetFunction": b["function"]})
      ok, proof = binding_read_back(
          cli.value("Device", "ListEventBindings", {"devicePath": dst}),
          b["event"], b["function"])
      if ok:
        wired.append({**b, "read_back": proof})
      else:
        errors.append({"type": "BINDING_NOT_READ_BACK", **b, "target_bindings": proof,
                       "detail": "le lien apparait sur la CIBLE : s'il n'y est pas, il n'est "
                                 "pas prouve (AddEventBinding est idempotent, rejouer sans risque)"})
  except McpError as exc:
    return mcp_failure("wire-devices", exc, {"wired_before_failure": wired,
                                             "errors_before_failure": errors})
  report = {"timestamp": now_iso(), "status": "PASSED" if not errors else "FAILED",
            "error_count": len(errors) + len(missing), "wired": wired, "errors": errors,
            "not_placed": missing,
            "scope": "cablage evenement -> fonction entre devices poses. Le cablage par canal "
                     "(GameplayTagContainer) et les references @editable ne sont pas couverts."}
  save_json(os.path.join(workspace, "08_wiring_report.json"), report)
  emit(report)
  return 0 if not errors and not missing else 1


# ------------------------------------------------- etapes 8 et 9 : Verse

def verse_payload(value):
  if isinstance(value, str):
    try:
      return json.loads(value)
    except ValueError:
      return value
  return value


def cmd_verse_scan(workspace: str, root: str, recursive: bool) -> int:
  cli = client_for(workspace)
  try:
    files = verse_payload(cli.value("Verse", "ListFiles",
                                    {"path": root, "bRecursive": recursive}))
  except McpError as exc:
    return mcp_failure("verse-scan", exc)
  save_json(os.path.join(workspace, "_verse_files.json"),
            {"root": root, "recursive": recursive, "at": now_iso(), "files": files})
  empty = not files
  emit({"status": "PASSED", "command": "verse-scan", "root": root, "recursive": recursive,
        "count": len(files) if isinstance(files, list) else None,
        "files": files if not isinstance(files, list) else files[:200],
        "warning": ("ListFiles vide : cela ne prouve PAS l'absence de fichier .verse "
                    "(reponse vide = inconnu)" if empty else None)})
  return 0


def cmd_verse_read(workspace: str, verse_path: str) -> int:
  """Relit un .verse du projet (Verse.ReadFile). Lecture seule."""
  try:
    text = verse_payload(client_for(workspace).value("Verse", "ReadFile", {"path": verse_path}))
  except McpError as exc:
    if "does not exist" not in str(exc):
      return mcp_failure("verse-read", exc, {"verse_path": verse_path})
    text = None
  if text is None:
    emit({"status": "FAILED", "command": "verse-read", "verse_path": verse_path,
          "error_kind": "VERSE_FILE_NOT_FOUND",
          "detail": "fichier absent (attendu avant une premiere ecriture)."})
    return 1
  emit({"status": "PASSED", "command": "verse-read", "verse_path": verse_path,
        "text": text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)})
  return 0


def cmd_list_devices(workspace: str, name_filter: str) -> int:
  """Catalogue des devices posables (Device.ListDeviceAssets) : assetPath exact. Lecture seule."""
  try:
    items = client_for(workspace).value("Device", "ListDeviceAssets", {"nameFilter": name_filter}) or []
  except McpError as exc:
    return mcp_failure("list-devices", exc)
  if not items:
    emit({"status": "FAILED", "command": "list-devices", "filter": name_filter, "count": 0,
          "error_kind": "DEVICE_ASSET_NOT_FOUND",
          "detail": "aucun device ne correspond : ne pas deviner un chemin approchant."})
    return 1
  emit({"status": "PASSED", "command": "list-devices", "filter": name_filter,
        "count": len(items), "devices": items[:100]})
  return 0


def cmd_verse_grep(workspace: str, pattern: str, symbols: str | None, path_glob: str,
                   max_results: int) -> int:
  cli = client_for(workspace)
  wanted = [s.strip() for s in symbols.split(",")] if symbols else [pattern]
  if not any(wanted):
    emit({"status": "FAILED", "command": "verse-grep",
          "error": "passer --pattern ou --symbols A,B,C"})
    return 1
  found, missing = {}, []
  try:
    for symbol in wanted:
      res = verse_payload(cli.value("Verse", "Grep", {
          "pattern": symbol, "pathGlob": path_glob, "maxResults": max_results}))
      hits = res if isinstance(res, list) else []
      if hits:
        found[symbol] = hits[:max_results]
      else:
        missing.append(symbol)
  except McpError as exc:
    return mcp_failure("verse-grep", exc, {"resolved": list(found)})
  report = {"timestamp": now_iso(), "command": "verse-grep", "pathGlob": path_glob,
            "status": "PASSED" if not missing else "FAILED",
            "resolved": found, "not_found": missing,
            "scope": "un Grep vide ne prouve PAS que l'API n'existe pas : verifier le motif "
                     "sur un nom connu avant de conclure. Une signature trouvee doit etre lue "
                     "dans son contexte (verse-scan puis ReadFile)."}
  save_json(os.path.join(workspace, "_verse_grep.json"), report)
  emit(report)
  return 0 if not missing else 1


def cmd_verse_write(workspace: str, local_file: str, verse_path: str, agree: bool) -> int:
  if not os.path.exists(local_file):
    emit({"status": "FAILED", "command": "verse-write", "error_kind": "FILE_NOT_FOUND",
          "local_file": os.path.abspath(local_file or "")})
    return 1
  with open(local_file, "r", encoding="utf-8") as f:
    content = f.read()
  if not agree:
    emit({"status": "FAILED", "command": "verse-write", "error_kind": "CONSENT_REQUIRED",
          "local_file": os.path.abspath(local_file), "verse_path": verse_path,
          "bytes": len(content),
          "detail": "VerseToolset.WriteFile est classe DANGEREUX et n'a jamais ete execute : "
                    "il modifie le code source du projet. Montrer le code a l'utilisateur, "
                    "obtenir son accord explicite, puis rejouer avec "
                    "--i-agree-to-modify-project. Sans accord : donner le code a coller."})
    return 1
  cli = client_for(workspace)
  try:
    try:
      cli.value("Verse", "WriteFile", {"path": verse_path, "content": content,
                                       "bCreateIfMissing": True})
    except McpError as exc_w:
      if "mounted Verse content root" in str(exc_w):
        roots = verse_payload(cli.value("Verse", "ListFiles", {"path": "", "bRecursive": False})) or []
        proj_root = next((r.get("name") for r in roots if isinstance(r, dict) and r.get("name") and "(" not in str(r.get("name"))), None)
        if proj_root:
          rel = verse_path.strip("/").split("/", 1)[-1] if "/" in verse_path.strip("/") else verse_path.strip("/")
          verse_path = f"{proj_root.rstrip('/')}/{rel}"
          cli.value("Verse", "WriteFile", {"path": verse_path, "content": content,
                                           "bCreateIfMissing": True})
        else:
          raise
      else:
        raise
    back = verse_payload(cli.value("Verse", "ReadFile", {"path": verse_path}))
  except McpError as exc:
    return mcp_failure("verse-write", exc, {"verse_path": verse_path})
  text = back if isinstance(back, str) else json.dumps(back, ensure_ascii=False)
  same = content.strip() in text or text.strip() == content.strip()
  record = {"timestamp": now_iso(), "verse_path": verse_path,
            "local_file": os.path.abspath(local_file), "bytes": len(content),
            "read_back_matches": same,
            "status": "PASSED" if same else "FAILED"}
  history_path = os.path.join(workspace, "_verse_written.json")
  history = load_json(history_path) if os.path.exists(history_path) else {"files": []}
  history["files"].append(record)
  save_json(history_path, history)
  emit({**record,
        "next": ("verse-build : Session.GetSessionStatus doit etre Disconnected" if same else
                 "le fichier relu ne contient pas le texte ecrit : ne pas compiler, "
                 "remontrer le diff a l'utilisateur")})
  return 0 if same else 1


def cmd_verse_build(workspace: str, dry_run: bool, log_entries: int) -> int:
  if dry_run:
    emit({"status": "DRY_RUN", "command": "verse-build",
          "next": "GetSessionStatus -> BuildAll -> Logs.GetLogEntries(VerseBuild)"})
    return 0
  cli = client_for(workspace)
  started = now_iso()
  try:
    session = verse_payload(cli.value("Session", "GetSessionStatus", {}))
    if isinstance(session, dict):
      session = session.get("status", session.get("returnValue", session))
    if session != "Disconnected":
      emit({"status": "FAILED", "command": "verse-build", "error_kind": "SESSION_CONNECTED",
            "session": session,
            "detail": "BuildAll n'est prouve qu'avec une session Disconnected. Son "
                      "comportement session connectee n'a jamais ete teste : ne pas lancer."})
      return 1
    diagnostics = verse_payload(cli.value("Verse", "BuildAll", {}))
    logs = verse_payload(cli.value("Logs", "GetLogEntries", {
        "category": VERSE_BUILD_LOG, "pattern": "", "maxEntries": log_entries}))
  except McpError as exc:
    return mcp_failure("verse-build", exc, {"session": session})
  diags = diagnostics if isinstance(diagnostics, list) else [diagnostics]
  errors = [d for d in diags if isinstance(d, dict)
            and str(d.get("severity", "")).lower() == "error"]
  lines = logs if isinstance(logs, list) else [logs]
  texts = [l if isinstance(l, str) else json.dumps(l, ensure_ascii=False) for l in lines]
  success = [t for t in texts if re.search(r"succ|termin|success|complete", t, re.IGNORECASE)]
  ok = not errors and bool(success)
  report = {"timestamp": started, "command": "verse-build", "session": session,
            "status": "PASSED" if ok else "FAILED",
            "diagnostics_count": len(diags), "error_diagnostics": errors,
            "warnings": [d for d in diags if isinstance(d, dict)
                         and str(d.get("severity", "")).lower() == "warning"],
            "build_log_lines": texts[:log_entries], "success_lines": success[:5],
            "scope": "une liste de diagnostics vide ne suffit PAS : il faut aussi une ligne "
                     "de succes recente dans VerseBuild. Les lignes sont localisees et le log "
                     "garde les builds precedents : comparer l'horodatage a " + started}
  save_json(os.path.join(workspace, "09_verse_report.json"), report)
  emit(report)
  return 0 if ok else 1


EDITABLE_RE = re.compile(r"^([A-Za-z_]\w*)\s*:\s*([^\s=]+)")
# Un @editable de type primitif est un parametre a regler, pas une reference d'acteur :
# aucune cible a cabler, donc pas d'erreur s'il n'a pas d'actor_label.
PARAM_TYPES = {"logic", "bool", "int", "float", "string", "message", "locale", "type"}


def editable_kind(vtype: str) -> str:
  base = str(vtype).strip().lstrip("?").lstrip("[]").strip()
  base = base.split("[")[0].strip()
  return "PARAMETRE" if base in PARAM_TYPES else "ACTEUR"


def parse_editables(text: str) -> list[dict]:
  out, pending = [], False
  for raw in text.splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
      continue
    if line.startswith("@editable"):
      pending = True
      continue
    if pending:
      m = EDITABLE_RE.match(line)
      if m:
        out.append({"name": m.group(1), "type": m.group(2).strip()})
      pending = False
  return out


def cmd_list_editables(workspace: str, device_label: str | None, live: bool,
                       apply_wiring: bool = False) -> int:
  verse_dir = os.path.join(workspace, "verse")
  files = sorted(f for f in os.listdir(verse_dir)) if os.path.isdir(verse_dir) else []
  files = [f for f in files if f.endswith(".verse")]
  if not files:
    emit({"status": "FAILED", "command": "list-editables", "error_count": 1,
          "errors": [{"type": "NO_VERSE_STAGED", "verse_dir": verse_dir,
                      "detail": "aucun .verse dans workspace/verse/ : le gabarit en fournit un, "
                                "ou ecrire le fichier d'abord"}]})
    return 1
  editables = {}
  for name in files:
    with open(os.path.join(verse_dir, name), "r", encoding="utf-8") as f:
      editables[name] = parse_editables(f.read())
  placed = load_placed(workspace)
  dev_path = os.path.join(workspace, "04_devices.json")
  devices = load_json(dev_path).get("devices", []) if os.path.exists(dev_path) else []
  labels = {d.get("actor_label"): d.get("asset_key") for d in devices}
  rows, missing = [], []
  for name, items in editables.items():
    for item in items:
      label = item["name"]
      kind = editable_kind(item["type"])
      row = {"file": name, "editable": label, "type": item["type"], "kind": kind,
             "declared_in_04_devices": label in labels,
             "asset_key": labels.get(label),
             "refPath": (placed.get(label) or {}).get("refPath"),
             "wiring": "MANUEL" if label in labels or label in placed else "AUCUNE_CIBLE"}
      rows.append(row)
      if kind == "ACTEUR" and not row["refPath"]:
        missing.append(row)
  extra = None
  wiring_errors = []
  if live or apply_wiring:
    cli = client_for(workspace)
    target_label = device_label or "Game_Manager_01"
    try:
      if target_label not in placed and apply_wiring:
        existing = find_by_label(cli, target_label)
        if existing:
          placed[target_label] = {"refPath": existing, "kind": "verse_device"}
          save_json(placed_path(workspace), placed)
        else:
          # Chercher le creative_device Verse dans ListDeviceAssets et le poser en Zone_Logic
          gdd_path = os.path.join(workspace, "01_gdd.json")
          mods = load_json(gdd_path).get("verse_modules", []) if os.path.exists(gdd_path) else []
          cname = mods[0].get("class_name", "game_manager_device") if mods else "game_manager_device"
          catalog = cli.value("Device", "ListDeviceAssets", {"nameFilter": cname}) or []
          if not catalog:
            catalog = [a for a in (cli.value("Device", "ListDeviceAssets", {"nameFilter": ""}) or [])
                       if isinstance(a, dict) and a.get("bIsVerseDevice")]
          vdev = next((a for a in catalog if isinstance(a, dict) and a.get("assetPath")), None)
          if vdev:
            ap = vdev["assetPath"]
            ap_ref = ap if isinstance(ap, dict) else {"refPath": ap}
            xf = xform([-5376.0, 1792.0, -2304.0], 0.0)
            ref = cli.value("Device", "PlaceDevice",
                            {"assetPath": ap_ref, "transform": xf})
            if isinstance(ref, dict) and ref.get("refPath"):
              act = {"refPath": ref["refPath"]}
              cli.value("Actor", "set_actor_transform", {"actor": act, "xform": xf, "worldspace": True})
              cli.value("Actor", "set_label", {"actor": act, "label": target_label})
              cli.value("Actor", "add_tag", {"actor": act, "tag": MAP_TAG})
              placed[target_label] = {"refPath": ref["refPath"], "asset": ap_ref.get("refPath", ap),
                                      "kind": "verse_device", "xform": xf}
              save_json(placed_path(workspace), placed)
      if target_label not in placed:
        emit({"status": "FAILED", "command": "list-editables", "error_count": 1,
              "errors": [{"type": "DEVICE_NOT_PLACED", "device": target_label,
                          "detail": "--live / --apply exige que le device Verse soit pose "
                                    "(ou trouvable via ListDeviceAssets avec --apply)"}]})
        return 1
      dev_ref = {"refPath": placed[target_label]["refPath"]}
      if apply_wiring:
        # En UEFN 42.40, chaque @editable d'appareil sur un VerseDevice_C est un sous-objet
        # wrapper (__verse_0x..._<Nom>) expose en camelCase par Device.ListDeviceProperties /
        # GetDeviceProperties, dont la propriete `savedActor` porte le refPath de l'acteur cible.
        raw_dev_props = cli.value("Device", "ListDeviceProperties",
                                  {"devicePath": dev_ref, "device": dev_ref})
        dev_props = json.loads(raw_dev_props) if isinstance(raw_dev_props, str) else raw_dev_props
        wired_ok = []
        for row in rows:
          if row["kind"] != "ACTEUR" or not row["refPath"]:
            continue
          prop_name = row["editable"]
          try:
            if isinstance(dev_props, dict):
              candidates = [prop_name, prop_name[:1].lower() + prop_name[1:]]
              real_prop = next((c for c in candidates if c in dev_props), None)
              if not real_prop:
                real_prop = next((k for k in dev_props if k.lower() == prop_name.lower()), None)
              if not real_prop:
                row["wiring"] = "MANUEL"
                wiring_errors.append({"type": "EDITABLE_PROPERTY_NOT_FOUND", "editable": prop_name,
                                      "available": list(dev_props.keys())[:30]})
                continue
              sub_map = as_dict(cli.value("Device", "GetDeviceProperties", {
                  "devicePath": dev_ref, "device": dev_ref, "properties": [real_prop],
                  "propertyNames": [real_prop]}))
              sub_obj = sub_map.get(real_prop)
              if isinstance(sub_obj, dict) and sub_obj.get("refPath"):
                sub_inst = {"refPath": sub_obj["refPath"]}
                cli.value("Object", "set_properties", {
                    "instance": sub_inst,
                    "values": json.dumps({"savedActor": {"refPath": row["refPath"]}}),
                })
                rb = as_dict(cli.value("Object", "get_properties", {
                    "instance": sub_inst, "properties": ["savedActor"],
                }))
                rb_ref = (rb.get("savedActor") or {}).get("refPath") if isinstance(rb.get("savedActor"), dict) else None
                if rb_ref == row["refPath"]:
                  row["wiring"] = "AUTO_VERIFIED"
                  wired_ok.append(prop_name)
                else:
                  row["wiring"] = "MANUEL"
                  wiring_errors.append({"type": "EDITABLE_READBACK_MISMATCH", "editable": prop_name,
                                        "written": row["refPath"], "read_back": rb})
                continue
            cli.value("Device", "SetDeviceProperty", {
                "devicePath": dev_ref, "device": dev_ref, "propertyName": prop_name,
                "value": row["refPath"]})
            read_val = cli.value("Device", "GetDeviceProperties", {
                "devicePath": dev_ref, "device": dev_ref, "properties": [prop_name],
                "propertyNames": [prop_name]})
            read_str = json.dumps(read_val, ensure_ascii=False)
            if row["refPath"] in read_str or prop_name in read_str:
              row["wiring"] = "AUTO_VERIFIED"
              wired_ok.append(prop_name)
            else:
              row["wiring"] = "MANUEL"
              wiring_errors.append({"type": "EDITABLE_READBACK_MISMATCH", "editable": prop_name,
                                    "written": row["refPath"], "read_back": read_val})
          except McpError as exc_prop:
            row["wiring"] = "MANUEL"
            wiring_errors.append({"type": "SET_DEVICE_PROPERTY_FAILED", "editable": prop_name,
                                  "error": str(exc_prop)})
        extra = {"device": target_label, "refPath": dev_ref["refPath"],
                 "schema": dev_props, "wired_ok": wired_ok, "wiring_errors": wiring_errors}
      else:
        listed = cli.value("Object", "list_properties", {"instance": dev_ref})
        extra = {"device": target_label, "property_names": property_names(listed),
                 "raw": listed if not isinstance(listed, (list, dict)) else None,
                 "note": "Utiliser --apply pour cabler via Device.SetDeviceProperty."}
    except McpError as exc:
      return mcp_failure("list-editables", exc)
  ok = not missing and not wiring_errors
  report = {"timestamp": now_iso(), "command": "list-editables",
            "status": "PASSED" if ok else "FAILED",
            "editable_count": len(rows),
            "actor_references": sum(1 for r in rows if r["kind"] == "ACTEUR"),
            "parameters": sum(1 for r in rows if r["kind"] == "PARAMETRE"),
            "without_target": missing, "wiring_errors": wiring_errors, "mapping": rows,
            "live": extra,
            "scope": "seules les references d'ACTEUR doivent viser un acteur pose : un "
                     "@editable de type primitif (logic, int, float...) est un parametre a "
                     "regler, pas une cible. Sans --apply, le cablage reste UNKNOWN (manuel) ; "
                     "avec --apply, chaque @editable est ecrit via Device.SetDeviceProperty et "
                     "relu via Device.GetDeviceProperties."}
  save_json(os.path.join(workspace, "10_editables.json"), report)
  emit(report)
  return 0 if ok else 1


def cmd_playtest_plan(workspace: str) -> int:
  placed = load_placed(workspace)
  verse_path = os.path.join(workspace, "09_verse_report.json")
  verse = load_json(verse_path) if os.path.exists(verse_path) else None
  audit_path = os.path.join(workspace, "06_audit_report.json")
  audit = load_json(audit_path) if os.path.exists(audit_path) else None
  plan = {
      "status": "PASSED", "command": "playtest-plan",
      "state": {"actors_places": len(placed),
                "audit": (audit or {}).get("status"), "audit_source": (audit or {}).get("source"),
                "verse_build": (verse or {}).get("status")},
      "consent_to_request": (
          "Pour lancer un playtest il faut votre accord explicite : StartSession, PushChanges "
          "et StopSession sont classes DANGEREUX et n'ont jamais ete executes. StartSession a "
          "deja bloque le pont lors d'un test anterieur. Rien ne sera sauvegarde ni publie."),
      "sequence_if_agreed": [
          "Session.StartSession {} UNE SEULE FOIS (jamais deux : un second appel n'est pas teste)",
          "Session.GetSessionStatus {} toutes les 10 s jusqu'a un etat stable "
          "(Connecting -> UpdatingContent -> Connected)",
          "Session.GetGameState {} pour lire l'etat du match",
          "Session.GetClientLogEntries {\"pattern\": \"[SELF_TEST\", \"maxResults\": 50} : "
          "a toujours echoue hors session, jamais reteste session ouverte",
          "Session.StopSession {} puis GetSessionStatus pour confirmer"],
      "gatekeeper": ("des lignes de log CLIENT reelles contenant l'auto-test. Sans elles, "
                     "ecrire « comportement en jeu non verifie » dans le rapport final : une "
                     "ligne [STEP] prouve que le code est arrive jusque la, pas que la "
                     "barriere ou le timer ont reagi."),
      "not_provided_by_this_skill": [
          "aucune validation d'asset (legalite, publication) n'est accessible par MCP",
          "le fun, l'equilibrage et la publication restent humains"]}
  emit(plan)
  return 0


def cmd_visual_snapshot(workspace: str, output_image: str, dry_run: bool) -> int:
  grid = load_json(os.path.join(workspace, "03_grid.json"))
  matrix = grid.get("floors", [{"matrix": [["."]]}])[0]["matrix"]
  rows, cols = len(matrix), len(matrix[0])
  ox, oy, oz = grid_origin(grid)
  cam = [(ox + rows / 2.0) * TILE_SIZE_XY, (oy + cols / 2.0) * TILE_SIZE_XY,
         oz * TILE_SIZE_Z + max(rows, cols) * TILE_SIZE_XY * 1.2]
  cam_xf = {"location": {"x": cam[0], "y": cam[1], "z": cam[2]},
            "rotation": {"pitch": -90.0, "yaw": 0.0, "roll": 0.0},
            "scale": {"x": 1.0, "y": 1.0, "z": 1.0}}
  if dry_run:
    emit({"status": "DRY_RUN", "camera": cam_xf})
    return 0
  cli = client_for(workspace)
  try:
    cli.value("EditorApp", "SetCameraTransform", {"transform": cam_xf})
    read = cli.value("EditorApp", "GetCameraTransform", {})
    shot = cli.call("EditorApp", "CaptureViewport", {})
  except McpError as exc:
    return mcp_failure("visual-snapshot", exc)
  if not shot["images"] or not shot["images"][0].get("data"):
    emit({"status": "FAILED", "error": "CaptureViewport sans image en ligne"})
    return 1
  data = base64.b64decode(shot["images"][0]["data"])
  os.makedirs(os.path.dirname(os.path.abspath(output_image)), exist_ok=True)
  with open(output_image, "wb") as f:
    f.write(data)
  emit({"status": "PASSED", "snapshot_path": os.path.abspath(output_image), "bytes": len(data),
        "camera_requested": cam_xf, "camera_read_back": read,
        "note": "Pas de grille A1/B2 dessinee : reperer les tuiles via X = ligne*512, Y = colonne*512."})
  return 0


def cmd_search_playsets(workspace: str, query: str, asset_type: str, max_results: int) -> int:
  cli = client_for(workspace)
  try:
    res = cli.value("Probe", "chercher_playsets", {
        "mot_cle": query, "type_asset": asset_type, "max_resultats": max_results,
    })
    if isinstance(res, str):
      res = json.loads(res)
  except McpError as exc:
    return mcp_failure("search-playsets", exc)
  if not isinstance(res, dict):
    emit({"status": "FAILED", "command": "search-playsets", "error": "Reponse inattendue de Probe.chercher_playsets"})
    return 1
  emit({"status": "PASSED", "command": "search-playsets", **res,
        "note": "Tous ces chemins sont des PPID_ / PID_ legaux exposes aux createurs UEFN."})
  return 0


def cmd_audit_legality(workspace: str, fix: bool = False, remove_unmatched: bool = False) -> int:
  cli = client_for(workspace)
  try:
    if fix:
      res = cli.value("Probe", "remplacer_acteurs_illegaux", {
          "supprimer_sans_equivalent": remove_unmatched,
      })
    else:
      res = cli.value("Probe", "verifier_legalite_scene", {})
    if isinstance(res, str):
      res = json.loads(res)
  except McpError as exc:
    return mcp_failure("audit-legality", exc)
  if not isinstance(res, dict):
    emit({"status": "FAILED", "command": "audit-legality", "error": "Reponse inattendue de IslandForgeProbe"})
    return 1
  report = {"timestamp": now_iso(), "command": "audit-legality", "fix_applied": fix, **res}
  save_json(os.path.join(workspace, "06_legality_report.json"), report)
  emit(report)
  return 0 if report.get("status") == "PASSED" else 1


LOG_TS_RE = re.compile(r"^\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\]")
# Formats reels (2026-10-29) : "...references disallowed object /Pkg/Nom.Nom." (fin de ligne) et
# "...references disallowed object /Pkg/Nom.Nom. (FortValidator_FortExposedActors)".
DISALLOWED_RE = re.compile(r"references disallowed object (/\S+)")


def _disallowed_paths(line: str) -> list[str]:
  return [p.rstrip(".") for p in DISALLOWED_RE.findall(line)]


def _log_lines(res) -> list[str]:
  """GetLogEntries rend des chaines horodatees '[2026.10.29-13.49.20:431][776]Cat: ...'
  (editeur reel) ou des objets {message} (anciens retours) : on normalise en chaines."""
  if isinstance(res, str):
    try:
      res = json.loads(res)
    except ValueError:
      res = [res]
  out = []
  for e in res or []:
    out.append(e if isinstance(e, str) else str(e.get("message", json.dumps(e, ensure_ascii=False))))
  return out


def cmd_check_validator(workspace: str, no_save: bool, update_catalogue: bool) -> int:
  """Verdict de legalite du validateur UEFN (seule preuve, cf. _commun/legalite-assets.md) :
  1) repere la derniere ligne du journal, 2) sauvegarde (declenche la validation),
  3) ne garde QUE les lignes posterieures (le journal garde les vieilles erreurs),
  4) extrait les chemins 'references disallowed object'."""
  cli = client_for(workspace)
  try:
    last = _log_lines(cli.value("Logs", "GetLogEntries", {"category": "", "pattern": "", "maxEntries": 1}))
    m = LOG_TS_RE.match(last[-1]) if last else None
    since = m.group(1) if m else None
    saved = None if no_save else cli.value("Asset", "save_assets", {"asset_paths": []})
    lines = _log_lines(cli.value("Logs", "GetLogEntries", {
        "category": "", "pattern": "AssetCheck|disallowed|LogValkyrieValidation: Error", "maxEntries": 1000}))
  except McpError as exc:
    return mcp_failure("check-validator", exc)

  def ts(line: str) -> str | None:
    mm = LOG_TS_RE.match(line)
    return mm.group(1) if mm else None

  kept = [l for l in lines if since is None or (ts(l) is not None and ts(l) > since)]
  errors = [l for l in kept if "Error" in l and ("AssetCheck" in l or "LogValkyrieValidation" in l)]
  refused = sorted({p for l in errors for p in _disallowed_paths(l)})
  validation_ran = any("AssetCheck" in l for l in kept)
  if since is None:
    status, why = "UNKNOWN", "journal sans horodatage lisible : impossible de separer les vieilles erreurs des nouvelles"
  elif errors:
    status, why = "FAILED", f"{len(refused)} chemin(s) refuse(s) par le validateur"
  elif validation_ran:
    status, why = "PASSED", "validation lancee par la sauvegarde, aucune erreur"
  else:
    status, why = "UNKNOWN", ("aucune trace de validation apres la sauvegarde (niveau peut-etre non "
                              "modifie) : ce n'est PAS une preuve de legalite")
  catalogue_added = []
  if update_catalogue and refused:
    cat = load_catalogue(force=True)
    if cat:
      known = cat.setdefault("refuses", {}).setdefault("chemins", [])
      catalogue_added = [p for p in refused if p not in known]
      known.extend(catalogue_added)
      cat["mise_a_jour"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
      save_json(CATALOGUE_PATH, cat)
  report = {"timestamp": now_iso(), "command": "check-validator", "status": status, "reason": why,
            "since_log_ts": since, "saved": saved, "validation_ran": validation_ran,
            "refused_paths": refused, "error_lines": errors[:20], "error_count": len(errors),
            "catalogue": CATALOGUE_PATH, "catalogue_added": catalogue_added}
  save_json(os.path.join(workspace, "06b_validator_report.json"), report)
  emit(report)
  return 0 if status == "PASSED" else 1


def cmd_launch_session(workspace: str, dry_run: bool, consent: bool,
                       wait_seconds: int = 90, stop_after_verify: bool = False) -> int:
  if dry_run:
    emit({"status": "DRY_RUN", "command": "launch-session",
          "wait_seconds": wait_seconds, "stop_after_verify": stop_after_verify,
          "next": "Verifier la legalite (Probe.verifier_legalite_scene), puis StartSession (si Disconnected) ou PushChanges (si Connected), suivre GetSessionStatus et lire GetGameState / GetClientLogEntries."})
    return 0
  if not consent:
    emit({"status": "FAILED", "command": "launch-session", "error_kind": "CONSENT_REQUIRED",
          "error": "Lancer une session Play-in-Client (StartSession / PushChanges) exige --i-agree-to-launch-session (accord obtenu a l'etape 1)."})
    return 1
  cli = client_for(workspace)
  try:
    leg = cli.value("Probe", "verifier_legalite_scene", {})
    if isinstance(leg, str):
      leg = json.loads(leg)
    if isinstance(leg, dict) and leg.get("illegal_count", 0) > 0:
      err_rep = {
          "timestamp": now_iso(), "command": "launch-session", "status": "FAILED",
          "error_kind": "ILLEGAL_ACTORS_BLOCK_SESSION",
          "illegal_count": leg.get("illegal_count"),
          "illegal_actors": leg.get("illegal_actors", []),
          "detail": "Lancement de session annule : la scene contient des acteurs illegaux qui bloqueraient la validation Valkyrie. Lancer `audit-legality --fix` pour les remplacer automatiquement par leurs PPID_ legaux.",
      }
      save_json(os.path.join(workspace, "12_session_report.json"), err_rep)
      emit(err_rep)
      return 1
    initial_status = str(cli.value("Session", "GetSessionStatus", {}) or "Disconnected")
    if "Connected" in initial_status and "Disconnected" not in initial_status:
      action_called = "PushChanges"
      action_res = cli.value("Session", "PushChanges", {"bVerseOnly": False})
    else:
      action_called = "StartSession"
      action_res = cli.value("Session", "StartSession", {})
    history = [{"t": 0.0, "status": initial_status}]
    t0 = time.time()
    current_status = initial_status
    while time.time() - t0 < max(0, wait_seconds):
      current_status = str(cli.value("Session", "GetSessionStatus", {}) or "")
      if not history or history[-1]["status"] != current_status:
        history.append({"t": round(time.time() - t0, 1), "status": current_status})
      if "Connected" in current_status and "Disconnected" not in current_status:
        break
      if wait_seconds <= 5:
        break
      time.sleep(min(5.0, max(0.5, wait_seconds - (time.time() - t0))))
    else:
      current_status = str(cli.value("Session", "GetSessionStatus", {}) or current_status)
      if not history or history[-1]["status"] != current_status:
        history.append({"t": round(time.time() - t0, 1), "status": current_status})

    valkyrie_logs = []
    try:
      valkyrie_logs = cli.value("Logs", "GetLogEntries", {"category": "Valkyrie", "maxResults": 20}) or []
    except Exception:
      pass
    game_state = None
    client_logs = []
    connected = ("Connected" in current_status and "Disconnected" not in current_status)
    if connected:
      try:
        game_state = cli.value("Session", "GetGameState", {})
      except Exception:
        pass
      try:
        client_logs = cli.value("Session", "GetClientLogEntries", {"pattern": "[SELF_TEST", "maxResults": 50}) or []
      except Exception:
        pass
      if stop_after_verify:
        try:
          cli.value("Session", "StopSession", {})
        except Exception:
          pass
  except McpError as exc:
    return mcp_failure("launch-session", exc)

  ok = connected or ("Connecting" in current_status or "Updating" in current_status or wait_seconds == 0)
  report = {
      "timestamp": now_iso(), "command": "launch-session",
      "status": "PASSED" if ok else "FAILED",
      "action_called": action_called,
      "action_result": action_res,
      "initial_session_status": initial_status,
      "final_session_status": current_status,
      "connected": connected,
      "status_history": history,
      "game_state": game_state,
      "client_logs": client_logs,
      "valkyrie_logs": valkyrie_logs,
      "scope": ("Session Play-in-Client lancee apres verification FortEditorValidatorSubsystem (0 acteur illegal). "
                + ("Connectee et etat du match relu." if connected else
                   "Lancement initie (en cours de connexion / chargement du client Fortnite).")),
  }
  save_json(os.path.join(workspace, "12_session_report.json"), report)
  emit(report)
  return 0 if ok else 1


def cmd_cleanup(workspace: str) -> int:
  cli = client_for(workspace)
  try:
    found = cli.value("Scene", "find_actors", {"tag": MAP_TAG, "collision_channels": []}) or []
    removed = sum(1 for a in found if cli.value("Scene", "remove_from_scene",
                                                {"actor": {"refPath": a["actorPath"]}}))
    left = cli.value("Scene", "find_actors", {"tag": MAP_TAG, "collision_channels": []}) or []
  except McpError as exc:
    return mcp_failure("cleanup", exc)
  if not left and os.path.exists(placed_path(workspace)):
    os.remove(placed_path(workspace))
  emit({"status": "PASSED" if not left else "FAILED", "tag": MAP_TAG, "found": len(found),
        "removed": removed, "left": len(left)})
  return 0 if not left else 1


def main() -> int:
  parser = argparse.ArgumentParser(description="UEFN Spatial CLI Gatekeeper (MCP)")
  sub = parser.add_subparsers(dest="command", required=True)

  def ws(p, dry=False):
    p.add_argument("--workspace", default="workspace_map",
                   help="dossier d'etat de la carte, HORS du skill (chemin absolu conseille)")
    if dry:
      p.add_argument("--dry-run", action="store_true")
    return p

  p = ws(sub.add_parser("init", help="cree le workspace et ses 5 fichiers depuis un gabarit"))
  p.add_argument("--template", default="blank")
  p.add_argument("--force", action="store_true")
  p.add_argument("--list", action="store_true", help="liste les gabarits disponibles")
  ws(sub.add_parser("preflight"))
  ws(sub.add_parser("measure-palette"), dry=True).add_argument("--force", action="store_true")
  ws(sub.add_parser("validate-scene", help="forme et coherence des 5 fichiers de spec"))
  p = ws(sub.add_parser("validate-grid"))
  p.add_argument("grid_file", nargs="?", default=None,
                 help="defaut : <workspace>/03_grid.json")
  ws(sub.add_parser("build-structure"), dry=True)
  ws(sub.add_parser("compile-transforms"))
  ws(sub.add_parser("place-scene"), dry=True)
  ws(sub.add_parser("audit-scene")).add_argument("--live", action="store_true")
  ws(sub.add_parser("check-navigation"))
  p = ws(sub.add_parser("check-symmetry", help="symetrie des specs et, avec --live, de la "
                                               "scene posee (axes X, Y, R180)"))
  p.add_argument("--live", action="store_true")
  ws(sub.add_parser("apply-properties"), dry=True)
  ws(sub.add_parser("wire-devices"), dry=True).add_argument(
      "--allow-empty", action="store_true",
      help="valide 08_wiring_report.json a PASSED si aucun binding Direct Event n'est declare (cablage Verse)")
  p = ws(sub.add_parser("verse-scan"))
  p.add_argument("--root", default="")
  p.add_argument("--recursive", action="store_true")
  p = ws(sub.add_parser("verse-grep"))
  p.add_argument("--pattern", default="")
  p.add_argument("--symbols", help="liste separee par des virgules, une recherche par symbole")
  p.add_argument("--glob", dest="path_glob", default="/Fortnite.com (Fortnite)/**")
  p.add_argument("--max-results", type=int, default=10)
  ws(sub.add_parser("verse-read", help="relit un .verse du projet (lecture seule)")).add_argument(
      "--path", dest="verse_path", required=True)
  ws(sub.add_parser("list-devices", help="assetPath exact des devices posables (lecture seule)")
     ).add_argument("--filter", dest="name_filter", default="")
  p = ws(sub.add_parser("verse-write"))
  p.add_argument("--file", required=True, help="fichier .verse local (workspace/verse/)")
  p.add_argument("--path", dest="verse_path", required=True, help="chemin .verse dans le projet")
  p.add_argument("--i-agree-to-modify-project", action="store_true")
  ws(sub.add_parser("verse-build"), dry=True).add_argument("--log-entries", type=int, default=15)
  p = ws(sub.add_parser("list-editables"))
  p.add_argument("--device", help="label du device Verse pose (defaut Game_Manager_01 avec --apply)")
  p.add_argument("--live", action="store_true")
  p.add_argument("--apply", action="store_true",
                 help="pose le creative_device si absent et cable les @editable via Device.SetDeviceProperty")
  ws(sub.add_parser("playtest-plan"))
  ws(sub.add_parser("visual-snapshot"), dry=True).add_argument(
      "--output", default=None, help="defaut : <workspace>/topdown.png")
  ws(sub.add_parser("cleanup"))
  p = ws(sub.add_parser("search-playsets", help="cherche uniquement dans les Playsets/Props Creatif legaux (PPID/PID)"))
  p.add_argument("--query", required=True, help="mots-cles (ex: 'neon vendor', 'fortilla ramp', 'military crate')")
  p.add_argument("--type", dest="asset_type", default="PPID", choices=["PPID", "PID", "ALL"])
  p.add_argument("--max", dest="max_results", type=int, default=30)
  p = ws(sub.add_parser("audit-legality", help="verifie tous les acteurs du niveau ouvert via FortEditorValidatorSubsystem"))
  p.add_argument("--fix", action="store_true", help="remplace automatiquement les acteurs illegaux par leurs PPID_ legaux")
  p.add_argument("--remove-unmatched", action="store_true", help="avec --fix, supprime aussi les acteurs illegaux sans PPID_ equivalent")
  p = ws(sub.add_parser("check-validator", help="sauvegarde puis lit le verdict du validateur UEFN "
                                                "(seule preuve de legalite) dans le journal"))
  p.add_argument("--no-save", action="store_true", help="ne pas sauvegarder (relit seulement)")
  p.add_argument("--update-catalogue", action="store_true",
                 help="ajoute les chemins refuses a agent-team/_commun/catalogue-verifie.json")
  p = ws(sub.add_parser("launch-session", help="verifie la legalite puis lance StartSession / PushChanges et suit la connexion"), dry=True)
  p.add_argument("--i-agree-to-launch-session", dest="consent", action="store_true")
  p.add_argument("--wait-seconds", type=int, default=90)
  p.add_argument("--stop-after-verify", action="store_true")

  a = parser.parse_args()
  c = a.command
  if c == "init" and a.list:
    emit({"status": "PASSED", "command": "init", "templates": list_templates(),
          "templates_root": TEMPLATES_ROOT})
    return 0
  if c == "validate-grid" and a.grid_file:
    # Fichier explicite : aucune raison d'exiger un workspace (ni de le refuser).
    return cmd_validate_grid(a.grid_file)
  workspace = resolve_workspace(a.workspace, c)
  if workspace is None:
    return 1
  a.workspace = workspace
  if c == "validate-grid":
    return cmd_validate_grid(a.grid_file or os.path.join(workspace, "03_grid.json"))
  if c == "init":
    return cmd_init(workspace, a.template, a.force)
  if c == "preflight":
    return cmd_preflight(workspace)
  if c == "measure-palette":
    return cmd_measure_palette(workspace, a.dry_run, a.force)
  if c == "validate-scene":
    return cmd_validate_scene(workspace)
  if c == "build-structure":
    return cmd_build_structure(workspace, a.dry_run)
  if c == "compile-transforms":
    return cmd_compile_transforms(workspace)
  if c == "place-scene":
    return cmd_place_scene(workspace, a.dry_run)
  if c == "audit-scene":
    return cmd_audit_scene(workspace, a.live)
  if c == "check-navigation":
    return cmd_check_navigation(workspace)
  if c == "check-symmetry":
    return cmd_check_symmetry(workspace, a.live)
  if c == "apply-properties":
    return cmd_apply_properties(workspace, a.dry_run)
  if c == "wire-devices":
    return cmd_wire_devices(workspace, a.dry_run, a.allow_empty)
  if c == "verse-scan":
    return cmd_verse_scan(workspace, a.root, a.recursive)
  if c == "verse-grep":
    return cmd_verse_grep(workspace, a.pattern, a.symbols, a.path_glob, a.max_results)
  if c == "verse-read":
    return cmd_verse_read(workspace, a.verse_path)
  if c == "list-devices":
    return cmd_list_devices(workspace, a.name_filter)
  if c == "verse-write":
    return cmd_verse_write(workspace, a.file, a.verse_path, a.i_agree_to_modify_project)
  if c == "verse-build":
    return cmd_verse_build(workspace, a.dry_run, a.log_entries)
  if c == "list-editables":
    return cmd_list_editables(workspace, a.device, a.live, a.apply)
  if c == "playtest-plan":
    return cmd_playtest_plan(workspace)
  if c == "visual-snapshot":
    return cmd_visual_snapshot(workspace, a.output or os.path.join(workspace, "topdown.png"),
                               a.dry_run)
  if c == "search-playsets":
    return cmd_search_playsets(workspace, a.query, a.asset_type, a.max_results)
  if c == "audit-legality":
    return cmd_audit_legality(workspace, a.fix, a.remove_unmatched)
  if c == "check-validator":
    return cmd_check_validator(workspace, a.no_save, a.update_catalogue)
  if c == "launch-session":
    return cmd_launch_session(workspace, a.dry_run, a.consent, a.wait_seconds, a.stop_after_verify)
  if c == "cleanup":
    return cmd_cleanup(workspace)
  return 1


if __name__ == "__main__":
  sys.exit(main())
