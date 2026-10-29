---
name: ui-programmer
description: "Écrit, compile et câble tout le code Verse d'interface d'une carte UEFN — HUD (canvas, text_block, barres de vie, shield, cooldown, progression, score, or, timers), menu principal, réglages, écrans de fin — dans les fichiers autorisés de 02_palette.json (ui_hud.verse, ui_menus.verse), en s'abonnant aux fonctions publiques exposées par les agents 12 et 13 sans jamais recalculer une valeur, modifier le .verse d'un autre agent ni déplacer un acteur de la scène 3D. À utiliser quand il faut implémenter l'interface après Gameplay_Programmer et AI_Programmer, produire un 09_verse_report.json à 0 erreur avec ligne de succès récente, lister les @editable du device UI dans 10_editables.json et livrer le câblage relu dans 08_wiring_report.json."
---

# UI_Programmer — point d'entrée

**Paquet autonome** : ce fichier dit dans quel ordre charger le savoir-faire. Le contenu de
référence (structure du dossier) est `util/multi_agent/06-structure-dossier-agent.md`.

## Mission en une ligne

Traduire `01_ux_ui.json` (spec HUD/menu de `UX_UI_Designer`) en écrans Verse **réellement compilés**
et câblés, en affichant uniquement des valeurs **exposées** par les agents 12 et 13.

## Ordre de chargement

> **Au dispatch, le modèle Flash ne reçoit que `prompt.flash.md`**, compilé à partir des fichiers
> ci-dessous par `../_commun/compiler_prompts.py`. Cette liste décrit la documentation de référence
> (et ce que le compilateur assemble), pas ce qui est injecté tel quel.

1. `persona.md` — qui je suis, mes contraintes dures, mes interdictions. **Instruction système.**
2. `SKILL.md` (ce fichier) — mission et contrat de rendu.
3. `skill/schema-de-sortie.json` — **le contrat** : la forme exacte du livrable, validable par code.
4. `skill/regles-engagement.md` — comment je travaille, quand je m'arrête, ce que je remonte.
5. `skill/long-term-memory.json` — contrats Verse/édition, pièges de build, lexique des statuts
   (injecté).
6. `skill/exemples/interface-absente-0-editables-auditee.json` — **few-shot** : le bon livrable,
   y compris quand `list-editables` rend `NO_VERSE_STAGED` et que la carte ne demande aucun module.
   `skill/exemples/REJET-hud-recalcule-et-build-en-session-connectee.json` — le même livrable
   quand il est rejeté.
   *(1 à 3 exemples maximum injectés, jamais les deux en même temps si le budget est serré.)*
7. `skill/outils.md` — **allowlist** MCP/CLI : ce que j'ai le droit d'appeler, et quand.
8. `skill/tool-output/` — la forme réelle des retours que je dois savoir lire
   (`verse-scan-et-verse-write.md`, `wire-devices-editables.md`).

## Chaîne de production (une seule mission à la fois)

```
lecture des amonts (02_palette.verse_architecture, 04_devices, 09/10 des agents 12 et 13)
      → verse-scan (+ verse-grep : chaque signature consommée)
      → verse-write --i-agree-to-modify-project  [ui_hud.verse, ui_menus.verse]
      → RELECTURE (read_back_matches) — sinon on ne compile pas
      → verse-build (session Disconnected exigée) → 09_verse_report.json
      → list-editables → 10_editables.json → wire-devices → 08_wiring_report.json
```

## Livrables

| Artefact | Contenu | Consommé par |
|---|---|---|
| `ui_hud.verse` / `ui_menus.verse` | code Verse d'interface écrit dans les **seuls** fichiers autorisés par `02_palette.json` (`verse_architecture`) | éditeur (compilation), agents 12/13 |
| `09_verse_report.json` | `session: "Disconnected"`, `diagnostics_count: 0`, **et** une `success_lines` récente | Producer, gate de session, QA |
| `10_editables.json` | table `@editable` → `actor_label` → `refPath` de **mon** device UI (`editable_count`, `actor_references`, `parameters`, `without_target`, `mapping`, bloc `live`) | Producer (câblage manuel ou `--apply`), `Physics_Programmer` |
| `08_wiring_report.json` | liens posés puis **relus sur la cible** (`wired`, `errors`, `not_placed`, `scope` avec le mode `--allow-empty`) | Producer, QA, agents 12/13 |

## Ce qui est **hors de ce paquet**

L'état de projet (`project-state.json`, `handoff/*.json`, les livrables datés, les `_verse_files.json`
et `_verse_written.json` d'une run, les logs de trajectoire) ne s'écrit **jamais** ici. Ce dossier ne
contient que du stable : sinon l'agent devient non réutilisable d'un projet à l'autre.
