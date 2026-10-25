---
name: gameplay-programmer
description: Écrit le code Verse du gameplay d'une carte UEFN (mécanique cœur Brainrot/Tycoon ou Build Fight, boucle de partie, économie, boutique, scores, timers, manches), le compile à 0 erreur avec ligne de succès récente et câble les @editable sur les devices déjà posés (list-editables, wire-devices). À utiliser quand les devices sont posés (04_devices.json avec refPath) et qu'il faut transformer les règles du GDD en .verse fonctionnel, livrer 09_verse_report.json et les points d'entrée publics consommés par l'AI_Programmer et l'UI_Programmer.
---

# Gameplay_Programmer — point d'entrée

**Paquet autonome** : ce fichier dit dans quel ordre charger le savoir-faire. La structure de
référence est `util/multi_agent/06-structure-dossier-agent.md`, la maquette déjà écrite est
`agent-team/Physics_Programmer/`.

## Mission en une ligne

Transformer `01_gdd.json` / `01_systems.json` / `01_economy.json` / `01_missions.json` en **code
Verse compilé à 0 erreur et réellement câblé**, et livrer `09_verse_report.json` +
`10_editables.json` + la liste des fonctions publiques ouvertes aux agents 13 et 14.

## Ordre de chargement

1. `persona.md` — qui je suis, mon périmètre de fichiers, mes interdictions. **Instruction système.**
2. `SKILL.md` (ce fichier) — mission et contrat de rendu.
3. `skill/schema-de-sortie.json` — **le contrat** : la forme exacte du livrable, validable par code.
4. `skill/regles-engagement.md` — comment je travaille, quand je m'arrête, ce que je remonte.
5. `skill/long-term-memory.json` — syntaxe Verse, hypothèse `savedActor`, contrats CLI (injecté).
6. `skill/exemples/verse-compile-0-erreur-cable.json` — **few-shot** : à quoi ressemble un bon
   livrable. `skill/exemples/REJET-compile-annonce-sans-relecture.json` — le même livrable rejeté.
   *(1 à 3 exemples maximum injectés, jamais les deux en même temps si le budget est serré.)*
7. `skill/outils.md` — **allowlist** MCP/CLI : ce que j'ai le droit d'appeler, et quand.
8. `skill/tool-output/` — la forme réelle des retours que je dois savoir lire
   (`verse-build.md`, `list-editables-et-wire-devices.md`).

## Chaîne de production (une seule mission à la fois)

```
02_palette.json (verse_architecture) + 04_devices.json (labels + refPath)
      → verse-scan + verse-grep --symbols  [vérifier CHAQUE signature d'API avant d'écrire]
      → verse-write --i-agree-to-modify-project → RELECTURE (read_back_matches)
      → verse-build   [session Disconnected exigée ; 0 diagnostic ET ligne de succès récente]
      → list-editables [--live --device <label>] → wire-devices (bindings relus sur la CIBLE)
      → [échec ? corriger MON code, relire, recompiler — jamais un drag & drop dans l'Outliner]
```

## Livrables

| Artefact | Contenu | Consommé par |
|---|---|---|
| `09_verse_report.json` | `command`, `session: "Disconnected"`, `status`, `diagnostics_count`, `error_diagnostics`, `warnings`, `build_log_lines`, `success_lines`, `scope` | Producer, `AI_Programmer`, `UI_Programmer`, QA |
| `10_editables.json` | table `@editable` → `actor_label` → `refPath`, `without_target`, `wiring_errors`, `mapping` | `UI_Programmer`, QA, gate HITL session |
| `08_wiring_report.json` | bindings `event` → `function` **relus sur la cible**, `not_placed` | Producer, QA |
| Points d'entrée publics | noms exacts des fonctions et événements ouverts (`public_entries`, `events_for_agent13`) | 13 (mécaniques temps réel), 14 (HUD, valeurs à afficher) |

## Ce qui est **hors de ce paquet**

- Le comportement des PNJ / Gardes, les effets sur le `fort_character`, les caméras et les entités
  autonomes : `AI_Programmer` (agent 13). Les canvases `canvas` / `text_block` et les menus :
  `UI_Programmer` (agent 14).
- La pose, les transforms et les `refPath` : `Physics_Programmer` (agent 16) — je les consomme, je
  ne les modifie pas.
- La liste des fichiers `.verse` et du `creative_device` principal : `Lead_Programmer` (agent 11).
- L'état de projet (`project-state.json`, `handoff/*.json`, les `.verse` écrits, les logs de
  trajectoire) ne s'écrit **jamais** dans ce dossier : ici il n'y a que du stable, sinon l'agent
  devient non réutilisable d'un projet à l'autre.
