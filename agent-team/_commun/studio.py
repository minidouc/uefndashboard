#!/usr/bin/env python3
"""Outils du Producer, utilisables depuis n'importe quel harness qui a un shell.

Deux commandes, toutes deux deterministes (aucun modele n'est appele) :

  dispatch  --mission <handoff Producer -> agent>
      Ecrit UN fichier de mission autonome (prompt.flash.md + mission + fichiers d'entree +
      consignes de rendu) et donne la ligne exacte a passer a l'outil de sous-agent du harness.
      Si une validation precedente de la meme mission a echoue, ses corrections sont incluses.

  validate  <livrable.json> [--agent X] [--mission M] [--workspace W]
      Juge le livrable par CODE : JSON (extrait du texte si besoin), schema complet de l'agent,
      emetteur, mission_ref, budget de tokens, legalite des chemins d'assets (catalogue commun),
      validator_clean relu dans le workspace, compteur de tentatives. Rend une decision conseillee
      (VALIDATE / LANCER_VERIFICATIONS / REJECT / ESCALATE_USER / HALT_PHASE) et, en cas d'echec,
      le message correctif a renvoyer tel quel a l'agent. `--essai` = auto-controle du sous-agent
      avant de rendre : meme jugement, aucune tentative comptee.

Code retour : 0 = PASSED, 1 = FAILED, 2 = erreur d'usage. Sortie : JSON sur stdout.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TEAM = os.path.dirname(HERE)
REPO = os.path.dirname(TEAM)
SCRIPT_CLI = os.path.join(REPO, "skill", "uefn_map_creator", "script")
HANDOFF_SCHEMA = os.path.join(REPO, "util", "multi_agent", "templates", "handoff.schema.json")
PRODUCER = "Producer_Orchestrator"
MEMOIRE_PRODUCER = os.path.join(TEAM, PRODUCER, "skill", "long-term-memory.json")
PROMPT = "prompt.flash.md"
CHARS_PAR_TOKEN = 3.5
PLAFOND_HANDOFF = 4000          # 04-contrat-handoff.md, regle 2
MAX_ERREURS = 15                # au-dela, un Flash ne corrige plus rien : on coupe

sys.path.insert(0, HERE)
sys.path.insert(0, SCRIPT_CLI)
import compiler_prompts  # noqa: E402
from uefn_spatial_cli import legal_status, SPEC_FILES, placed_path  # noqa: E402

# Criteres d'acceptance que ce script ne peut pas cocher seul : la commande qui les prouve.
A_LANCER = {
    "0_overlap": "audit-scene --live",
    "0_floating": "audit-scene --live",
    "spawn_reachable": "check-navigation",
    "mcp_ok": "preflight",
    "clamp_deterministe": "compile-transforms",
}
# Une liste d'assets refuses ou bloques cite legitimement des chemins illegaux.
CLE_LISTE_NOIRE = re.compile(r"block|refus|reject|illegal|interdit|forbidden|bannis", re.I)
CHEMIN_ASSET = re.compile(r"^/[A-Za-z0-9_\-]+/[^\s\"']+$")


def emit(res: dict, rc: int) -> int:
  sys.stdout.reconfigure(encoding="utf-8")
  print(json.dumps(res, ensure_ascii=False, indent=1))
  return rc


def maintenant() -> str:
  return datetime.now(timezone.utc).isoformat(timespec="seconds")


def lire_json(path: str):
  with open(path, encoding="utf-8") as f:
    return json.load(f)


def ecrire_json(path: str, data) -> None:
  os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
  with open(path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)


def tokens(texte: str) -> int:
  return round(len(texte) / CHARS_PAR_TOKEN)


def agents_flash() -> list[str]:
  return [os.path.basename(os.path.normpath(d)) for d in compiler_prompts.agents()]


def schema_agent(agent: str) -> dict:
  return lire_json(os.path.join(TEAM, agent, "skill", "schema-de-sortie.json"))


def erreurs_schema(data, schema: dict) -> list[dict]:
  from jsonschema import validators
  v = validators.validator_for(schema)(schema)
  out = []
  for e in sorted(v.iter_errors(data), key=lambda e: list(map(str, e.absolute_path))):
    chemin = "/".join(map(str, e.absolute_path)) or "(racine)"
    out.append({"type": "SCHEMA", "ou": chemin, "detail": e.message[:300]})
  return out


def extraire_json(texte: str):
  """JSON brut, ou le premier bloc ```json``` / objet {...} d'une reponse en texte libre.
  Rend (donnees, extrait: bool) ; leve ValueError si rien n'est lisible."""
  try:
    return json.loads(texte), False
  except ValueError:
    pass
  for m in re.finditer(r"```(?:json)?\s*\n(.*?)```", texte, re.S):
    try:
      return json.loads(m.group(1)), True
    except ValueError:
      continue
  debut, fin = texte.find("{"), texte.rfind("}")
  if 0 <= debut < fin:
    return json.loads(texte[debut:fin + 1]), True
  raise ValueError("aucun objet JSON trouve")


