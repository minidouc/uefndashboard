#!/usr/bin/env python3
"""Branche agent-team/ sur Qoder / QoderWork (~/.qoder), sans copie a maintenir.

  - ~/.qoder/skills/<Agent> et ~/.qoder/skills/_commun deviennent des JONCTIONS vers agent-team/ :
    chaque correction du projet est vue tout de suite par le harness (fini les copies figees).
  - ~/.qoder/agents/<Agent>.md : l'en-tete (name, model, permissionMode, skills) est garde ;
    le corps devient le prompt compile prompt.flash.md (le Producer garde son persona.md).
  - Avant toute modification, l'existant est sauvegarde dans ~/.qoder/_backup_agent-team/<date>/.

  python agent-team/_commun/sync_qoder.py                     # synchronise
  python agent-team/_commun/sync_qoder.py --check             # rc 1 si un agent Qoder est perime
  python agent-team/_commun/sync_qoder.py --modele-producer performance
  (--qoder-dir pour un autre dossier, ex. tests ; variable QODER_DIR equivalente)
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
TEAM = os.path.dirname(HERE)
PRODUCER = "Producer_Orchestrator"
MODELE_FLASH = "efficient"     # "Standard reasoning at low cost" dans le selecteur Qoder

sys.path.insert(0, HERE)
import compiler_prompts  # noqa: E402


def qoder_dir(arg: str | None) -> str:
  return os.path.normpath(arg or os.environ.get("QODER_DIR")
                          or os.path.join(os.path.expanduser("~"), ".qoder"))


def roles() -> list[str]:
  return sorted(os.path.basename(os.path.normpath(d)) for d in compiler_prompts.agents()) + [PRODUCER]


def corps_attendu(role: str) -> str:
  nom = "persona.md" if role == PRODUCER else compiler_prompts.OUT_NAME
  with open(os.path.join(TEAM, role, nom), encoding="utf-8") as f:
    return f.read().strip() + "\n"


def lire_agent(path: str) -> tuple[str, str]:
  """(en-tete sans les ---, corps) ; en-tete vide si le fichier n'en a pas."""
  with open(path, encoding="utf-8") as f:
    t = f.read()
  m = re.match(r"---\n(.*?)\n---\n?(.*)", t, re.S)
  return (m.group(1), m.group(2)) if m else ("", t)


def description(role: str) -> str:
  """Ligne `description:` du SKILL.md du role (deja entre guillemets)."""
  with open(os.path.join(TEAM, role, "SKILL.md"), encoding="utf-8") as f:
    m = re.search(r"^description:\s*(.+)$", f.read(), re.M)
  return m.group(1).strip() if m else f'"{role} du studio UEFN."'


def entete(role: str, existant: str, modele_producer: str | None) -> str:
  lignes = existant.splitlines() if existant else [f"name: {role}", "permissionMode: auto",
                                                    "skills:", f"  - {role}"]
  if not any(l.startswith("model:") for l in lignes):
    lignes.insert(1, f"model: {MODELE_FLASH}")
  # Sans description non vide, Qoder rejette l'agent (« Validation failed ... description ») et
  # lance le sous-agent comme assistant generique, sur le modele de la session.
  lignes = [l for l in lignes if not re.match(r"description:\s*(\"\"|'')?\s*$", l)]
  if not any(l.startswith("description:") for l in lignes):
    lignes.insert(1, f"description: {description(role)}")
  if role == PRODUCER and modele_producer:
    lignes = [f"model: {modele_producer}" if l.startswith("model:") else l for l in lignes]
  return "\n".join(lignes)


def est_jonction(path: str) -> bool:
  return os.path.isdir(path) and os.path.realpath(path) != os.path.abspath(path)


def jonction(lien: str, cible: str) -> None:
  if os.name == "nt":
    # mklink exige des antislashs : un chemin en / echoue sans message utile.
    subprocess.run(["cmd", "/c", "mklink", "/J", os.path.normpath(lien), os.path.normpath(cible)],
                   check=True, capture_output=True)
  else:
    os.symlink(cible, lien, target_is_directory=True)


def etat(q: str) -> list[dict]:
  ecarts = []
  for role in roles():
    p = os.path.join(q, "agents", f"{role}.md")
    if not os.path.exists(p) or lire_agent(p)[1].strip() + "\n" != corps_attendu(role):
      ecarts.append({"type": "AGENT_PERIME", "role": role, "fichier": p})
    elif not re.search(r"^description:\s*\S", lire_agent(p)[0], re.M):
      ecarts.append({"type": "AGENT_SANS_DESCRIPTION", "role": role, "fichier": p,
                     "effet": "Qoder rejette l'agent : le sous-agent tourne sans son role"})
  for nom in roles() + ["_commun"]:
    s = os.path.join(q, "skills", nom)
    if not (est_jonction(s) and os.path.samefile(s, os.path.join(TEAM, nom))):
      ecarts.append({"type": "SKILL_NON_RELIE", "role": nom, "dossier": s})
  return ecarts


def synchroniser(q: str, modele_producer: str | None) -> dict:
  sauvegarde = os.path.join(q, "_backup_agent-team", datetime.now().strftime("%Y-%m-%d_%H%M%S"))
  fait = {"sauvegarde": sauvegarde, "agents": [], "jonctions": []}
  os.makedirs(os.path.join(q, "agents"), exist_ok=True)
  os.makedirs(os.path.join(q, "skills"), exist_ok=True)
  for role in roles():
    p = os.path.join(q, "agents", f"{role}.md")
    tete = ""
    if os.path.exists(p):
      os.makedirs(os.path.join(sauvegarde, "agents"), exist_ok=True)
      shutil.copy2(p, os.path.join(sauvegarde, "agents"))
      tete = lire_agent(p)[0]
    with open(p, "w", encoding="utf-8", newline="\n") as f:
      f.write(f"---\n{entete(role, tete, modele_producer)}\n---\n\n{corps_attendu(role)}")
    fait["agents"].append(role)
  for nom in roles() + ["_commun"]:
    s = os.path.join(q, "skills", nom)
    cible = os.path.join(TEAM, nom)
    if est_jonction(s):
      if os.path.samefile(s, cible):
        continue
      os.rmdir(s) if os.name == "nt" else os.unlink(s)   # retire le lien, jamais la cible
    elif os.path.exists(s):
      os.makedirs(os.path.join(sauvegarde, "skills"), exist_ok=True)
      shutil.move(s, os.path.join(sauvegarde, "skills", nom))
    jonction(s, cible)
    fait["jonctions"].append(nom)
  return fait


def main() -> int:
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("--qoder-dir")
  ap.add_argument("--check", action="store_true")
  ap.add_argument("--modele-producer", help="ex. performance, efficient (defaut : inchange)")
  a = ap.parse_args()
  q = qoder_dir(a.qoder_dir)
  sys.stdout.reconfigure(encoding="utf-8")
  if a.check:
    ecarts = etat(q)
    print(json_dump({"status": "FAILED" if ecarts else "PASSED", "qoder": q, "ecarts": ecarts}))
    return 1 if ecarts else 0
  fait = synchroniser(q, a.modele_producer)
  ecarts = etat(q)
  print(json_dump({"status": "FAILED" if ecarts else "PASSED", "qoder": q, **fait,
                   "ecarts_restants": ecarts}))
  return 1 if ecarts else 0


def json_dump(d) -> str:
  import json
  return json.dumps(d, ensure_ascii=False, indent=1)


if __name__ == "__main__":
  sys.exit(main())
