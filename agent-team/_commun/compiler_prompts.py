#!/usr/bin/env python3
"""Compile le prompt COMPACT envoye a chaque agent Flash : agent-team/<Agent>/prompt.flash.md.

Pourquoi : un agent chargeait ~19 000 tokens (persona + SKILL + regles + memoire + schema JSON
complet + exemples + tool-output), alors que util/multi_agent/03-parametrage-agents.md vise un
prompt de quelques centaines de lignes. Un modele Flash suit mal un long mur de regles (context
rot, WP3 p.9). Les fichiers sources restent la DOCUMENTATION de reference ; le schema complet reste
utilise par le validateur Python. Seul prompt.flash.md est injecte au modele.

Regles de compilation (deterministes, aucune IA) :
  - persona.md : garde, citations « (WPn p.X) » et meta-commentaires retires ;
  - regles-engagement.md : la section « 1. Regles communes » (recopiee 21 fois) est remplacee par
    _commun/regles-communes-flash.md ; la « Regle speciale Design » est gardee ;
  - long-term-memory.json : rendu en texte compact, sans metadonnees ni chiffres_de_reference ;
  - schema-de-sortie.json : SQUELETTE (champs, types, enums, obligatoires), sans descriptions ;
  - un seul bon exemple (jamais un REJET), minifie, sans annotations ;
  - tool-output/*.md : seulement les tableaux « pieges » / « echecs reconnus ».

Usage :
  python compiler_prompts.py              compile les 21 agents et affiche le bilan
  python compiler_prompts.py --check      echoue si un prompt est perime ou depasse le budget
  python compiler_prompts.py --agent Level_Designer --budget 6000
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEAM = os.path.dirname(HERE)
OUT_NAME = "prompt.flash.md"
BUDGET_DEFAUT = 11000         # PLAFOND dur (anti-regression) : au-dela, la compilation echoue
CIBLE = 6000                  # objectif : au-dela, le bilan signale une passe editoriale a faire
CHARS_PAR_TOKEN = 3.5         # estimation pour du francais technique (pas un tokenizer exact)
MEMOIRE_IGNOREE = {"$schema", "$id", "$comment", "agent", "description", "langue",
                   "chiffres_de_reference", "_comment",
                   # regles de pipeline destinees au Producer ; le role de l'agent les redit deja
                   "decisions_de_pipeline"}
EXEMPLE_IGNORE = {"exemple_annotations", "_comment", "$comment", "golden_example_ref"}
NOMS_AGENTS = {os.path.basename(os.path.normpath(d)) for d in glob.glob(os.path.join(TEAM, "*", ""))
               if os.path.exists(os.path.join(d, "persona.md"))}
FRONTIER = {"Producer_Orchestrator"}   # modele Frontier : hors budget Flash, prompt non compile


# ------------------------------------------------------------------ nettoyage de texte

CITATION = re.compile(r"\s*\((?:[^()]|\([^()]*\))*?\bWP\d[^()]*(?:\([^()]*\)[^()]*)*\)")
MARQUEUR = re.compile(r"\s*`?\[(?:adaptation maison|AM)[^\]]*\]`?", re.I)
WP_NU = re.compile(r"\s*\bWP\d p\.\d+(?:[-/]p?\.?\d+)*\b")


def nettoyer(texte: str) -> str:
  lignes = []
  for l in texte.splitlines():
    if l.lstrip().startswith(">"):          # blocs de citation / meta
      continue
    l = CITATION.sub("", l)
    l = MARQUEUR.sub("", l)
    l = WP_NU.sub("", l)
    l = l.replace("**", "")
    lignes.append(l.rstrip())
  texte = "\n".join(lignes)
  texte = re.sub(r"<!--.*?-->", "", texte, flags=re.S)
  texte = re.sub(r"\n{3,}", "\n\n", texte)
  return texte.strip()


def sections_md(texte: str) -> list[tuple[str, str]]:
  """Decoupe un markdown en (titre, corps) au niveau ## (le titre # est ignore)."""
  out, titre, corps = [], None, []
  for l in texte.splitlines():
    if l.startswith("## "):
      if titre is not None:
        out.append((titre, "\n".join(corps)))
      titre, corps = l[3:].strip(), []
    elif l.startswith("# ") and titre is None:
      continue
    else:
      corps.append(l)
  if titre is not None:
    out.append((titre, "\n".join(corps)))
  return out


def lire(path: str) -> str:
  with open(path, encoding="utf-8") as f:
    return f.read()


# ------------------------------------------------------------------ morceaux du prompt

