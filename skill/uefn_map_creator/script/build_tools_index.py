"""Generateur de la liste des outils MCP dans mcp_tools/.

Lit les dumps d'une campagne de test (inventory/*.json + capabilities.json) et
reecrit un fichier par toolset, ranges par famille. Les descriptions d'outils
sont celles, officielles, renvoyees par describe_toolset : elles ne sont pas
reformulees pour eviter d'inventer un comportement.

    python script/build_tools_index.py --inventory DIR --capabilities FICHIER --out mcp_tools
"""
import argparse
import io
import json
import os
import re
import unicodedata

FAMILLES = {
    "scene-acteur": ["editor_toolset.toolsets.scene.SceneTools",
                     "editor_toolset.toolsets.actor.ActorTools",
                     "ValkyrieToolset.EntityToolset",
                     "editor_toolset.toolsets.primitive.PrimitiveTools"],
    "objet-proprietes": ["editor_toolset.toolsets.object.ObjectTools",
                         "VerseFieldsToolset.VerseFieldsToolset"],
    "devices": ["ValkyrieToolset.DeviceToolset"],
    "verse": ["ValkyrieToolset.VerseToolset"],
    "editor-session": ["EditorToolset.EditorAppToolset", "EditorToolset.LogsToolset",
                       "ValkyrieToolset.SessionToolset",
                       "editor_toolset.toolsets.programmatic.ProgrammaticToolset",
                       "ValkyrieToolset.ValkyriePythonToolset"],
    "assets-ressources": ["editor_toolset.toolsets.asset.AssetTools",
                          "editor_toolset.toolsets.static_mesh.StaticMeshTools",
                          "editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools",
                          "editor_toolset.toolsets.texture.TextureTools",
                          "editor_toolset.toolsets.material.MaterialTools",
                          "editor_toolset.toolsets.material_instance.MaterialInstanceTools",
                          "editor_toolset.toolsets.curve_table.CurveTableTools",
                          "editor_toolset.toolsets.data_table.DataTableTools",
                          "PhysicsToolsets.PhysicsAssetToolset"],
    "effets-ui": ["NiagaraToolsets.NiagaraToolset_System",
                  "NiagaraToolsets.NiagaraToolset_Component",
                  "NiagaraToolsets.NiagaraToolset_Assets",
                  "NiagaraToolsets.NiagaraToolset_Info",
                  "UMGToolSet.UMGToolSet", "WidgetAnimationToolset.WidgetAnimationToolset",
                  "MVVMToolset.MVVMToolset", "GameplayTagsToolset.GameplayTagsToolset"],
}
ALIAS = {"EditorToolset.EditorAppToolset": "EditorApp", "EditorToolset.LogsToolset": "Logs",
         "ValkyrieToolset.VerseToolset": "Verse", "ValkyrieToolset.SessionToolset": "Session",
         "ValkyrieToolset.DeviceToolset": "Device", "ValkyrieToolset.EntityToolset": "Entity",
         "ValkyrieToolset.ValkyriePythonToolset": "Python",
         "editor_toolset.toolsets.actor.ActorTools": "Actor",
         "editor_toolset.toolsets.asset.AssetTools": "Asset",
         "editor_toolset.toolsets.object.ObjectTools": "Object",
         "editor_toolset.toolsets.primitive.PrimitiveTools": "Primitive",
         "editor_toolset.toolsets.programmatic.ProgrammaticToolset": "Prog",
         "editor_toolset.toolsets.scene.SceneTools": "Scene",
         "editor_toolset.toolsets.static_mesh.StaticMeshTools": "SMesh"}
CLASSE = {"read": "lecture", "write": "ecriture", "dangerous": "DANGEREUX"}
STATUT = {"proven": "verifie", "failed": "echec", "unknown": "inconnu"}
TRAITS = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-",
          "\u2014": "-", "\u2026": "...", "\u0153": "oe", "\u0152": "OE"}


def net(s, n=0):
  """Sans accents, sans retours ligne, coupe a n caracteres sur un mot."""
  if not s:
    return ""
  t = unicodedata.normalize("NFKD", str(s).replace("\r", " ").replace("\n", " "))
  t = "".join(c for c in t if not unicodedata.combining(c))
  for k, v in TRAITS.items():
    t = t.replace(k, v)
  t = re.sub(r"\s+", " ", t).strip()
  if n and len(t) > n:
    t = t[:n].rsplit(" ", 1)[0].rstrip(" ,;:-.") + " ..."
  return t


def phrase(txt, k=1, n=150):
  """Les k premieres phrases d'une description officielle."""
  t = unicodedata.normalize("NFKD", str(txt or ""))
  t = re.sub(r"\s+", " ", t).strip()
  parts = re.split(r"(?<=[.!?])\s+", t)
  return net(" ".join(parts[:k]), n)


def signature(schema):
  props, req = (schema or {}).get("properties", {}), set((schema or {}).get("required", []))
  out = [f"{p}{'*' if p in req else ''}" for p in props]
  return ",".join(out[:4] + (["..."] if len(out) > 4 else []))