def chaines(v, chemin=""):
  if isinstance(v, dict):
    for k, x in v.items():
      yield from chaines(x, f"{chemin}/{k}")
  elif isinstance(v, list):
    for i, x in enumerate(v):
      yield from chaines(x, f"{chemin}/{i}")
  elif isinstance(v, str):
    yield chemin, v


def erreurs_legalite(payload, autoriser_non_verifies: bool) -> list[dict]:
  out = []
  for chemin, s in chaines(payload):
    s = s.strip()
    # /Fortnite.com/..., /Verse.org/... : modules Verse, pas des assets.
    if not CHEMIN_ASSET.match(s) or "." in s.split("/")[1] or CLE_LISTE_NOIRE.search(chemin):
      continue
    statut = legal_status(s)
    if statut == "REFUSED":
      out.append({"type": "ILLEGAL_ASSET_PATH", "ou": "payload" + chemin, "detail":
                  f"{s} est refuse par le validateur UEFN : prendre un asset de "
                  "agent-team/_commun/catalogue-verifie.json -> acceptes."})
    elif statut == "UNVERIFIED" and not autoriser_non_verifies:
      out.append({"type": "UNVERIFIED_ASSET_PATH", "ou": "payload" + chemin, "detail":
                  f"{s} n'est pas dans le catalogue commun : legalite non prouvee. Prendre un "
                  "asset 'acceptes' ou ecrire UNKNOWN."})
  return out


def verdict_validateur(workspace: str) -> dict | None:
  """Erreur si 06b_validator_report.json manque, n'est pas PASSED, ou date d'avant le dernier
  changement de scene ; None si la preuve tient."""
  rapport = os.path.join(workspace, "06b_validator_report.json")
  if not os.path.exists(rapport):
    return {"type": "VALIDATOR_ABSENT", "ou": rapport,
            "detail": "aucun verdict du validateur UEFN : lancer check-validator."}
  statut = lire_json(rapport).get("status")
  if statut != "PASSED":
    return {"type": "VALIDATOR_NON_PROPRE", "ou": rapport,
            "detail": f"status {statut!r} (seul PASSED prouve la legalite ; UNKNOWN ne compte pas)."}
  scene = [os.path.join(workspace, f) for f in SPEC_FILES] + [placed_path(workspace)]
  plus_recent = max((os.path.getmtime(f) for f in scene if os.path.exists(f)), default=0)
  if plus_recent > os.path.getmtime(rapport):
    return {"type": "VALIDATOR_PERIME", "ou": rapport,
            "detail": "la scene a change apres le dernier check-validator : le relancer."}
  return None


def caps() -> dict:
  try:
    return lire_json(MEMOIRE_PRODUCER).get("iteration_caps", {})
  except (OSError, ValueError):
    return {}


def chemin_tentatives(livrable: str) -> str:
  return os.path.join(os.path.dirname(os.path.abspath(livrable)), ".tentatives.json")


def rapport_validation(livrable: str) -> str:
  return os.path.splitext(os.path.abspath(livrable))[0] + ".validation.json"


def message_correctif(agent: str, livrable: str, erreurs: list[dict]) -> str:
  lignes = [f"Ton livrable {os.path.basename(livrable)} est REFUSÉ par le validateur (code, pas un "
            "avis). Corrige UNIQUEMENT ces points, garde tout le reste identique, puis réécris le "
            f"fichier {os.path.abspath(livrable)} :"]
  for i, e in enumerate(erreurs[:MAX_ERREURS], 1):
    lignes.append(f"{i}. [{e['type']}] {e['ou']} : {e['detail']}")
  if len(erreurs) > MAX_ERREURS:
    lignes.append(f"(+{len(erreurs) - MAX_ERREURS} autres erreurs : corrige d'abord celles-ci)")
  lignes.append("Si une valeur t'est inconnue, écris UNKNOWN au lieu d'inventer.")
  return "\n".join(lignes)


