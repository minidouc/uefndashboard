#!/usr/bin/env python3
"""CLI spatial du skill uefn-map-creator (v2, MCP officiel UEFN).

Calculs hors ligne : validate-grid, compile-transforms, audit-scene, check-navigation.
Actions editeur (MCP http://127.0.0.1:8000/mcp, editeur ouvert) :
  preflight, measure-palette, build-structure, place-scene, audit-scene --live,
  visual-snapshot, cleanup.
--dry-run : calcule sans toucher l'editeur, statut DRY_RUN (jamais PASSED).
Editeur injoignable ou timeout : statut FAILED, code retour 2 ou 3.
"""

import argparse
from collections import deque
from datetime import datetime, timezone
import base64
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_client import McpClient, McpError, McpOffline, McpTimeout  # noqa: E402

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
BATCH_SIZE = 10
PAGINATION_CVAR = "ModelContextProtocol.PaginationPageSize"
MAP_TAG = os.environ.get("UEFN_MAP_TAG", "UEFNMAP")
MEASURE_AT = [0.0, -20000.0, 5000.0]

SPAWN = "editor_toolset.toolsets.scene.SceneTools.add_to_scene_from_asset"
ADD_TAG = "editor_toolset.toolsets.actor.ActorTools.add_tag"


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


def mcp_failure(command: str, exc: Exception, extra: dict | None = None) -> int:
  kind = {McpOffline: "OFFLINE", McpTimeout: "TIMEOUT_OUTCOME_UNKNOWN"}.get(
      type(exc), "TOOL_ERROR")
  out = {"status": "FAILED", "command": command, "error_kind": kind,
         "error": str(exc)}
  if kind == "TIMEOUT_OUTCOME_UNKNOWN":
    out["next"] = "Relire l'etat (find_actors, get_actor_transform) avant de rejouer."
  if extra:
    out.update(extra)
  emit(out)
  return 3 if kind == "TIMEOUT_OUTCOME_UNKNOWN" else 2


# ---------------------------------------------------------------- geometrie

def xyz_to_luf(xyz: list[float]) -> list[float]:
  x, y, z = xyz
  return [-y, z, x]


def luf_to_xyz(luf: list[float]) -> list[float]:
  left, up, forward = luf
  return [forward, -left, up]


def xform(loc: list[float], yaw: float = 0.0) -> dict:
  return {"location": {"x": loc[0], "y": loc[1], "z": loc[2]},
          "rotation": {"pitch": 0.0, "yaw": yaw, "roll": 0.0},
          "scale": {"x": 1.0, "y": 1.0, "z": 1.0}}


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


def anchor_center(tile: list[int], slot: str, size_cm: list[float]) -> list[float]:
  tx, ty, tz = tile
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


def asset_size_pivot(palette: dict, key: str) -> tuple[list[float], list[float], str]:
  a = palette.get(key)
  if not a:
    raise KeyError(f"asset_key absent de 02_palette.json : {key}")
  if not a.get("measured"):
    raise KeyError(f"asset non mesure (lancer measure-palette) : {key}")
  return a["size_cm"], a["pivot_offset_cm"], a["uefn_path"]


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


def find_by_label(cli: McpClient, label: str) -> str | None:
  found = cli.value("Scene", "find_actors", {"name": label, "collision_channels": []}) or []
  exact = [a for a in found if label in (a.get("label"), a.get("name"))]
  return exact[0]["actorPath"] if len(exact) == 1 else None


def verify_transform(cli: McpClient, ref: str, op: dict) -> dict | None:
  tf = cli.value("Actor", "get_actor_transform", {"actor": {"refPath": ref}})
  want = op["xform"]
  dl = max(abs(tf["location"][k] - want["location"][k]) for k in "xyz")
  dyaw = abs(((tf["rotation"]["yaw"] - want["rotation"]["yaw"]) + 180.0) % 360.0 - 180.0)
  if dl > POS_TOLERANCE_CM or dyaw > YAW_TOLERANCE_DEG:
    return {"type": "TRANSFORM_MISMATCH", "actor": op["label"],
            "requested": want, "read_back": tf}
  return None


def place_actors(cli: McpClient, workspace: str, ops: list[dict]) -> dict:
  """Spawn par lots de 10 dans execute_tool_script, refPath persistes a chaque lot."""
  placed = load_placed(workspace)
  todo = [o for o in ops if o["label"] not in placed]
  errors, warnings, verified = [], [], 0
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
  return {"requested": len(ops), "already_placed": len(ops) - len(todo),
          "verified": verified, "errors": errors, "warnings": warnings}


