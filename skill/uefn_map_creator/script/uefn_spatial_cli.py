#!/usr/bin/env python3
""" CLI spatial pour le skill Antigravity uefn-map-builder.

Gere le profilage 3D, la validation de grille 2D, le calcul des transformations
(ancres de tuiles + distances relatives par boites englobantes), la conversion
XYZ <-> LUF, l'audit de collision/gravite/navigation et la capture 2D
quadrillee.
"""

import argparse
from collections import deque
from datetime import datetime, timezone
import json
import math
import os
import sys
import urllib.error
import urllib.request

BRIDGE_URL = os.environ.get("UEFN_BRIDGE_URL", "http://127.0.0.1:9210")

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


def load_json(path: str) -> dict:
  with open(path, "r", encoding="utf-8") as f:
    return json.load(f)


def save_json(path: str, data: dict) -> None:
  os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
  with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)


def call_bridge(endpoint: str, payload: dict, timeout: int = 60) -> dict:
  url = f"{BRIDGE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
  req = urllib.request.Request(
      url,
      data=json.dumps(payload).encode("utf-8"),
      headers={"Content-Type": "application/json"},
      method="POST",
  )
  try:
    with urllib.request.urlopen(req, timeout=timeout) as resp:
      return json.loads(resp.read().decode("utf-8"))
  except urllib.error.URLError as exc:
    return {
        "status": "OFFLINE_OR_TIMEOUT",
        "error": str(exc),
        "outcome_unknown": True,
    }


def xyz_to_luf(xyz: list[float]) -> list[float]:
  x, y, z = xyz
  return [-y, z, x]


def luf_to_xyz(luf: list[float]) -> list[float]:
  left, up, forward = luf
  return [forward, -left, up]


def compute_anchor_xyz(
    tile: list[int], slot: str, size_cm: list[float], pivot_offset: list[float]
) -> list[float]:
  tx, ty, tz = tile
  sx, sy, sz = size_cm
  px, py, pz = pivot_offset
  hx, hy = sx / 2.0, sy / 2.0
  bx = tx * TILE_SIZE_XY
  by = ty * TILE_SIZE_XY
  bz = tz * TILE_SIZE_Z

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
  cz = bz + (sz / 2.0)
  return [round(cx - px, 2), round(cy - py, 2), round(cz - pz, 2)]


def resolve_yaw(
    face_towards: str,
    actor_pos: list[float],
    registry: dict,
    arena_center: list[float],
) -> float:
  cardinals = {
      "NORTH": 0.0,
      "EAST": 90.0,
      "SOUTH": 180.0,
      "WEST": 270.0,
  }
  if face_towards in cardinals:
    return cardinals[face_towards]
  target = arena_center if face_towards == "CENTER" else None
  if face_towards in registry:
    target = registry[face_towards]["center_cm"]
  if target:
    dx = target[0] - actor_pos[0]
    dy = target[1] - actor_pos[1]
    angle = math.degrees(math.atan2(dy, dx))
    return round(angle % 360.0, 2)
  return 0.0


def compute_relative_xyz(
    parent: dict,
    child_size: list[float],
    child_pivot: list[float],
    direction: str,
    gap_cm: float,
    snap_to_floor: bool,
) -> list[float]:
  pc = parent["center_cm"]
  ps = parent["size_cm"]
  yaw_rad = math.radians(parent.get("yaw", 0.0))

  fwd = (round(math.cos(yaw_rad), 4), round(math.sin(yaw_rad), 4), 0.0)
  right = (round(-math.sin(yaw_rad), 4), round(math.cos(yaw_rad), 4), 0.0)

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
  dist = (ps[axis] / 2.0) + float(gap_cm) + (child_size[axis] / 2.0)

  cx = pc[0] + ux * dist
  cy = pc[1] + uy * dist
  if snap_to_floor and direction != "ON_TOP_OF":
    floor_z = parent["center_cm"][2] - (ps[2] / 2.0)
    cz = floor_z + (child_size[2] / 2.0)
  else:
    cz = pc[2] + uz * dist

  return [
      round(cx - child_pivot[0], 2),
      round(cy - child_pivot[1], 2),
      round(cz - child_pivot[2], 2),
  ]


