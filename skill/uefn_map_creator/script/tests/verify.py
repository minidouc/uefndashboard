#!/usr/bin/env python3
"""Verification hors ligne du skill : `python script/tests/verify.py`.

Aucun editeur UEFN n'est requis : `mock_mcp.py` repond aux appels du CLI.

Ce qui est verifie ici, ce sont les CONTRATS du skill — codes retour, statuts, refus sans
accord, rapports qui disent ce qu'ils n'ont pas verifie. Un PASSED obtenu contre le mock ne
prouve RIEN sur l'editeur reel : il prouve que le CLI tient ses propres regles.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
CLI = os.path.join(SKILL, "script", "uefn_spatial_cli.py")
CLIENT = os.path.join(SKILL, "script", "mcp_client.py")
MOCK = os.path.join(HERE, "mock_mcp.py")
ROOT = os.path.join(tempfile.gettempdir(), "uefn_skill_verify")
shutil.rmtree(ROOT, ignore_errors=True)

results = []


# --------------------------------------------------------------------- utilitaires

def run(args, env=None, cwd=None):
  e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
  if env:
    e.update(env)
  p = subprocess.run([sys.executable] + args, capture_output=True, text=True,
                     encoding="utf-8", errors="replace", env=e, cwd=cwd or HERE)
  return p.returncode, p.stdout, p.stderr


def cli(args, ws, env=None):
  """Lance une commande du CLI, renvoie (rc, dict ou None, sortie brute)."""
  rc, out, err = run([CLI, *args, "--workspace", ws], env=env)
  try:
    return rc, json.loads(out), out
  except ValueError:
    return rc, None, out + err


def check(name, cond, detail=""):
  results.append((name, bool(cond), detail))
  print(("  OK   " if cond else "  ECHEC") + f" {name}"
        + (f"  <- {detail}" if detail and not cond else ""))


def types(payload, key="errors"):
  return [e.get("type") or e.get("error_kind") for e in (payload or {}).get(key, [])]


def write(path, data):
  os.makedirs(os.path.dirname(path), exist_ok=True)
  with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=1, ensure_ascii=False)
  return path


def free_port():
  s = socket.socket()
  s.bind(("127.0.0.1", 0))
  port = s.getsockname()[1]
  s.close()
  return port


class Mock:
  """Serveur MCP de test. `state()` change le scenario sans relancer le serveur."""

  def __init__(self, mode="ok"):
    self.port = free_port()
    self.mode = mode
    self.state_file = os.path.join(ROOT, f"mock_state_{self.port}.json")
    self.url = f"http://127.0.0.1:{self.port}/mcp"
    os.makedirs(ROOT, exist_ok=True)
    write(self.state_file, {})
    self.proc = subprocess.Popen(
        [sys.executable, MOCK, str(self.port), mode],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=dict(os.environ, MOCK_STATE=self.state_file, PYTHONDONTWRITEBYTECODE="1"))
    for _ in range(50):
      try:
        socket.create_connection(("127.0.0.1", self.port), 0.2).close()
        return
      except OSError:
        time.sleep(0.1)
    raise RuntimeError(f"mock {mode} introuvable sur le port {self.port}")

  def state(self, **kw):
    data = json.load(open(self.state_file, encoding="utf-8")) if os.path.exists(
        self.state_file) else {}
    data.update(kw)
    write(self.state_file, data)

  def env(self, extra=None):
    e = {"UEFN_MCP_URL": self.url, "UEFN_MCP_TIMEOUT": "10"}
    if extra:
      e.update(extra)
    return e

  def stop(self):
    self.proc.terminate()
    try:
      self.proc.wait(3)
    except subprocess.TimeoutExpired:
      self.proc.kill()


def grid(matrix, axis=None, symmetric=False, floors=None):
  return {"symmetric": symmetric, "symmetry_axis": axis,
          "floors": floors if floors else [{"z_index": 0, "matrix": matrix}]}


def validate_grid(g, name, want_status, want_type=None, ws=None):
  ws = ws or os.path.join(ROOT, "grid")
  os.makedirs(ws, exist_ok=True)
  path = write(os.path.join(ws, "03_grid.json"), g)
  rc, out, err = run([CLI, "validate-grid", path])
  try:
    d = json.loads(out)
  except ValueError:
    check(name, False, f"sortie non JSON rc={rc} err={err[:200]}")
    return None
  got = [e.get("type") for e in d.get("errors", [])]
  check(name, d["status"] == want_status and (want_type is None or want_type in got),
        f"rc={rc} status={d['status']} types={got}")
  return d


# =========================================================== A. validate-grid

print("== A. validate-grid : symetrie et bordures ==")
SYM_X = [["#", "#", "#", "#"], ["#", "S1", "S1", "#"], ["#", ".", ".", "#"],
         ["#", "O", "O", "#"], ["#", ".", ".", "#"], ["#", "S2", "S2", "#"],
         ["#", "#", "#", "#"]]
validate_grid(grid(SYM_X, "X", True), "A1 symetrie X correcte -> PASSED", "PASSED")
broken_x = [r[:] for r in SYM_X]
broken_x[2][1] = "W"
validate_grid(grid(broken_x, "X", True), "A2 symetrie X cassee -> SYMMETRY_BROKEN",
              "FAILED", "SYMMETRY_BROKEN")
SYM_Y = [["#", "#", "#", "#", "#"], ["#", "S1", ".", "S1", "#"], ["#", ".", "O", ".", "#"],
         ["#", ".", "O", ".", "#"], ["#", "S2", ".", "S2", "#"], ["#", "#", "#", "#", "#"]]
validate_grid(grid(SYM_Y, "Y", True), "A3 symetrie Y correcte -> PASSED", "PASSED")
broken_y = [r[:] for r in SYM_Y]
broken_y[2][1] = "W"
validate_grid(grid(broken_y, "Y", True),
              "A4 symetrie Y cassee -> SYMMETRY_BROKEN (avant : PASSED)",
              "FAILED", "SYMMETRY_BROKEN")
validate_grid(grid(broken_y, None, True),
              "A5 symmetric sans axe -> SYMMETRY_AXIS_UNSUPPORTED",
              "FAILED", "SYMMETRY_AXIS_UNSUPPORTED")
validate_grid(grid(broken_y, "XY", True), "A6 axe inconnu -> SYMMETRY_AXIS_UNSUPPORTED",
              "FAILED", "SYMMETRY_AXIS_UNSUPPORTED")
RAMPS = {"symmetric": True, "symmetry_axis": "X", "floors": [
    {"z_index": 0, "matrix": [["#", "#", "#"], ["#", "S1", "#"], ["#", "R_N", "#"],
                               ["#", "R_S", "#"], ["#", "S2", "#"], ["#", "#", "#"]]},
    {"z_index": 1, "matrix": [["#", "#", "#"], ["#", ".", "#"], ["#", "T", "#"],
                               ["#", "T", "#"], ["#", ".", "#"], ["#", "#", "#"]]}]}
validate_grid(RAMPS, "A7 miroir X : R_N/R_S symetriques -> PASSED", "PASSED")
same_ramp = json.loads(json.dumps(RAMPS))
same_ramp["floors"][0]["matrix"][3][1] = "R_N"
validate_grid(same_ramp, "A7b deux R_N face a face -> SYMMETRY_BROKEN",
              "FAILED", "SYMMETRY_BROKEN")
RAGGED = {"symmetric": True, "symmetry_axis": "X", "floors": [
    {"z_index": 0, "matrix": [["#", "#", "#"], ["#", "R_N", "#"], ["#", "#"]]},
    {"z_index": 1, "matrix": [["#", "#"], ["#", "."], ["#", "."]]}]}
ragged_path = write(os.path.join(ROOT, "grid", "03_grid.json"), RAGGED)
rc, out, err = run([CLI, "validate-grid", ragged_path])
check("A8 matrice irreguliere : pas de crash", "Traceback" not in err and rc in (0, 1),
      f"rc={rc} err={err[-200:]}")

# =========================================================== B. schemas (forme)

print("== B. schemas : une faute de forme ne doit plus passer ==")
WS_SHAPE = os.path.join(ROOT, "shape")
rc, d, _ = cli(["init", "--template", "blank"], WS_SHAPE)
check("B1 init blank -> PASSED", rc == 0 and d and d["status"] == "PASSED", str(d)[:160])
# Palette mesuree : sinon PALETTE_EMPTY se melange aux erreurs de forme teste ici.
write(os.path.join(WS_SHAPE, "02_palette.json"), {"assets": {
    "prop_cube": {"uefn_path": "/Engine/BasicShapes/Cube", "category": "PROP",
                  "scale": [1.2, 1.2, 1.2], "size_cm": [100.0, 100.0, 100.0],
                  "pivot_offset_cm": [0.0, 0.0, 0.0],
                  "measured": {"at": "2026-10-20T00:00:00+00:00", "kind": "actor"}}}})


def scene(devices=None, props=None, name="", want_status="FAILED", want_type=None):
  if devices is not None:
    write(os.path.join(WS_SHAPE, "04_devices.json"), {"devices": devices})
  if props is not None:
    write(os.path.join(WS_SHAPE, "05_props.json"), {"props": props})
  rc, d, raw = cli(["validate-scene"], WS_SHAPE)
  got = types(d)
  check(name, d is not None and d["status"] == want_status
        and (want_type is None or want_type in got),
        f"rc={rc} status={(d or {}).get('status')} types={got} raw={raw[:150]}")
  return d


DEV = {"actor_label": "D1", "asset_key": "prop_cube", "tile": [1, 1, 0], "slot": "CENTER"}
PROP = {"actor_label": "P1", "asset_key": "prop_cube", "placement_mode": "TILE_ANCHOR",
        "tile": [1, 2, 0], "slot": "CENTER"}
scene(props=[dict(PROP, placement_mode="TILE_ANCHORX")],
      name="B2 placement_mode inconnu -> BAD_ENUM", want_type="BAD_ENUM")
scene(props=[{k: v for k, v in PROP.items() if k != "slot"}],
      name="B3 TILE_ANCHOR sans slot -> CONDITIONAL_MISSING",
      want_type="CONDITIONAL_MISSING")
scene(props=[dict(PROP, placement_mode="RELATIVE_TO_ACTOR")],
      name="B4 RELATIVE sans reference -> CONDITIONAL_MISSING",
      want_type="CONDITIONAL_MISSING")
scene(props=[dict(PROP, slot="MIDDLE")], name="B5 slot inconnu -> BAD_ENUM",
      want_type="BAD_ENUM")
scene(props=[dict(PROP, gap_cm=120.0)], name="B6 cle toleree (gap_cm) -> PASSED",
      want_status="PASSED")
scene(props=[dict(PROP, tile=[9, 9, 0])], name="B7 tuile hors grille -> TILE_OUT_OF_GRID",
      want_type="TILE_OUT_OF_GRID")
scene(props=[PROP, dict(PROP)], name="B8 label en double -> DUPLICATE_LABEL",
      want_type="DUPLICATE_LABEL")
scene(props=[dict(PROP, placement_modee="TILE_ANCHOR")],
      name="B9 cle inconnue -> UNKNOWN_KEY", want_type="UNKNOWN_KEY")
write(os.path.join(WS_SHAPE, "05_props.json"), {"props": [PROP]})
scene(devices=[dict(DEV, placement_mode="WORLD")],
      name="B10 device WORLD sans coordonnees -> CONDITIONAL_MISSING",
      want_type="CONDITIONAL_MISSING")
scene(devices=[dict(DEV, placement_mode="WORLD", world_location_cm=[-5888.0, 1280.0, -2304.0],
                    zone="Zone_Logic")],
      name="B11 device WORLD complet -> PASSED", want_status="PASSED")
scene(devices=[dict(DEV, bindings=[{"event": "OnTriggered", "to": "D1"}])],
      name="B12 binding sans function -> MISSING_KEY", want_type="MISSING_KEY")
write(os.path.join(WS_SHAPE, "04_devices.json"), {"devices": [DEV]})
write(os.path.join(WS_SHAPE, "05_props.json"), {"props": ["pas un objet"]})
rc, d, raw = cli(["validate-scene"], WS_SHAPE)
check("B13 entree non-objet : pas de crash", "Traceback" not in raw and rc in (0, 1),
      f"rc={rc} raw={raw[-200:]}")
write(os.path.join(WS_SHAPE, "03_grid.json"),
      grid([["#", "#", "#"], ["#", "X", "#"], ["#", "#", "#"]]))
rc, d, _ = cli(["validate-scene"], WS_SHAPE)
check("B14 cellule inconnue -> BAD_CELL", d and "BAD_CELL" in types(d), str(types(d)))

# =========================================================== C. init / gabarits

print("== C. init, gabarits et workspace ==")
rc, out, _ = run([CLI, "init", "--list"])
tpl = json.loads(out) if out.strip().startswith("{") else {}
check("C1 init --list donne les 3 gabarits",
      set(tpl.get("templates", [])) >= {"blank", "1v1_arena", "boxfight"}, out[:160])
rc, d, _ = cli(["init", "--template", "inexistant"], os.path.join(ROOT, "c_unk"))
check("C2 gabarit inconnu -> TEMPLATE_UNKNOWN rc=1",
      rc == 1 and (d or {}).get("error_kind") == "TEMPLATE_UNKNOWN", str(d)[:160])
rc, d, _ = cli(["init", "--template", "blank"], WS_SHAPE)
check("C3 workspace non vide sans --force -> WORKSPACE_NOT_EMPTY rc=1",
      rc == 1 and (d or {}).get("error_kind") == "WORKSPACE_NOT_EMPTY", str(d)[:160])
rc, d, _ = cli(["init", "--template", "blank", "--force"], WS_SHAPE)
check("C4 --force recopie le gabarit -> PASSED", rc == 0 and d and d["status"] == "PASSED",
      str(d)[:160])
inside = os.path.join(SKILL, "workspace_map_test")
rc, d, _ = cli(["validate-scene"], inside)
check("C5 workspace DANS le skill -> WORKSPACE_INSIDE_SKILL rc=1",
      rc == 1 and (d or {}).get("error_kind") == "WORKSPACE_INSIDE_SKILL", str(d)[:160])
for t in ("blank", "1v1_arena", "boxfight"):
  ws = os.path.join(ROOT, "fresh", t)
  shutil.rmtree(ws, ignore_errors=True)
  rc, d, _ = cli(["init", "--template", t], ws)
  rc2, d2, _ = cli(["validate-grid"], ws)
  rc3, d3, _ = cli(["validate-scene"], ws)
  check(f"C6.{t} gabarit neuf : grid PASSED et scene -> une seule erreur PALETTE_EMPTY",
        rc == 0 and d2 and d2["status"] == "PASSED" and d3
        and d3["status"] == "FAILED" and types(d3) == ["PALETTE_EMPTY"],
        f"grid={(d2 or {}).get('status')} scene={types(d3)}")

# =========================================================== D. codes retour

print("== D. codes retour MCP (0/1/2/3) ==")
m_err = Mock("error")
rc, d, _ = cli(["preflight"], os.path.join(ROOT, "codes"), m_err.env())
check("D1 erreur d'outil -> rc 1 TOOL_ERROR (avant : 2 = « rien execute »)",
      rc == 1 and (d or {}).get("error_kind") == "TOOL_ERROR" and "next" in (d or {}),
      f"rc={rc} d={str(d)[:160]}")
m_err.stop()
m_slow = Mock("slow")
rc, d, _ = cli(["preflight"], os.path.join(ROOT, "codes"),
               m_slow.env({"UEFN_MCP_TIMEOUT": "1"}))
check("D2 timeout -> rc 3 TIMEOUT_OUTCOME_UNKNOWN",
      rc == 3 and (d or {}).get("error_kind") == "TIMEOUT_OUTCOME_UNKNOWN",
      f"rc={rc} d={str(d)[:160]}")
m_slow.stop()
rc, d, _ = cli(["preflight"], os.path.join(ROOT, "codes"),
               {"UEFN_MCP_URL": "http://127.0.0.1:9/mcp", "UEFN_MCP_TIMEOUT": "3"})
check("D3 editeur eteint -> rc 2 OFFLINE", rc == 2 and (d or {}).get("error_kind") == "OFFLINE",
      f"rc={rc} d={str(d)[:160]}")

# =========================================================== E. journalisation

print("== E. journalisation des appels directs ==")
m_log = Mock("ok")
log_file = os.path.join(ROOT, "log", "_mcp_calls.jsonl")
shutil.rmtree(os.path.dirname(log_file), ignore_errors=True)
rc, out, err = run([CLIENT, "ping", "--log", log_file], env=m_log.env())
check("E1 mcp_client.py ping --log -> rc 0", rc == 0, f"rc={rc} err={err[:160]}")
n = len(open(log_file, encoding="utf-8").read().splitlines()) if os.path.exists(log_file) else 0
check("E2 journal ecrit (avant : aucun appel direct n'etait journalise)", n >= 1, f"{n} lignes")
rc, out, _ = run([CLIENT, "ping"], env=m_log.env({"UEFN_MCP_LOG": log_file}))
n2 = len(open(log_file, encoding="utf-8").read().splitlines()) if os.path.exists(log_file) else 0
check("E3 UEFN_MCP_LOG journalise aussi", rc == 0 and n2 > n, f"{n} -> {n2}")
m_log.stop()

# =========================================================== F. chaine complete

print("== F. chaine complete contre le mock (gabarit blank) ==")
m = Mock("ok")
WS = os.path.join(ROOT, "chain")
shutil.rmtree(WS, ignore_errors=True)
env = m.env()
rc, d, raw = cli(["init", "--template", "blank"], WS, env)
check("F1 init", rc == 0 and d and d["status"] == "PASSED", raw[:160])
rc, d, raw = cli(["preflight"], WS, env)
check("F2 preflight : pagination 0 -> 200, niveau relu",
      rc == 0 and d and d["status"] == "PASSED" and d.get("pagination_before") == "0"
      and str(d.get("pagination_after")) == "200" and d.get("level") == "MockLevel",
      str(d)[:200])
rc, d, raw = cli(["measure-palette"], WS, env)
pal = json.load(open(os.path.join(WS, "02_palette.json"), encoding="utf-8"))["assets"]
check("F3 measure-palette : 3 assets mesures (Cube 100 cm, pivot 0)",
      rc == 0 and d and d["status"] == "PASSED"
      and all(v.get("measured") and v.get("size_cm") == [100.0, 100.0, 100.0]
              for v in pal.values()),
      f"rc={rc} d={str(d)[:160]} pal={json.dumps(pal)[:200]}")
rc, d, raw = cli(["validate-scene"], WS, env)
check("F4 validate-scene apres mesure -> PASSED", rc == 0 and d and d["status"] == "PASSED",
      raw[:200])
rc, d, raw = cli(["compile-transforms"], WS, env)
reg = json.load(open(os.path.join(WS, "_compiled_scene.json"), encoding="utf-8"))
check("F5 compile-transforms : 2 props, echelle [1.2]*3 reportee",
      rc == 0 and d and d["status"] == "PASSED" and len(reg) == 2
      and all(v["scale"] == [1.2, 1.2, 1.2] for v in reg.values()),
      f"rc={rc} reg={json.dumps({k: v['scale'] for k, v in reg.items()})}")
rc, d, raw = cli(["build-structure"], WS, env)
check("F6 build-structure : 32 operations, aucune erreur",
      rc == 0 and d and d["status"] == "PASSED" and d.get("errors") == [],
      f"rc={rc} d={str(d)[:200]}")
rc, d, raw = cli(["place-scene"], WS, env)
placed = json.load(open(os.path.join(WS, "_placed.json"), encoding="utf-8"))
check("F7 place-scene : 2 props poses et RELUS (yaw force apres PlaceDevice)",
      rc == 0 and d and d["status"] == "PASSED" and d["props"]["verified"] == 2
      and {"Test_Cube_01", "Test_Cube_02"} <= set(placed), f"rc={rc} d={str(d)[:200]}")
rc, d, raw = cli(["audit-scene", "--live"], WS, env)
check("F8 audit-scene --live : source=live, bounds relus, pas d'erreur",
      rc == 0 and d and d["source"] == "live" and d["status"] == "PASSED"
      and d.get("gravity_scope") == "bounds relus dans l'editeur", str(d)[:200])
rc, d, _ = cli(["audit-scene"], WS, env)
check("F9 audit-scene hors ligne : source=compiled et gravity_scope dit la verite",
      d and d["source"] == "compiled" and "non detectable" in d.get("gravity_scope", ""),
      str(d.get("gravity_scope"))[:120])
rc, d, _ = cli(["check-navigation"], WS, env)
check("F10 check-navigation -> PASSED (ecart 120 cm > 100 cm)", rc == 0 and d
      and d["status"] == "PASSED", str(d)[:200])
rc, d, _ = cli(["visual-snapshot"], WS, env)
snap = (d or {}).get("snapshot_path", "")
check("F11 visual-snapshot ecrit un PNG", rc == 0 and d and d["status"] == "PASSED"
      and os.path.exists(snap) and os.path.getsize(snap) > 0, str(d)[:200])

print("== G. echelle relue : une echelle perdue doit etre signalee ==")
m.state(drop_scale=True)
if os.path.exists(os.path.join(WS, "_placed.json")):
  os.remove(os.path.join(WS, "_placed.json"))
rc, d, _ = cli(["place-scene"], WS, env)
errs = (d or {}).get("props", {}).get("errors", [])
check("G1 editeur qui perd l'echelle -> TRANSFORM_MISMATCH avec detail",
      rc == 1 and any(e.get("type") == "TRANSFORM_MISMATCH" and "echelle" in e.get("detail", "")
                      for e in errs), f"rc={rc} errs={json.dumps(errs)[:220]}")
m.state(drop_scale=False)
if os.path.exists(os.path.join(WS, "_placed.json")):
  os.remove(os.path.join(WS, "_placed.json"))
rc, d, _ = cli(["place-scene"], WS, env)
check("G2 relance apres correction -> PASSED (idempotent)",
      rc == 0 and d and d["status"] == "PASSED", str(d)[:200])

# =========================================================== H. proprietes

print("== H. apply-properties (etape 6) ==")
WS1 = os.path.join(ROOT, "chain1v1")
shutil.rmtree(WS1, ignore_errors=True)
rc, d, raw = cli(["init", "--template", "1v1_arena"], WS1, env)
gdd_path = os.path.join(WS1, "01_gdd.json")
gdd = json.load(open(gdd_path, encoding="utf-8"))
missing_paths = [k for k, v in gdd["requested_assets"].items() if not v.get("uefn_path")]
for k in missing_paths:
  gdd["requested_assets"][k]["uefn_path"] = "/Engine/BasicShapes/Cube"
write(gdd_path, gdd)
rc, d, raw = cli(["measure-palette"], WS1, env)
check("H1 measure-palette 1v1_arena (12 assets)", rc == 0 and d and d["status"] == "PASSED",
      f"rc={rc} d={str(d)[:200]}")
rc, d, raw = cli(["compile-transforms"], WS1, env)
check("H2 compile-transforms 1v1_arena (devices WORLD inclus)",
      rc == 0 and d and d["status"] == "PASSED" and d.get("compiled_actors", 0) >= 13,
      f"rc={rc} d={str(d)[:200]}")
comp = json.load(open(os.path.join(WS1, "_compiled_scene.json"), encoding="utf-8"))
world = [k for k, v in comp.items() if v.get("placement") == "WORLD"]
check("H3 les 5 devices Zone_Logic sont en placement WORLD, hors grille",
      len(world) == 5 and all(comp[k]["tile"][0] < 0 for k in world), str(world))
check("H3b origin_tile [2, 2, 0] applique aux acteurs sur la grille",
      comp["Spawner_P1_01"]["center_cm"][0] == (3 + 2) * 512.0 + 256.0
      and comp["Spawner_P1_01"]["center_cm"][1] == (1 + 2) * 512.0 + 256.0,
      str(comp["Spawner_P1_01"]["center_cm"]))
rc, d_struct, _ = cli(["build-structure", "--dry-run"], WS1, env)
check("H3c edge_policy fall_zone -> 64 dalles de sol, 0 mur de perimetre",
      rc == 0 and d_struct and d_struct.get("operations") == 64, str(d_struct)[:200])
rc, d, raw = cli(["place-scene"], WS1, env)
check("H4 place-scene : devices + props poses et relus", rc == 0 and d
      and d["status"] == "PASSED" and not d["devices"]["errors"] and not d["props"]["errors"],
      f"rc={rc} d={str(d)[:300]}")
rc, d, raw = cli(["apply-properties", "--dry-run"], WS1, env)
check("H5a apply-properties --dry-run -> DRY_RUN, jamais PASSED",
      rc == 0 and d and d["status"] == "DRY_RUN", str(d)[:200])
dev_path = os.path.join(WS1, "04_devices.json")
devs = json.load(open(dev_path, encoding="utf-8"))
# Le mock joue un editeur qui expose exactement les proprietes declarees par le gabarit.
m.state(props=sorted({k for dv in devs["devices"] for k in (dv.get("properties") or {})}))
rc, d, _ = cli(["apply-properties"], WS1, env)
rep = json.load(open(os.path.join(WS1, "07_properties_report.json"), encoding="utf-8"))
check("H5 apply-properties -> PASSED, rapport 07 ecrit, valeurs relues",
      rc == 0 and rep["status"] == "PASSED" and rep["applied"], str(rep)[:220])
check("H6 playerTeam relu avec teamType en plus : tolere (chaque cle ECRITE confirmee)",
      any(a["property"] == "playerTeam" and isinstance(a["read_back"], dict)
          and "teamType" in a["read_back"] for a in rep["applied"]),
      json.dumps([a for a in rep["applied"] if a["property"] == "playerTeam"])[:220])
devs["devices"][0]["properties"]["playerTeamX"] = {"teamIndex": 1}
write(dev_path, devs)
rc, d, _ = cli(["apply-properties"], WS1, env)
e0 = (d or {}).get("errors", [])
check("H7 nom de propriete invente -> PROPERTY_NOT_FOUND + suggestion",
      rc == 1 and any(e.get("type") == "PROPERTY_NOT_FOUND" and e.get("nearest") for e in e0),
      json.dumps(e0)[:220])
devs["devices"][0]["properties"].pop("playerTeamX")
devs["devices"][0]["properties"]["enabledDuringPhase"] = "Toujours"
write(dev_path, devs)
m.state(prop_overrides={"enabledDuringPhase": "Always"})
rc, d, _ = cli(["apply-properties"], WS1, env)
check("H8 valeur relue differente -> PROPERTY_MISMATCH (ecrit vs relu)",
      rc == 1 and "PROPERTY_MISMATCH" in types(d), json.dumps(types(d))[:160])
m.state(prop_overrides={})
devs["devices"][0]["properties"]["enabledDuringPhase"] = "Always"
write(dev_path, devs)

# =========================================================== I. cablage

print("== I. wire-devices (etape 6) ==")
rc, d, _ = cli(["wire-devices"], WS1, env)
check("I1 aucun binding declare -> NO_BINDING_DECLARED rc=1",
      rc == 1 and "NO_BINDING_DECLARED" in types(d)
      and os.path.exists(os.path.join(WS1, "08_wiring_report.json")), str(d)[:200])
rc, d, _ = cli(["wire-devices", "--allow-empty"], WS1, env)
check("I1b --allow-empty sans binding -> PASSED et 08_wiring_report.json ecrit",
      rc == 0 and d and d["status"] == "PASSED", str(d)[:200])
devs["devices"][0]["bindings"] = [{"event": "OnTriggered", "to": "Barrier_Center_01",
                                   "function": "Disable"}]
write(dev_path, devs)
rc, d, _ = cli(["wire-devices"], WS1, env)
rep = json.load(open(os.path.join(WS1, "08_wiring_report.json"), encoding="utf-8"))
check("I2 binding valide -> PASSED, relu sur la CIBLE (ListEventBindings)",
      rc == 0 and rep["status"] == "PASSED" and len(rep["wired"]) == 1
      and rep["wired"][0]["read_back"], str(rep)[:240])
devs["devices"][0]["bindings"] = [{"event": "OnTriggered", "to": "Barrier_Center_01",
                                   "function": "Desactiver"}]
write(dev_path, devs)
rc, d, _ = cli(["wire-devices"], WS1, env)
e = (d or {}).get("errors", [])
check("I3 fonction inventee -> BINDING_FUNCTION_UNKNOWN avec la vraie liste",
      rc == 1 and any(x.get("type") == "BINDING_FUNCTION_UNKNOWN"
                      and x.get("targetFunctions") for x in e), json.dumps(e)[:220])
devs["devices"][0]["bindings"] = [{"event": "OnExplose", "to": "Barrier_Center_01",
                                   "function": "Disable"}]
write(dev_path, devs)
rc, d, _ = cli(["wire-devices"], WS1, env)
check("I4 evenement invente -> BINDING_EVENT_UNKNOWN", rc == 1
      and "BINDING_EVENT_UNKNOWN" in types(d), json.dumps(types(d))[:160])
devs["devices"][0]["bindings"] = [{"event": "OnTriggered", "to": "Device_Inexistant",
                                   "function": "Disable"}]
write(dev_path, devs)
rc, d, _ = cli(["wire-devices"], WS1, env)
check("I5 cible non posee -> not_placed, rc=1", rc == 1 and (d or {}).get("not_placed"),
      str(d)[:200])
devs["devices"][0]["bindings"] = []
write(dev_path, devs)

# =========================================================== J. Verse

print("== J. Verse (etapes 8 et 9) ==")
verse_local = os.path.join(WS1, "verse", "game_manager_device.verse")
rc, d, _ = cli(["verse-scan"], WS1, env)
check("J1 verse-scan -> PASSED, _verse_files.json ecrit",
      rc == 0 and d and d["status"] == "PASSED" and d.get("count") == 2
      and os.path.exists(os.path.join(WS1, "_verse_files.json")), str(d)[:200])
m.state(files=[])
rc, d, _ = cli(["verse-scan"], WS1, env)
check("J2 ListFiles vide : PASSED mais avertissement « ne prouve PAS l'absence »",
      rc == 0 and d and "ne prouve PAS" in (d.get("warning") or ""), str(d)[:200])
m.state(files=["/Fortnite.com (Fortnite)/Modules/creative.verse"])
rc, d, _ = cli(["verse-grep", "--symbols", "GetGameState,CreateGameSettings"], WS1, env)
check("J3 verse-grep : un symbole trouve, un manquant -> FAILED + not_found",
      rc == 1 and d and d["status"] == "FAILED" and d.get("not_found") == ["CreateGameSettings"]
      and "GetGameState" in (d.get("resolved") or {}), str(d)[:220])
m.state(symbols=["GetGameState", "CreateGameSettings"])
rc, d, _ = cli(["verse-grep", "--symbols", "GetGameState,CreateGameSettings"], WS1, env)
check("J4 les deux symboles resolus -> PASSED, _verse_grep.json ecrit",
      rc == 0 and d and d["status"] == "PASSED"
      and os.path.exists(os.path.join(WS1, "_verse_grep.json")), str(d)[:200])
rc, d, _ = cli(["verse-write", "--file", verse_local,
                "--path", "/Mock/Modules/game_manager_device.verse"], WS1, env)
check("J5 verse-write sans accord -> CONSENT_REQUIRED rc=1 (WriteFile jamais execute)",
      rc == 1 and (d or {}).get("error_kind") == "CONSENT_REQUIRED"
      and "DANGEREUX" in (d or {}).get("detail", ""), str(d)[:220])
rc, d, _ = cli(["verse-write", "--file", verse_local,
                "--path", "/Mock/Modules/game_manager_device.verse",
                "--i-agree-to-modify-project"], WS1, env)
hist = json.load(open(os.path.join(WS1, "_verse_written.json"), encoding="utf-8"))
check("J6 verse-write avec accord -> PASSED, relecture identique, historique ecrit",
      rc == 0 and d and d["status"] == "PASSED" and d.get("read_back_matches")
      and len(hist["files"]) == 1, str(d)[:220])
rc, d, _ = cli(["verse-write", "--file", os.path.join(WS1, "absent.verse"),
                "--path", "/Mock/x.verse", "--i-agree-to-modify-project"], WS1, env)
check("J7 fichier local absent -> FILE_NOT_FOUND rc=1",
      rc == 1 and (d or {}).get("error_kind") == "FILE_NOT_FOUND", str(d)[:160])
rc, d, _ = cli(["verse-build"], WS1, env)
rep = json.load(open(os.path.join(WS1, "09_verse_report.json"), encoding="utf-8"))
check("J8 verse-build session Disconnected -> PASSED (diagnostics + ligne de succes)",
      rc == 0 and rep["status"] == "PASSED" and rep["success_lines"], str(rep)[:220])
m.state(session="Connected")
rc, d, _ = cli(["verse-build"], WS1, env)
check("J9 session connectee -> SESSION_CONNECTED rc=1 (BuildAll non teste dans ce cas)",
      rc == 1 and (d or {}).get("error_kind") == "SESSION_CONNECTED", str(d)[:200])
m.state(session="Disconnected", build_log=[{"severity": "Info", "message": "rien a signaler"}])
rc, d, _ = cli(["verse-build"], WS1, env)
check("J10 aucune ligne de succes -> FAILED (une liste vide ne suffit pas)",
      rc == 1 and d and d["status"] == "FAILED" and not d.get("success_lines"), str(d)[:200])
m.state(build_diags=[{"severity": "Error", "message": "type introuvable : barrier_device",
                      "filePath": "/Mock/Modules/game_manager_device.verse", "lineNumber": 30}],
        build_log=[{"severity": "Info", "message": "Verse build succeeded"}])
rc, d, _ = cli(["verse-build"], WS1, env)
check("J11 diagnostic Error -> FAILED malgre la ligne de succes",
      rc == 1 and d and d["status"] == "FAILED" and d.get("error_diagnostics"), str(d)[:220])
m.state(build_diags=[], build_log=[{"severity": "Info",
                                    "message": "Verse build succeeded (0 errors)"}])
rc, d, _ = cli(["verse-build", "--dry-run"], WS1, env)
check("J12 verse-build --dry-run -> DRY_RUN, jamais PASSED",
      rc == 0 and d and d["status"] == "DRY_RUN", str(d)[:160])

# =========================================================== K. @editable / playtest

print("== K. list-editables et playtest-plan (etapes 9 et 10) ==")
rc, d, _ = cli(["list-editables"], WS1, env)
rep = json.load(open(os.path.join(WS1, "10_editables.json"), encoding="utf-8"))
actors = [r for r in rep["mapping"] if r["kind"] == "ACTEUR"]
check("K1 list-editables : chaque reference d'ACTEUR a son refPath",
      rc == 0 and rep["status"] == "PASSED" and len(actors) == 6
      and all(r["refPath"] for r in actors) and rep["parameters"] == 1,
      str({k: rep.get(k) for k in ("status", "editable_count", "actor_references",
                                   "parameters")})[:200])
check("K2 un @editable primitif est un PARAMETRE, pas une cible manquante",
      [r["editable"] for r in rep["mapping"] if r["kind"] == "PARAMETRE"] == ["DebugSelfTest"]
      and not rep["without_target"], json.dumps(rep["without_target"])[:200])
check("K2b le rapport dit que le cablage automatique est UNKNOWN (manuel)",
      "UNKNOWN" in rep.get("scope", "") and actors
      and actors[0]["wiring"] in ("MANUEL", "AUCUNE_CIBLE"), str(rep.get("scope"))[:160])
rc, d, _ = cli(["list-editables", "--apply"], WS1, env)
rep_apply = json.load(open(os.path.join(WS1, "10_editables.json"), encoding="utf-8"))
actors_apply = [r for r in rep_apply["mapping"] if r["kind"] == "ACTEUR"]
check("K2c list-editables --apply : pose le creative_device et cable via SetDeviceProperty -> AUTO_VERIFIED",
      rc == 0 and rep_apply["status"] == "PASSED"
      and all(r["wiring"] == "AUTO_VERIFIED" for r in actors_apply),
      str(rep_apply.get("live"))[:200])
rc, d, _ = cli(["list-editables"], WS, env)
check("K3 gabarit blank sans .verse -> NO_VERSE_STAGED rc=1",
      rc == 1 and "NO_VERSE_STAGED" in types(d), str(d)[:200])
rc, d, _ = cli(["playtest-plan"], WS1, env)
check("K4 playtest-plan : PASSED, demande d'accord explicite, aucune session lancee",
      rc == 0 and d and d["status"] == "PASSED" and "accord explicite" in d["consent_to_request"]
      and d["not_provided_by_this_skill"], str(d)[:240])

# =========================================================== L. audit / menage

print("== L. audit hors ligne et menage ==")
ws_off = os.path.join(ROOT, "offline")
shutil.rmtree(ws_off, ignore_errors=True)
os.makedirs(ws_off, exist_ok=True)
write(os.path.join(ws_off, "02_palette.json"), {"assets": {
    "prop_crate": {"uefn_path": "/Game/C.SM_Crate", "category": "PROP",
                   "size_cm": [120.0, 120.0, 130.0], "pivot_offset_cm": [0.0, 0.0, -6.5],
                   "measured": {"at": "2026-10-20T00:00:00+00:00", "kind": "actor"}}}})
write(os.path.join(ws_off, "03_grid.json"), grid([["#", "#", "#"], ["#", ".", "#"],
                                                  ["#", "#", "#"]]))
write(os.path.join(ws_off, "05_props.json"), {"props": [
    {"actor_label": "Crate_A", "asset_key": "prop_crate", "placement_mode": "TILE_ANCHOR",
     "tile": [1, 1, 0], "slot": "CENTER", "face_towards": "SOUTH", "snap_to_floor": True}]})
rc, out, _ = run([CLI, "compile-transforms", "--workspace", ws_off])
check("L1 compile-transforms hors ligne -> PASSED", rc == 0
      and json.loads(out)["status"] == "PASSED", out[:150])
rc, d, _ = cli(["audit-scene", "--live"], ws_off,
               {"UEFN_MCP_URL": "http://127.0.0.1:9/mcp", "UEFN_MCP_TIMEOUT": "3"})
check("L2 --live sans _placed.json -> source=not_live + NO_LIVE_DATA (avant : source=live)",
      rc == 1 and d and d["source"] == "not_live" and "NO_LIVE_DATA" in types(d, "scene_errors"),
      f"rc={rc} d={str(d)[:200]}")
rc, d, _ = cli(["check-navigation"], ws_off)
check("L3 check-navigation hors ligne -> PASSED, rapport propre",
      rc == 0 and d and d["status"] == "PASSED" and d["error_count"] == 0
      and os.path.exists(os.path.join(ws_off, "06_navigation_report.json")), str(d)[:200])
check("L3b check-navigation n'herite PAS des erreurs d'un audit precedent",
      d and "scene_errors" not in d and d.get("other_report"), json.dumps(d)[:200])
# =========================================================== M. symetrie reelle

print("== M. check-symmetry : la symetrie posee, pas seulement la matrice ==")
SYM_GRID = [["#", "#", "#", "#"], ["#", "S1", ".", "#"], ["#", ".", "S2", "#"],
            ["#", "#", "#", "#"]]
G5 = [["#", "#", "#", "#", "#"], ["#", "S1", ".", ".", "#"], ["#", ".", "R_N", ".", "#"],
      ["#", ".", ".", "S2", "#"], ["#", "#", "#", "#", "#"]]
R180_RAMPS = {"symmetric": True, "symmetry_axis": "R180", "floors": [
    {"z_index": 0, "matrix": [["#", "#", "#", "#"], ["#", "R_N", "S1", "#"],
                              ["#", "S2", "R_S", "#"], ["#", "#", "#", "#"]]}]}
SYM_PAL = {"assets": {"prop_ramp": {
    "uefn_path": "/Fortnite/Game/Props/Ramp", "category": "PROP", "scale": 1.0,
    "size_cm": [200.0, 100.0, 150.0], "pivot_offset_cm": [0.0, 0.0, 0.0],
    "measured": {"at": "2026-10-22T00:00:00+00:00", "kind": "actor"}}}}


def ramp(label, tile, slot, face, extra=None):
  p = {"actor_label": label, "asset_key": "prop_ramp", "placement_mode": "TILE_ANCHOR",
       "tile": tile, "slot": slot, "face_towards": face}
  p.update(extra or {})
  return p


PAIRED = [ramp("Ramp_A", [1, 1, 0], "NORTH_EDGE", "SOUTH"),
          ramp("Ramp_B", [2, 2, 0], "SOUTH_EDGE", "NORTH")]
DECENTRE = [ramp("Ramp_A", [1, 1, 0], "NORTH_EDGE", "SOUTH"),
            ramp("Ramp_B", [2, 2, 0], "CENTER", "NORTH")]


def sym_ws(name, axis, props_list, matrix=None):
  ws = os.path.join(ROOT, "sym", name)
  shutil.rmtree(ws, ignore_errors=True)
  write(os.path.join(ws, "01_gdd.json"), {"project_name": "sym", "game_mode": "1v1"})
  write(os.path.join(ws, "02_palette.json"), SYM_PAL)
  write(os.path.join(ws, "03_grid.json"), grid(matrix or SYM_GRID, axis, axis is not None))
  write(os.path.join(ws, "04_devices.json"), {"devices": []})
  write(os.path.join(ws, "05_props.json"), {"props": props_list})
  return ws


ws = sym_ws("ok", "R180", PAIRED)
rc, d, raw = cli(["check-symmetry"], ws, env)
check("M1 R180 : deux rampes miroirs -> PASSED, 1 paire verifiee, un seul JSON emis",
      rc == 0 and d and d["status"] == "PASSED" and d["axis"] == "R180"
      and d["checked_pairs"] == 1 and d["source"] == "compiled"
      and raw.count('"status"') == 1, f"rc={rc} raw={raw[:200]}")
ws_bad = sym_ws("decalee", "R180", DECENTRE)
rc, d, _ = cli(["check-symmetry"], ws_bad, env)
e0 = ((d or {}).get("spec_errors") or [{}])[0]
check("M2 rampe decalee -> SPEC_ASYMMETRY avec position attendue (le defaut de la capture)",
      rc == 1 and d and d["status"] == "FAILED" and e0.get("type") == "SPEC_ASYMMETRY"
      and e0.get("max_delta_cm", 0) > 100 and e0.get("expected_center_b_cm")
      and e0.get("actor_b") == "Ramp_B", json.dumps(e0)[:260])
ws = sym_ws("absente", "R180", [ramp("Ramp_A", [1, 1, 0], "NORTH_EDGE", "SOUTH"),
                                ramp("Ramp_B", [2, 1, 0], "SOUTH_EDGE", "NORTH")])
rc, d, _ = cli(["check-symmetry"], ws, env)
check("M3 partenaire hors de la tuile miroir -> MIRROR_PARTNER_MISSING",
      rc == 1 and "MIRROR_PARTNER_MISSING" in types(d, "spec_errors"), json.dumps(d)[:220])
ws = sym_ws("optout", "R180", [ramp("Ramp_A", [1, 1, 0], "NORTH_EDGE", "SOUTH",
                                    {"mirror": False}),
                               ramp("Ramp_B", [2, 2, 0], "CENTER", "NORTH", {"mirror": False})])
rc, d, _ = cli(["check-symmetry"], ws, env)
check("M4 `mirror: false` des deux cotes -> PASSED, exclusion annoncee dans le scope",
      rc == 0 and d and d["status"] == "PASSED" and d["checked_pairs"] == 0
      and any("mirror: false" in s for s in d["scope"]), json.dumps(d)[:260])
ws = sym_ws("sansaxe", None, DECENTRE)
rc, d, _ = cli(["check-symmetry"], ws, env)
check("M5 aucun symmetry_axis -> PASSED mais le scope dit que RIEN n'est verifie",
      rc == 0 and d and d["status"] == "PASSED" and d["axis"] is None
      and d["scope"][0].startswith("AUCUN AXE"), json.dumps(d)[:240])
ws = sym_ws("yaw", "R180", [ramp("Ramp_A", [1, 1, 0], "NORTH_EDGE", "SOUTH"),
                            ramp("Ramp_B", [2, 2, 0], "SOUTH_EDGE", "SOUTH")])
rc, d, _ = cli(["check-symmetry"], ws, env)
e0 = ((d or {}).get("spec_errors") or [{}])[0]
check("M6 position juste mais yaw non miroite -> fault yaw",
      rc == 1 and e0.get("fault") == "yaw" and e0.get("expected_yaw_b") == 0.0
      and e0.get("yaw_b") == 180.0, json.dumps(e0)[:240])
ws = sym_ws("schema", "R180", [ramp("Ramp_A", [1, 1, 0], "NORTH_EDGE", "SOUTH",
                                    {"mirror": False})])
rc, d, _ = cli(["validate-scene"], ws, env)
check("M7 `mirror` est une cle de schema -> pas de UNKNOWN_KEY",
      rc == 0 and d and d["status"] == "PASSED", json.dumps(d)[:200])

validate_grid(grid(SYM_GRID, "R180", True), "M8 validate-grid R180 correct -> PASSED", "PASSED")
broken_r180 = [r[:] for r in SYM_GRID]
broken_r180[2][2] = "S1"
validate_grid(grid(broken_r180, "R180", True),
              "M9 R180 : S1 au lieu de S2 -> SYMMETRY_BROKEN (avant : non controle)",
              "FAILED", "SYMMETRY_BROKEN")
validate_grid(R180_RAMPS, "M10 R180 : R_N/R_S et S1/S2 -> PASSED", "PASSED")
same_ramp_r180 = json.loads(json.dumps(R180_RAMPS))
same_ramp_r180["floors"][0]["matrix"][2][2] = "R_N"
validate_grid(same_ramp_r180, "M11 R180 : deux R_N opposes -> SYMMETRY_BROKEN",
              "FAILED", "SYMMETRY_BROKEN")
d = validate_grid(grid(G5, "R180", True),
                  "M12 rampe sur le plan de symetrie -> SYMMETRY_ON_AXIS seul",
                  "FAILED", "SYMMETRY_ON_AXIS")
check("M12b SYMMETRY_ON_AXIS est la seule erreur de M12",
      d and [e["type"] for e in d["errors"]] == ["SYMMETRY_ON_AXIS"],
      json.dumps((d or {}).get("errors"))[:220])
tpl = os.path.join(SKILL, "templates", "1v1_arena", "03_grid.json")
rc, out, err = run([CLI, "validate-grid", tpl])
check("M13 gabarit 1v1_arena declare en R180 -> validate-grid PASSED",
      rc == 0 and json.loads(out)["status"] == "PASSED", out[:200] + err[:200])
MIRROR_X_VERSUS = [["#", "#", "#", "#"], ["#", "S1", "S2", "#"], ["#", "S2", "S1", "#"],
                   ["#", "#", "#", "#"]]
validate_grid(grid(MIRROR_X_VERSUS, "X", True),
              "M13b miroir X versus : S1 <-> S2 de part et d'autre -> PASSED", "PASSED")
same_side = [r[:] for r in MIRROR_X_VERSUS]
same_side[2][1] = "S1"
validate_grid(grid(same_side, "X", True),
              "M13c miroir X : S1 des deux cotes -> PASSED (portee assumee : l'echange des "
              "equipes n'est exige qu'en R180, sinon boxfight casse)", "PASSED")
validate_grid(grid([["#", "#", "#", "#"], ["#", "S1", ".", "#"], ["#", "S1", ".", "#"],
                    ["#", "#", "#", "#"]], "X", True),
              "M13d une seule equipe (co-op) : rien a echanger -> PASSED", "PASSED")

ws_live = sym_ws("live", "R180", PAIRED)
cli(["compile-transforms"], ws_live, env)
rc, d, _ = cli(["place-scene"], ws_live, env)
rc, d, raw = cli(["check-symmetry", "--live"], ws_live, env)
check("M14 --live sans derive : source=live, PASSED",
      rc == 0 and d and d["source"] == "live" and d["status"] == "PASSED"
      and d["checked_pairs"] == 1, f"rc={rc} raw={raw[:220]}")
m.state(drift={"Ramp_B": [40.0, 0.0, 0.0]})
rc, d, _ = cli(["check-symmetry", "--live"], ws_live, env)
check("M15 acteur pousse de 40 cm dans l'editeur -> TRANSFORM_DRIFT + SCENE_ASYMMETRY",
      rc == 1 and d and "TRANSFORM_DRIFT" in types(d, "drift_errors")
      and "SCENE_ASYMMETRY" in types(d, "scene_errors"), json.dumps(d)[:300])
m.state(drift={})
ws_np = sym_ws("nonplace", "R180", PAIRED)
cli(["compile-transforms"], ws_np, env)
rc, d, _ = cli(["check-symmetry", "--live"], ws_np, env)
check("M16 --live sans _placed.json -> not_live + NO_LIVE_DATA + NOT_PLACED",
      rc == 1 and d and d["source"] == "not_live"
      and "NO_LIVE_DATA" in types(d, "scene_errors")
      and "NOT_PLACED" in types(d, "drift_errors"), json.dumps(d)[:260])
rep = os.path.join(ws_live, "11_symmetry_report.json")
loaded = json.load(open(rep, encoding="utf-8")) if os.path.exists(rep) else {}
check("M17 11_symmetry_report.json ecrit avec les cles du contrat",
      {"timestamp", "command", "status", "axis", "symmetric", "source", "error_count",
       "checked_pairs", "spec_errors", "drift_errors", "scene_errors", "scope"} <= set(loaded),
      json.dumps(sorted(loaded))[:220])
ws_ko = sym_ws("specko", "R180", [ramp("Ramp_A", [1, 1, 0], "NORTH_EDGE", "SOUTH"),
                                  ramp("Ramp_B", [2, 2, 0], "CENTER", "NOPE")])
rc, d, _ = cli(["check-symmetry"], ws_ko, env)
check("M18 specs invalides -> COMPILE_FAILED explicite, pas un silence",
      rc == 1 and d and types(d) == ["COMPILE_FAILED"], json.dumps(d)[:220])
ws = sym_ws("annonce", "R180", PAIRED)
rc, d, _ = cli(["validate-scene"], ws, env)
check("M19 validate-scene annonce check-symmetry (SYMMETRY_SCOPE, avant : jamais emis)",
      rc == 0 and d and "SYMMETRY_SCOPE" in [w.get("type") for w in d.get("warnings", [])]
      and "check-symmetry" in json.dumps(d.get("warnings")), json.dumps(d)[:260])
ws = sym_ws("annonce2", "R180", PAIRED)
write(os.path.join(ws, "03_grid.json"), grid(SYM_GRID, None, True))
rc, d, _ = cli(["validate-scene"], ws, env)
check("M20 symmetric: true sans axe -> SYMMETRY_SCOPE dit que rien n'est controle",
      rc == 0 and d and any(w.get("type") == "SYMMETRY_SCOPE"
                            and "aucun controle" in w.get("detail", "")
                            for w in d.get("warnings", [])), json.dumps(d)[:260])

before = len(json.load(open(os.path.join(WS, "_placed.json"), encoding="utf-8")))
rc, d, _ = cli(["cleanup"], WS, env)
check("L4 cleanup supprime les acteurs taggues et efface _placed.json",
      rc == 0 and d and d["status"] == "PASSED" and d["found"] >= before and d["left"] == 0
      and not os.path.exists(os.path.join(WS, "_placed.json")), str(d)[:200])

print("\n== N. Legalite UEFN : interdiction de /Game/ et recherche Playsets (PPID_/PID_) ==")
ws_ill = sym_ws("illegal_game", "R180", PAIRED)
pal_ill = json.load(open(os.path.join(ws_ill, "02_palette.json"), encoding="utf-8"))
pal_ill["assets"]["prop_ramp"]["uefn_path"] = "/Game/Environments/Asteria/NeonCity/Props/SM_BusStop.SM_BusStop"
write(os.path.join(ws_ill, "02_palette.json"), pal_ill)
rc, d, _ = cli(["validate-scene"], ws_ill, env)
check("N1 validate-scene bloque les chemins /Game/ non exposes (ILLEGAL_ASSET_PATH)",
      rc == 1 and d and "ILLEGAL_ASSET_PATH" in types(d), json.dumps(d)[:240])
rc, d, _ = cli(["search-playsets", "--query", "neon busstop"], WS, env)
check("N2 search-playsets retourne uniquement des chemins PPID_/PID_ legaux",
      rc == 0 and d and d["status"] == "PASSED" and d.get("total_trouves", 0) >= 1
      and "PPID_" in json.dumps(d.get("resultats", [])), json.dumps(d)[:240])
rc, d, _ = cli(["audit-legality"], WS, env)
check("N3 audit-legality verifie la scene via FortEditorValidatorSubsystem -> PASSED",
      rc == 0 and d and d["status"] == "PASSED" and d.get("illegal_count") == 0
      and os.path.exists(os.path.join(WS, "06_legality_report.json")), json.dumps(d)[:240])
m.state(illegal_actors=[{"actor_label": "BusStop_01", "asset_path": "/Game/Athena/BusStop",
                         "errors": ["référence illégale"], "suggested_legal_ppids": ["PPID_BusStop"]}])
rc, d, _ = cli(["audit-legality"], WS, env)
check("N4 audit-legality detecte un acteur /Game/ illegal et suggere un PPID_ -> FAILED rc=1",
      rc == 1 and d and d["status"] == "FAILED" and d.get("illegal_count") == 1, json.dumps(d)[:240])
rc, d, _ = cli(["launch-session", "--i-agree-to-launch-session"], WS, env)
check("N5 launch-session bloque si des acteurs illegaux sont presents (ILLEGAL_ACTORS_BLOCK_SESSION)",
      rc == 1 and d and d.get("error_kind") == "ILLEGAL_ACTORS_BLOCK_SESSION", json.dumps(d)[:240])
rc, d, _ = cli(["audit-legality", "--fix"], WS, env)
check("N6 audit-legality --fix remplace automatiquement les acteurs illegaux -> PASSED",
      rc == 0 and d and d["status"] == "PASSED" and d.get("replaced_count") == 1, json.dumps(d)[:240])
rc, d, _ = cli(["launch-session"], WS, env)
check("N7 launch-session sans accord -> CONSENT_REQUIRED rc=1",
      rc == 1 and d and d.get("error_kind") == "CONSENT_REQUIRED", json.dumps(d)[:240])
rc, d, _ = cli(["launch-session", "--i-agree-to-launch-session", "--wait-seconds", "5"], WS, env)
check("N8 launch-session avec accord -> StartSession + Connected + 12_session_report.json -> PASSED",
      rc == 0 and d and d["status"] == "PASSED" and d.get("connected") is True
      and os.path.exists(os.path.join(WS, "12_session_report.json")), json.dumps(d)[:240])
m.state(illegal_actors=[], session="Disconnected")

m.stop()

print("\n== Resultat ==")
ko = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(ko)}/{len(results)} OK")
for n in ko:
  print("  ECHEC : " + n)
shutil.rmtree(ROOT, ignore_errors=True)
sys.exit(1 if ko else 0)