def place_devices(cli: McpClient, workspace: str, ops: list[dict]) -> dict:
  """PlaceDevice ignore le yaw demande (0 relu 90) : forcer la transform puis relire."""
  placed = load_placed(workspace)
  errors, verified = [], 0
  for op in ops:
    if op["label"] in placed:
      continue
    ref = cli.value("Device", "PlaceDevice", {"assetPath": {"refPath": op["asset"]},
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
  return {"requested": len(ops), "verified": verified, "errors": errors}


# ---------------------------------------------------------------- commandes

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
    ref = cli.value("Device", "PlaceDevice", {"assetPath": {"refPath": item["uefn_path"]},
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
  todo = [k for k, v in assets.items()
          if v.get("uefn_path") and (force or not v.get("measured"))]
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
  if not floors:
    errors.append({"type": "EMPTY_GRID", "detail": "Aucun etage defini."})
  else:
    floor_map = {f["z_index"]: f["matrix"] for f in floors}
    for z_idx, matrix in floor_map.items():
      rows = len(matrix)
      cols = len(matrix[0]) if rows > 0 else 0
      for r in range(rows):
        if len(matrix[r]) != cols:
          errors.append({"type": "RAGGED_ROW", "row": r, "z_index": z_idx})
          continue
        for c in range(cols):
          cell = matrix[r][c]
          if (r in (0, rows - 1) or c in (0, cols - 1)) and cell not in ("#", "V"):
            errors.append({"type": "UNCLOSED_BORDER", "tile": [r, c, z_idx], "cell": cell})
          if cell.startswith("R_"):
            upper = floor_map.get(z_idx + 1)
            if upper and upper[r][c] != "T":
              errors.append({"type": "HEADROOM_BLOCKED_ON_STAIRS",
                             "stair_tile": [r, c, z_idx], "upper_tile": [r, c, z_idx + 1],
                             "current_upper_cell": upper[r][c], "required_upper_cell": "T"})
      if data.get("symmetric") and data.get("symmetry_axis") == "X":
        for r in range(rows // 2):
          mirror_r = rows - 1 - r
          for c in range(cols):
            a = matrix[r][c].replace("S1", "S").replace("S2", "S")
            b = matrix[mirror_r][c].replace("S1", "S").replace("S2", "S")
            if a != b:
              errors.append({"type": "SYMMETRY_BROKEN", "tile_a": [r, c, z_idx],
                             "tile_b": [mirror_r, c, z_idx]})
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
  pick = {}
  for cat in ("STRUCTURE_FLOOR", "STRUCTURE_WALL"):
    keys = [k for k, v in palette.items() if v.get("category") == cat]
    if not keys:
      errors.append({"type": "MISSING_PALETTE_CATEGORY", "category": cat})
      continue
    try:
      pick[cat] = asset_size_pivot(palette, keys[0])
    except KeyError as exc:
      errors.append({"type": "UNMEASURED_ASSET", "error": str(exc)})
  if errors:
    return ops, errors, warnings
  fsize, fpivot, fasset = pick["STRUCTURE_FLOOR"]
  wsize, wpivot, wasset = pick["STRUCTURE_WALL"]
  for floor in grid.get("floors", []):
    z = floor["z_index"]
    matrix = floor["matrix"]
    rows, cols = len(matrix), len(matrix[0]) if matrix else 0
    bz = z * TILE_SIZE_Z
    for r in range(rows):
      for c in range(cols):
        cell = matrix[r][c]
        if cell in ("V", "T"):
          continue
        cx, cy = r * TILE_SIZE_XY + 256.0, c * TILE_SIZE_XY + 256.0
        floor_center = [cx, cy, bz - fsize[2] / 2.0]
        ops.append({"label": f"Floor_{r}_{c}_{z}", "asset": fasset, "category": "FLOOR",
                    "tile": [r, c, z], "center_cm": floor_center, "size_cm": fsize, "yaw": 0.0,
                    "xform": xform(loc_from_center(floor_center, fpivot, 0.0), 0.0)})
        if cell != "#":
          continue
        border = r in (0, rows - 1) or c in (0, cols - 1)
        if not border:
          warnings.append({"type": "INTERIOR_WALL_NOT_BUILT", "tile": [r, c, z],
                           "detail": "build-structure ne pose des murs que sur le perimetre"})
        # Mur pose a l'exterieur de la tuile : l'interieur 512 x 512 reste libre.
        half_t = min(wsize[0], wsize[1]) / 2.0
        walls = []
        if r == 0:
          walls.append(("South", [r * TILE_SIZE_XY - half_t, cy], 0.0))
        if r == rows - 1:
          walls.append(("North", [(r + 1) * TILE_SIZE_XY + half_t, cy], 180.0))
        if c == 0:
          walls.append(("West", [cx, c * TILE_SIZE_XY - half_t], 90.0))
        if c == cols - 1:
          walls.append(("East", [cx, (c + 1) * TILE_SIZE_XY + half_t], 270.0))
        for side, (wx, wy), yaw in walls:
          center = [wx, wy, bz + wsize[2] / 2.0]
          ops.append({"label": f"Wall_{side}_{r}_{c}_{z}", "asset": wasset, "category": "WALL",
                      "tile": [r, c, z], "center_cm": center,
                      "size_cm": rotated_size(wsize, yaw), "yaw": yaw,
                      "xform": xform(loc_from_center(center, wpivot, yaw), yaw)})
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


def cmd_compile_transforms(workspace: str) -> int:
  palette = load_json(os.path.join(workspace, "02_palette.json")).get("assets", {})
  grid = load_json(os.path.join(workspace, "03_grid.json"))
  dev_path = os.path.join(workspace, "04_devices.json")
  props_path = os.path.join(workspace, "05_props.json")
  devices = load_json(dev_path).get("devices", []) if os.path.exists(dev_path) else []
  props = load_json(props_path).get("props", []) if os.path.exists(props_path) else []
  matrix = grid.get("floors", [{"matrix": [["."]]}])[0]["matrix"]
  arena_center = [len(matrix) * TILE_SIZE_XY / 2.0, len(matrix[0]) * TILE_SIZE_XY / 2.0, 0.0]
  registry, errors = {}, []

  def add(entry: dict, category: str, size_rot: list[float], pivot: list[float], asset: str,
          center: list[float], tile: list[int], snap: bool, yaw: float) -> None:
    floor_z = tile[2] * TILE_SIZE_Z
    loc = loc_from_center(center, pivot, yaw)
    registry[entry["actor_label"]] = {
        "actor_label": entry["actor_label"], "category": category, "asset": asset,
        "tile": tile, "center_cm": center, "size_cm": size_rot, "yaw": yaw,
        "location_xyz": loc, "location_luf": xyz_to_luf(loc), "snap_to_floor": snap,
        "distance_to_floor_cm": round(center[2] - size_rot[2] / 2.0 - floor_z, 2),
    }

  def tile_center(tile: list[int]) -> list[float]:
    return [tile[0] * TILE_SIZE_XY + 256.0, tile[1] * TILE_SIZE_XY + 256.0, tile[2] * TILE_SIZE_Z]

  def anchored(entry: dict, size: list[float]) -> tuple[list[float], list[float], float]:
    yaw = resolve_yaw(entry.get("face_towards", "NORTH"), tile_center(entry["tile"]),
                      registry, arena_center)
    size_rot = rotated_size(size, yaw)
    return anchor_center(entry["tile"], entry["slot"], size_rot), size_rot, yaw

  for dev in devices:
    try:
      size, pivot, asset = asset_size_pivot(palette, dev.get("asset_key", ""))
      center, size_rot, yaw = anchored(dev, size)
      add(dev, "DEVICE", size_rot, pivot, asset, center, dev["tile"], dev.get("on_floor", True), yaw)
    except (KeyError, ValueError) as exc:
      errors.append({"type": "COMPILE_ERROR", "actor": dev.get("actor_label"), "error": str(exc)})

  for prop in props:
    try:
      size, pivot, asset = asset_size_pivot(palette, prop.get("asset_key", ""))
      snap = prop.get("snap_to_floor", True)
      if prop.get("placement_mode") == "TILE_ANCHOR":
        center, size_rot, yaw = anchored(prop, size)
        tile = prop["tile"]
      else:
        parent = registry.get(prop.get("reference_actor"))
        if not parent:
          raise KeyError(f"reference_actor introuvable ou place apres : {prop.get('reference_actor')}")
        yaw = resolve_yaw(prop.get("face_towards", "NORTH"), parent["center_cm"],
                          registry, arena_center)
        size_rot = rotated_size(size, yaw)
        center = relative_center(parent, size_rot, prop["direction"],
                                 float(prop.get("gap_cm", 20.0)), snap)
        tile = parent["tile"]
      add(prop, "PROP", size_rot, pivot, asset, center, tile, snap, yaw)
    except (KeyError, ValueError) as exc:
      errors.append({"type": "COMPILE_ERROR", "actor": prop.get("actor_label"), "error": str(exc)})

  save_json(os.path.join(workspace, "_compiled_scene.json"), registry)
  emit({"status": "PASSED" if not errors else "FAILED", "compiled_actors": len(registry),
        "error_count": len(errors), "errors": errors})
  return 0 if not errors else 1


def cmd_place_scene(workspace: str, dry_run: bool) -> int:
  compiled = os.path.join(workspace, "_compiled_scene.json")
  if not os.path.exists(compiled):
    emit({"status": "FAILED", "error": "lancer compile-transforms d'abord"})
    return 1
  registry = load_json(compiled)
  ops = [{"label": k, "asset": v["asset"], "category": v["category"],
          "xform": xform(v["location_xyz"], v["yaw"])} for k, v in registry.items()]
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


def live_entries(cli: McpClient, workspace: str, registry: dict) -> tuple[dict, list[dict]]:
  """Remplace centre et taille theoriques par les bounds reels relus dans l'editeur."""
  placed = load_placed(workspace)
  missing = []
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
  return registry, missing


def cmd_audit_scene(workspace: str, live: bool) -> int:
  compiled_path = os.path.join(workspace, "_compiled_scene.json")
  if not os.path.exists(compiled_path) and cmd_compile_transforms(workspace) != 0:
    return 1
  registry = load_json(compiled_path)
  struct_path = os.path.join(workspace, "_compiled_structure.json")
  structure = load_json(struct_path).get("operations", []) if os.path.exists(struct_path) else []
  walls = {o["label"]: {"actor_label": o["label"], "category": "WALL", "tile": o["tile"],
                        "center_cm": o["center_cm"], "size_cm": o["size_cm"]}
           for o in structure if o["category"] == "WALL"}
  floors = {o["label"]: {"actor_label": o["label"], "category": "FLOOR", "tile": o["tile"],
                         "center_cm": o["center_cm"], "size_cm": o["size_cm"]}
            for o in structure if o["category"] == "FLOOR"}
  missing = []
  if live:
    cli = client_for(workspace)
    try:
      registry, m1 = live_entries(cli, workspace, registry)
      walls, m2 = live_entries(cli, workspace, walls)
      floors, m3 = live_entries(cli, workspace, floors)
    except McpError as exc:
      return mcp_failure("audit-scene --live", exc)
    missing = m1 + m2 + m3
  floor_top = {}
  for f in floors.values():
    t = tuple(f["tile"])
    floor_top[t] = f["center_cm"][2] + f["size_cm"][2] / 2.0

  overlap_errors, gravity_errors = [], []
  actors = list(registry.values())
  for a in actors:
    tile = tuple(a["tile"])
    ref_z = floor_top.get(tile, tile[2] * TILE_SIZE_Z)
    dist = round(a["center_cm"][2] - a["size_cm"][2] / 2.0 - ref_z, 2)
    if a.get("snap_to_floor", True) and abs(dist) > MAX_GRAVITY_CM:
      gravity_errors.append({
          "type": "GRAVITY_ERROR", "actor": a["actor_label"], "distance_to_floor_cm": dist,
          "state": "FLOATING" if dist > 0 else "BURIED", "tile": a["tile"],
          "floor_reference": "bounds du sol" if tile in floor_top else "tile_z * 384",
          "suggestion": "Remesurer pivot_offset_cm (measure-palette --force) ou corriger snap_to_floor."})
  others = actors + list(walls.values())
  for i, a in enumerate(actors):
    for b in others[i + 1:]:
      pen = aabb_penetration_cm(a, b)
      if pen > MAX_OVERLAP_CM:
        overlap_errors.append({
            "type": "OVERLAP_ERROR", "actor_a": a["actor_label"], "actor_b": b["actor_label"],
            "penetration_cm": pen, "tile": a["tile"],
            "suggestion": f"Placer {a['actor_label']} en RELATIVE_TO_ACTOR avec gap_cm >= 15."})
  total = len(overlap_errors) + len(gravity_errors) + len(missing)
  report = {"timestamp": now_iso(), "source": "live" if live else "compiled",
            "status": "PASSED" if total == 0 else "FAILED", "error_count": total,
            "overlap_errors": overlap_errors, "gravity_errors": gravity_errors,
            "scene_errors": missing, "navigation_errors": []}
  save_json(os.path.join(workspace, "06_audit_report.json"), report)
  emit(report)
  return 0 if total == 0 else 1


def cmd_check_navigation(workspace: str) -> int:
  compiled_path = os.path.join(workspace, "_compiled_scene.json")
  report_path = os.path.join(workspace, "06_audit_report.json")
  if not os.path.exists(compiled_path) and cmd_compile_transforms(workspace) != 0:
    return 1
  registry = load_json(compiled_path)
  report = load_json(report_path) if os.path.exists(report_path) else {
      "overlap_errors": [], "gravity_errors": [], "scene_errors": []}
  nav_errors = []
  by_tile = {}
  for p in (v for v in registry.values() if v.get("category") == "PROP"):
    by_tile.setdefault(tuple(p["tile"]), []).append(p)
  for tile_key, tile_props in by_tile.items():
    for i in range(len(tile_props)):
      for j in range(i + 1, len(tile_props)):
        pa, pb = tile_props[i], tile_props[j]
        dx = abs(pa["center_cm"][0] - pb["center_cm"][0]) - (pa["size_cm"][0] + pb["size_cm"][0]) / 2.0
        dy = abs(pa["center_cm"][1] - pb["center_cm"][1]) - (pa["size_cm"][1] + pb["size_cm"][1]) / 2.0
        gap = max(dx, dy)
        if 0.0 < gap < MIN_CORRIDOR_WIDTH:
          nav_errors.append({"type": "CORRIDOR_TOO_NARROW", "tile": list(tile_key),
                             "free_width_cm": round(gap, 2),
                             "required_width_cm": MIN_CORRIDOR_WIDTH,
                             "blocking_actors": [pa["actor_label"], pb["actor_label"]]})
  report["navigation_errors"] = nav_errors
  report["navigation_scope"] = "paires de props dans une meme tuile ; pas de capsule ni de murs"
  report["error_count"] = (len(report.get("overlap_errors", [])) + len(report.get("gravity_errors", []))
                           + len(report.get("scene_errors", [])) + len(nav_errors))
  report["status"] = "PASSED" if report["error_count"] == 0 else "FAILED"
  save_json(report_path, report)
  emit(report)
  return 0 if not nav_errors else 1


def cmd_visual_snapshot(workspace: str, output_image: str, dry_run: bool) -> int:
  grid = load_json(os.path.join(workspace, "03_grid.json"))
  matrix = grid.get("floors", [{"matrix": [["."]]}])[0]["matrix"]
  rows, cols = len(matrix), len(matrix[0])
  cam = [rows * TILE_SIZE_XY / 2.0, cols * TILE_SIZE_XY / 2.0,
         max(rows, cols) * TILE_SIZE_XY * 1.2]
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
    p.add_argument("--workspace", default="workspace_map")
    if dry:
      p.add_argument("--dry-run", action="store_true")
    return p

  ws(sub.add_parser("preflight"))
  ws(sub.add_parser("measure-palette"), dry=True).add_argument("--force", action="store_true")
  sub.add_parser("validate-grid").add_argument(
      "grid_file", nargs="?", default="workspace_map/03_grid.json")
  ws(sub.add_parser("build-structure"), dry=True)
  ws(sub.add_parser("compile-transforms"))
  ws(sub.add_parser("place-scene"), dry=True)
  ws(sub.add_parser("audit-scene")).add_argument("--live", action="store_true")
  ws(sub.add_parser("check-navigation"))
  ws(sub.add_parser("visual-snapshot"), dry=True).add_argument(
      "--output", default="workspace_map/topdown.png")
  ws(sub.add_parser("cleanup"))

  a = parser.parse_args()
  c = a.command
  if c == "preflight":
    return cmd_preflight(a.workspace)
  if c == "measure-palette":
    return cmd_measure_palette(a.workspace, a.dry_run, a.force)
  if c == "validate-grid":
    return cmd_validate_grid(a.grid_file)
  if c == "build-structure":
    return cmd_build_structure(a.workspace, a.dry_run)
  if c == "compile-transforms":
    return cmd_compile_transforms(a.workspace)
  if c == "place-scene":
    return cmd_place_scene(a.workspace, a.dry_run)
  if c == "audit-scene":
    return cmd_audit_scene(a.workspace, a.live)
  if c == "check-navigation":
    return cmd_check_navigation(a.workspace)
  if c == "visual-snapshot":
    return cmd_visual_snapshot(a.workspace, a.output, a.dry_run)
  if c == "cleanup":
    return cmd_cleanup(a.workspace)
  return 1


if __name__ == "__main__":
  sys.exit(main())