LIGNES_META = re.compile(r"^\|\s*(ID|N° d'agent|Modèle|Alias)\s*\|", re.I)


def bloc_persona(agent_dir: str) -> str:
  texte = re.sub(r"^# .*\n", "", lire(os.path.join(agent_dir, "persona.md")), count=1)
  texte = "\n".join(l for l in texte.splitlines() if not LIGNES_META.match(l))
  return nettoyer(texte)


def bloc_regles(agent_dir: str) -> str:
  p = os.path.join(agent_dir, "skill", "regles-engagement.md")
  if not os.path.exists(p):
    return ""
  garde = []
  for titre, corps in sections_md(lire(p)):
    if re.match(r"1\.\s*R[eè]gles communes", titre, re.I):
      # garder seulement les sous-sections propres (ex. « Regle speciale Design »)
      for m in re.finditer(r"(### .*?)(?=\n### |\Z)", corps, re.S):
        if "commune" not in m.group(1).split("\n")[0].lower():
          garde.append(m.group(1))
      continue
    garde.append(f"## {titre}\n{corps}")
  return nettoyer("\n\n".join(garde)).replace("## ", "### ")


def bloc_outils(agent_dir: str) -> str:
  p = os.path.join(agent_dir, "skill", "outils.md")
  if not os.path.exists(p):
    return ""
  garde = [f"## {t}\n{c}" for t, c in sections_md(lire(p))
           if "pour comprendre" not in t.lower()]          # sections explicatives, pas des regles
  return nettoyer("\n\n".join(garde)).replace("## ", "### ")


def rendre(v, indent=0) -> list[str]:
  """Rend une valeur JSON en texte compact (moins de tokens que du JSON indente)."""
  pad = "  " * indent
  if isinstance(v, dict):
    if {"signe", "conduite"} <= set(v):          # piege signe / cause / conduite
      return [f"{pad}- SI {v['signe']} → {v['conduite']}"]
    out = []
    for k, x in v.items():
      if k in MEMOIRE_IGNOREE:
        continue
      if isinstance(x, list) and x and all(not isinstance(e, (dict, list)) for e in x) \
          and sum(len(str(e)) for e in x) <= 160:
        out.append(f"{pad}{k}: " + ", ".join(str(e) for e in x))   # petite liste : une ligne
      elif isinstance(x, (dict, list)):
        out.append(f"{pad}{k}:")
        out += rendre(x, indent + 1)
      else:
        out.append(f"{pad}{k}: {x}")
    return out
  if isinstance(v, list):
    out = []
    for x in v:
      if isinstance(x, (dict, list)):
        sous = rendre(x, indent + 1)
        if sous and not sous[0].lstrip().startswith("- "):
          sous[0] = f"{pad}- " + sous[0].lstrip()
        out += sous
      else:
        out.append(f"{pad}- {x}")
    return out
  return [f"{pad}{v}"]


def bloc_memoire(agent_dir: str) -> str:
  p = os.path.join(agent_dir, "skill", "long-term-memory.json")
  if not os.path.exists(p):
    return ""
  data = json.loads(lire(p))
  return nettoyer("\n".join(rendre({k: v for k, v in data.items() if k not in MEMOIRE_IGNOREE})))


def resoudre(schema: dict, racine: dict) -> dict:
  ref = schema.get("$ref")
  if ref and ref.startswith("#/"):
    node = racine
    for part in ref[2:].split("/"):
      node = node.get(part, {})
    return node
  return schema


def type_court(s: dict, racine: dict) -> str:
  s = resoudre(s, racine)
  if "const" in s:
    return f"= {json.dumps(s['const'], ensure_ascii=False)}"
  if "enum" in s:
    if len(s["enum"]) >= 15 and set(s["enum"]) <= NOMS_AGENTS:
      return "nom d'un agent du studio (ex. \"Producer_Orchestrator\")"
    vals = [json.dumps(x, ensure_ascii=False) for x in s["enum"]]
    return "un de " + " | ".join(vals)
  t = s.get("type", "")
  if isinstance(t, list):
    t = "|".join(t)
  extra = []
  if "pattern" in s and len(s["pattern"]) <= 40:
    extra.append(f"motif {s['pattern']}")
  for k, lab in (("maxLength", "≤"), ("maximum", "≤"), ("minItems", "≥"), ("maxItems", "items ≤")):
    if k in s:
      extra.append(f"{lab}{s[k]}" if k != "minItems" else f"≥{s[k]} élément(s)")
  return (t or "objet") + (f" ({', '.join(extra)})" if extra else "")