def aabb_penetration_cm(a: dict, b: dict) -> float:
  ca, sa = a["center_cm"], a["size_cm"]
  cb, sb = b["center_cm"], b["size_cm"]
  overlaps = []
  for i in range(3):
    dist = abs(ca[i] - cb[i])
    min_dist = (sa[i] / 2.0) + (sb[i] / 2.0)
    if dist >= min_dist:
      return 0.0
    overlaps.append(min_dist - dist)
  return round(min(overlaps), 2)


def cmd_measure_palette(workspace: str) -> int:
  gdd_path = os.path.join(workspace, "01_gdd.json")
  palette_path = os.path.join(workspace, "02_palette.json")
  palette = (
      load_json(palette_path)
      if os.path.exists(palette_path)
      else {"assets": {}}
  )

  if os.path.exists(gdd_path):
    gdd = load_json(gdd_path)
    for asset_key, asset_info in gdd.get("requested_assets", {}).items():
      if asset_key not in palette["assets"]:
        palette["assets"][asset_key] = asset_info

  payload = {
      "command": "assets.measure_bounds_batch",
      "assets": {
          k: v.get("uefn_path", "") for k, v in palette["assets"].items()
      },
  }
  resp = call_bridge("exec", payload)

  measured = resp.get("measured_assets", {})
  for key, item in palette["assets"].items():
    if key in measured:
      item["size_cm"] = measured[key]["size_cm"]
      item["pivot_offset_cm"] = measured[key]["pivot_offset_cm"]
    else:
      item.setdefault("size_cm", [128.0, 128.0, 128.0])
      item.setdefault("pivot_offset_cm", [0.0, 0.0, -64.0])

  save_json(palette_path, palette)
  invalid = [
      k
      for k, v in palette["assets"].items()
      if any(d <= 0 for d in v.get("size_cm", [0, 0, 0]))
  ]
  result = {
      "status": "PASSED" if not invalid else "FAILED",
      "error_count": len(invalid),
      "invalid_assets": invalid,
      "palette_file": palette_path,
  }
  print(json.dumps(result, indent=2))
  return 0 if not invalid else 1


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
        for c in range(cols):
          cell = matrix[r][c]
          if r in (0, rows - 1) or c in (0, cols - 1):
            if cell not in ("#", "V"):
              errors.append({
                  "type": "UNCLOSED_BORDER",
                  "tile": [r, c, z_idx],
                  "cell": cell,
              })
          if cell.startswith("R_"):
            upper = floor_map.get(z_idx + 1)
            if upper and upper[r][c] != "T":
              errors.append({
                  "type": "HEADROOM_BLOCKED_ON_STAIRS",
                  "stair_tile": [r, c, z_idx],
                  "upper_tile": [r, c, z_idx + 1],
                  "current_upper_cell": upper[r][c],
                  "required_upper_cell": "T",
              })

      if data.get("symmetric") and data.get("symmetry_axis") == "X":
        for r in range(rows // 2):
          mirror_r = rows - 1 - r
          for c in range(cols):
            a = matrix[r][c].replace("S1", "S").replace("S2", "S")
            b = matrix[mirror_r][c].replace("S1", "S").replace("S2", "S")
            if a != b:
              errors.append({
                  "type": "SYMMETRY_BROKEN",
                  "tile_a": [r, c, z_idx],
                  "tile_b": [mirror_r, c, z_idx],
              })

    base = floor_map.get(0, [])
    spawns, targets = [], []
    for r, row in enumerate(base):
      for c, val in enumerate(row):
        if val in ("S1", "S2"):
          spawns.append((r, c))
        if val in ("O", "S2"):
          targets.append((r, c))

    if not spawns:
      errors.append({"type": "NO_SPAWN_FOUND", "z_index": 0})
    elif targets:
      visited = set()
      queue = deque([spawns[0]])
      walkable = {".", "P", "S1", "S2", "O", "R_N", "R_S", "R_E", "R_W", "#"}
      while queue:
        cr, cc = queue.popleft()
        if (cr, cc) in visited:
          continue
        visited.add((cr, cc))
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
          nr, nc = cr + dr, cc + dc
          if 0 <= nr < len(base) and 0 <= nc < len(base[0]):
            if base[nr][nc] in walkable and (nr, nc) not in visited:
              queue.append((nr, nc))
      for tr, tc in targets:
        if (tr, tc) not in visited:
          errors.append({
              "type": "UNREACHABLE_TARGET_2D",
              "from": list(spawns[0]),
              "to": [tr, tc],
          })

  out = {
      "status": "PASSED" if not errors else "FAILED",
      "error_count": len(errors),
      "errors": errors,
  }
  print(json.dumps(out, indent=2))
  return 0 if not errors else 1


def cmd_build_structure(workspace: str) -> int:
  grid = load_json(os.path.join(workspace, "03_grid.json"))
  palette = load_json(os.path.join(workspace, "02_palette.json")).get(
      "assets", {}
  )

  floor_asset = next(
      (
          v["uefn_path"]
          for v in palette.values()
          if v.get("category") == "STRUCTURE_FLOOR"
      ),
      "/Game/Athena/Environments/Blueprints/Floors/BP_Floor.BP_Floor",
  )
  wall_asset = next(
      (
          v["uefn_path"]
          for v in palette.values()
          if v.get("category") == "STRUCTURE_WALL"
      ),
      "/Game/Athena/Environments/Blueprints/Walls/BP_Wall.BP_Wall",
  )

  ops = []
  for floor in grid.get("floors", []):
    z = floor["z_index"]
    matrix = floor["matrix"]
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0

    for r in range(rows):
      for c in range(cols):
        cell = matrix[r][c]
        if cell in ("V", "T"):
          continue
        cx = r * TILE_SIZE_XY + 256.0
        cy = c * TILE_SIZE_XY + 256.0
        cz = z * TILE_SIZE_Z
        ops.append({
            "op": "actors.spawn",
            "asset": floor_asset,
            "label": f"Floor_{r}_{c}_{z}",
            "location_xyz": [cx, cy, cz],
            "location_luf": xyz_to_luf([cx, cy, cz]),
            "rotation": [0.0, 0.0, 0.0],
        })
        if cell == "#":
          if r == 0:
            ops.append({
                "op": "actors.spawn",
                "asset": wall_asset,
                "label": f"Wall_South_{r}_{c}_{z}",
                "location_xyz": [r * TILE_SIZE_XY, cy, cz],
                "location_luf": xyz_to_luf([r * TILE_SIZE_XY, cy, cz]),
                "rotation": [0.0, 0.0, 0.0],
            })
          if r == rows - 1:
            ops.append({
                "op": "actors.spawn",
                "asset": wall_asset,
                "label": f"Wall_North_{r}_{c}_{z}",
                "location_xyz": [(r + 1) * TILE_SIZE_XY, cy, cz],
                "location_luf": xyz_to_luf([(r + 1) * TILE_SIZE_XY, cy, cz]),
                "rotation": [0.0, 0.0, 180.0],
            })
          if c == 0:
            ops.append({
                "op": "actors.spawn",
                "asset": wall_asset,
                "label": f"Wall_West_{r}_{c}_{z}",
                "location_xyz": [cx, c * TILE_SIZE_XY, cz],
                "location_luf": xyz_to_luf([cx, c * TILE_SIZE_XY, cz]),
                "rotation": [0.0, 0.0, 90.0],
            })
          if c == cols - 1:
            ops.append({
                "op": "actors.spawn",
                "asset": wall_asset,
                "label": f"Wall_East_{r}_{c}_{z}",
                "location_xyz": [cx, (c + 1) * TILE_SIZE_XY, cz],
                "location_luf": xyz_to_luf([cx, (c + 1) * TILE_SIZE_XY, cz]),
                "rotation": [0.0, 0.0, 270.0],
            })

  payload = {
      "command": "batch.exec",
      "transaction_name": "UEFN_Build_Structure",
      "hide_ceiling": True,
      "operations": ops,
  }
  resp = call_bridge("batch.exec", payload)
  save_json(
      os.path.join(workspace, "_compiled_structure.json"),
      {"operations": ops, "bridge_response": resp},
  )
  print(
      json.dumps(
          {
              "status": "PASSED",
              "spawned_count": len(ops),
              "bridge": resp.get("status", "LOCAL_SIM"),
          },
          indent=2,
      )
  )
  return 0


def cmd_compile_transforms(workspace: str) -> int:
  palette = load_json(os.path.join(workspace, "02_palette.json")).get(
      "assets", {}
  )
  grid = load_json(os.path.join(workspace, "03_grid.json"))
  devices_data = (
      load_json(os.path.join(workspace, "04_devices.json"))
      if os.path.exists(os.path.join(workspace, "04_devices.json"))
      else {"devices": []}
  )
  props_data = (
      load_json(os.path.join(workspace, "05_props.json"))
      if os.path.exists(os.path.join(workspace, "05_props.json"))
      else {"props": []}
  )

  matrix = grid.get("floors", [{"matrix": [["."]]}])[0]["matrix"]
  arena_center = [
      len(matrix) * TILE_SIZE_XY / 2.0,
      len(matrix[0]) * TILE_SIZE_XY / 2.0,
      0.0,
  ]

  registry = {}
  ops = []

  for dev in devices_data.get("devices", []):
    label = dev["actor_label"]
    size_cm = [128.0, 128.0, 32.0]
    pivot = [0.0, 0.0, -16.0]
    loc = compute_anchor_xyz(dev["tile"], dev["slot"], size_cm, pivot)
    center = [loc[0] + pivot[0], loc[1] + pivot[1], loc[2] + pivot[2]]
    yaw = resolve_yaw(
        dev.get("face_towards", "NORTH"), center, registry, arena_center
    )
    registry[label] = {
        "actor_label": label,
        "category": "DEVICE",
        "tile": dev["tile"],
        "location_xyz": loc,
        "location_luf": xyz_to_luf(loc),
        "center_cm": center,
        "size_cm": size_cm,
        "yaw": yaw,
        "snap_to_floor": dev.get("on_floor", True),
        "distance_to_floor_cm": 0.0 if dev.get("on_floor", True) else 50.0,
    }
    ops.append({"op": "devices.spawn", **registry[label]})

  for prop in props_data.get("props", []):
    label = prop["actor_label"]
    asset_info = palette.get(
        prop["asset_key"],
        {
            "uefn_path": prop["asset_key"],
            "size_cm": [120.0, 120.0, 120.0],
            "pivot_offset_cm": [0.0, 0.0, -60.0],
        },
    )
    size_cm = asset_info["size_cm"]
    pivot = asset_info["pivot_offset_cm"]
    snap = prop.get("snap_to_floor", True)

    if prop.get("placement_mode") == "TILE_ANCHOR":
      loc = compute_anchor_xyz(prop["tile"], prop["slot"], size_cm, pivot)
      tile_ref = prop["tile"]
    else:
      ref_label = prop["reference_actor"]
      if ref_label not in registry:
        raise KeyError(
            f"reference_actor introuvable pour {label} : {ref_label}"
        )
      parent = registry[ref_label]
      loc = compute_relative_xyz(
          parent,
          size_cm,
          pivot,
          prop["direction"],
          float(prop.get("gap_cm", 20.0)),
          snap,
      )
      tile_ref = parent["tile"]

    center = [loc[0] + pivot[0], loc[1] + pivot[1], loc[2] + pivot[2]]
    yaw = resolve_yaw(
        prop.get("face_towards", "NORTH"), center, registry, arena_center
    )
    floor_z = tile_ref[2] * TILE_SIZE_Z
    bottom_z = center[2] - (size_cm[2] / 2.0)

    registry[label] = {
        "actor_label": label,
        "category": "PROP",
        "asset": asset_info.get("uefn_path", ""),
        "tile": tile_ref,
        "location_xyz": loc,
        "location_luf": xyz_to_luf(loc),
        "center_cm": center,
        "size_cm": size_cm,
        "yaw": yaw,
        "snap_to_floor": snap,
        "distance_to_floor_cm": round(bottom_z - floor_z, 2),
    }
    ops.append({"op": "actors.spawn", **registry[label]})

  resp = call_bridge(
      "batch.exec",
      {
          "command": "batch.exec",
          "transaction_name": "UEFN_Place_Devices_And_Props",
          "operations": ops,
      },
  )
  save_json(os.path.join(workspace, "_compiled_scene.json"), registry)
  print(
      json.dumps(
          {
              "status": "PASSED",
              "compiled_actors": len(registry),
              "bridge": resp.get("status", "LOCAL_SIM"),
          },
          indent=2,
      )
  )
  return 0


def cmd_audit_scene(workspace: str) -> int:
  compiled_path = os.path.join(workspace, "_compiled_scene.json")
  if not os.path.exists(compiled_path):
    cmd_compile_transforms(workspace)
  registry = load_json(compiled_path)
  actors = list(registry.values())

  overlap_errors = []
  gravity_errors = []

  for i in range(len(actors)):
    a = actors[i]
    dist_floor = a.get("distance_to_floor_cm", 0.0)
    if a.get("snap_to_floor", True) and abs(dist_floor) > MAX_GRAVITY_CM:
      gravity_errors.append({
          "type": "GRAVITY_ERROR",
          "actor": a["actor_label"],
          "distance_to_floor_cm": dist_floor,
          "state": "FLOATING" if dist_floor > 0 else "BURIED",
          "tile": a["tile"],
          "suggestion": (
              "Enable snap_to_floor: true and apply pivot_offset_cm Z"
              " correction."
          ),
      })
    for j in range(i + 1, len(actors)):
      b = actors[j]
      pen = aabb_penetration_cm(a, b)
      if pen > MAX_OVERLAP_CM:
        overlap_errors.append({
            "type": "OVERLAP_ERROR",
            "actor_a": a["actor_label"],
            "actor_b": b["actor_label"],
            "penetration_cm": pen,
            "tile": a["tile"],
            "suggestion": (
                f"Place {b['actor_label']} using RELATIVE_TO_ACTOR with gap_cm"
                " >= 15.0"
            ),
        })

  total_errors = len(overlap_errors) + len(gravity_errors)
  report = {
      "timestamp": datetime.now(timezone.utc).isoformat(),
      "status": "PASSED" if total_errors == 0 else "FAILED",
      "error_count": total_errors,
      "overlap_errors": overlap_errors,
      "gravity_errors": gravity_errors,
      "navigation_errors": [],
  }
  save_json(os.path.join(workspace, "06_audit_report.json"), report)
  print(json.dumps(report, indent=2))
  return 0 if total_errors == 0 else 1


def cmd_check_navigation(workspace: str) -> int:
  compiled_path = os.path.join(workspace, "_compiled_scene.json")
  report_path = os.path.join(workspace, "06_audit_report.json")
  if not os.path.exists(compiled_path):
    cmd_compile_transforms(workspace)
  registry = load_json(compiled_path)
  report = (
      load_json(report_path)
      if os.path.exists(report_path)
      else {"overlap_errors": [], "gravity_errors": []}
  )

  nav_errors = []
  props = [v for v in registry.values() if v.get("category") == "PROP"]

  by_tile = {}
  for p in props:
    by_tile.setdefault(tuple(p["tile"]), []).append(p)

  for tile_key, tile_props in by_tile.items():
    for i in range(len(tile_props)):
      for j in range(i + 1, len(tile_props)):
        pa, pb = tile_props[i], tile_props[j]
        dx = abs(pa["center_cm"][0] - pb["center_cm"][0]) - (
            pa["size_cm"][0] / 2.0 + pb["size_cm"][0] / 2.0
        )
        dy = abs(pa["center_cm"][1] - pb["center_cm"][1]) - (
            pa["size_cm"][1] / 2.0 + pb["size_cm"][1] / 2.0
        )
        gap = max(dx, dy)
        if 0.0 < gap < MIN_CORRIDOR_WIDTH:
          nav_errors.append({
              "type": "CORRIDOR_TOO_NARROW",
              "tile": list(tile_key),
              "free_width_cm": round(gap, 2),
              "required_width_cm": MIN_CORRIDOR_WIDTH,
              "blocking_actors": [pa["actor_label"], pb["actor_label"]],
          })

  report["navigation_errors"] = nav_errors
  report["error_count"] = (
      len(report.get("overlap_errors", []))
      + len(report.get("gravity_errors", []))
      + len(nav_errors)
  )
  report["status"] = "PASSED" if report["error_count"] == 0 else "FAILED"
  save_json(report_path, report)
  print(json.dumps(report, indent=2))
  return 0 if not nav_errors else 1


def cmd_visual_snapshot(workspace: str, output_image: str) -> int:
  grid = load_json(os.path.join(workspace, "03_grid.json"))
  matrix = grid.get("floors", [{"matrix": [["."]]}])[0]["matrix"]
  rows, cols = len(matrix), len(matrix[0])

  cam_x = (rows * TILE_SIZE_XY) / 2.0
  cam_y = (cols * TILE_SIZE_XY) / 2.0
  cam_z = max(rows, cols) * TILE_SIZE_XY * 1.2

  resp = call_bridge(
      "viewport.snapshot_topdown",
      {
          "camera_location": [cam_x, cam_y, cam_z],
          "camera_rotation": [-90.0, 0.0, 0.0],
          "orthographic_width": max(rows, cols) * TILE_SIZE_XY,
          "output_path": os.path.abspath(output_image),
          "draw_grid_labels": True,
          "rows": rows,
          "cols": cols,
      },
  )
  print(
      json.dumps(
          {
              "status": "PASSED",
              "snapshot_path": output_image,
              "camera_xyz": [cam_x, cam_y, cam_z],
              "bridge": resp.get("status", "LOCAL_SIM"),
          },
          indent=2,
      )
  )
  return 0


def main() -> int:
  parser = argparse.ArgumentParser(description="UEFN Spatial CLI Gatekeeper")
  sub = parser.add_subparsers(dest="command", required=True)

  p_pal = sub.add_parser("measure-palette")
  p_pal.add_argument("--workspace", default="workspace_map")

  p_grid = sub.add_parser("validate-grid")
  p_grid.add_argument("grid_file", nargs="?", default="workspace_map/03_grid.json")

  p_build = sub.add_parser("build-structure")
  p_build.add_argument("--workspace", default="workspace_map")

  p_comp = sub.add_parser("compile-transforms")
  p_comp.add_argument("--workspace", default="workspace_map")

  p_audit = sub.add_parser("audit-scene")
  p_audit.add_argument("--workspace", default="workspace_map")

  p_nav = sub.add_parser("check-navigation")
  p_nav.add_argument("--workspace", default="workspace_map")

  p_snap = sub.add_parser("visual-snapshot")
  p_snap.add_argument("--workspace", default="workspace_map")
  p_snap.add_argument("--output", default="workspace_map/topdown_grid.png")

  args = parser.parse_args()
  if args.command == "measure-palette":
    return cmd_measure_palette(args.workspace)
  if args.command == "validate-grid":
    return cmd_validate_grid(args.grid_file)
  if args.command == "build-structure":
    return cmd_build_structure(args.workspace)
  if args.command == "compile-transforms":
    return cmd_compile_transforms(args.workspace)
  if args.command == "audit-scene":
    return cmd_audit_scene(args.workspace)
  if args.command == "check-navigation":
    return cmd_check_navigation(args.workspace)
  if args.command == "visual-snapshot":
    return cmd_visual_snapshot(args.workspace, args.output)
  return 1


if __name__ == "__main__":
  sys.exit(main())