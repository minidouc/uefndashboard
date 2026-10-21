#!/usr/bin/env python3
"""Schema des fichiers de `workspace_map/` : cles autorisees, types, enums.

Pourquoi ce module existe : avant lui, un `placement_mode` mal orthographie tombait dans la
branche `RELATIVE_TO_ACTOR` sans erreur, et toute cle inconnue etait ignoree. Le calcul
produisait alors un transform faux mais `PASSED`.
"""

SLOTS = ["CENTER", "NORTH_EDGE", "SOUTH_EDGE", "EAST_EDGE", "WEST_EDGE",
         "CORNER_NE", "CORNER_NW", "CORNER_SE", "CORNER_SW"]
CARDINALS = ["NORTH", "EAST", "SOUTH", "WEST", "CENTER"]
DIRECTIONS = ["IN_FRONT_OF", "BEHIND", "LEFT_OF", "RIGHT_OF", "ON_TOP_OF"]
PLACEMENT_MODES = ["TILE_ANCHOR", "RELATIVE_TO_ACTOR"]
# Un device non spatial (granter, score, end_game...) vit sur la plateforme Zone_Logic,
# hors de la grille : `WORLD` le place en coordonnees absolues au lieu d'une tuile.
DEVICE_PLACEMENT_MODES = ["TILE_ANCHOR", "WORLD"]
GRID_CELLS = ["#", ".", "W", "P", "S1", "S2", "O", "R_N", "R_S", "R_E", "R_W", "T", "V"]
AXES = ["X", "Y"]

# cle -> (obligatoire, type, enum ou None)
DEVICE_KEYS = {
    "actor_label": (True, "str", None),
    "asset_key": (True, "str", None),
    "placement_mode": (False, "str", DEVICE_PLACEMENT_MODES),
    "tile": (False, "int3", None),
    "slot": (False, "str", SLOTS),
    "world_location_cm": (False, "float3", None),
    "zone": (False, "str", None),
    "device_class": (False, "str", None),
    "face_towards": (False, "str", None),
    "on_floor": (False, "bool", None),
    "properties": (False, "dict", None),
    "bindings": (False, "list", None),
}
PROP_KEYS = {
    "actor_label": (True, "str", None),
    "asset_key": (True, "str", None),
    "placement_mode": (True, "str", PLACEMENT_MODES),
    "tile": (False, "int3", None),
    "slot": (False, "str", SLOTS),
    "reference_actor": (False, "str", None),
    "direction": (False, "str", DIRECTIONS),
    "gap_cm": (False, "num", None),
    "face_towards": (False, "str", None),
    "snap_to_floor": (False, "bool", None),
}
ASSET_KEYS = {
    # uefn_path reste optionnel ici : un gabarit neuf contient des chemins a trouver a l'etape 2.
    # C'est `measure-palette` qui refuse un asset sans chemin, pas le controle de forme.
    "uefn_path": (False, "str", None),
    "category": (True, "str", None),
    "size_cm": (False, "float3", None),
    "pivot_offset_cm": (False, "float3", None),
    "measured": (False, "any", None),
    "scale": (False, "scale", None),
    "path_status": (False, "str", None),
    "notes": (False, "str", None),
}
GRID_KEYS = {
    "floors": (True, "list", None),
    "tile_size_cm": (False, "float3", None),
    "symmetric": (False, "bool", None),
    "symmetry_axis": (False, "str", AXES),
    "origin_tile": (False, "int3", None),
    "edge_policy": (False, "str", None),
}
GDD_KEYS = {
    "project_name": (False, "str", None),
    "game_mode": (False, "str", None),
    "scale_category": (False, "str", None),
    "grid_dimensions_tiles": (False, "int3", None),
    "zones": (False, "list", None),
    "connects_to": (False, "list", None),
    "status": (False, "str", None),
    "gameplay_timeline_sec": (False, "list", None),
    "required_devices": (False, "list", None),
    "requested_assets": (False, "dict", None),
    "verse_modules": (False, "list", None),
    "simulation": (False, "any", None),
    "notes": (False, "str", None),
}

