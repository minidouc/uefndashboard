---
name: physics-programmer
description: Pose la géométrie d'une carte UEFN (sols, murs, props, devices) depuis 03_grid.json et 02_palette.json par batchs déterministes, puis la prouve par audits live (0 overlap, 0 flottant, navigation, symétrie, légalité). À utiliser quand il faut réellement construire le niveau et livrer 04_devices.json avec les refPath pour le câblage Verse.
---

# Physics_Programmer — point d'entrée

**Paquet autonome** : ce fichier dit dans quel ordre charger le savoir-faire. Le contenu de
référence (structure du dossier) est `util/multi_agent/06-structure-dossier-agent.md`.

## Mission en une ligne

Transformer les specs (`02_palette.json`, `03_grid.json`, `05_props.json`) en **niveau posé et
audité**, et livrer `04_devices.json` + les rapports d'audit **PASSED source `live`**.

## Ordre de chargement

1. `persona.md` — qui je suis, mes contraintes dures, mes interdictions. **Instruction système.**
2. `SKILL.md` (ce fichier) — mission et contrat de rendu.
3. `skill/schema-de-sortie.json` — **le contrat** : la forme exacte du livrable, validable par code.
4. `skill/regles-engagement.md` — comment je travaille, quand je m'arrête, ce que je remonte.
5. `skill/long-term-memory.json` — constantes de grille, pièges d'éditeur, contrats CLI (injecté).
6. `skill/exemples/geometrie-21x21-auditee.json` — **few-shot** : à quoi ressemble un bon livrable.
   `skill/exemples/REJET-succes-annonce-sans-live.json` — le même livrable quand il est rejeté.
   *(1 à 3 exemples maximum injectés, jamais les deux en même temps si le budget est serré.)*
7. `skill/outils.md` — **allowlist** MCP/CLI : ce que j'ai le droit d'appeler, et quand.
8. `skill/tool-output/` — la forme réelle des retours que je dois savoir lire
   (`place-scene.md`, `audit-scene-live.md`).

## Chaîne de production (une seule mission à la fois)

```
validate-grid → validate-scene → compile-transforms
      → build-structure (sols + périmètre, lots de 10)
      → place-scene (props + devices, refPath persistés dans _placed.json)
      → audit-scene --live → check-navigation → check-symmetry --live → audit-legality
      → [échec ? corriger la SPEC, relire, recompiler, reposer — jamais un drag & drop éditeur]
```

## Livrables

| Artefact | Contenu | Consommé par |
|---|---|---|
| `04_devices.json` | labels exacts + `ref_path` (`savedActor`) + `xform` relus de chaque device | 12 / 13 / 14 (câblage) |
| `06_audit_report.json` | `source: "live"`, 0 `overlap_errors`, 0 `gravity_errors`, 0 `scene_errors` | Producer, `Graphics_Programmer`, QA |
| `06_navigation_report.json` | couloirs < 100 cm | Producer, `Level_Designer` |
| `11_symmetry_report.json` | paires contrôlées, `TRANSFORM_DRIFT`, ou `axis: null` assumé | Producer, QA |
| `06_legality_report.json` | `valid_actors`, `illegal_count: 0` | Producer, gate HITL session |

## Ce qui est **hors de ce paquet**

L'état de projet (`project-state.json`, `handoff/*.json`, les livrables datés, les logs de
trajectoire) ne s'écrit **jamais** ici. Ce dossier ne contient que du stable : sinon l'agent
devient non réutilisable d'un projet à l'autre.