def squelette(s: dict, racine: dict, indent: int, prof: int, vus: set) -> list[str]:
  s = resoudre(s, racine)
  pad = "  " * indent
  out = []
  if prof > 5:
    return out
  props = s.get("properties", {})
  req = set(s.get("required", []))
  for nom, sub in props.items():
    if nom in EXEMPLE_IGNORE or nom.startswith("_"):
      continue
    subr = resoudre(sub, racine)
    marque = "*" if nom in req else ""
    if subr.get("type") == "object" or "properties" in subr:
      out.append(f"{pad}- {nom}{marque}: objet")
      ref = sub.get("$ref")
      if ref in vus:
        continue
      out += squelette(subr, racine, indent + 1, prof + 1, vus | ({ref} if ref else set()))
    elif subr.get("type") == "array" and isinstance(subr.get("items"), dict):
      it = resoudre(subr["items"], racine)
      if it.get("type") == "object" or "properties" in it:
        out.append(f"{pad}- {nom}{marque}: liste d'objets")
        out += squelette(it, racine, indent + 1, prof + 1, vus)
      else:
        out.append(f"{pad}- {nom}{marque}: liste de {type_court(it, racine)}")
    else:
      out.append(f"{pad}- {nom}{marque}: {type_court(subr, racine)}")
  return out


def bloc_schema(agent_dir: str) -> str:
  p = os.path.join(agent_dir, "skill", "schema-de-sortie.json")
  if not os.path.exists(p):
    return ""
  sch = json.loads(lire(p))
  lignes = squelette(sch, sch, 0, 0, set())
  return ("`*` = champ obligatoire. Aucun autre champ n'est accepté.\n" + "\n".join(lignes)).strip()


MAX_OBJETS_EXEMPLE = 3


def nettoyer_exemple(v, coupes: list):
  """Retire les annotations ; limite les listes d'OBJETS a 3 (la forme suffit au few-shot).
  Les listes de valeurs simples (ex. lignes d'une matrice de grille) restent entieres."""
  if isinstance(v, dict):
    return {k: nettoyer_exemple(x, coupes) for k, x in v.items() if k not in EXEMPLE_IGNORE}
  if isinstance(v, list):
    if len(v) > MAX_OBJETS_EXEMPLE and all(isinstance(x, dict) for x in v):
      coupes.append(len(v))
      v = v[:MAX_OBJETS_EXEMPLE]
    return [nettoyer_exemple(x, coupes) for x in v]
  return v


def bloc_exemple(agent_dir: str) -> tuple[str, str]:
  bons = sorted(f for f in glob.glob(os.path.join(agent_dir, "skill", "exemples", "*.json"))
                if not os.path.basename(f).upper().startswith("REJET"))
  if not bons:
    return "", ""
  coupes: list = []
  data = nettoyer_exemple(json.loads(lire(bons[0])), coupes)
  texte = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
  if coupes:
    texte += (f"\n```\n(Extrait : {len(coupes)} liste(s) d'objets limitée(s) à {MAX_OBJETS_EXEMPLE} "
              f"éléments ; ton livrable contient TOUS les éléments nécessaires.)\n```json")
  return os.path.basename(bons[0]), texte


def bloc_pieges_outils(agent_dir: str) -> str:
  garde = []
  for p in sorted(glob.glob(os.path.join(agent_dir, "skill", "tool-output", "*.md"))):
    for titre, corps in sections_md(lire(p)):
      if re.search(r"pi[eè]ge|[ée]checs? reconnus", titre, re.I):
        tableau = "\n".join(l for l in corps.splitlines() if l.startswith("|"))
        if tableau:
          garde.append(f"Source {os.path.basename(p)} — {titre}\n{tableau}")
  return nettoyer("\n\n".join(garde))


# ------------------------------------------------------------------ assemblage

def sources(agent_dir: str) -> list[str]:
  fichiers = [os.path.join(agent_dir, "persona.md"), os.path.join(HERE, "regles-communes-flash.md")]
  fichiers += sorted(glob.glob(os.path.join(agent_dir, "skill", "*.md")))
  fichiers += sorted(glob.glob(os.path.join(agent_dir, "skill", "*.json")))
  fichiers += sorted(glob.glob(os.path.join(agent_dir, "skill", "exemples", "*.json")))
  fichiers += sorted(glob.glob(os.path.join(agent_dir, "skill", "tool-output", "*.md")))
  fichiers.append(os.path.abspath(__file__))
  return [f for f in fichiers if os.path.exists(f)]


