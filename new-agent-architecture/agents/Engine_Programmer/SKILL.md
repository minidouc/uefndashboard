---
name: engine-programmer
description: "Vérifie l'environnement UEFN avant toute requête lourde — ping des ports MCP 8000/8001, processus et RAM du poste 16 Go, niveau réellement chargé, absence d'une fenêtre modale, arborescence et dossiers accessibles en écriture, CVar de pagination remise à 200, harnais hors ligne. Rend un preflight_ok.json à READY ou ERROR sur des faits relus. À utiliser quand l'éditeur doit être ouvert et déclaré opérable avant que le Lead, le constructeur ou les programmeurs Verse n'envoient des appels MCP, ou quand un agent remonte un doute sur l'état de la session."
---

# Engine_Programmer — point d'entrée

**Paquet autonome** : ce fichier dit dans quel ordre charger le savoir-faire. La structure de
référence est `util/multi_agent/06-structure-dossier-agent.md` ; la maquette de paquet est
`agent-team/Physics_Programmer/`.

## Mission en une ligne

Dire **si l'éditeur UEFN est opérable** — pont MCP joignable et relu, mémoire sous le seuil, niveau
confirmé, dossiers écréables, pagination à 200 — et livrer `preflight_ok.json` (`READY` ou `ERROR`).

## Ordre de chargement

1. `persona.md` — qui je suis, mes contraintes dures, mes interdictions. **Instruction système.**
2. `SKILL.md` (ce fichier) — mission et contrat de rendu.
3. `skill/schema-de-sortie.json` — **le contrat** : la forme exacte de `preflight_ok.json`,
   validable par code.
4. `skill/regles-engagement.md` — comment je travaille, quand je m'arrête, ce que je remonte.
5. `skill/long-term-memory.json` — ports, CVar, seuils, pièges d'éditeur, contrats CLI (injecté).
6. `skill/exemples/preflight-pret-sur-8001.json` — **few-shot** : un préflight `READY` sur valeurs
   réellement relues. `skill/exemples/REJET-pret-annonce-sans-relecture.json` — le même livrable
   quand il est rejeté.
   *(1 à 3 exemples maximum injectés, jamais les deux en même temps si le budget est serré.)*
7. `skill/outils.md` — **allowlist** : le strict minimum lecture/état, et ce qui est interdit.
8. `skill/tool-output/` — la forme réelle des retours que je dois savoir lire
   (`ping-et-decouverte-du-pont.md`, `etat-editeur-et-cvar.md`).

## Chaîne de préflight (une seule mission à la fois)

```
python script/tests/verify.py            # harnais hors editeur, 122/122 attendu
  -> ping 8000 puis 8001 (UEFN_MCP_URL)  # le pont qui REPOND, pas le port documentaire
  -> processus UnrealEditorFortnite + RAM systeme
  -> Scene.get_current_level             # le VRAI nom du niveau, pas celui affiche
  -> GetSessionStatus                    # Disconnected / Connected
  -> GetCVarValue -> SetCVarValue(200) -> GetCVarValue   # relecture obligatoire
  -> arborescence : Content/, verse/, sortie JSON + captures, acces en ecriture
  -> [cleanup UNIQUEMENT sur demande explicite du Producer]
```

## Livrables

| Artefact | Contenu | Consommé par |
|---|---|---|
| `preflight_ok.json` | `status` READY/ERROR, `mcp_port_active`, `ram_usage_mb`, `active_level_name`, `verse_path_valid`, `error_log`, et `checks[]` avec la preuve relue de chaque case | Tous les agents techniques + `Producer_Orchestrator` |
| `mcp-inventory.json` *(outillage d'état, si mission d'inventaire confiée)* | toolsets et outils listés avec statut `VERIFIE` / `DANGEREUX_UNTESTE` / `INCONNU`, `known_limitations` non vide | Producer, `Lead_Programmer` avant toute promesse |
| `tech/env-status.md` *(idem, sur demande)* | ce qui marche, ce qui est limité, ce qui ne marche pas | `Producer_Orchestrator` |

## Ce qui est **hors de ce paquet**

L'état de projet (`project-state.json`, les `handoff/*.json`, les `preflight_ok.json` datés, les
logs éditeur, `_mcp_calls.jsonl`) ne s'écrit **jamais** ici. Ni le layout (`Level_Designer`), ni la
palette mesurée (`Lead_Programmer`), ni la moindre géométrie posée (`Physics_Programmer`), ni la
moindre ligne de Verse (12 / 13 / 14) : ce dossier ne contient que du stable.