# --------------------------------------------------------------------------- validate

def cmd_validate(livrable: str, agent: str | None, mission: str | None, workspace: str | None,
                 autoriser_non_verifies: bool, essai: bool = False) -> int:
  res = {"commande": "validate", "livrable": os.path.abspath(livrable), "a": maintenant()}
  if not os.path.exists(livrable):
    res.update(status="FAILED", erreurs=[{"type": "LIVRABLE_ABSENT", "ou": livrable,
               "detail": "l'agent n'a pas ecrit son fichier de rendu."}])
    return emit(res, 1)
  with open(livrable, encoding="utf-8", errors="replace") as f:
    brut = f.read()
  erreurs, avertissements = [], []
  try:
    data, extrait = extraire_json(brut)
  except ValueError as e:
    res.update(status="FAILED", decision_conseillee="REJECT",
               erreurs=[{"type": "JSON_ILLISIBLE", "ou": "(fichier)", "detail": str(e)[:200]}])
    res["message_correctif"] = message_correctif(agent or "?", livrable, res["erreurs"])
    return emit(res, 1)
  if extrait:
    # On garde la reponse brute a cote, et le fichier devient le JSON seul.
    with open(livrable + ".brut.txt", "w", encoding="utf-8") as f:
      f.write(brut)
    ecrire_json(livrable, data)
    avertissements.append({"type": "JSON_EXTRAIT_DU_TEXTE", "ou": "(fichier)", "detail":
                           "la reponse contenait du texte autour du JSON ; JSON extrait, brut "
                           "conserve dans .brut.txt."})

  agent = agent or (data.get("from") if isinstance(data, dict) else None)
  res["agent"] = agent
  if agent not in agents_flash():
    res.update(status="FAILED", erreurs=[{"type": "AGENT_INCONNU", "ou": "from",
               "detail": f"{agent!r} n'est pas un agent Flash de agent-team/."}])
    return emit(res, 2)

  erreurs += erreurs_schema(data, schema_agent(agent))
  if isinstance(data, dict):
    if data.get("from") != agent:
      erreurs.append({"type": "MAUVAIS_EMETTEUR", "ou": "from",
                      "detail": f"attendu {agent!r}, recu {data.get('from')!r}."})
    m = lire_json(mission) if mission else None
    if m and m.get("mission_ref") and data.get("mission_ref") != m["mission_ref"]:
      erreurs.append({"type": "MAUVAISE_MISSION", "ou": "mission_ref",
                      "detail": f"attendu {m['mission_ref']!r}, recu {data.get('mission_ref')!r}."})
    taille = tokens(json.dumps(data.get("payload"), ensure_ascii=False))
    budget = min(int(data.get("context_budget_tokens") or PLAFOND_HANDOFF), PLAFOND_HANDOFF)
    res["payload_tokens"] = taille
    if taille > budget:
      erreurs.append({"type": "HANDOFF_TROP_GROS", "ou": "payload", "detail":
                      f"~{taille} tokens > {budget} : ecrire le gros livrable dans un fichier "
                      "separe et ne passer que son nom dans le payload."})
    erreurs += erreurs_legalite(data.get("payload"), autoriser_non_verifies)

    acceptance = [a for a in data.get("acceptance", []) if isinstance(a, str)]
    if m:
      acceptance += [a for a in m.get("acceptance", []) if isinstance(a, str)]
    acceptance = list(dict.fromkeys(acceptance))
    a_lancer, non_verifies = [], []
    for crit in acceptance:
      if crit in ("schema_valid", "pid_legal"):
        continue
      if crit == "validator_clean":
        if workspace:
          e = verdict_validateur(workspace)
          if e:
            erreurs.append(e)
        else:
          a_lancer.append({"critere": crit, "commande": "check-validator"})
      elif crit in A_LANCER:
        a_lancer.append({"critere": crit, "commande": A_LANCER[crit]})
      else:
        non_verifies.append(crit)
    for x in a_lancer:
      x["commande"] = (f"python {os.path.join(SCRIPT_CLI, 'uefn_spatial_cli.py')} {x['commande']}"
                       f" --workspace {workspace or '<workspace>'}")
    res["a_lancer"] = a_lancer
    res["criteres_non_verifiables_par_code"] = non_verifies

  if essai:
    # Auto-controle du sous-agent : meme jugement, mais rien n'est compte ni enregistre. Seule la
    # validation du Producer fait foi pour les tentatives et le message correctif.
    res.update(status="FAILED" if erreurs else "PASSED", essai=True, erreurs=erreurs,
               avertissements=avertissements)
    if erreurs:
      res["message_correctif"] = message_correctif(agent, livrable, erreurs)
    return emit(res, 1 if erreurs else 0)

  # Tentatives : memes seuils que Producer long-term-memory.json -> iteration_caps.
  c = caps()
  cle = f"{agent}|{(data.get('mission_ref') if isinstance(data, dict) else None) or livrable}"
  empreinte = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False)
                             .encode()).hexdigest()[:16]
  journal_path = chemin_tentatives(livrable)
  try:
    journal = lire_json(journal_path)
  except (OSError, ValueError):
    journal = {}
  suivi = journal.setdefault(cle, {"echecs": 0, "empreintes_refusees": []})
  if erreurs:
    deja_vu = empreinte in suivi["empreintes_refusees"]
    suivi["echecs"] += 1
    suivi["empreintes_refusees"].append(empreinte)
    if deja_vu:
      decision = "HALT_PHASE"
      erreurs.append({"type": "PAYLOAD_IDENTIQUE", "ou": "(livrable)", "detail":
                      "meme livrable deja refuse : l'agent tourne en rond (anti-boucle)."})
    elif suivi["echecs"] >= int(c.get("per_role_attempt_escalate", 3)):
      decision = "ESCALATE_USER"
    else:
      decision = "REJECT"
  else:
    suivi["echecs"] = 0
    decision = "LANCER_VERIFICATIONS" if res.get("a_lancer") else "VALIDATE"
  suivi["dernier"] = {"a": res["a"], "status": "FAILED" if erreurs else "PASSED"}
  ecrire_json(journal_path, journal)

  res.update(status="FAILED" if erreurs else "PASSED", decision_conseillee=decision,
             tentatives_echouees=suivi["echecs"], erreurs=erreurs,
             avertissements=avertissements)
  if erreurs:
    res["message_correctif"] = message_correctif(agent, livrable, erreurs)
  ecrire_json(rapport_validation(livrable), res)
  return emit(res, 1 if erreurs else 0)