TYPES = {
    "str": str,
    "bool": bool,
    "int": int,
    "num": (int, float),
    "dict": dict,
    "list": list,
    "any": object,
}


def _type_ok(value, kind: str) -> bool:
  if kind in ("int3", "float3"):
    if not isinstance(value, list) or len(value) != 3:
      return False
    want = int if kind == "int3" else (int, float)
    return all(isinstance(v, want) and not isinstance(v, bool) for v in value)
  if kind == "num":
    return isinstance(value, (int, float)) and not isinstance(value, bool)
  if kind == "scale":
    # facteur uniforme (5.12) ou par axe ([5.12, 5.12, 0.32]) : les deux sont acceptes
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            or _type_ok(value, "float3"))
  if kind == "bool":
    return isinstance(value, bool)
  if kind == "int":
    return isinstance(value, int) and not isinstance(value, bool)
  return isinstance(value, TYPES[kind])


def _check_keys(errors: list, where: str, data: dict, schema: dict,
                conditional: dict | None = None) -> None:
  if not isinstance(data, dict):
    errors.append({"type": "BAD_TYPE", "where": where, "expected": "objet",
                   "found": type(data).__name__})
    return
  for key, value in data.items():
    if key.startswith("_"):
      continue  # cle de commentaire libre (`_comment`, `_notes`) : jamais consommee
    if key not in schema:
      errors.append({"type": "UNKNOWN_KEY", "where": where, "key": key,
                     "allowed": sorted(schema)})
      continue
    required, kind, enum = schema[key]
    if value is None:
      if required:
        errors.append({"type": "MISSING_KEY", "where": where, "key": key,
                       "detail": "valeur null alors que la cle est obligatoire"})
      continue
    if not _type_ok(value, kind):
      errors.append({"type": "BAD_TYPE", "where": where, "key": key,
                     "expected": kind, "found": json_type(value)})
      continue
    if enum and value not in enum:
      errors.append({"type": "BAD_ENUM", "where": where, "key": key, "value": value,
                     "allowed": enum})
  for key, (required, _, _) in schema.items():
    if required and key not in data:
      errors.append({"type": "MISSING_KEY", "where": where, "key": key})
  if conditional:
    branch = conditional["on"]
    mode = data.get(branch)
    for value, keys in conditional["cases"].items():
      if mode == value:
        for key in keys:
          if data.get(key) in (None, ""):
            errors.append({"type": "CONDITIONAL_MISSING", "where": where, "key": key,
                           "required_by": f"{branch}={value}"})


def json_type(value) -> str:
  return {dict: "objet", list: "liste", bool: "bool", str: "chaine"}.get(
      type(value), type(value).__name__)


def validate_devices(data) -> list:
  errors = []
  if not isinstance(data, dict) or not isinstance(data.get("devices"), list):
    return [{"type": "MISSING_KEY", "where": "04_devices.json", "key": "devices"}]
  labels = set()
  for i, dev in enumerate(data["devices"]):
    where = f"04_devices.json devices[{i}]"
    _check_keys(errors, where, dev, DEVICE_KEYS)
    if not isinstance(dev, dict):
      continue
    mode = dev.get("placement_mode", "TILE_ANCHOR")
    wanted = ["tile", "slot"] if mode == "TILE_ANCHOR" else ["world_location_cm"]
    for key in wanted:
      if dev.get(key) in (None, ""):
        errors.append({"type": "CONDITIONAL_MISSING", "where": where, "key": key,
                       "required_by": f"placement_mode={mode}"})
    label = dev.get("actor_label")
    if label:
      if label in labels:
        errors.append({"type": "DUPLICATE_LABEL", "where": where, "actor_label": label})
      labels.add(label)
    bindings = dev.get("bindings")
    if isinstance(bindings, list):
      for j, b in enumerate(bindings):
        _check_keys(errors, f"{where} bindings[{j}]", b,
                    {"event": (True, "str", None), "to": (True, "str", None),
                     "function": (True, "str", None)})
  return errors


