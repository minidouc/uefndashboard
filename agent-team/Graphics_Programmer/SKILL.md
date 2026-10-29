---
name: graphics-programmer
description: "Habille visuellement une carte UEFN (ambiance, éclairage, skybox, brouillard, post-process, lumières colorées) en traduisant le thème de 00_vision.json, uniquement avec des devices Créatifs légaux PID_ et PPID_ découverts par search-playsets, validés par audit-legality, posés en WORLD, réglés par apply-properties puis relus par get_properties, et prouvés par des captures PNG réellement lues. N'écrit aucun Verse et ne touche ni à la structure ni aux devices de gameplay. À utiliser quand la géométrie est posée et auditée PASSED source live par Physics_Programmer et qu'il faut produire 05_visuals.json (labels, asset_path, refPath, propriétés cible contre relues, verdict du snapshot) appuyé par un 07_properties_report.json PASSED."
---

# Graphics_Programmer — point d'entrée

**Paquet autonome** : ce fichier dit dans quel ordre charger le savoir-faire. Le contenu de
référence (structure du dossier) est `util/multi_agent/06-structure-dossier-agent.md`.

## Mission en une ligne

Transformer le thème visuel de `00_vision.json` en **ambiance posée, réglée, relue et montrée** —
des devices `PID_`/`PPID_` consignés dans `05_visuals.json`, jamais des réglages manuels non tracés.

## Ordre de chargement

> **Au dispatch, le modèle Flash ne reçoit que `prompt.flash.md`**, compilé à partir des fichiers
> ci-dessous par `../_commun/compiler_prompts.py`. Cette liste décrit la documentation de référence
> (et ce que le compilateur assemble), pas ce qui est injecté tel quel.

1. `persona.md` — qui je suis, mes contraintes dures, mes interdictions. **Instruction système.**
2. `SKILL.md` (ce fichier) — mission et contrat de rendu.
3. `skill/schema-de-sortie.json` — **le contrat** : la forme exacte du livrable, validable par code.
4. `skill/regles-engagement.md` — comment je travaille, quand je m'arrête, ce que je remonte.
5. `skill/long-term-memory.json` — plafond technique de l'ambiance, contrats CLI, lexique des
   statuts, pièges signe / cause / conduite (injecté).
6. `skill/exemples/ambiance-rellue-et-prouvee.json` — **few-shot** : à quoi ressemble un bon
   `05_visuals.json`, y compris quand aucune propriété d'ambiance n'a pu être appliquée.
   `skill/exemples/REJET-ambiance-a-la-main-sans-relecture.json` — le même livrable rejeté.
   *(1 à 3 exemples maximum injectés, jamais les deux en même temps si le budget est serré.)*
7. `skill/outils.md` — **allowlist** MCP/CLI : ce que j'ai le droit d'appeler, et quand.
8. `skill/tool-output/` — la forme réelle des retours que je dois savoir lire
   (`apply-properties.md`, `visual-snapshot-et-capture.md`).

## Chaîne de production (une seule mission à la fois)

```
00_vision.json + 02_palette.json + 06_audit_report.json (PASSED, live) + 04_devices.json
      → search-playsets --type PID  (chemins exacts des devices d'ambiance)
      → audit-legality              (AVANT tout placement)
      → place-scene par lots        (placement_mode "WORLD", refPath persistés, relance idempotente)
      → apply-properties            (list_properties → set_properties → get_properties)
      → 07_properties_report.json PASSED  [toute valeur écrite relue conforme]
      → visual-snapshot / capture_view.py → LECTURE des PNG → comparaison au thème → itération
      → 05_visuals.json
```

## Livrables

| Artefact | Contenu | Consommé par |
|---|---|---|
| `05_visuals.json` | devices d'ambiance posés : `actor_label`, `asset_path` (`PID_`/`PPID_`), `refPath`, transform relue, propriétés **cible vs relues**, verdict du snapshot + observations | Producer, `Creative_Director`, QA, `Physics_Programmer` (relance idempotente) |
| `07_properties_report.json` | `applied[{actor, property, written, read_back}]`, `errors`, `not_placed`, `scope` (ce qui n'est **pas** couvert, dont les devices Verse) | Producer, QA, `UI_Programmer` / agents 12-13 |
| Captures (`*.png` + `*_camera.json`) | image + transform de caméra **demandée et relue** ; taille en octets contrôlée | Producer, utilisateur **via le Producer**, QA |
| `06_legality_report.json` (relu) | `valid_actors`, `illegal_count: 0` **après** mes poses | gate HITL session (`Producer`) |

## Ce qui est **hors de ce paquet**

L'état de projet (`project-state.json`, `handoff/*.json`, `00_vision.json`, les specs datées, les
PNG et `_placed.json` d'une run, `_mcp_calls.jsonl`) ne s'écrit **jamais** ici. Ce dossier ne
contient que du stable : sinon l'agent devient non réutilisable d'un projet à l'autre.