# --------------------------------------------------------------------------- dispatch

def racine_projet(mission: str) -> str:
  d = os.path.dirname(os.path.abspath(mission))
  return os.path.dirname(d) if os.path.basename(d) == "handoff" else d


def cmd_dispatch(mission: str, agent: str | None, out: str | None) -> int:
  res = {"commande": "dispatch", "mission": os.path.abspath(mission), "a": maintenant()}
  try:
    m = lire_json(mission)
  except (OSError, ValueError) as e:
    res.update(status="FAILED", erreurs=[{"type": "MISSION_ILLISIBLE", "ou": mission,
               "detail": str(e)[:200]}])
    return emit(res, 2)
  erreurs = erreurs_schema(m, lire_json(HANDOFF_SCHEMA))
  dest = [t for t in m.get("to", []) if t in agents_flash()]
  if agent is None and len(dest) == 1:
    agent = dest[0]
  if agent not in agents_flash():
    erreurs.append({"type": "AGENT_INCONNU", "ou": "to",
                    "detail": f"destinataire Flash introuvable ({m.get('to')!r}) : passer --agent."})
  elif agent not in m.get("to", []):
    erreurs.append({"type": "MAUVAIS_DESTINATAIRE", "ou": "to",
                    "detail": f"la mission ne s'adresse pas a {agent}."})
  racine = racine_projet(mission)
  entrees = []
  payload = m.get("payload") if isinstance(m.get("payload"), dict) else {}
  for e in payload.get("inputs_fournis", []) or []:
    p = e if os.path.isabs(e) else os.path.join(racine, e)
    entrees.append(os.path.abspath(p))
    if not os.path.exists(p):
      erreurs.append({"type": "ENTREE_MANQUANTE", "ou": "payload/inputs_fournis", "detail":
                      f"{p} n'existe pas : l'agent inventerait. Produire l'amont d'abord."})
  res["agent"] = agent
  if erreurs:
    res.update(status="FAILED", erreurs=erreurs)
    return emit(res, 1)

  agent_dir = os.path.join(TEAM, agent)
  prompt_path = os.path.join(agent_dir, PROMPT)
  texte = compiler_prompts.compiler(agent_dir)
  if not os.path.exists(prompt_path) or compiler_prompts.lire(prompt_path) != texte:
    with open(prompt_path, "w", encoding="utf-8", newline="\n") as f:
      f.write(texte)
    res["prompt_recompile"] = True

  ident = m.get("handoff_id") or os.path.splitext(os.path.basename(mission))[0]
  rendu = os.path.abspath(out or os.path.join(racine, "handoff", f"{ident}__{agent}__retour.json"))
  validate_cmd = (f"python {os.path.abspath(__file__)} validate {rendu} --mission "
                  f"{os.path.abspath(mission)} --essai")

  parts = [
      f"# MISSION POUR {agent}",
      f"Tu es **{agent}**. Ce fichier contient TOUT ce dont tu as besoin : ton rôle, tes règles, ta "
      "mission. Lis-le en entier avant d'agir. Tu ne parles pas à l'utilisateur.",
      texte.strip(),
      "# TA MISSION (handoff du Producer)",
      "```json\n" + json.dumps(m, ensure_ascii=False, indent=1) + "\n```",
  ]
  if entrees:
    parts += ["# FICHIERS D'ENTRÉE (lis-les, ce sont tes seules sources)",
              "\n".join(f"- {p}" for p in entrees)]
  precedent = rapport_validation(rendu)
  if os.path.exists(precedent):
    v = lire_json(precedent)
    if v.get("status") == "FAILED" and v.get("message_correctif"):
      parts += ["# CORRECTIONS DEMANDÉES (ta tentative précédente a été refusée)",
                v["message_correctif"]]
      res["correction_incluse"] = True
  parts += [
      "# RENDU (obligatoire, dans cet ordre)",
      f"1. Écris ton livrable JSON, et rien d'autre, dans : `{rendu}`\n"
      f"   Il respecte FORMAT DE SORTIE ; `from` = \"{agent}\" ; `mission_ref` = "
      f"\"{m.get('mission_ref', 'UNKNOWN')}\".\n"
      f"2. Lance : `{validate_cmd}`\n"
      "3. Si la sortie dit `\"status\": \"FAILED\"`, applique `message_correctif` et recommence "
      "1-2 (2 essais au maximum).\n"
      "4. Termine par une seule ligne : `RENDU <chemin> <PASSED|FAILED>`.",
  ]
  dossier = os.path.join(racine, "dispatch")
  fichier = os.path.join(dossier, f"{ident}__{agent}.md")
  os.makedirs(dossier, exist_ok=True)
  contenu = "\n\n".join(parts) + "\n"
  with open(fichier, "w", encoding="utf-8", newline="\n") as f:
    f.write(contenu)
  res.update(
      status="PASSED", fichier_mission=fichier, rendu_attendu=rendu, tokens=tokens(contenu),
      prompt_sous_agent=(f"Tu es {agent}. Lis en entier le fichier {fichier} puis exécute "
                         "exactement la mission qu'il contient. Ne fais rien d'autre."),
      apres_retour=f"python {os.path.abspath(__file__)} validate {rendu} --mission "
                   f"{os.path.abspath(mission)} [--workspace <workspace>]")
  return emit(res, 0)