def slug(full):
  s = full.split(".")[-1].replace("_", "-")
  s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "-", s)
  return s.lower().replace("tool-set", "toolset")


def raison(t):
  for k in ("error", "skip_reason", "notes"):
    v = phrase(t.get(k), 1, 120)
    if v and "aucune raison" not in v.lower():
      return v
  return ""


def ecrire(chemin, texte):
  os.makedirs(os.path.dirname(chemin), exist_ok=True)
  with io.open(chemin, "w", encoding="utf-8", newline="\n") as f:
    f.write(texte)


def ligne(x):
  marks = [CLASSE.get(x["class"], x["class"]), STATUT.get(x["status"], x["status"])]
  if x.get("hazard"):
    marks.append("DANGER:" + net(x["hazard"]))
  etat = " | ".join(marks)
  s = f"- **{x['tool']}**({signature(x['params_schema'])}) — {phrase(x['description'])} [{etat}]"
  if x["status"] != "proven":
    r = raison(x)
    if r:
      s += f"\n  - {'erreur' if x['status'] == 'failed' else 'motif'} : {r}"
  return s


def ts_par_nom(caps):
  return {t["toolset"]: t for t in caps["toolsets"]}


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--inventory", required=True)
  ap.add_argument("--capabilities", required=True)
  ap.add_argument("--out", required=True)
  a = ap.parse_args()
  caps = json.load(io.open(a.capabilities, encoding="utf-8"))
  ts = ts_par_nom(caps)
  orphelins = [n for n in ts if n not in {x for v in FAMILLES.values() for x in v}]
  if orphelins:
    FAMILLES["autre"] = orphelins
    print("OUTILS SANS FAMILLE DECLAREE, classes dans `autre/` : " + ", ".join(orphelins))
  meta = caps.get("meta", {})
  lignes_sommaire, total = [], 0
  for famille, noms in FAMILLES.items():
    for full in noms:
      t = ts[full]
      off = json.load(io.open(os.path.join(a.inventory, full + ".json"), encoding="utf-8"))
      desc = {x["name"].split(".")[-1]: x.get("description", "") for x in off["content"]["tools"]}
      for x in t["tools"]:
        x["description"] = desc.get(x["tool"], "")
      c = {k: sum(1 for x in t["tools"] if x["status"] == k) for k in STATUT}
      d = sum(1 for x in t["tools"] if x["class"] == "dangerous")
      total += len(t["tools"])
      entetes = [f"# {full}", "",
                 f"Famille : `{famille}` | Alias CLI : "
                 + (f"`{ALIAS[full]}`" if full in ALIAS else "aucun") +
                 f" | Outils : {len(t['tools'])} (verifie {c['proven']}, echec {c['failed']},"
               f" inconnu {c['unknown']}, dont {d} classes DANGEREUX)", "",
                 "Description reprise du dump `describe_toolset`, en anglais ou en francais selon le "
                 "toolset, recopiee sans reformulation (accents retires). Tri : decroissant du nombre "
                 "d'arguments requis, puis nom. Statuts : `verifie` = appele puis relu dans l'editeur, "
                 "`echec` = appele et refuse, `inconnu` = jamais appele (tout outil `DANGEREUX` est "
                 "inconnu).", ""]
      corps = sorted(t["tools"], key=lambda x: (-len((x["params_schema"] or {}).get("required", [])),
                                                 x["tool"].lower()))
      ecrire(os.path.join(a.out, famille, slug(full) + ".md"),
             "\n".join(entetes + [ligne(x) for x in corps] + [""]))
      lignes_sommaire.append(
          f"| `{famille}` | [{slug(full)}.md]({famille}/{slug(full)}.md) | `{full}` | "
          f"{ALIAS.get(full, '-')} | {len(t['tools'])} | {c['proven']} | {c['failed']} | "
          f"{c['unknown']} |")
  ecrire(os.path.join(a.out, "sommaire.md"), "\n".join(
      [f"# Les {total} outils MCP releves le {net(meta.get('date', ''))[:10]}", "",
       f"Campagne : {net(meta.get('campaign_status', ''), 240)}.",
       f"Version : {net(meta.get('uefn_version', ''))} | niveau de test : "
       f"`{net(str(meta.get('test_level', '')).split(' (')[0])}` | pagination : "
       f"{meta.get('pagination_page_size')}", "",
       "Relancer la generation : `python script/build_tools_index.py --inventory DIR "
       "--capabilities FICHIER --out mcp_tools`.", "",
       "| Famille | Fichier | Toolset | Alias | Outils | verifie | echec | inconnu |",
       "| --- | --- | --- | --- | --- | --- | --- | --- |"] + lignes_sommaire +
      ["", f"Total : {total} outils dans {len(ts)} toolsets.", ""]))
  print(f"{total} outils, {len(ts)} toolsets ecrits dans {a.out}")


if __name__ == "__main__":
  main()
