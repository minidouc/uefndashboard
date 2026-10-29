#!/usr/bin/env python3
"""Verifie que chaque outil cite par les agents existe vraiment.

Deux references, toutes deux relues dans le code ou dans l'editeur, jamais supposees :
  - les commandes du CLI et leurs options : lues dans le parseur de uefn_spatial_cli.py ;
  - les outils MCP : l'inventaire skill/uefn_map_creator/mcp_tools/ (388 outils, 30 toolsets,
    releve le 2026-10-19 ; identique au serveur le 2026-10-29 sur 8 toolsets / 115 outils compares).

Ce qui est controle dans agent-team/ (hors _archive et prompt.flash.md) :
  - `commande-cli --option` : commande et options existent ;
  - `Alias.Outil` / `toolset.complet.Outil` : l'outil existe dans ce toolset ;
  - dans outils.md et tool-output/ : tout nom nu qui a la forme d'un outil (get_x, SetX...).
Une ligne qui dit explicitement qu'un nom n'existe pas (« n'existe », « caduque ») est ignoree.

  python agent-team/_commun/verifier_outils.py           # rapport, rc 1 si un nom est inconnu
  python agent-team/_commun/verifier_outils.py --live inventaire.json
      # compare d'abord l'index a un releve du serveur {"toolset": ["outil", ...]}
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TEAM = os.environ.get("UEFN_AGENT_TEAM") or os.path.dirname(HERE)   # surcharge : tests
SCRIPT_CLI = os.path.join(REPO, "skill", "uefn_map_creator", "script")
MCP_TOOLS = os.path.join(REPO, "skill", "uefn_map_creator", "mcp_tools")

NEGATION = re.compile(r"n'existe|n’existe|caduque|inexistant", re.I)
VERBES = (r"(?:get|set|add|remove|list|find|load|save|create|delete|spawn|place|capture|start|stop|"
          r"push|build|read|write|search|trace|replace|execute|run|move|duplicate|focus|select|"
          r"bind|destroy|exists|update)")
NOM_SNAKE = re.compile(rf"^{VERBES}_[a-z0-9_]+$")
NOM_CAMEL = re.compile(rf"^(?i:{VERBES})[A-Z][A-Za-z0-9]+$")
# Noms qui ont la forme d'un outil mais n'en sont pas : champs de rapport, outil MCP de premier
# niveau, API Verse.
PAS_DES_OUTILS = {"read_back", "read_back_matches", "build_log_lines", "search_ref",
                  "spawn_reference", "list_toolsets", "describe_toolset", "call_tool",
                  "MoveTo", "TeleportTo"}
CMD_CLI = re.compile(r"^(?:python \S*uefn_spatial_cli\.py )?([a-z]+(?:-[a-z]+)+)((?: --?[a-z-]+(?:[ =]\S+)?)*)")


def index_mcp() -> tuple[dict, dict]:
  """{toolset: {outils}}, {alias: toolset} depuis mcp_tools/*/*.md."""
  outils, alias = {}, {}
  for f in glob.glob(os.path.join(MCP_TOOLS, "*", "*.md")):
    with open(f, encoding="utf-8") as fh:
      t = fh.read()
    m = re.match(r"# ([\w.]+)", t)
    if not m:
      continue
    outils[m.group(1)] = set(re.findall(r"^- \*\*(\w+)\*\*\(", t, re.M))
    a = re.search(r"Alias CLI : `(\w+)`", t)
    if a:
      alias[a.group(1)] = m.group(1)
  return outils, alias


def commandes_cli() -> dict:
  """{commande: {options}} lu dans le parseur argparse du CLI, sans l'executer."""
  import argparse as ap
  sys.path.insert(0, SCRIPT_CLI)
  import uefn_spatial_cli
  pris = {}

  def capturer(self, *a, **k):
    for act in self._actions:
      if isinstance(act, ap._SubParsersAction):
        for nom, p in act.choices.items():
          pris[nom] = {o for x in p._actions for o in x.option_strings}
    raise SystemExit(0)

  orig = ap.ArgumentParser.parse_args
  ap.ArgumentParser.parse_args = capturer
  argv = sys.argv
  try:
    sys.argv = ["uefn_spatial_cli.py"]
    uefn_spatial_cli.main()
  except SystemExit:
    pass
  finally:
    ap.ArgumentParser.parse_args = orig
    sys.argv = argv
  return pris


def fichiers() -> list[str]:
  out = []
  for f in glob.glob(os.path.join(TEAM, "**", "*.*"), recursive=True):
    rel = os.path.relpath(f, TEAM)
    if f.endswith((".md", ".json")) and "_archive" not in rel and not rel.endswith("prompt.flash.md") \
        and not rel.startswith("_commun"):
      out.append(f)
  return sorted(out)


def verifier() -> list[dict]:
  outils, alias = index_mcp()
  tous = set().union(*outils.values())
  cli = commandes_cli()
  problemes = []

  def signaler(genre, nom, f, ln):
    problemes.append({"type": genre, "nom": nom, "ou": f"{os.path.relpath(f, TEAM)}:{ln}"})

  for f in fichiers():
    rel = os.path.relpath(f, TEAM).replace("\\", "/")
    noms_nus = rel.endswith("/outils.md") or "/tool-output/" in rel
    with open(f, encoding="utf-8") as fh:
      lignes = fh.readlines()
    for ln, ligne in enumerate(lignes, 1):
      if NEGATION.search(ligne):
        continue
      for tok in re.findall(r"`([^`\n]+)`", ligne):
        t = tok.strip()
        m = CMD_CLI.match(t)
        # Une commande inconnue n'est signalee que dans la 1re colonne d'une table d'outils.md :
        # ailleurs, un mot-compose (famille `effets-ui`, skill `uefn-map-creator`) n'en est pas une.
        premiere_cellule = ligne.lstrip().startswith(f"| `{tok}`")
        if m and (m.group(1) in cli or (rel.endswith("/outils.md") and premiere_cellule)):
          cmd = m.group(1)
          if cmd not in cli:
            signaler("COMMANDE_CLI_INCONNUE", cmd, f, ln)
          else:
            for opt in re.findall(r"(--[a-z-]+)", m.group(2) or ""):
              if opt not in cli[cmd]:
                signaler("OPTION_CLI_INCONNUE", f"{cmd} {opt}", f, ln)
          continue
        for a, n in re.findall(r"\b([A-Z][A-Za-z]+)\.([A-Za-z_]+)\b", t):
          if a in alias and n not in outils[alias[a]] and n != "org":
            signaler("OUTIL_MCP_INCONNU", f"{a}.{n}", f, ln)
        for ts, n in re.findall(r"\b((?:editor_toolset\.toolsets\.\w+\.\w+)|(?:\w+Toolsets?\.\w+))\.(\w+)", t):
          if ts in outils and n not in outils[ts]:
            signaler("OUTIL_MCP_INCONNU", f"{ts}.{n}", f, ln)
        if noms_nus:
          for mot in re.split(r"[\s(),/]+", t):
            if "." in mot:
              continue   # forme Alias.Outil : deja jugee ci-dessus
            if (NOM_SNAKE.match(mot) or (NOM_CAMEL.match(mot) and mot[0].isupper())) \
                and mot not in tous and mot not in PAS_DES_OUTILS:
              signaler("OUTIL_MCP_INCONNU", mot, f, ln)
  return problemes


def comparer_live(path: str) -> list[dict]:
  outils, _ = index_mcp()
  with open(path, encoding="utf-8") as f:
    live = json.load(f)
  noms_toolsets = set(live)
  if "tools" in live and "toolsets" in live:
    # Releve partiel : liste complete des toolsets, detail de quelques-uns seulement.
    noms_toolsets, live = set(live["toolsets"]), live["tools"]
  ecarts = []
  ecarts += [{"type": "TOOLSET_DISPARU", "nom": ts} for ts in sorted(set(outils) - noms_toolsets)]
  ecarts += [{"type": "TOOLSET_NOUVEAU", "nom": ts} for ts in sorted(noms_toolsets - set(outils))]
  for ts in sorted(set(outils) & set(live)):
    noms = {n.rsplit(".", 1)[-1] for n in live[ts]}
    ecarts += [{"type": "OUTIL_NOUVEAU", "nom": f"{ts}.{n}"} for n in sorted(noms - outils[ts])]
    ecarts += [{"type": "OUTIL_DISPARU", "nom": f"{ts}.{n}"} for n in sorted(outils[ts] - noms)]
  return ecarts


def main() -> int:
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("--live", help="releve du serveur {toolset: [outils]} a comparer a l'index")
  a = ap.parse_args()
  sys.stdout.reconfigure(encoding="utf-8")
  res = {}
  if a.live:
    res["ecarts_index_vs_serveur"] = comparer_live(a.live)
  res["problemes"] = verifier()
  res["status"] = "FAILED" if res["problemes"] or res.get("ecarts_index_vs_serveur") else "PASSED"
  print(json.dumps(res, ensure_ascii=False, indent=1))
  return 1 if res["status"] == "FAILED" else 0


if __name__ == "__main__":
  sys.exit(main())