def empreinte(agent_dir: str) -> str:
  h = hashlib.sha256()
  for f in sources(agent_dir):
    h.update(os.path.relpath(f, TEAM).replace("\\", "/").encode())
    with open(f, "rb") as fh:
      h.update(fh.read())
  return h.hexdigest()[:16]


def compiler(agent_dir: str) -> str:
  nom = os.path.basename(os.path.normpath(agent_dir))
  parts = [
      f"# {nom} — prompt Flash",
      f"<!-- GENERE par agent-team/_commun/compiler_prompts.py ; ne pas editer a la main. "
      f"sources:{empreinte(agent_dir)} -->",
      "## RÔLE\n" + bloc_persona(agent_dir),
      "## RÈGLES COMMUNES\n" + lire(os.path.join(HERE, "regles-communes-flash.md")).strip(),
  ]
  for titre, bloc in (("RÈGLES DU RÔLE", bloc_regles(agent_dir)),
                      ("OUTILS AUTORISÉS", bloc_outils(agent_dir)),
                      ("MÉMOIRE (faits stables)", bloc_memoire(agent_dir)),
                      ("PIÈGES D'OUTILS", bloc_pieges_outils(agent_dir)),
                      ("FORMAT DE SORTIE (vérifié par code)", bloc_schema(agent_dir))):
    if bloc:
      parts.append(f"## {titre}\n{bloc}")
  nom_ex, ex = bloc_exemple(agent_dir)
  if ex:
    parts.append(f"## EXEMPLE DE LIVRABLE ACCEPTÉ ({nom_ex})\n```json\n{ex}\n```")
  return "\n\n".join(parts).strip() + "\n"


def tokens(texte: str) -> int:
  return round(len(texte) / CHARS_PAR_TOKEN)


def taille_avant(agent_dir: str) -> int:
  total = 0
  for f in ("persona.md", "SKILL.md", "skill/regles-engagement.md", "skill/long-term-memory.json",
            "skill/schema-de-sortie.json", "skill/outils.md"):
    p = os.path.join(agent_dir, f)
    if os.path.exists(p):
      total += len(lire(p))
  for p in glob.glob(os.path.join(agent_dir, "skill", "exemples", "*.json")) + \
      glob.glob(os.path.join(agent_dir, "skill", "tool-output", "*.md")):
    total += len(lire(p))
  return round(total / CHARS_PAR_TOKEN)


def agents() -> list[str]:
  return sorted(d for d in glob.glob(os.path.join(TEAM, "*", ""))
                if not os.path.basename(os.path.normpath(d)).startswith("_")
                and os.path.basename(os.path.normpath(d)) not in FRONTIER
                and os.path.exists(os.path.join(d, "persona.md")))


def main() -> int:
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  ap.add_argument("--agent")
  ap.add_argument("--check", action="store_true")
  ap.add_argument("--budget", type=int, default=BUDGET_DEFAUT)
  a = ap.parse_args()
  cibles = [d for d in agents() if not a.agent or os.path.basename(os.path.normpath(d)) == a.agent]
  if not cibles:
    print(f"agent introuvable : {a.agent}")
    return 1
  echecs = 0
  print(f"{'agent':28} {'avant':>7} {'apres':>7}  statut")
  for d in cibles:
    nom = os.path.basename(os.path.normpath(d))
    texte = compiler(d)
    out = os.path.join(d, OUT_NAME)
    n = tokens(texte)
    statut = "OK" if n <= CIBLE else f"OK (au-dessus de la cible {CIBLE} : passe editoriale utile)"
    if n > a.budget:
      statut, echecs = f"HORS BUDGET (>{a.budget})", echecs + 1
    if a.check:
      if not os.path.exists(out) or lire(out) != texte:
        statut, echecs = "PERIME : relancer compiler_prompts.py", echecs + 1
    else:
      with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(texte)
    print(f"{nom:28} {taille_avant(d):>7} {n:>7}  {statut}")
  avant = sum(taille_avant(d) for d in cibles)
  apres = sum(tokens(compiler(d)) for d in cibles)
  print(f"\nTotal : {avant} -> {apres} tokens ({round(100 * (apres - avant) / avant)} %), "
        f"moyenne {round(apres / len(cibles))} par agent")
  print(f"(tokens estimes a {CHARS_PAR_TOKEN} caracteres/token ; plafond {a.budget}, cible {CIBLE})")
  return 1 if echecs else 0


if __name__ == "__main__":
  sys.exit(main())