def validate_props(data) -> list:
  errors = []
  if not isinstance(data, dict) or not isinstance(data.get("props"), list):
    return [{"type": "MISSING_KEY", "where": "05_props.json", "key": "props"}]
  labels = set()
  for i, prop in enumerate(data["props"]):
    where = f"05_props.json props[{i}]"
    _check_keys(errors, where, prop, PROP_KEYS, conditional={
        "on": "placement_mode",
        "cases": {"TILE_ANCHOR": ["tile", "slot"],
                  "RELATIVE_TO_ACTOR": ["reference_actor", "direction"]}})
    if not isinstance(prop, dict):
      continue
    label = prop.get("actor_label")
    if label:
      if label in labels:
        errors.append({"type": "DUPLICATE_LABEL", "where": where, "actor_label": label})
      labels.add(label)
  return errors


def validate_palette(data) -> list:
  errors = []
  if not isinstance(data, dict) or not isinstance(data.get("assets"), dict):
    return [{"type": "MISSING_KEY", "where": "02_palette.json", "key": "assets"}]
  for key, asset in data["assets"].items():
    if key.startswith("_"):
      continue
    where = f"02_palette.json assets[{key}]"
    _check_keys(errors, where, asset, ASSET_KEYS)
    if isinstance(asset, dict):
      scale = asset.get("scale", 1.0)
      values = scale if isinstance(scale, list) else [scale]
      if any(isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0 for v in values):
        errors.append({"type": "BAD_VALUE", "where": where, "key": "scale",
                       "detail": "chaque facteur d'echelle doit etre un nombre > 0"})
  return errors


def validate_grid(data) -> list:
  errors = []
  _check_keys(errors, "03_grid.json", data, GRID_KEYS)
  floors = data.get("floors") if isinstance(data, dict) else None
  if not isinstance(floors, list):
    return errors
  seen = set()
  for i, floor in enumerate(floors):
    where = f"03_grid.json floors[{i}]"
    _check_keys(errors, where, floor, {"z_index": (True, "int", None),
                                       "matrix": (True, "list", None)})
    if isinstance(floor, dict) and floor.get("z_index") in seen:
      errors.append({"type": "DUPLICATE_Z_INDEX", "where": where,
                     "z_index": floor["z_index"]})
    seen.add(floor.get("z_index") if isinstance(floor, dict) else None)
    matrix = floor.get("matrix") if isinstance(floor, dict) else None
    if not isinstance(matrix, list):
      continue
    for r, row in enumerate(matrix):
      if not isinstance(row, list):
        errors.append({"type": "BAD_TYPE", "where": f"{where} matrix[{r}]",
                       "expected": "liste", "found": json_type(row)})
        continue
      for c, cell in enumerate(row):
        if cell not in GRID_CELLS:
          errors.append({"type": "BAD_CELL", "where": f"{where} matrix[{r}][{c}]",
                         "value": cell, "allowed": GRID_CELLS})
  return errors


def validate_gdd(data) -> tuple[list, list]:
  """Le GDD est un document de conception : une cle inconnue est un avertissement, pas un blocage."""
  errors, warnings = [], []
  if not isinstance(data, dict):
    return [{"type": "BAD_TYPE", "where": "01_gdd.json", "expected": "objet",
             "found": json_type(data)}], warnings
  for key, value in data.items():
    if key.startswith("_"):
      continue
    if key not in GDD_KEYS:
      warnings.append({"type": "UNKNOWN_KEY", "where": "01_gdd.json", "key": key,
                       "detail": "cle hors schema : ignoree par le CLI"})
      continue
    _, kind, _ = GDD_KEYS[key]
    if value is not None and not _type_ok(value, kind):
      errors.append({"type": "BAD_TYPE", "where": "01_gdd.json", "key": key,
                     "expected": kind, "found": json_type(value)})
  requested = data.get("requested_assets")
  if isinstance(requested, dict):
    for key, asset in requested.items():
      _check_keys(errors, f"01_gdd.json requested_assets[{key}]", asset, ASSET_KEYS)
  return errors, warnings


CHECKS = {
    "01_gdd.json": ("gdd", validate_gdd),
    "02_palette.json": ("palette", validate_palette),
    "03_grid.json": ("grid", validate_grid),
    "04_devices.json": ("devices", validate_devices),
    "05_props.json": ("props", validate_props),
}