def main() -> int:
  ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  sub = ap.add_subparsers(dest="commande", required=True)
  p = sub.add_parser("dispatch", help="ecrit le fichier de mission d'un sous-agent")
  p.add_argument("--mission", required=True, help="handoff Producer -> agent (uefn.handoff.v1)")
  p.add_argument("--agent", help="si la mission a plusieurs destinataires")
  p.add_argument("--out", help="chemin du livrable attendu (defaut : handoff/<id>__<agent>__retour.json)")
  p = sub.add_parser("validate", help="juge un livrable par code et conseille la decision")
  p.add_argument("livrable")
  p.add_argument("--agent", help="defaut : champ 'from' du livrable")
  p.add_argument("--mission", help="handoff de mission : verifie mission_ref et ses criteres")
  p.add_argument("--workspace", help="workspace de la carte : prouve validator_clean")
  p.add_argument("--essai", action="store_true",
                 help="auto-controle du sous-agent : ne compte pas de tentative")
  p.add_argument("--allow-unverified", action="store_true",
                 help="tolere les chemins /Game/ absents du catalogue (avant check-validator)")
  a = ap.parse_args()
  if a.commande == "dispatch":
    return cmd_dispatch(a.mission, a.agent, a.out)
  return cmd_validate(a.livrable, a.agent, a.mission, a.workspace,
                      a.allow_unverified or os.environ.get("UEFN_ALLOW_UNVERIFIED") == "1",
                      a.essai)


if __name__ == "__main__":
  sys.exit(main())
